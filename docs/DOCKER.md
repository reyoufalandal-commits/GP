# Docker

## Build and run

From the repository root:

```bash
docker compose build
docker compose up
```

- **API + UI:** Open `http://127.0.0.1:8000/app/` (static dashboard from `HAWK_EYE_DASHBOARD_STATIC`).
- **Health:** `GET http://127.0.0.1:8000/health`
- **SQLite:** Persisted in the named volume `hawk_eye_data` (mounted at `/app/data` inside the container).
- **Bundles:** Mount host `artifacts/` read-only at `/app/artifacts` (see `docker-compose.yml`). Train bundles on the host or copy them into the mount.

## Optional lab overlay (conn.log on the host)

Zeek usually runs on the host, not inside the API container. To pass through lab or live `conn.log` paths without rebuilding the image:

```bash
docker compose -f docker-compose.yml -f docker-compose.lab.yml up
```

This bind-mounts `./data/live` and `./data/lab` next to the named volume that holds SQLite. Create those directories on the host first. See [TROUBLESHOOTING_STREAM.md](TROUBLESHOOTING_STREAM.md) if the Live stream job scores zero rows.

## Environment

See [ENVIRONMENT.md](ENVIRONMENT.md) and [SECURITY.md](SECURITY.md). For production-like deployments, set `HAWK_EYE_ENV=production` and `HAWK_EYE_INITIAL_ADMIN_PASSWORD` (or provision users with `scripts/seed_user.py`).

**Secrets on disk:** Avoid committing a production `.env` with real passwords or API keys. Prefer environment injection from your orchestrator, Docker/Kubernetes secrets, or a locked-down secrets manager; keep only non-secret defaults in tracked `.env.example`.

## API-only (no frontend rebuild)

Omit the frontend stage and run `uvicorn` from a Python image with `pip install -e .`; use a reverse proxy for TLS and optional SPA hosting.

## Production checklist

- **Secrets:** Set `HAWK_EYE_ENV=production` and a strong `HAWK_EYE_INITIAL_ADMIN_PASSWORD` (or provision users with `scripts/seed_user.py`). Use Docker secrets or your orchestrator’s secret store, not plain compose env for real deployments.
- **TLS:** Terminate HTTPS in front of the container (Caddy or nginx). Example configs: `deploy/Caddyfile.example`, `deploy/nginx.conf.example`.
- **CORS:** Set `HAWK_EYE_CORS_ORIGINS` to your real dashboard origin(s); avoid `*` in production.
- **Static UI:** Build the dashboard (`dashboard/frontend`) and set `HAWK_EYE_DASHBOARD_STATIC` to the `dist/` path, or serve the SPA from the same host as the API via the reverse proxy.
- **Data:** The named volume `hawk_eye_data` holds SQLite under `/app/data`. Plan backups (`scripts/backup_hawk_eye.sh` archives DB + `data/stream_sessions` when run from the repo/host layout).
- **Models:** Keep `artifacts/` mounted read-only with trained bundles; see `docs/VERSIONING.md` for bundle layout expectations.
- **Monitoring:** Prometheus text at `GET /metrics` (see `docs/METRICS.md`). Optionally scrape `/health` and `/ready` for synthetic checks.

See also [QUICKSTART_LAB.md](QUICKSTART_LAB.md) for a short end-to-end lab path on a developer machine.
