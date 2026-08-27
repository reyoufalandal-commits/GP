# Preprocessing (contract)

This project uses a strict contract:

- Raw data stays in `data/raw/` and is never overwritten.
- Interim merges may be written to `data/interim/merged.parquet`.
- Train/val/test splits and the preprocessing manifest are written to `data/processed/`.

## Leakage rules (must follow)

- Split **before** fitting any scaler/imputer/encoder.
- The label column and ID columns are never part of `X`.
- The feature column order used for scoring is driven by `feature_columns.json` in the bundle.

## Optional derived columns (CIC)

[`hawk_eye.features_cic`](../src/hawk_eye/features_cic.py) can add `der_*` columns (e.g. `log1p` of large magnitudes). If you train with extra columns, scoring inputs must include the same engineered columns and the same bundle.
