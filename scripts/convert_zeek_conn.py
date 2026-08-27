#!/usr/bin/env python3
from __future__ import annotations

import argparse

from hawk_eye.io import write_table
from hawk_eye.live.zeek import conn_to_basic_features, read_zeek_conn_log


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conn-log", required=True, help="Path to Zeek conn.log")
    ap.add_argument("--out", required=True, help="Output CSV/Parquet of features")
    args = ap.parse_args()

    df = read_zeek_conn_log(args.conn_log)
    feat = conn_to_basic_features(df)
    write_table(feat, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

