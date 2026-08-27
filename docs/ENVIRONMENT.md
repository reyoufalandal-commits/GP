# Environment variables

Reference for operators and CI. Paths are relative to the repository root unless absolute.

## Backend (FastAPI)

On import, the app loads the repository **`.env`** with **`python-dotenv`** (does not override variables already set in the shell). You can still use `./scripts/run_api_8000.sh`, which also `source`s `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `HAWK_EYE_DEFAULT_CONN_LOG` | *(unset)* | Optional absolute path to Zeek `conn.log` used for **Live stream** when the request body and detection settings do not set `conn_log_path` (lab convenience). `scripts/run_api_8000.sh` sets this to `data/live/conn.log` or `data/lab/sim_conn.log` when those files exist. |
| `HAWK_EYE_LIVE_CONN_LOG` | *(unset)* | Optional override like `HAWK_EYE_DEFAULT_CONN_LOG`, checked after `HAWK_EYE_DEFAULT_CONN_LOG` when resolving `conn_log_path` for stream jobs. |
| `HAWK_EYE_ENV` | *(unset)* | Set `production` to enforce stricter bootstrap (no default `admin` password). |
| `HAWK_EYE_INITIAL_ADMIN_PASSWORD` | *(unset)* | Password for the initial `admin` user when `HAWK_EYE_ENV=production`. |
| `HAWK_EYE_API_KEY_PEPPER` | *(empty)* | Optional secret mixed into API key hashes; **re-create all API keys** after enabling. |
| `HAWK_EYE_CORS_ORIGINS` | *(unset)* | Comma-separated allowed origins (e.g. `http://localhost:5173`). If unset, no CORS middleware is registered. |
| `HAWK_EYE_DASHBOARD_STATIC` | *(unset)* | Absolute path to the built React `dist/` (served at `/app`). |
| `HAWK_EYE_PASSWORD_MIN_LENGTH` | `8` | Minimum length for new passwords (bootstrap admin, `scripts/seed_user.py`). |
| `HAWK_EYE_LOG_JSON` | *(unset)* | Set to `1`/`true`/`yes` to emit one JSON line per HTTP request on the `hawk_eye.access` logger (method, path, status, `request_id`, timing). |

## Observability

| Item | Description |
|------|-------------|
| `X-Request-ID` | Every response includes this header (reused from the inbound request when present, otherwise a UUID). Useful when correlating client errors with API logs. |
| Rate limiting | In-memory sliding window: **~120 requests per minute per client IP and path** (health, metrics, OpenAPI, and WebSocket upgrade paths are excluded). On **429**, the JSON `detail` points here for tuning. |

## ML / detection (CLI and API)

| Variable | Description |
|----------|-------------|
| `HAWK_EYE_MODEL_DIR` | Supervised multiclass bundle directory. |
| `HAWK_EYE_ANOMALY_DIR` | Anomaly bundle directory. |
| `HAWK_EYE_BINARY_DIR` | Binary Benign-vs-Attack bundle (triage / attack-uncertain). |

## Other

| Variable | Description |
|----------|-------------|
| `HAWK_EYE_AUDIT_LOG` | Default `reports/audit/events.jsonl` (`ops_guardrails`). |
| `OPENAI_API_KEY` | Optional; server-side LLM formatting (OpenAI-compatible). If set, it takes precedence over `DEEPSEEK_API_KEY`. |
| `DEEPSEEK_API_KEY` | Optional; same wire format as OpenAI; used when `OPENAI_API_KEY` is empty. Defaults base URL to `https://api.deepseek.com/v1` and model to `deepseek-chat` unless `OPENAI_BASE_URL` / `OPENAI_MODEL` are set. |
| `OPENAI_BASE_URL` | Optional; default `https://api.openai.com/v1`, or `https://api.deepseek.com/v1` when only `DEEPSEEK_API_KEY` is set. |
| `OPENAI_MODEL` | Optional; default `gpt-4o-mini`, or `deepseek-chat` when only `DEEPSEEK_API_KEY` is set. |
| `HAWK_EYE_LLM_TEMPERATURE` | Optional; default `0.15` for chat completions (`hawk_eye.llm_format`). |
| `HAWK_EYE_LLM_TEMPERATURE_INCIDENT` | Optional; default `0.42` for stream **incident reports** only (slightly more natural prose; still grounded in JSON). |
| `HAWK_EYE_LLM_MAX_TOKENS_EXPLAIN` | Optional; max completion tokens for row explanations (default 2048 if unset). |
| `HAWK_EYE_LLM_MAX_TOKENS_INCIDENT` | Optional; max completion tokens for stream incident reports (default 4096 if unset). |
| `HAWK_EYE_LLM_MAX_TOKENS` | Optional; fallback max tokens when the per-task variables above are unset. |
| `HAWK_EYE_LLM_REDACT_IPS` | Optional; default masks IPv4 in `sample_rows` sent to the LLM (`1`/`true`/`yes`). |

See also [SECURITY.md](SECURITY.md), [AUTH_TOKENS.md](AUTH_TOKENS.md), and [OPERATOR_GUIDE_LOCAL.md](OPERATOR_GUIDE_LOCAL.md).
