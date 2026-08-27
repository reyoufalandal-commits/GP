# Operations runbook

## Model bundle resolution

Supervised scoring resolves the bundle in this order:

1. `--model-dir` (CLI)
2. `HAWK_EYE_MODEL_DIR` (environment)
3. `./artifacts/current` (symlink)

Anomaly scoring uses the same pattern with `HAWK_EYE_ANOMALY_DIR` and `./artifacts/current_anomaly`.

## Updating the active model

Training scripts symlink the newest bundle to `artifacts/current` (or `artifacts/current_anomaly`). To roll back:

```bash
ln -sfn hawk-eye-kaggle-20260324-0151 artifacts/current
```

Use the full versioned directory name under `artifacts/`.

## Secrets

Do not commit `~/.kaggle/kaggle.json` or live capture files with sensitive IPs. Use [`hawk_eye.redact`](../src/hawk_eye/redact.py) where applicable for exported explanations.

## Drift (lightweight)

For long-running deployment, periodically compare distribution of numeric features in live data vs a reference split:

```bash
python3 scripts/compare_feature_stats.py \
  --reference data/processed/train.csv \
  --sample path/to/live_flows.csv
```

Large `abs_mean_shift_ratio` on important columns suggests retraining or pipeline review — this project does not auto-retrain.

**Retrain triggers (manual):** if drift exceeds a threshold you define (e.g. mean shift > 0.3 on key bytes/s features), schedule retrain + validation; optionally document the threshold in your internal SOP.

## Validate features before scoring

```bash
python3 scripts/validate_feature_schema.py --input path/to/flows.csv --model-dir artifacts/current
```

Exit code `0` means column names and numeric dtypes match the bundle contract.

## SOC alerting (policy layer)

`hawk_eye.soc_policy` adds `soc_action` (`allow`, `alert_review`, `block_candidate`) and `soc_reason` from scored rows. It does **not** block traffic — export to your SIEM/SOAR and enforce in the firewall/WAF with separate governance.

- **Accuracy vs papers:** train with `--model-type hist_gradient_boosting` and calibrate `--block-min-proba` on a held-out split using **cost** your org accepts (FPR budget), not raw accuracy alone.
- **Production blocking:** never rely on ML scores alone; combine with rules, allowlists, rate limits, and human review for `alert_review`.

```bash
python3 -m hawk_eye.score --input data/processed/val.csv --output scored.parquet \
  --predictions --proba-max --emit-run-summary reports/run_score.json
python3 scripts/select_thresholds.py --input scored.parquet --label-col Label --benign-label BENIGN \
  --max-fpr 0.01 --out reports/thresholds.json
python3 -m hawk_eye.soc_policy --input scored.parquet --output soc_scored.parquet \
  --benign-label BENIGN --benign-label benign --thresholds-file reports/thresholds.json
```

**Roles:** name who may approve changing `block_candidate` to automated blocking in your firewall/WAF; ML output alone is insufficient without org sign-off.

**Feedback:** see [`feedback_loop.md`](feedback_loop.md). **Evasion:** [`adversarial_evasion.md`](adversarial_evasion.md). **Retention:** [`compliance_retention.md`](compliance_retention.md). **Temporal/graph scope:** [`temporal_graph_limits.md`](temporal_graph_limits.md).
