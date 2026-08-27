This folder holds versioned model bundles produced by training.

Each bundle is a directory like:

  artifacts/hawk-eye-0.1.0/
    model.joblib
    preprocessor.joblib
    feature_columns.json
    config.json
    metadata.json

Scoring resolves the bundle directory in this order:

1) --model-dir
2) HAWK_EYE_MODEL_DIR
3) ./artifacts/current (optional symlink)

Bundles are not committed to git by default (they are machine-generated and can be large).

---

Anomaly bundles (benign-only training) live under e.g.:

  artifacts/hawk-eye-anomaly-<timestamp>/
    preprocessor.joblib
    feature_columns.json
    config.json   (model_type: isolation_forest | autoencoder)
    model.joblib  (Isolation Forest only)
    ae_weights.pt (autoencoder only)
    metadata.json

Resolve via --model-dir, HAWK_EYE_ANOMALY_DIR, or ./artifacts/current_anomaly
