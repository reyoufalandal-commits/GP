# Evaluation discipline

## Fair comparison (sklearn vs PyTorch)

Both [`scripts/pipeline_kaggle_data.sh`](../scripts/pipeline_kaggle_data.sh) and [`scripts/pipeline_kaggle_torch.sh`](../scripts/pipeline_kaggle_torch.sh) default to **`MAX_ROWS=400000`**. For a controlled comparison, use the **same** value for both runs (and the same `LABEL_COL`, `RAW_DIR`):

```bash
export MAX_ROWS=800000
./scripts/pipeline_kaggle_data.sh
# After splits exist, or re-run both from scratch:
./scripts/pipeline_kaggle_torch.sh
```

Copy [`reports/run_manifest.template.json`](../reports/run_manifest.template.json) to `reports/run_manifest.json` (or another name) and fill in bundle paths, timestamp, and optional git commit.

## Metrics to report

- **Accuracy** and **weighted F1** — headline numbers (dominated by majority classes on imbalanced IDS data).
- **Macro F1** — average across classes; more informative for imbalance.
- **Per-class** precision/recall/F1 for **rare** classes (low support) — what matters for security use cases.

Evaluation output is JSON from [`hawk_eye.evaluate`](../src/hawk_eye/evaluate.py) (`classification_report` includes `macro avg` and per-class rows).

**Extended metrics:** pass `--benign-label BENIGN` (or your benign string) to add `macro_micro` detail and `binary_benign_vs_attack` with ROC/PR AUC and approximate thresholds at target max FPR on benign.

**Latency vs accuracy:** `ensemble_voting` in [`hawk_eye.train`](../src/hawk_eye/train.py) is slower at inference than a single `hist_gradient_boosting` model.

**Time splits:** prefer [`scripts/build_splits_time.py`](../scripts/build_splits_time.py) when rows have a monotonic time column (reduces leakage vs random stratified splits).
