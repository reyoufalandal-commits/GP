from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from hawk_eye.io import read_table, write_table


@dataclass(frozen=True)
class NoveltyCalibratorBundle:
    model: Any
    feature_columns: list[str]
    threshold: float
    max_alert_rate: float
    known_labels: list[str]


def _prepare_xy(df: pd.DataFrame, *, label_col: str, known_labels: set[str], feature_columns: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    missing = [c for c in feature_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns for novelty calibrator: {missing}")
    if label_col not in df.columns:
        raise ValueError(f"Missing label column: {label_col}")
    X = df[feature_columns].copy()
    y_unknown = (~df[label_col].astype(str).isin(known_labels)).to_numpy(dtype=np.int32)
    return X, y_unknown


def _choose_threshold(y_true_unknown: np.ndarray, scores_unknown: np.ndarray, *, max_alert_rate: float) -> tuple[float, dict[str, float]]:
    best_t = 0.5
    best_rec = -1.0
    best_payload = {"alert_rate": 1.0, "unknown_recall": 0.0}
    for t in np.linspace(0.0, 1.0, 1001):
        pred = scores_unknown >= t
        alert_rate = float(pred.mean())
        if alert_rate > max_alert_rate:
            continue
        pos = y_true_unknown == 1
        rec = float((pred[pos].sum()) / max(int(pos.sum()), 1))
        if rec > best_rec:
            best_rec = rec
            best_t = float(t)
            best_payload = {"alert_rate": alert_rate, "unknown_recall": rec}
    return best_t, best_payload


def fit_calibrator(
    df: pd.DataFrame,
    *,
    label_col: str,
    known_labels: set[str],
    feature_columns: list[str],
    max_alert_rate: float,
    random_state: int = 42,
) -> tuple[NoveltyCalibratorBundle, dict[str, Any]]:
    X, y = _prepare_xy(df, label_col=label_col, known_labels=known_labels, feature_columns=feature_columns)
    X_tr, X_va, y_tr, y_va = train_test_split(
        X, y, test_size=0.3, random_state=random_state, stratify=y
    )
    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )
    pipe.fit(X_tr, y_tr)
    s_va = pipe.predict_proba(X_va)[:, 1]
    t, pick = _choose_threshold(y_va, s_va, max_alert_rate=max_alert_rate)
    pred_va = s_va >= t
    rep = classification_report(y_va, pred_va.astype(int), output_dict=True, zero_division=0)
    bundle = NoveltyCalibratorBundle(
        model=pipe,
        feature_columns=feature_columns,
        threshold=t,
        max_alert_rate=float(max_alert_rate),
        known_labels=sorted(known_labels),
    )
    summary = {
        "rows_train": int(len(X_tr)),
        "rows_val": int(len(X_va)),
        "chosen_threshold": float(t),
        "budget_max_alert_rate": float(max_alert_rate),
        "val_alert_rate": float(pick["alert_rate"]),
        "val_unknown_recall": float(pick["unknown_recall"]),
        "val_classification_report": rep,
    }
    return bundle, summary


def save_bundle(bundle: NoveltyCalibratorBundle, out_dir: str | Path) -> None:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle.model, p / "novelty_calibrator.joblib")
    (p / "novelty_calibrator_meta.json").write_text(
        json.dumps(
            {
                "feature_columns": bundle.feature_columns,
                "threshold": bundle.threshold,
                "max_alert_rate": bundle.max_alert_rate,
                "known_labels": bundle.known_labels,
            },
            indent=2,
        )
    )


def load_bundle(bundle_dir: str | Path) -> NoveltyCalibratorBundle:
    p = Path(bundle_dir)
    model = joblib.load(p / "novelty_calibrator.joblib")
    meta = json.loads((p / "novelty_calibrator_meta.json").read_text())
    return NoveltyCalibratorBundle(
        model=model,
        feature_columns=list(meta["feature_columns"]),
        threshold=float(meta["threshold"]),
        max_alert_rate=float(meta.get("max_alert_rate", 0.1)),
        known_labels=list(meta.get("known_labels", [])),
    )


def apply_calibrator(df: pd.DataFrame, bundle: NoveltyCalibratorBundle) -> pd.DataFrame:
    X = df[bundle.feature_columns].copy()
    s = bundle.model.predict_proba(X)[:, 1]
    out = df.copy()
    out["novelty_calibrated_score"] = s
    out["novelty_calibrated_flag"] = s >= float(bundle.threshold)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Train/apply UNSW-aware novelty calibrator over existing score columns.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    fit = sub.add_parser("fit")
    fit.add_argument("--input", required=True, help="Labeled scored CSV/Parquet (e.g. reports/unsw_scored_labeled.parquet).")
    fit.add_argument("--label-col", default="Label")
    fit.add_argument("--known-label", action="append", default=[], help="Known label (repeatable).")
    fit.add_argument(
        "--feature-col",
        action="append",
        default=None,
        help="Score feature column (repeatable). Default: p_attack,suspected_zero_day_pct,anomaly_score,open_set_ood_score,max_class_probability",
    )
    fit.add_argument("--max-alert-rate", type=float, default=0.10)
    fit.add_argument("--out-dir", default="artifacts/novelty_calibrator_unsw")
    fit.add_argument("--out-summary", default="reports/novelty_calibrator_unsw_fit.json")

    app = sub.add_parser("apply")
    app.add_argument("--input", required=True)
    app.add_argument("--bundle-dir", required=True)
    app.add_argument("--output", required=True)
    app.add_argument("--out-summary", default=None)

    args = ap.parse_args()
    if args.cmd == "fit":
        df = read_table(args.input)
        feature_cols = (
            args.feature_col
            if args.feature_col
            else [
                "p_attack",
                "suspected_zero_day_pct",
                "anomaly_score",
                "open_set_ood_score",
                "max_class_probability",
            ]
        )
        known = set(args.known_label)
        bundle, summary = fit_calibrator(
            df,
            label_col=args.label_col,
            known_labels=known,
            feature_columns=feature_cols,
            max_alert_rate=float(args.max_alert_rate),
        )
        save_bundle(bundle, args.out_dir)
        Path(args.out_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_summary).write_text(json.dumps(summary, indent=2))
        print(json.dumps({"bundle_dir": str(Path(args.out_dir).resolve()), **summary}, indent=2))
        return 0

    bundle = load_bundle(args.bundle_dir)
    df = read_table(args.input)
    out = apply_calibrator(df, bundle)
    write_table(out, args.output)
    summ = {
        "rows": len(out),
        "output": str(Path(args.output).resolve()),
        "threshold": float(bundle.threshold),
        "flagged": int(out["novelty_calibrated_flag"].sum()),
    }
    if args.out_summary:
        Path(args.out_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_summary).write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
