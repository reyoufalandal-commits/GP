from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.decision_fusion import KNOWN_ATTACK, fuse_decisions
from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.features import align_columns_strict
from hawk_eye.io import read_table, write_table


def known_attack_type_counts(df: pd.DataFrame) -> dict[str, int]:
    """
    For rows with ``decision_label == KnownAttack``, count supervised multiclass names.

    Uses ``supervised_prediction`` when present, else ``prediction`` (may include novel tier labels).
    """
    if df.empty or "decision_label" not in df.columns:
        return {}
    sub = df.loc[df["decision_label"].astype(str) == KNOWN_ATTACK]
    if sub.empty:
        return {}
    for col in ("supervised_prediction", "prediction"):
        if col not in sub.columns:
            continue
        raw = sub[col].astype(str).value_counts().to_dict()
        return {str(k): int(v) for k, v in raw.items()}
    return {}


def summarize_stream_risk(
    *,
    rows_scored: int,
    decision_counts: dict[str, int],
    known_attack_types: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Plain-language attack vs benign assessment for dashboards and reports.

    ``risk_level``: ``low`` (no attack-style labels), ``elevated`` (known or uncertain attack signals),
    ``unknown`` (nothing scored).
    """
    counts = decision_counts or {}
    known = int(counts.get("KnownAttack", 0) or 0)
    uncertain = int(counts.get("AttackUncertain", 0) or 0)
    if rows_scored <= 0:
        return {
            "risk_level": "unknown",
            "attack_indicators": "none",
            "risk_headline": "Still waiting on live flows to score.",
            "risk_plain_summary": (
                "Once Zeek appends conn.log lines and the path matches, Hawk-Eye will fuse binary, supervised, and "
                "anomaly signals into a verdict for each connection. Check Zeek, the interface, and conn_log_path."
            ),
        }
    if known == 0 and uncertain == 0:
        return {
            "risk_level": "low",
            "attack_indicators": "none",
            "risk_headline": "This window looks clean — no attack-style hits.",
            "risk_plain_summary": (
                f"Hawk-Eye scored {rows_scored} connection(s) end-to-end; every fused decision was BenignOrLowRisk. "
                "Nothing in this slice matched KnownAttack or AttackUncertain under your current bundles and thresholds."
            ),
        }
    parts: list[str] = []
    if known > 0:
        parts.append(
            f"{known} flow(s) matched a high-confidence attack pattern (KnownAttack) relative to your supervised bundle."
        )
    if uncertain > 0:
        parts.append(
            f"{uncertain} flow(s) are AttackUncertain (worth analyst review: novelty, open-set, or threshold mix)."
        )
    kt = known_attack_types or {}
    if known > 0 and kt:
        top = sorted(kt.items(), key=lambda x: -x[1])[:6]
        parts.append("Supervised family labels on KnownAttack rows: " + ", ".join(f"{k} ({v})" for k, v in top) + ".")
    return {
        "risk_level": "elevated",
        "attack_indicators": "present",
        "risk_headline": "Hawk-Eye surfaced traffic worth your attention.",
        "risk_plain_summary": (
            "Fusion flagged attack-like or high-uncertainty behavior in this window — that is exactly what this mode is for. "
            + " ".join(parts)
        ),
    }


def read_zeek_conn_log_with_fields(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        return pd.DataFrame()
    fields: list[str] = []
    rows: list[list[str]] = []
    for line in p.read_text(errors="ignore").splitlines():
        if not line:
            continue
        if line.startswith("#fields"):
            parts = line.split("\t")
            fields = parts[1:] if len(parts) > 1 else []
            continue
        if line.startswith("#"):
            continue
        parts = line.split("\t")
        rows.append(parts)
    if not rows:
        return pd.DataFrame(columns=fields)
    if fields and len(fields) == len(rows[0]):
        return pd.DataFrame(rows, columns=fields)
    return pd.DataFrame(rows)


def _proto_to_num(x: Any) -> float:
    v = str(x).strip().lower()
    if v == "tcp":
        return 6.0
    if v == "udp":
        return 17.0
    if v == "icmp":
        return 1.0
    return 0.0


def _num_series(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series([0.0] * len(df), index=df.index)
    return pd.to_numeric(df[name], errors="coerce").fillna(0.0)


def zeek_to_bundle_contract(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(0.0, index=df.index, columns=expected_columns)

    duration_s = _num_series(df, "duration")
    orig_bytes = _num_series(df, "orig_bytes")
    resp_bytes = _num_series(df, "resp_bytes")
    orig_pkts = _num_series(df, "orig_pkts")
    resp_pkts = _num_series(df, "resp_pkts")
    total_bytes = orig_bytes + resp_bytes
    total_pkts = orig_pkts + resp_pkts
    safe_dur = duration_s.where(duration_s > 0, 1.0)

    mapping_numeric = {
        "Protocol": df.get("proto", pd.Series([""] * len(df), index=df.index)).map(_proto_to_num),
        "Flow Duration": duration_s * 1_000_000.0,
        "Total Fwd Packets": orig_pkts,
        "Total Backward Packets": resp_pkts,
        "Fwd Packets Length Total": orig_bytes,
        "Bwd Packets Length Total": resp_bytes,
        "Flow Bytes/s": total_bytes / safe_dur,
        "Flow Packets/s": total_pkts / safe_dur,
        "Fwd Packets/s": orig_pkts / safe_dur,
        "Bwd Packets/s": resp_pkts / safe_dur,
        "Fwd Packet Length Max": orig_bytes,
        "Fwd Packet Length Min": orig_bytes.where(orig_bytes > 0, 0.0),
        "Fwd Packet Length Mean": orig_bytes.where(orig_pkts > 0, 0.0) / orig_pkts.where(orig_pkts > 0, 1.0),
        "Bwd Packet Length Max": resp_bytes,
        "Bwd Packet Length Min": resp_bytes.where(resp_bytes > 0, 0.0),
        "Bwd Packet Length Mean": resp_bytes.where(resp_pkts > 0, 0.0) / resp_pkts.where(resp_pkts > 0, 1.0),
        "Packet Length Min": total_bytes.where(total_bytes > 0, 0.0),
        "Packet Length Max": total_bytes,
        "Packet Length Mean": total_bytes.where(total_pkts > 0, 0.0) / total_pkts.where(total_pkts > 0, 1.0),
        "Avg Packet Size": total_bytes.where(total_pkts > 0, 0.0) / total_pkts.where(total_pkts > 0, 1.0),
        "Subflow Fwd Packets": orig_pkts,
        "Subflow Fwd Bytes": orig_bytes,
        "Subflow Bwd Packets": resp_pkts,
        "Subflow Bwd Bytes": resp_bytes,
        "Init Fwd Win Bytes": _num_series(df, "id.orig_p"),
        "Init Bwd Win Bytes": _num_series(df, "id.resp_p"),
    }

    for col, s in mapping_numeric.items():
        if col in out.columns:
            out[col] = pd.to_numeric(s, errors="coerce").fillna(0.0)
    return out


def prepare_input_dataframe(input_df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    if set(expected_columns).issubset(set(input_df.columns)):
        return align_columns_strict(input_df, expected_columns)
    zeek_like = {"orig_bytes", "resp_bytes", "duration", "orig_pkts", "resp_pkts"}
    if zeek_like.intersection(set(input_df.columns)):
        return zeek_to_bundle_contract(input_df, expected_columns)
    raise ValueError(
        "Input does not match model feature contract and is not recognized Zeek conn format."
    )


def score_and_fuse(
    df_input: pd.DataFrame,
    *,
    binary_dir: str | Path,
    supervised_dir: str | Path,
    anomaly_dir: str | Path,
    thresholds_file: str | Path | None = None,
) -> pd.DataFrame:
    scored = attack_uncertain_dataframe(
        df_input,
        binary_dir=binary_dir,
        supervised_dir=supervised_dir,
        anomaly_dir=anomaly_dir,
    )
    if thresholds_file and Path(thresholds_file).exists():
        t = json.loads(Path(thresholds_file).read_text())
        return fuse_decisions(
            scored,
            open_set_col="open_set_ood_score" if "open_set_ood_score" in scored.columns else None,
            min_p_attack_known=float(t.get("min_p_attack_known", 0.70)),
            min_szd_uncertain=float(t.get("min_szd_uncertain", 70.0)),
            min_open_set_uncertain=float(t.get("min_open_set_uncertain", 0.60)),
        )
    return fuse_decisions(
        scored,
        open_set_col="open_set_ood_score" if "open_set_ood_score" in scored.columns else None,
    )


def score_and_fuse_with_fusion_kwargs(
    df_input: pd.DataFrame,
    *,
    binary_dir: str | Path,
    supervised_dir: str | Path,
    anomaly_dir: str | Path,
    fusion_kwargs: dict[str, float],
) -> pd.DataFrame:
    scored = attack_uncertain_dataframe(
        df_input,
        binary_dir=binary_dir,
        supervised_dir=supervised_dir,
        anomaly_dir=anomaly_dir,
    )
    return fuse_decisions(
        scored,
        open_set_col="open_set_ood_score" if "open_set_ood_score" in scored.columns else None,
        **fusion_kwargs,
    )


def _write_stream_progress(
    progress_path: str | Path | None,
    *,
    rows_scored: int,
    conn_log_line_offset: int,
) -> None:
    """Small JSON sidecar so the dashboard can poll rows scored while Zeek appends to conn.log."""
    if not progress_path:
        return
    p = Path(progress_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {
                    "rows_scored": int(rows_scored),
                    "conn_log_line_offset": int(conn_log_line_offset),
                    "updated_at": int(time.time()),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


def run_stream_collect_duration(
    *,
    conn_log: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    binary_dir: str | Path,
    supervised_dir: str | Path,
    anomaly_dir: str | Path,
    duration_seconds: float,
    poll_seconds: float,
    fusion_kwargs: dict[str, float],
    alert_log_path: str | Path | None = None,
    webhook_url: str | None = None,
    webhook_only_known_attack: bool = False,
    progress_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    For ``duration_seconds``, repeatedly read Zeek ``conn.log`` (growing file), score new rows
    since the last offset, merge into ``output_path``, and sleep ``poll_seconds`` between polls.
    """
    bb = load_bundle(binary_dir)
    st = Path(state_path)
    offset = 0
    if st.exists():
        try:
            offset = int(json.loads(st.read_text()).get("line_offset", 0))
        except Exception:
            offset = 0

    deadline = time.monotonic() + float(duration_seconds)
    poll_seconds = max(0.5, float(poll_seconds))
    total_new = 0
    total_alerts = 0
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    _write_stream_progress(progress_path, rows_scored=0, conn_log_line_offset=int(offset))

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        df_all = read_zeek_conn_log_with_fields(conn_log)
        if offset >= len(df_all):
            time.sleep(min(poll_seconds, remaining))
            continue
        df_new = df_all.iloc[offset:].reset_index(drop=True)
        X = prepare_input_dataframe(df_new, bb.feature_columns)
        out = score_and_fuse_with_fusion_kwargs(
            X,
            binary_dir=binary_dir,
            supervised_dir=supervised_dir,
            anomaly_dir=anomaly_dir,
            fusion_kwargs=fusion_kwargs,
        )
        total_new += int(len(out))
        if out_p.exists():
            old = read_table(out_p)
            merged = pd.concat([old, out], ignore_index=True)
            write_table(merged, out_p)
        else:
            write_table(out, out_p)
        if alert_log_path:
            total_alerts += emit_alerts(
                out,
                alert_log_path=alert_log_path,
                webhook_url=webhook_url,
                print_console=False,
                webhook_only_known_attack=bool(webhook_only_known_attack),
            )
        offset = len(df_all)
        st.parent.mkdir(parents=True, exist_ok=True)
        st.write_text(json.dumps({"line_offset": int(offset), "updated_at": int(time.time())}, indent=2))
        _write_stream_progress(progress_path, rows_scored=int(total_new), conn_log_line_offset=int(offset))
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(poll_seconds, remaining))

    final_counts: dict[str, int] = {}
    ka_types: dict[str, int] = {}
    if out_p.exists():
        final = read_table(out_p)
        if "decision_label" in final.columns:
            raw = final["decision_label"].value_counts().to_dict()
            final_counts = {str(k): int(v) for k, v in raw.items()}
        ka_types = known_attack_type_counts(final)

    risk = summarize_stream_risk(
        rows_scored=int(total_new),
        decision_counts=final_counts,
        known_attack_types=ka_types,
    )
    return {
        "mode": "stream_window",
        "duration_seconds": float(duration_seconds),
        "rows_scored": int(total_new),
        "alerts_emitted": int(total_alerts),
        "output": str(out_p.resolve()),
        "state": str(Path(state_path).resolve()),
        "decision_counts": final_counts,
        "known_attack_types": ka_types,
        **risk,
    }


