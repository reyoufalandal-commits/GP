# Hawk-Eye React dashboard

Vite + React + TypeScript + TanStack Query + React Router.

## First-run verification (before trusting the UI)

| Step | Command / action |
|------|------------------|
| 1. Dependencies | From repo root: `pip install -e ".[dev]"`, `cd dashboard/frontend && npm install` |
| 2. API process | `./scripts/run_api_8000.sh` (sets CORS for Vite on 5173/5174 by default) |
| 3. Liveness | `curl -s http://127.0.0.1:8000/health` → JSON with `"status":"ok"` |
| 4. Scoring readiness | `curl -s http://127.0.0.1:8000/ready` → `"ready": true` when `data/db/hawk_eye.db` and artifact dirs exist (see message body for `checks`) |
| 5. DB / users | Start API once so SQLite is created; optional: `python scripts/seed_user.py ...` ([`docs/OPERATOR_GUIDE_LOCAL.md`](../../docs/OPERATOR_GUIDE_LOCAL.md)) |
| 6. Frontend | `npm run dev` → open Vite URL (default **5173**; if busy, Vite may use **5174**—CORS must include that origin on the API) |
| 7. Automated tests | Repo root: `pytest tests/ -q`; frontend: `npm run build && npm run lint` |
| 8. E2E | Repo root: `./scripts/run_e2e_dashboard.sh` (starts API + Vite via Playwright when `CI=true`; see [E2E](#e2e)) |

**Data input:** Model lab accepts pasted JSON **or** uploaded `.json` / `.jsonl` (rows in the browser). **Live stream** still needs a `conn_log_path` the **API host** can read, **or** upload a Zeek `conn.log` snippet on Model lab for a one-shot **Triage via upload** (multipart API).

## Model lab (default home)

After login, **Model lab** is the first screen: paste feature rows (matching your supervised bundle), run **Score** / **Triage**, inspect the results table, optional **Explain** (linear models) and **LLM narrative** via the API (the browser never sends `OPENAI_API_KEY`; configure the server per [`docs/llm.md`](../../docs/llm.md)).

Bookmark **`/lab`** redirects to `/` (same as Model lab).

### Sidebar layout matrix

| | **`VITE_DASHBOARD_LAYOUT=full`** (default) | **`VITE_DASHBOARD_LAYOUT=ml_focus`** |
|--|--|--|
| **Full navigation** (checkbox off, or not using simpler nav) | Model lab, Live stream, **Activity summary**, SOC tools (alerts, cases, …), Ops, settings, Session | Model lab, Live stream, Ops, settings, Session — **no** Activity summary or SOC section |
| **Lab mode (simpler sidebar)** (`VITE_STUDENT_LAYOUT=true` **or** sidebar checkbox on) | Same core links; **Activity summary** and SOC links move under **More (activity & SOC tools)** | Unchanged from `ml_focus` row (already minimal) |

- **`VITE_STUDENT_LAYOUT`**: when `true`, forces lab sidebar and hides the checkbox (instructor/deployer-controlled). The sidebar label **Lab mode (simpler sidebar)** matches the **Lab mode** tag next to the Hawk-Eye title.

## Styles

All dashboard chrome and pages use **`src/index.css`** (design tokens, sidebar, tables). There is no separate `App.css` in this tree—the Vite default was removed to avoid dead CSS.

## Develop

1. Start the FastAPI backend on **port 8000** (same as the Vite proxy; `./scripts/run_api_service.sh` defaults to **8080**):

   ```bash
   ./scripts/run_api_8000.sh
   ```

   Or see all steps: `./scripts/run_model_lab_stack.sh`

2. Start the UI (proxies `/api`, `/health`, `/ready`, `/metrics`, WebSocket under `/api`):

   ```bash
   npm install
   npm run dev
   ```

   Open http://localhost:5173 — log in as `admin` / `admin123` (first DB init) or use an API key (`X-API-Key` mode).

3. Optional CORS for a non-proxied origin:

   ```bash
   export HAWK_EYE_CORS_ORIGINS=http://localhost:5173
   ```

## Build / production

```bash
npm run build
```

Serve `dist/` via nginx/Caddy **or** set `HAWK_EYE_DASHBOARD_STATIC` to the absolute path of `dist/` and open `http://api-host:8000/app/` (see `docs/DASHBOARD_DEPLOY.md`).

## OpenAPI types

With the API running:

```bash
npm run openapi
```

## E2E

Ensure `pip install -e ".[dev]"` so the repo root has `uvicorn` and `websockets` (dev extra) for `/api/v1/ws/events`. Prefer a `.venv` at the repo root so `playwright.config.ts` picks `.venv/bin/python` automatically.

From repo root:

```bash
./scripts/run_e2e_dashboard.sh
```

The script sets **`CI=true` by default** so Playwright’s `webServer` block starts **uvicorn on :8000** and **Vite on :5173** (see [`playwright.config.ts`](playwright.config.ts)). To reuse servers you already started instead: `CI= ./scripts/run_e2e_dashboard.sh`.

First time only (or in CI): `npx playwright install chromium` (CI uses `npx playwright install --with-deps chromium`).

Set `PLAYWRIGHT_PYTHON` if `python3` is not the interpreter with Hawk-Eye installed.
