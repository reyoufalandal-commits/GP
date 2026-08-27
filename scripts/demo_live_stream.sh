#!/usr/bin/env bash
# Environment checks for live Zeek → Hawk-Eye streaming (no sudo; does not start capture).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Hawk-Eye live stream — preflight (read-only) ==="
echo "Repo: $ROOT"
echo

if command -v zeek >/dev/null 2>&1; then
  echo "[ok] zeek on PATH: $(command -v zeek)"
else
  echo "[warn] zeek not found — install Zeek for live capture (optional if using lab sim only)."
fi

for p in "$ROOT/data/live/conn.log" "$ROOT/data/lab/sim_conn.log"; do
  if [[ -f "$p" ]]; then
    echo "[ok] exists: $p"
  else
    echo "[info] missing (optional): $p"
  fi
done

if [[ -d "$ROOT/artifacts" ]] && [[ -n "$(ls -A "$ROOT/artifacts" 2>/dev/null | head -1)" ]]; then
  echo "[ok] artifacts/ has content (bundles for scoring)"
else
  echo "[warn] artifacts/ empty — run scripts/ci_build_minimal_bundles.py for smoke bundles"
fi

echo
echo "Next: start API (./scripts/run_api_8000.sh), dashboard (npm run dev in dashboard/frontend),"
echo "then follow docs/STUDENT_LAB.md — Zeek capture uses sudo only when you run zeek_network_capture.sh."
