#!/usr/bin/env python3
"""Apply ``data/lab/stream_lab.generated.json`` to global ``detection_settings`` in SQLite."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hawk_eye.backend.db import get_db, init_db  # noqa: E402
from hawk_eye.backend.detection_settings_repo import upsert  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge stream_lab.generated.json into detection_settings.")
    ap.add_argument(
        "--json",
        default="data/lab/stream_lab.generated.json",
        help="Path to stream_lab.generated.json (from lab simulator).",
    )
    args = ap.parse_args()
    p = Path(args.json)
    if not p.is_file():
        print(f"Missing file: {p.resolve()}", file=sys.stderr)
        return 1
    data = json.loads(p.read_text(encoding="utf-8"))
    patch = data.get("detection_settings_patch")
    if not isinstance(patch, dict) or not patch:
        print("No detection_settings_patch in JSON.", file=sys.stderr)
        return 1
    init_db()
    with get_db() as db:
        upsert(db, tenant_id=None, patch=patch)
    print("Updated global detection_settings:", patch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
