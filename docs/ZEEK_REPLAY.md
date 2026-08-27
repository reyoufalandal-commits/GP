# Offline PCAP → Zeek `conn.log`

Use this when you have a saved capture and want Hawk-Eye to score **flows** the same way as live traffic.

1. Install Zeek (`brew install zeek`, distro packages, etc.).
2. From the repo root:

```bash
chmod +x scripts/zeek_replay_pcap.sh
./scripts/zeek_replay_pcap.sh /path/to/capture.pcap ./data/replay_out
```

3. Point **Live stream** (or Detection settings) `conn_log_path` at the generated `conn.log` absolute path on the API host, or copy `conn.log` next to your lab files.

Zeek writes multiple logs; Hawk-Eye reads **`conn.log`** only. This path is **read-only** analysis — only use PCAPS you are authorized to handle.

See also [`STUDENT_LAB.md`](STUDENT_LAB.md) and [`PROJECT_CAPABILITY_REPORT.md`](PROJECT_CAPABILITY_REPORT.md).
