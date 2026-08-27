#!/usr/bin/env bash
# Backup SQLite DB and optional stream session outputs. Run from repo root or cron.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${1:-$ROOT/backups/hawk-eye-$STAMP.tar.gz}"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT"
tar czf "$OUT" \
  --exclude='data/db/*.sqlite-journal' \
  data/db/hawk_eye.db \
  data/stream_sessions 2>/dev/null || true
if [[ ! -f data/db/hawk_eye.db ]]; then
  echo "warning: data/db/hawk_eye.db not found; archive may be empty" >&2
fi
echo "Wrote $OUT"
echo "Restore: stop API, extract archive over repo root, fix permissions."
