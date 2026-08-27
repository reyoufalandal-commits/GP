# Dashboard readiness

Hawk-Eye is designed so you can put a UI on top without changing the ML pipeline.

## Score output schema (JSON-friendly)

`score.py` produces a tabular output (CSV/Parquet). For dashboards, use `--jsonl` to also emit `results.jsonl`.

Recommended fields:

- `id`: stable identifier (optional; pass-through from input)
- `timestamp`: ISO8601 (optional)
- `score`: float anomaly/classification score
- `label`: optional thresholded label (future)
- `model_version`: bundle version string

## Local storage (optional)

Use `scripts/store_results_sqlite.py` to append scoring rows to the **`scored_events`** table in `data/db/hawk_eye.db` (same database as the FastAPI dashboard).
