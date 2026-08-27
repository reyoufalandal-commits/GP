from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

from hawk_eye.bundle import load as load_bundle
from hawk_eye.evaluate_extended import binary_benign_attack_metrics, multiclass_macro_micro
from hawk_eye.features import FeatureSpec, split_xy
from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV/Parquet with features + label.")
    ap.add_argument("--label-col", default="label", help="Label column name in --data.")
    ap.add_argument("--model-dir", required=True, help="Bundle directory.")
    ap.add_argument("--out-metrics", default=None, help="Optional metrics.json output path.")
    ap.add_argument(
        "--summary",
        action="store_true",
        help="Print macro F1 and lowest-F1 classes (stderr) for imbalanced metrics review.",
    )
    ap.add_argument(
        "--benign-label",
        default=None,
        help="If set with predict_proba, add binary benign-vs-attack ROC/PR and FPR thresholds.",
    )
    args = ap.parse_args()

    df = read_table(args.data)
    bundle = load_bundle(args.model_dir)

    spec = FeatureSpec(feature_columns=bundle.feature_columns, label_column=args.label_col, id_columns=[])
    X, y = split_xy(df, spec)
    X = X[bundle.feature_columns]
    Xt = bundle.preprocessor.transform(X)

    model = bundle.model
    y_pred = model.predict(Xt)

    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    cm = confusion_matrix(y, y_pred).tolist()
    payload: dict = {"classification_report": report, "confusion_matrix": cm}
    try:
        cls = getattr(model, "classes_", None)
        payload["macro_micro"] = multiclass_macro_micro(
            np.asarray(y),
            np.asarray(y_pred),
            labels=np.asarray(cls) if cls is not None else None,
        )
    except Exception:
        pass
    if args.benign_label and hasattr(model, "predict_proba"):
        proba = model.predict_proba(Xt)
        classes = np.asarray(model.classes_, dtype=object)
        bl = np.asarray(classes == args.benign_label).nonzero()[0]
        benign_idx = int(bl[0]) if len(bl) else -1
        if benign_idx >= 0:
            p_benign = proba[:, benign_idx]
            score_attack = 1.0 - p_benign
            payload["binary_benign_vs_attack"] = binary_benign_attack_metrics(
                np.asarray(y),
                score_attack,
                benign_label=args.benign_label,
            )

    print(json.dumps(payload, indent=2))
    if args.summary:
        rep = report
        macro = rep.get("macro avg", {})
        print(
            f"\n[summary] macro F1={macro.get('f1-score', 0):.4f} "
            f"macro recall={macro.get('recall', 0):.4f} accuracy={rep.get('accuracy', 0):.4f}\n",
            file=sys.stderr,
        )
        rows: list[tuple[str, float, float]] = []
        for k, v in rep.items():
            if k in ("accuracy", "macro avg", "weighted avg") or not isinstance(v, dict):
                continue
            f1 = float(v.get("f1-score", 0))
            sup = float(v.get("support", 0))
            rows.append((k, f1, sup))
        rows.sort(key=lambda x: x[1])
        print("[summary] lowest F1 classes (watch rare support):", file=sys.stderr)
        for name, f1, sup in rows[:12]:
            print(f"  {name!s}: F1={f1:.4f}  support={int(sup)}", file=sys.stderr)
        print(file=sys.stderr)
    if args.out_metrics:
        p = Path(args.out_metrics)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

