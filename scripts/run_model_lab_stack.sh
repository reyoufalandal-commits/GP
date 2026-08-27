#!/usr/bin/env bash
# Print how to run API + React Model lab locally (two terminals).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cat <<EOF
Hawk-Eye Model lab — run these in two terminals from the repo.

Terminal 1 (API on :8000, CORS for Vite):
  cd $ROOT
  ./scripts/run_api_8000.sh

Terminal 2 (dashboard):
  cd $ROOT/dashboard/frontend
  npm run dev

Then open:  http://127.0.0.1:5173
Log in:     admin / admin123  (first DB init)

Check API:   curl -s http://127.0.0.1:8000/ready | jq .
Optional LLM: export OPENAI_API_KEY=... in terminal 1 before starting the API.
EOF
