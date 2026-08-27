#!/usr/bin/env python3
from __future__ import annotations

import argparse

import pandas as pd

from hawk_eye.backend.db import db_path
from hawk_eye.dashboard.store import insert_results
from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Insert score/triage CSV or Parquet rows into hawk_eye.db (scored_events table).",
    )
    ap.add_argument("--results", required=True, help="CSV/Parquet produced by score.py")
    ap.add_argument(
        "--db",
        default=None,
        help=f"SQLite DB path (default: {db_path()})",
    )
    ap.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Optional tenant id (FK to tenants.id) for multi-tenant installs",
    )
    args = ap.parse_args()

    df = read_table(args.results)
    n = insert_results(df, database=args.db, tenant_id=args.tenant_id)
    out = db_path() if args.db is None else args.db
    print(f"Inserted {n} rows into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
