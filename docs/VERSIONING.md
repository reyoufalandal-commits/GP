# Versioning and compatibility

## API server

- The HTTP API is versioned under **`/api/v1/`**. Breaking changes should bump the prefix (e.g. `/api/v2/`) and be documented in release notes.
- The Python package version is `hawk_eye.__version__` (see `pyproject.toml`) and appears in OpenAPI metadata.

## Model bundles (`artifacts/`)

Scoring expects **versioned bundle directories** with stable feature contracts:

| Role | Typical path | Loaded by |
|------|----------------|-----------|
| Binary Benign vs Attack | `artifacts/hawk-eye-binary` | Fusion / triage |
| Supervised multiclass | `artifacts/current` (or `HAWK_EYE_MODEL_DIR`) | Supervised head |
| Anomaly | `artifacts/current_anomaly` (or `HAWK_EYE_ANOMALY_DIR`) | Anomaly scores |

Detection settings (per tenant or global) may override these paths. The **`/ready`** endpoint checks that default paths exist on disk before reporting ready.

**Rule:** Train and score with bundles built from the **same feature pipeline** (`train.py` / `hawk_eye.features`). Mixing a model trained on dataset A with features from dataset B will mis-score or fail column alignment.

## Dashboard frontend

- Build the React app with `npm run build` in `dashboard/frontend/`; serve `dist/` via `HAWK_EYE_DASHBOARD_STATIC` or a reverse proxy.
- `VITE_*` variables are **build-time**; rebuild after changing them.

## Database

- SQLite schema version is tracked in `schema_meta` (`hawk_eye.backend.db.SCHEMA_VERSION`). **Back up** `data/db/hawk_eye.db` before upgrading (see [scripts/backup_hawk_eye.sh](../scripts/backup_hawk_eye.sh)).
- Recent DDL includes optional **`scored_events`** (batch scoring inserts), **`stream_job_artifact_index`** (paths for completed stream jobs), and **`detection_history`** (API score/triage runs from the dashboard); all live in the same file as the rest of the dashboard schema.

## Migrations

- There is **no Alembic** migration runner today; schema evolves via `init_db()` idempotent DDL. For upgrades: **backup first**, pull the new release, run the API once to apply DDL, and verify `/ready`.

## Restore (from backup archive)

1. **Stop** the API (and anything holding the DB open).
2. Extract the tarball from the repository root so paths align (e.g. `data/db/hawk_eye.db`, `data/stream_sessions/`).
3. Fix **file ownership** if the service runs as a non-root user in Docker.
4. Start the API and check **`GET /ready`** and a few UI flows.

The backup script [`scripts/backup_hawk_eye.sh`](../scripts/backup_hawk_eye.sh) prints a one-line restore reminder when it finishes.
