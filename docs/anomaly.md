# Anomaly / novelty detection (not guaranteed “zero-day”)

## When to use which model

| Goal | Use |
|------|-----|
| Classify into **known** labels (Benign, DDoS, …) | Supervised bundle (`train.py` / `train_torch.py`, `hawk_eye.score`) |
| Flag traffic **unlike** benign training (novelty / drift) | Anomaly bundle (`train_anomaly.py`, `hawk_eye.score_anomaly`) |
| Both signals on the **same rows** | Score each with the **same feature columns**, then [`scripts/fuse_scores.py`](../scripts/fuse_scores.py) (row order must match) |

Supervised and anomaly bundles are **independent**; only fuse scores when both models were trained on compatible feature spaces.

## What this is

- **Supervised** multiclass training ([`train.py`](../src/hawk_eye/train.py)) labels **known** attack classes.
- **Anomaly** training ([`train_anomaly.py`](../src/hawk_eye/train_anomaly.py)) uses **benign-only** traffic to learn “normal,” then flags flows with **high deviation** (Isolation Forest or autoencoder reconstruction error).

That is the standard ML approach to **novelty** — it does **not** prove detection of real-world zero-days.

## Workflow

1. **Export benign** rows from processed splits:

   `python -m hawk_eye.export_benign --processed-dir data/processed`

2. **Train anomaly model** (example: Isolation Forest):

   `python -m hawk_eye.train_anomaly --mode iforest --benign-train data/processed/benign_train.csv --benign-val data/processed/benign_val.csv --out artifacts/hawk-eye-anomaly-1`

3. **Evaluate** on a split that includes attacks (e.g. `val.csv`):

   `python -m hawk_eye.evaluate_anomaly --data data/processed/val.csv --model-dir artifacts/hawk-eye-anomaly-1 --out-metrics reports/metrics_anomaly_val.json`

4. **Score** new flows (features only, same columns as training):

   `python -m hawk_eye.score_anomaly --input features.csv --output anomaly_scores.csv`

## Bundle resolution

- **Anomaly bundles** are separate from supervised bundles.
- Use `--model-dir` or **`HAWK_EYE_ANOMALY_DIR`**, or symlink **`artifacts/current_anomaly`**.

## Metrics

Read **FPR** (false positives on benign) and **TPR** (attacks caught). Do not rely on accuracy alone when Benign dominates.

## Ops

- Retrain when benign behavior **drifts**; refresh **threshold** using new benign validation data.
- Version each bundle; keep `metadata.json` notes.

## Fused output (optional)

If you score the same rows with both supervised and anomaly models:

```bash
python scripts/fuse_scores.py --supervised reports/sup.csv --anomaly reports/anom.csv --out reports/fused.csv
```

## Novel / “zero-day–style” label (combined)

You cannot name a specific unknown attack family without training data. The project provides **`detect_novel`**, which assigns a **configurable label** (default `Suspected_ZeroDay` — suspicion only, not proof of a real zero-day) when:

- the **benign-trained anomaly** score is above the anomaly threshold, and  
- the **supervised** model’s max class probability is below a confidence threshold (optional; tunable).

Requires **identical `feature_columns.json`** in both the supervised and anomaly bundles (train anomaly on the same feature table as supervised).

```bash
python3 -m hawk_eye.detect_novel \
  --input data/processed/val.csv \
  --output novel_scored.parquet \
  --supervised-dir artifacts/current \
  --anomaly-dir artifacts/current_anomaly \
  --novel-label Suspected_ZeroDay \
  --confidence-threshold 0.55
```

Output includes **`suspected_zero_day_pct`** (0–100): a heuristic blend of anomaly strength and classifier uncertainty (`1 - max softmax`). It is **not** a calibrated “probability of a true zero-day”; use it to rank rows within a batch. Adjust mixing with `--risk-weight-anomaly` and `--risk-weight-uncertainty` (normalized to sum to 1). Use **`--risk-scale-ref`** (Parquet/CSV with column `anomaly_score`, e.g. benign reference batch) to stabilize scaling. **`--softmax-temperature`** rescales logits when the model exposes `decision_function`.

Use `--no-require-low-confidence` to flag on high anomaly only (more false positives). Tune thresholds on validation traffic.
