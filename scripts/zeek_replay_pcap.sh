#!/usr/bin/env bash
# Replay an offline PCAP through Zeek to produce conn.log (lab / forensics workflows).
# Requires: zeek on PATH; read-only on the PCAP file.
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <capture.pcap> [output_dir]"
  echo "Writes conn.log (and other Zeek logs) under output_dir (default: ./zeek_replay_out)."
  exit 1
fi
PCAP="$(realpath "$1")"
OUT="${2:-./zeek_replay_out}"
mkdir -p "$OUT"
cd "$OUT"
zeek -r "$PCAP"
echo "Done. See $OUT/conn.log"
