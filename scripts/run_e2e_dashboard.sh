#!/usr/bin/env bash
# Run Playwright E2E from repo root. Default CI=true so webServer starts API + Vite
# (reuseExistingServer=false). To attach to already-running :8000 and :5173: CI= ./scripts/run_e2e_dashboard.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export CI="${CI:-true}"
cd "$REPO_ROOT/dashboard/frontend"
npm run test:e2e
