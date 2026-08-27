#!/usr/bin/env bash
# Live Zeek capture: write Zeek conn.log under data/live/ for Hawk-Eye Live stream.
# Requires Zeek on PATH (e.g. brew install zeek). Often needs root for raw sockets:
#   sudo ./scripts/zeek_network_capture.sh en0
#
# Then start the API, open Live stream, and use conn_log_path:
#   <repo>/data/live/conn.log
# (or leave the field empty if that file exists — the server auto-discovers it.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IFACE="${1:?Usage: $0 <interface>  Examples: en0 (macOS), eth0 or wlan0 (Linux)}"
OUT_DIR="$ROOT/data/live"
mkdir -p "$OUT_DIR"
if ! command -v zeek >/dev/null 2>&1; then
  echo "zeek not found in PATH. Install Zeek (e.g. brew install zeek) and retry." >&2
  exit 1
fi
echo "Zeek live capture — interface: $IFACE"
echo "Writing conn.log to: $OUT_DIR/conn.log"
echo "Stop with Ctrl+C when finished."
echo ""
cd "$OUT_DIR"
exec zeek -C -i "$IFACE"
