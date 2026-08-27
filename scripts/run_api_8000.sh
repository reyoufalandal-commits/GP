#!/usr/bin/env bash
# FastAPI on port 8000 with CORS for Vite (matches dashboard/frontend/vite.config.ts proxy).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Load repo .env (OPENAI_API_KEY, DEEPSEEK_API_KEY, bundle paths, etc.)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
export HAWK_EYE_CORS_ORIGINS="${HAWK_EYE_CORS_ORIGINS:-http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174}"
# Optional: default Zeek log for Live stream when UI/settings omit conn_log_path.
# Prefer live network capture (data/live/conn.log) over lab sim.
if [[ -z "${HAWK_EYE_DEFAULT_CONN_LOG:-}" ]]; then
  if [[ -f "$ROOT/data/live/conn.log" ]]; then
    export HAWK_EYE_DEFAULT_CONN_LOG="$ROOT/data/live/conn.log"
  elif [[ -f "$ROOT/data/lab/sim_conn.log" ]]; then
    export HAWK_EYE_DEFAULT_CONN_LOG="$ROOT/data/lab/sim_conn.log"
  fi
fi
exec "$PY" -m uvicorn hawk_eye.api_service:app --host 127.0.0.1 --port 8000
