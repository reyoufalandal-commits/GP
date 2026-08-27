from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_zeek_conn_log(path: str | Path) -> pd.DataFrame:
    """
    Reads Zeek conn.log in TSV format (default Zeek output). This is intentionally minimal:
    it supports the common case of Zeek logs with a commented header and tab-separated fields.
    """
    p = Path(path)
    # Zeek logs often have "#fields" and "#types" header lines.
    # pandas can read with comment="#" to skip them if the file includes a header row elsewhere.
    # Many conn.log files do not have a header row; in that case users should pre-convert.
    return pd.read_csv(p, sep="\t", comment="#", engine="python")


def conn_to_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert Zeek conn records into a tiny, stable feature set.

    This is a bridge for Phase 8: it does not try to replicate CICIDS features 1:1.
    """
    out = pd.DataFrame()
    # Common conn.log columns include: ts, uid, id.orig_h, id.orig_p, id.resp_h, id.resp_p,
    # proto, service, duration, orig_bytes, resp_bytes, conn_state, orig_pkts, resp_pkts
    for col, dst in [
        ("orig_bytes", "orig_bytes"),
        ("resp_bytes", "resp_bytes"),
        ("duration", "duration"),
        ("id.resp_p", "dst_port"),
        ("id.orig_p", "src_port"),
        ("orig_pkts", "orig_pkts"),
        ("resp_pkts", "resp_pkts"),
    ]:
        if col in df.columns:
            out[dst] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    if "proto" in df.columns:
        out["proto"] = df["proto"].astype(str)
    if "service" in df.columns:
        out["service"] = df["service"].astype(str)
    if "conn_state" in df.columns:
        out["conn_state"] = df["conn_state"].astype(str)

    return out

