from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any


def _payload_get(payload: dict[str, Any], key: str) -> Any:
    if key in payload:
        return payload[key]
    lk = key.lower().replace(" ", "_")
    for k, v in payload.items():
        if str(k).lower().replace(" ", "_") == lk:
            return v
    return None


def is_suppressed(
    conn: sqlite3.Connection,
    *,
    payload: dict[str, Any],
    tenant_id: int | None,
    now_ts: int | None = None,
) -> bool:
    now_ts = now_ts or int(time.time())
    rows = conn.execute(
        """
        SELECT id, target_type, target_value, until_ts, tenant_id
        FROM suppressions
        WHERE (until_ts IS NULL OR until_ts > ?)
        """,
        (now_ts,),
    ).fetchall()
    for r in rows:
        if r["tenant_id"] is not None and tenant_id is not None and int(r["tenant_id"]) != int(tenant_id):
            continue
        if r["tenant_id"] is not None and tenant_id is None:
            continue
        tt = str(r["target_type"]).lower()
        tv = str(r["target_value"])
        if tt == "ip":
            ip = _payload_get(payload, "ip") or _payload_get(payload, "dst_ip") or _payload_get(payload, "src_ip")
            if ip is not None and str(ip) == tv:
                return True
        elif tt == "label" or tt == "decision":
            lab = _payload_get(payload, "decision_label") or _payload_get(payload, "label")
            if lab is not None and str(lab) == tv:
                return True
        elif tt == "subnet":
            # minimal: prefix match on ip string
            ip = str(_payload_get(payload, "ip") or "")
            if ip.startswith(tv):
                return True
    return False


def _safe_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def eval_rule_expression(expr: str, row: dict[str, Any]) -> bool:
    """
    Supports:
    - JSON: {"field":"p_attack","op":">","value":0.9}
    - Simple: p_attack > 0.9  (field names: [a-z0-9_]+)
    """
    expr = expr.strip()
    if expr.startswith("{"):
        try:
            spec = json.loads(expr)
        except json.JSONDecodeError:
            return False
        field = str(spec.get("field", ""))
        op = str(spec.get("op", ""))
        val = spec.get("value")
        got = _payload_get(row, field)
        if got is None and field in row:
            got = row[field]
        gf = _safe_float(got)
        vf = _safe_float(val)
        if gf is None or vf is None:
            return False
        if op == ">":
            return gf > vf
        if op == ">=":
            return gf >= vf
        if op == "<":
            return gf < vf
        if op == "<=":
            return gf <= vf
        if op == "==":
            return gf == vf
        return False
    m = re.match(r"^\s*([a-zA-Z0-9_]+)\s*([><=!]+)\s*([0-9.eE+-]+)\s*$", expr)
    if not m:
        return False
    field, op, num = m.group(1), m.group(2), m.group(3)
    got = _safe_float(_payload_get(row, field) if _payload_get(row, field) is not None else row.get(field))
    vf = _safe_float(num)
    if got is None or vf is None:
        return False
    if op == ">":
        return got > vf
    if op == ">=":
        return got >= vf
    if op == "<":
        return got < vf
    if op == "<=":
        return got <= vf
    if op in ("==", "="):
        return abs(got - vf) < 1e-9
    return False


def apply_enabled_rules(conn: sqlite3.Connection, row: dict[str, Any], tenant_id: int | None) -> list[str]:
    """Returns list of rule names that matched."""
    q = "SELECT id, name, expression, tenant_id FROM detection_rules WHERE enabled = 1"
    rows = conn.execute(q).fetchall()
    matched: list[str] = []
    for r in rows:
        if r["tenant_id"] is not None and tenant_id is not None and int(r["tenant_id"]) != int(tenant_id):
            continue
        if r["tenant_id"] is not None and tenant_id is None:
            continue
        if eval_rule_expression(str(r["expression"]), row):
            matched.append(str(r["name"]))
    return matched
