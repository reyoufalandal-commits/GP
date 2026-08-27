# Tuning novel / “zero-day–style” detection

After running [`scripts/run_novel_pipeline.sh`](../scripts/run_novel_pipeline.sh):

1. **Anomaly model (AE)** — `percentile` on benign-val scores sets the threshold (default script uses **97.5**; lower percentile = more sensitive, more benign FPR on attacks).
2. **`evaluate_anomaly`** on `val.csv` — check `true_positive_rate_attack`, `false_positive_rate_benign`, `f1_attack` in `reports/metrics_anomaly_val_ae_tuned.json`.
3. **`detect_novel`** — labels (default `Suspected_ZeroDay`; use `--novel-label` to override). Two modes:
   - **Combo (recommended to start):** high anomaly **and** `max_class_probability` &lt; `--confidence-threshold` (try **0.85–0.95**). Fewer rows, fewer random FPs from confident wrong classes.
   - **Anomaly-only:** `--no-require-low-confidence` — flags all high anomaly scores with the novel label (many rows; use for hunting, not low-FPR alerting).

Example counts on a full val split (illustrative — your numbers will vary):

| `--confidence-threshold` | Approx. suspected-zero-day rows (combo mode) |
|--------------------------|-------------------------------------------|
| 0.85 | ~53 |
| 0.90 | ~77 |
| 0.95 | ~123 |

**Tiered labels:** pass e.g. `--tier-strong-label Suspected_ZeroDay_Strong` (with default `--tier-percentile 90`) so the top ~10% of anomaly scores *among already-flagged rows* use the strong label; the rest keep `--novel-label`.

Set `NOVEL_CONFIDENCE=0.90` when calling `run_novel_pipeline.sh` to reproduce.

**Anomaly-only** (`scripts/run_novel_detect_only.sh`): thousands of flags on val — good for analyst review queues, not for silent blocking.
