# Hawk-Eye operational baseline and dashboard deployment

This document is the **Phase A** checklist (reproducible “project works”) plus **React SPA** deployment notes aligned with the Hawk-Eye backend.

## Phase A — Baseline verification

### A1. Install and tests

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

**Pass criteria:** all tests pass (CI uses Python **3.11** and **3.12** on Ubuntu).

### A2. Model bundles (API `/ready`)

Detection and `/ready` expect **supervised**, **binary**, and **anomaly** bundles on disk. Typical layout:

- `artifacts/current` or `HAWK_EYE_MODEL_DIR` — supervised multiclass bundle
- `artifacts/hawk-eye-binary` — binary Benign vs Attack bundle
- `artifacts/current_anomaly` or `HAWK_EYE_ANOMALY_DIR` — anomaly bundle (Isolation Forest or autoencoder)

Align paths with [`config/run_manifest.local.json`](../config/run_manifest.local.json) and resolve logic in [`src/hawk_eye/backend/detection_resolution.py`](../src/hawk_eye/backend/detection_resolution.py).

### A3. Canonical acceptance (optional, full local gate)

```bash
./scripts/run_canonical_local.sh
```

**Pass criteria:** manifest validation, triage-related steps, production readiness, quality iteration report, KPI gate per your local `reports/` and policy JSON.

### A4. API smoke

```bash
./scripts/run_api_service.sh
# or: uvicorn hawk_eye.api_service:app --host 0.0.0.0 --port 8000
```

- `GET /health` — process up  
- `GET /ready` — required bundles readable  
- `GET /openapi.json` — OpenAPI schema  

Authenticate with `POST /api/v1/auth/login` (see [`OPERATOR_GUIDE_LOCAL.md`](OPERATOR_GUIDE_LOCAL.md)). There is **no public registration**; use seeded `admin` / `admin123` on first DB init or [`scripts/seed_user.py`](../scripts/seed_user.py).

### A5. Human checklist

1. Bundles present and symlinks OK  
2. Login returns `access_token`  
3. `POST /api/v1/detections/score` with a small `rows` JSON array  
4. Optional: `POST /api/v1/detections/stream-session` with `conn_log_path` configured in settings  
5. Create alert → case → rule → suppression (viewer/analyst/admin as appropriate)

### ~5-minute verification (model path)

Use this when you only need to confirm **install + API + bundles + one score**.

1. `pip install -e ".[dev]"` and `pytest -q`  
2. Start the API (`uvicorn` or `./scripts/run_api_service.sh`; note default port **8080** in that script vs **8000** in examples)  
3. `curl -s http://127.0.0.1:8000/health` and `curl -s http://127.0.0.1:8000/ready` — `ready` should be `true` when artifact dirs exist  
4. Log in and score one row (column names must match the **supervised** bundle — same contract as [`hawk_eye.features.align_columns_strict`](../src/hawk_eye/features.py)):

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .access_token)
curl -s -X POST http://127.0.0.1:8000/api/v1/detections/score \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"rows":[{"f_bytes":1200,"f_pkts":10,"duration_ms":120,"dst_port":443}]}'
```

If your trained bundle uses different feature names, replace the object inside `rows` with columns from that bundle’s feature list (or run against [`tests/fixtures/sample_features.csv`](../tests/fixtures/sample_features.csv) column names for a quick local sanity check after training on that fixture).

**Common failures:** missing required feature columns (400 / scoring error), missing bundle directories (`GET /ready` false), stream jobs without `conn_log_path` in settings or request body.

**Explain + LLM (server-side):** after scoring, analysts can call `POST /api/v1/detections/explain` with the same feature row (linear supervised models yield `top_features`; tree/deep models may return an empty list). Optional prose: `POST /api/v1/llm/format-explanation` with `{ "explain": { ... } }` — uses `OPENAI_API_KEY` on the **server** only ([`docs/llm.md`](llm.md)).

**Timed Zeek stream:** after `POST /api/v1/detections/stream-session`, poll `GET /api/v1/jobs/{id}`; when `completed`, use `GET /api/v1/jobs/{id}/stream-summary` and `GET /api/v1/jobs/{id}/scored-preview?limit=100` for row-level JSON without opening Parquet on disk. Full checklist: [`docs/OPERATOR_GUIDE_LOCAL.md`](OPERATOR_GUIDE_LOCAL.md) §8.

---

## Phase B — Backend and CORS

Set **`HAWK_EYE_CORS_ORIGINS`** to a comma-separated list of allowed browser origins (e.g. `http://localhost:5173` for Vite). If unset, no CORS middleware is added (use a reverse proxy or Vite dev proxy).

**Optional static dashboard:** set `HAWK_EYE_DASHBOARD_STATIC` to the absolute path of the React `dist/` folder to mount the SPA at `/app` (see [`src/hawk_eye/backend/app.py`](../src/hawk_eye/backend/app.py)).

---

## React dashboard (`dashboard/frontend`)

See [`dashboard/frontend/README.md`](../dashboard/frontend/README.md) for:

- `npm install` / `npm run dev` (Vite dev server with API proxy)  
- `npm run build` for production assets  
- `npm run test:e2e` (Playwright; starts API + Vite via `playwright.config.ts` when `CI=true`, or reuses servers locally — see [`dashboard/frontend/playwright.config.ts`](../dashboard/frontend/playwright.config.ts))

From repo root:

```bash
./scripts/run_e2e_dashboard.sh
```

**Interpreter:** Playwright launches `python3 -m uvicorn` from the repo root. If the default `python3` does not have Hawk-Eye installed, create `.venv`, `pip install -e ".[dev]"`, and re-run (the config prefers `.venv/bin/python` when present). Override with `PLAYWRIGHT_PYTHON=/path/to/python`. CI sets `PLAYWRIGHT_PYTHON=python` after `actions/setup-python`.

**GitHub Actions:** the `dashboard-e2e` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs `npm ci`, `npm run build`, and the Playwright smoke against Chromium.

### Production (recommended)

Use a **reverse proxy** (nginx, Caddy, Traefik):

- Serve static files from `dashboard/frontend/dist/`  
- Proxy `/api`, `/health`, `/ready`, `/metrics`, `/docs`, `/openapi.json` to uvicorn  
- Proxy **WebSocket** `GET /api/v1/ws/events` to the same backend  

Set `HAWK_EYE_CORS_ORIGINS` only if the browser origin differs from the API (SPA on another host).

### OpenAPI → TypeScript

With the API running:

```bash
cd dashboard/frontend
npm run openapi
```

Regenerates `src/api/schema.d.ts` from `http://127.0.0.1:8000/openapi.json` (configure `OPENAPI_URL` if needed).
