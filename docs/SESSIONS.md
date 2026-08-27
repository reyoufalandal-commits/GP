# Stream sessions on disk

Live **stream** jobs write artifacts under **`data/stream_sessions/`** (relative to the process working directory, usually the repo or container `/app`).

## Typical files

| Pattern | Role |
|---------|------|
| `job_<id>_progress.json` | Updated while a `stream_collect` job runs (rows scored, line offset). |
| `job_<id>_summary.json` | Written when the job completes; feeds **Stream session** report UI and exports. |
| Parquet / other outputs | Paths recorded in `background_jobs.result_path` and returned in API payloads. |

Paths are validated so they stay inside `data/stream_sessions` (or allowed subpaths) to avoid directory traversal.

## Operations

- **Backup:** `scripts/backup_hawk_eye.sh` includes the SQLite DB and `data/stream_sessions` when those paths exist.
- **Retention:** Remove old `job_*` files according to your policy after exporting anything you need; deleting DB rows alone does not remove files on disk.

See [TROUBLESHOOTING_STREAM.md](TROUBLESHOOTING_STREAM.md) for common stream issues.
