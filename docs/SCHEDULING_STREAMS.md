# Scheduling timed stream jobs

The dashboard starts **stream_collect** jobs via `POST /api/v1/detections/stream-session` with a bearer token or API key. There is no built-in cron inside Hawk-Eye; use the OS scheduler plus `curl`.

## Example: curl + cron (API on localhost)

1. Log in once and store a long-lived **API key** (see `SECURITY.md`) or use a script that logs in and caches the bearer (short-lived).

2. Call the same JSON the UI sends:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/detections/stream-session" \
  -H "Authorization: Bearer $HAWK_EYE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"duration":"5m","conn_log_path":"/absolute/path/to/conn.log"}'
```

3. Add to crontab (runs every day at 08:00):

```cron
0 8 * * * /path/to/repo/scripts/cron_stream_session.sh
```

Keep **`conn_log_path`** valid on the API host (Zeek or lab sim). Prefer a dedicated service user with minimal rights. Multi-tenant deployments should scope **tenant_id** and secrets carefully; global admin tokens are powerful.

## Retention

Large Parquet files accumulate under `data/stream_sessions/`. Optional cleanup:

```bash
HAWK_EYE_STREAM_SESSION_RETENTION_DAYS=14 python scripts/cleanup_stream_sessions.py
```
