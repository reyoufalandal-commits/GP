#!/usr/bin/env python3
"""Delete old stream session Parquet/summary/state files under data/stream_sessions/.

Set HAWK_EYE_STREAM_SESSION_RETENTION_DAYS (default: 0 = disabled). Intended for cron.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def main() -> int:
    raw = os.environ.get("HAWK_EYE_STREAM_SESSION_RETENTION_DAYS", "0").strip()
    try:
        days = float(raw)
    except ValueError:
        print("HAWK_EYE_STREAM_SESSION_RETENTION_DAYS must be a number")
        return 1
    if days <= 0:
        print("Retention disabled (HAWK_EYE_STREAM_SESSION_RETENTION_DAYS <= 0); nothing to do.")
        return 0
    here = Path(__file__).resolve().parents[1]
    root = here / "data" / "stream_sessions"
    if not root.is_dir():
        print(f"No directory {root}")
        return 0
    cutoff = time.time() - days * 86400.0
    removed = 0
    for p in root.iterdir():
        if not p.is_file():
            continue
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            pass
    print(f"Removed {removed} file(s) older than {days} days under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