def _post_webhook(webhook_url: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.URLError, TimeoutError):
        return


def emit_alerts(
    df: pd.DataFrame,
    *,
    alert_log_path: str | Path,
    webhook_url: str | None,
    print_console: bool = True,
    webhook_only_known_attack: bool = False,
) -> int:
    if webhook_only_known_attack:
        alerts = df[df["decision_label"].astype(str) == KNOWN_ATTACK].copy()
    else:
        alerts = df[df["decision_label"].isin(["KnownAttack", "AttackUncertain"])].copy()
    if alerts.empty:
        return 0
    p = Path(alert_log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("a") as f:
        for row in alerts.to_dict(orient="records"):
            f.write(json.dumps(row) + "\n")
            if print_console:
                print(json.dumps({"alert": row}, ensure_ascii=False))
            if webhook_url:
                _post_webhook(webhook_url, row)
            n += 1
    return n


def run_batch_mode(
    *,
    input_path: str | Path,
    output_path: str | Path,
    binary_dir: str | Path,
    supervised_dir: str | Path,
    anomaly_dir: str | Path,
    thresholds_file: str | Path | None,
    alert_log_path: str | Path,
    webhook_url: str | None,
) -> dict[str, Any]:
    bb = load_bundle(binary_dir)
    raw = read_table(input_path)
    X = prepare_input_dataframe(raw, bb.feature_columns)
    out = score_and_fuse(
        X,
        binary_dir=binary_dir,
        supervised_dir=supervised_dir,
        anomaly_dir=anomaly_dir,
        thresholds_file=thresholds_file,
    )
    write_table(out, output_path)
    alert_count = emit_alerts(out, alert_log_path=alert_log_path, webhook_url=webhook_url, print_console=True)
    dc_raw = out["decision_label"].value_counts().to_dict()
    decision_counts = {str(k): int(v) for k, v in dc_raw.items()}
    return {
        "mode": "batch",
        "rows": int(len(out)),
        "alerts_emitted": int(alert_count),
        "output": str(Path(output_path).resolve()),
        "decision_counts": decision_counts,
        "known_attack_types": known_attack_type_counts(out),
    }


def run_stream_mode(
    *,
    conn_log: str | Path,
    state_path: str | Path,
    output_path: str | Path,
    binary_dir: str | Path,
    supervised_dir: str | Path,
    anomaly_dir: str | Path,
    thresholds_file: str | Path | None,
    alert_log_path: str | Path,
    webhook_url: str | None,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    bb = load_bundle(binary_dir)
    st = Path(state_path)
    offset = 0
    if st.exists():
        try:
            offset = int(json.loads(st.read_text()).get("line_offset", 0))
        except Exception:
            offset = 0

    df_all = read_zeek_conn_log_with_fields(conn_log)
    if offset >= len(df_all):
        return {"mode": "stream", "new_rows": 0, "alerts_emitted": 0}
    df_new = df_all.iloc[offset:].reset_index(drop=True)
    X = prepare_input_dataframe(df_new, bb.feature_columns)
    out = score_and_fuse(
        X,
        binary_dir=binary_dir,
        supervised_dir=supervised_dir,
        anomaly_dir=anomaly_dir,
        thresholds_file=thresholds_file,
    )

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    if out_p.exists():
        old = read_table(out_p)
        merged = pd.concat([old, out], ignore_index=True)
        write_table(merged, out_p)
    else:
        write_table(out, out_p)

    alerts = emit_alerts(out, alert_log_path=alert_log_path, webhook_url=webhook_url, print_console=True)
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps({"line_offset": int(len(df_all)), "updated_at": int(time.time())}, indent=2))
    dc_raw = out["decision_label"].value_counts().to_dict()
    decision_counts = {str(k): int(v) for k, v in dc_raw.items()}
    return {
        "mode": "stream",
        "new_rows": int(len(out)),
        "alerts_emitted": int(alerts),
        "decision_counts": decision_counts,
        "known_attack_types": known_attack_type_counts(out),
        "sleep_hint_seconds": poll_seconds,
    }
