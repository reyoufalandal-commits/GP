# Lab quickstart (~15 minutes)

Use this path the first time you run Hawk-Eye as a **student or instructor** on one machine. For deployment and operations, see [OPERATOR_GUIDE_LOCAL.md](OPERATOR_GUIDE_LOCAL.md) and [DOCKER.md](DOCKER.md).

## 1. Prerequisites

- Python 3.11+ recommended, **Node.js 18+** for the dashboard
- Repo cloned and dependencies: `pip install -e ".[dev]"` from the repo root
- Optional: Zeek for live `conn.log` (or use the lab simulator — see step 6)

## 2. Environment

```bash
cp .env.example .env
# Edit .env if you use DeepSeek/OpenAI for LLM narratives (optional)
```

## 3. API

```bash
./scripts/run_api_8000.sh
```

Verify: `curl -s http://127.0.0.1:8000/health` → `{"status":"ok",...}`

## 4. Dashboard

```bash
cd dashboard/frontend && npm install && npm run dev
```

Open **http://localhost:5173/** and sign in (default dev: `admin` / `admin123` unless `HAWK_EYE_ENV=production`).

## 5. First clicks in the UI

1. **Start here** — readiness badge and links to Ops, Model lab, Live stream  
2. **Model lab** — paste JSON rows, **Load demo row** (keys from your bundle), or **Load lab sample** (two fixed rows matching `data/lab/model_lab_sample_rows.json` / CI minimal bundles)  
3. **Ops / health** — confirm `/ready` when bundles exist under `artifacts/`  
4. **Live stream** — short window on a `conn.log` the API can read (see [TROUBLESHOOTING_STREAM.md](TROUBLESHOOTING_STREAM.md))

## 6. Bundles and CI

If `artifacts/` is empty, run:

```bash
python scripts/ci_build_minimal_bundles.py
```

## 7. Deeper docs

The main [README.md](../README.md) is the full handbook. Governance: [MODEL_GOVERNANCE.md](MODEL_GOVERNANCE.md). Zeek/lab: [STUDENT_LAB.md](STUDENT_LAB.md).
