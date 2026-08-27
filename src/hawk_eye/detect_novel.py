"""
Combine supervised multiclass predictions with benign-only anomaly scores to flag
likely novel / zero-day–style behavior and assign a dedicated label.

This does not identify real CVEs or prove an exploit is a true zero-day; it labels
flows that look *anomalous vs benign* and (optionally) *uncertain to the classifier*
with strings such as ``Suspected_ZeroDay`` (default) or tiered variants.

Each row also gets ``suspected_zero_day_pct`` (0–100): a **heuristic** “how much this
looks like an unknown / zero-day–style case” from the same signals — **not** a calibrated
probability of a real zero-day exploit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.anomaly_bundle import load_anomaly_bundle
from hawk_eye.anomaly_score import score_frame_anomaly
from hawk_eye.bundle import Bundle
from hawk_eye.bundle import load as load_bundle
from hawk_eye.features import align_columns_strict
from hawk_eye.io import read_table, write_table
from hawk_eye.labels_binary import BINARY_ATTACK
from hawk_eye.paths import resolve_anomaly_dir, resolve_model_dir


def _softmax(z: np.ndarray, axis: int = 1) -> np.ndarray:
    m = np.max(z, axis=axis, keepdims=True)
    e = np.exp(z - m)
    return e / np.sum(e, axis=axis, keepdims=True)


def _max_proba(model: Any, Xt: Any, *, temperature: float = 1.0) -> np.ndarray:
    if temperature != 1.0 and hasattr(model, "decision_function"):
        z = np.asarray(model.decision_function(Xt), dtype=np.float64)
        z = z / float(temperature)
        p = _softmax(z, axis=1)
        return np.max(p, axis=1)
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(Xt)
        return np.asarray(np.max(p, axis=1), dtype=np.float64)
    return np.ones(len(Xt), dtype=np.float64)


def _suspected_zero_day_pct(
    anom_scores: np.ndarray,
    thr: float,
    max_p: np.ndarray,
    *,
    weight_anomaly: float,
    weight_uncertainty: float,
    ref_p99: float | None = None,
    ref_hi: float | None = None,
) -> np.ndarray:
    """
    Map anomaly excess + supervised uncertainty into 0–100 for dashboards.

    - Uncertainty: ``1 - max(softmax)`` (high when the classifier is unsure).
    - Anomaly: how far above ``thr`` the score is, scaled by this batch's spread
      (99th percentile vs threshold), clipped to [0, 1].

    Comparable mainly **within one** ``detect_novel`` run (same batch).
    """
    w_sum = float(weight_anomaly) + float(weight_uncertainty)
    if w_sum <= 0:
        wa, wu = 0.5, 0.5
    else:
        wa = float(weight_anomaly) / w_sum
        wu = float(weight_uncertainty) / w_sum
    unc = 1.0 - np.clip(max_p, 0.0, 1.0)
    p99 = float(ref_p99) if ref_p99 is not None else float(np.percentile(anom_scores, 99.0))
    hi = float(ref_hi) if ref_hi is not None else float(np.max(anom_scores))
    denom = max(p99 - thr, hi - thr, 1e-9)
    excess = np.clip((anom_scores - thr) / denom, 0.0, 1.0)
    s01 = wa * excess + wu * unc
    return np.clip(100.0 * s01, 0.0, 100.0)


def detect_novel_dataframe(
    df: pd.DataFrame,
    *,
    supervised_dir: str | Path | None,
    anomaly_dir: str | Path | None,
    novel_label: str = "Suspected_ZeroDay",
    confidence_threshold: float = 0.55,
    anomaly_threshold: float | None = None,
    require_low_confidence: bool = True,
    tier_strong_label: str | None = None,
    tier_percentile: float = 90.0,
    risk_weight_anomaly: float = 0.5,
    risk_weight_uncertainty: float = 0.5,
    softmax_temperature: float = 1.0,
    risk_ref_anomaly_scores: np.ndarray | None = None,
) -> pd.DataFrame:
    """
    - Supervised model: normal multiclass prediction.
    - Anomaly model (IF or AE trained on benign only): higher score = more unusual.
    - If anomaly score > threshold AND (optionally) max(softmax) < confidence_threshold,
      assign `novel_label` instead of the supervised class.
    - If ``tier_strong_label`` is set, among rows that pass the novel heuristic, the
      top ``100 - tier_percentile`` percent by anomaly score get ``tier_strong_label``;
      the rest get ``novel_label`` (ranks "how suspicious" within the batch).
    - ``suspected_zero_day_pct`` (0–100): weighted blend of anomaly strength and
      ``1 - max_class_probability``; tune with ``risk_weight_anomaly`` /
      ``risk_weight_uncertainty`` (normalized to sum to 1).
    """
    sup_path = resolve_model_dir(model_dir=supervised_dir)
    anom_path = resolve_anomaly_dir(model_dir=anomaly_dir)
    sup = load_bundle(sup_path)
    anom = load_anomaly_bundle(anom_path)

    if sup.feature_columns != anom.feature_columns:
        raise ValueError(
            "Supervised and anomaly bundles must share the same feature_columns. "
            f"Supervised: {len(sup.feature_columns)} cols, anomaly: {len(anom.feature_columns)}."
        )

    Xs = align_columns_strict(df, sup.feature_columns)
    Xt = sup.preprocessor.transform(Xs)
    model = sup.model
    sup_pred = model.predict(Xt)
    max_p = _max_proba(model, Xt, temperature=float(softmax_temperature))

    anom_scores = score_frame_anomaly(df, anom)
    thr = float(anomaly_threshold) if anomaly_threshold is not None else float(anom.config["threshold"])

    high_anom = anom_scores > thr
    if require_low_confidence:
        novel_mask = high_anom & (max_p < float(confidence_threshold))
    else:
        novel_mask = high_anom

    if tier_strong_label is not None and novel_mask.any():
        sub = anom_scores[novel_mask]
        cut = float(np.percentile(sub, float(tier_percentile)))
        strong = novel_mask & (anom_scores >= cut)
        final = np.where(
            strong,
            tier_strong_label,
            np.where(novel_mask, novel_label, sup_pred.astype(object)),
        )
    else:
        final = np.where(novel_mask, novel_label, sup_pred.astype(object))

    ref_p99: float | None = None
    ref_hi: float | None = None
    if risk_ref_anomaly_scores is not None and len(risk_ref_anomaly_scores) > 0:
        ref_p99 = float(np.percentile(risk_ref_anomaly_scores, 99.0))
        ref_hi = float(np.max(risk_ref_anomaly_scores))

    szd_pct = _suspected_zero_day_pct(
        anom_scores,
        thr,
        max_p,
        weight_anomaly=risk_weight_anomaly,
        weight_uncertainty=risk_weight_uncertainty,
        ref_p99=ref_p99,
        ref_hi=ref_hi,
    )

    out = pd.DataFrame(
        {
            "prediction": final,
            "supervised_prediction": sup_pred,
            "max_class_probability": max_p,
            "anomaly_score": anom_scores,
            "anomaly_threshold": thr,
            "suspected_zero_day_pct": szd_pct,
            "is_novel_flagged": novel_mask,
        }
    )
    out["supervised_model_version"] = sup.config.get("bundle_version", "")
    out["anomaly_model_type"] = anom.config.get("model_type", "")
    out["anomaly_bundle_version"] = anom.config.get("bundle_version", "")
    return out


def _binary_attack_pred_proba(
    df: pd.DataFrame,
    *,
    binary_bundle_dir: str | Path,
) -> tuple[np.ndarray, np.ndarray, Bundle]:
    """Return (binary_prediction, p_attack, bundle) for a benign-vs-attack bundle."""
    bpath = resolve_model_dir(model_dir=binary_bundle_dir)
    bb = load_bundle(bpath)
    if not bb.config.get("binary_benign_vs_attack"):
        raise ValueError(
            "Binary bundle must be trained with --binary-benign-vs-attack "
            f"(config.binary_benign_vs_attack missing or false): {bpath}"
        )
    model = bb.model
    classes = getattr(model, "classes_", None)
    if classes is None:
        raise ValueError("Binary model has no classes_; cannot resolve Attack probability.")
    cl = [str(c) for c in classes]
    if BINARY_ATTACK not in cl:
        raise ValueError(
            f"Binary model classes must include '{BINARY_ATTACK}'; got {cl}"
        )
    attack_i = cl.index(BINARY_ATTACK)
    Xb = align_columns_strict(df, bb.feature_columns)
    Xt = bb.preprocessor.transform(Xb)
    pred = model.predict(Xt)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(Xt)
        p_attack = np.asarray(proba[:, attack_i], dtype=np.float64)
    else:
        p_attack = np.asarray(pred == BINARY_ATTACK, dtype=np.float64)
    return np.asarray(pred, dtype=object), p_attack, bb


def attack_uncertain_dataframe(
    df: pd.DataFrame,
    *,
    binary_dir: str | Path,
    supervised_dir: str | Path | None,
    anomaly_dir: str | Path | None,
    novel_label: str = "Suspected_ZeroDay",
    confidence_threshold: float = 0.55,
    anomaly_threshold: float | None = None,
    require_low_confidence: bool = True,
    tier_strong_label: str | None = None,
    tier_percentile: float = 90.0,
    risk_weight_anomaly: float = 0.5,
    risk_weight_uncertainty: float = 0.5,
    softmax_temperature: float = 1.0,
    risk_ref_anomaly_scores: np.ndarray | None = None,
    min_szd_pct_for_attack_uncertain: float = 70.0,
) -> pd.DataFrame:
    """
    **Attack but suspicious / not like known (operational triage):**

    Requires a **binary** bundle (Benign vs Attack) plus the same supervised (multiclass)
    and anomaly bundles as :func:`detect_novel_dataframe`.

    Rows are flagged ``is_attack_uncertain`` when the binary model says **Attack** and either
    the novelty heuristic fires (``is_novel_flagged``) **or** ``suspected_zero_day_pct`` is
    at least ``min_szd_pct_for_attack_uncertain``. This focuses analyst attention on
    attack-like traffic that also looks unusual vs benign and/or uncertain to the multiclass
    head — **not** proof of a new family or zero-day.
    """
    bin_pred, p_attack, bb = _binary_attack_pred_proba(df, binary_bundle_dir=binary_dir)
    sup_path = resolve_model_dir(model_dir=supervised_dir)
    sup = load_bundle(sup_path)
    if bb.feature_columns != sup.feature_columns:
        raise ValueError(
            "Binary and supervised bundles must share the same feature_columns "
            f"(binary {len(bb.feature_columns)} vs supervised {len(sup.feature_columns)})."
        )

    novel = detect_novel_dataframe(
        df,
        supervised_dir=supervised_dir,
        anomaly_dir=anomaly_dir,
        novel_label=novel_label,
        confidence_threshold=confidence_threshold,
        anomaly_threshold=anomaly_threshold,
        require_low_confidence=require_low_confidence,
        tier_strong_label=tier_strong_label,
        tier_percentile=tier_percentile,
        risk_weight_anomaly=risk_weight_anomaly,
        risk_weight_uncertainty=risk_weight_uncertainty,
        softmax_temperature=softmax_temperature,
        risk_ref_anomaly_scores=risk_ref_anomaly_scores,
    )

    is_bin_attack = bin_pred == BINARY_ATTACK
    high_szd = novel["suspected_zero_day_pct"] >= float(min_szd_pct_for_attack_uncertain)
    uncertain = novel["is_novel_flagged"].to_numpy() | high_szd.to_numpy()
    is_attack_uncertain = is_bin_attack & uncertain

    out = novel.copy()
    out.insert(0, "binary_prediction", bin_pred)
    out.insert(1, "p_attack", p_attack)
    out["binary_bundle_version"] = bb.config.get("bundle_version", "")
    out["is_attack_uncertain"] = is_attack_uncertain
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Flag likely novel attacks: high benign-anomaly score + low supervised confidence."
    )
    ap.add_argument("--input", required=True, help="CSV/Parquet with same features as both bundles.")
    ap.add_argument("--output", required=True, help="Output CSV/Parquet with prediction + diagnostics.")
    ap.add_argument("--supervised-dir", default=None, help="Supervised bundle (default HAWK_EYE_MODEL_DIR / current).")
    ap.add_argument("--anomaly-dir", default=None, help="Anomaly bundle (default HAWK_EYE_ANOMALY_DIR / current_anomaly).")
    ap.add_argument(
        "--novel-label",
        default="Suspected_ZeroDay",
        help="Label when the novel heuristic fires (not a verified zero-day or CVE).",
    )
    ap.add_argument(
        "--tier-strong-label",
        default=None,
        help="If set, among flagged rows the top (100 - --tier-percentile)%% by anomaly score get this label; others get --novel-label.",
    )
    ap.add_argument(
        "--tier-percentile",
        type=float,
        default=90.0,
        help="Percentile of anomaly scores within flagged rows; scores at or above it get --tier-strong-label (default 90 → top ~10%%).",
    )
    ap.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.55,
        help="Max softmax prob below this (and high anomaly) → novel label when --require-low-confidence.",
    )
    ap.add_argument(
        "--anomaly-threshold",
        type=float,
        default=None,
        help="Override anomaly bundle threshold (default: use bundle config).",
    )
    ap.add_argument(
        "--no-require-low-confidence",
        action="store_true",
        help="Flag as novel on high anomaly only (more false positives).",
    )
    ap.add_argument(
        "--risk-weight-anomaly",
        type=float,
        default=0.5,
        help="Weight for anomaly strength in suspected_zero_day_pct (0-100).",
    )
    ap.add_argument(
        "--risk-weight-uncertainty",
        type=float,
        default=0.5,
        help="Weight for (1 - max softmax) in suspected_zero_day_pct.",
    )
    ap.add_argument(
        "--softmax-temperature",
        type=float,
        default=1.0,
        help="If != 1 and model has decision_function, scale logits before softmax for max_p.",
    )
    ap.add_argument(
        "--risk-scale-ref",
        default=None,
        help="CSV/Parquet with an 'anomaly_score' column (e.g. benign reference) to stabilize risk scaling.",
    )
    ap.add_argument(
        "--emit-run-summary",
        default=None,
        help="Write JSON summary of this run (counts, percentiles) to this path.",
    )
    args = ap.parse_args()

    df = read_table(args.input)
    risk_ref: np.ndarray | None = None
    if args.risk_scale_ref:
        ref_df = read_table(args.risk_scale_ref)
        if "anomaly_score" not in ref_df.columns:
            raise ValueError("--risk-scale-ref must contain column 'anomaly_score'")
        risk_ref = ref_df["anomaly_score"].to_numpy(dtype=np.float64)

    out = detect_novel_dataframe(
        df,
        supervised_dir=args.supervised_dir,
        anomaly_dir=args.anomaly_dir,
        novel_label=args.novel_label,
        confidence_threshold=args.confidence_threshold,
        anomaly_threshold=args.anomaly_threshold,
        require_low_confidence=not args.no_require_low_confidence,
        tier_strong_label=args.tier_strong_label,
        tier_percentile=args.tier_percentile,
        risk_weight_anomaly=args.risk_weight_anomaly,
        risk_weight_uncertainty=args.risk_weight_uncertainty,
        softmax_temperature=args.softmax_temperature,
        risk_ref_anomaly_scores=risk_ref,
    )
    write_table(out, args.output)
    n_novel = int(out["is_novel_flagged"].sum())
    summary: dict[str, Any] = {
        "rows": len(out),
        "novel_flagged": n_novel,
        "novel_label": args.novel_label,
        "output": str(Path(args.output).resolve()),
    }
    if args.tier_strong_label:
        summary["tier_strong_label"] = args.tier_strong_label
        summary["tier_percentile"] = args.tier_percentile
    sp = out["suspected_zero_day_pct"] if "suspected_zero_day_pct" in out.columns else None
    summary["suspected_zero_day_pct_median"] = float(np.median(sp)) if sp is not None else None
    summary["anomaly_score_p99"] = float(np.percentile(out["anomaly_score"], 99.0))
    if args.emit_run_summary:
        Path(args.emit_run_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit_run_summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
