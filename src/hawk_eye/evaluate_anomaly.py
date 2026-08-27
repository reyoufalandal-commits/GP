from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score

from hawk_eye.anomaly_bundle import load_anomaly_bundle
from hawk_eye.anomaly_score import score_frame_anomaly
from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser(description="Binary eval: benign vs attack using anomaly scores.")
    ap.add_argument("--data", required=True, help="Val or test CSV with Label column.")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--model-dir", required=True, help="Anomaly bundle directory.")
    ap.add_argument(
        "--benign-values",
        default="BENIGN,Benign,benign",
        help="Comma-separated values treated as benign (ground truth negative).",
    )
    ap.add_argument("--out-metrics", default=None, help="Write metrics JSON here.")
    args = ap.parse_args()

    benign_set = {x.strip() for x in args.benign_values.split(",") if x.strip()}
    df = read_table(args.data)
    bundle = load_anomaly_bundle(args.model_dir)
    thr = float(bundle.config["threshold"])

    scores = score_frame_anomaly(df, bundle)
    y_true = (~df[args.label_col].astype(str).isin(benign_set)).astype(int).to_numpy()
    y_pred = (scores > thr).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    n_benign = int((y_true == 0).sum())
    n_attack = int((y_true == 1).sum())
    fpr = fp / max(n_benign, 1)
    tpr = tp / max(n_attack, 1)

    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", pos_label=1, zero_division=0
    )
    try:
        auc = float(roc_auc_score(y_true, scores))
        if math.isnan(auc):
            auc = None
    except Exception:
        auc = None

    alerts_per_10k = float(y_pred.sum() / max(len(df), 1) * 10_000)

    payload = {
        "threshold": thr,
        "n_rows": len(df),
        "n_benign_gt": n_benign,
        "n_attack_gt": n_attack,
        "false_positive_rate_benign": fpr,
        "true_positive_rate_attack": tpr,
        "precision_attack": float(prec),
        "recall_attack": float(rec),
        "f1_attack": float(f1),
        "roc_auc_score": auc,
        "alerts_per_10k_rows": alerts_per_10k,
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }
    print(json.dumps(payload, indent=2))
    if args.out_metrics:
        p = Path(args.out_metrics)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
