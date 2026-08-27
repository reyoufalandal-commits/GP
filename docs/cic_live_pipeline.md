# Live capture → CICIDS-compatible flows → Hawk-Eye

This document closes the **end-to-end gap** for running the default Kaggle/CICIDS-trained bundles on **new traffic** (PCAP or mirrored port).

## 1. Capture (authorized networks only)

- **PCAP** from a span port, tap, or `tcpdump` / Wireshark on a lab interface.
- **Do not** capture production traffic without policy and consent.

## 2. Flow features (CICFlowMeter or equivalent)

Use **CICFlowMeter** (Java) or any exporter that produces **per-flow** statistics compatible with the CICIDS2017-style column set used in training.

1. Install a CICFlowMeter build (see the project’s release page for your OS).
2. Export flows to CSV; column names should match **or** be mappable to the bundle’s `feature_columns.json`.

## 3. Normalize headers

Tools may differ casing, spacing, or underscores. From the repo root:

```bash
python3 scripts/normalize_flow_csv.py \
  --input path/from/cicflowmeter.csv \
  --output data/interim/live_normalized.csv \
  --model-dir artifacts/current \
  --label-col Label
```

If your CSV has no labels yet, omit `--label-col` (only features are written).

Optional: add mappings in `config/cic_column_aliases.json`:

```json
{
  "flow_duration": "Flow Duration"
}
```

## 4. Validate

```bash
python3 scripts/validate_feature_schema.py \
  --input data/interim/live_normalized.csv \
  --model-dir artifacts/current
```

## 5. Score

```bash
python3 -m hawk_eye.score \
  --input data/interim/live_normalized.csv \
  --output scored.parquet \
  --predictions --proba-all --proba-max
```

## 6. Optional: one-shot shell wrapper

If `CICFLOWMETER_JAR` points to your JAR and your build supports the same CLI as the script expects:

```bash
export CICFLOWMETER_JAR=/path/to/CICFlowMeter.jar
./scripts/run_live_pipeline.sh /path/to/pcaps_dir
```

Adjust `scripts/run_live_pipeline.sh` if your CICFlowMeter version uses different CLI flags (document the command in your environment).

## Drift

Compare live feature stats to training:

```bash
python3 scripts/compare_feature_stats.py \
  --reference data/processed/train.csv \
  --sample data/interim/live_normalized.csv
```

## Class imbalance (training)

Imbalance is a **data** problem; mitigation options in this repo:

- **Sklearn**: `python3 -m hawk_eye.train ... --logistic-class-weight balanced`
- **PyTorch**: `train_torch.py` already supports `--class-weight balanced` (default)
- **Metrics**: `hawk_eye.evaluate --summary` and `scripts/summarize_rare_metrics.py` highlight low-F1 / rare support classes.
