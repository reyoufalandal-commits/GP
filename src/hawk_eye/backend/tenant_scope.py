from __future__ import annotations

from typing import Any


def is_global_admin(user: dict[str, Any]) -> bool:
    return str(user.get("role")) == "admin" and user.get("tenant_id") is None


def tenant_id_for_write(user: dict[str, Any], explicit: int | None) -> int | None:
    if explicit is not None:
        if not is_global_admin(user) and user.get("tenant_id") is not None:
            if int(explicit) != int(user["tenant_id"]):
                raise PermissionError("cannot set tenant_id outside your tenant")
        return explicit
    return user.get("tenant_id")


def sql_tenant_filter(user: dict[str, Any], table_alias: str = "") -> tuple[str, list[Any]]:
    """Returns (WHERE fragment without leading AND, params). Empty if global admin."""
    prefix = f"{table_alias}." if table_alias else ""
    if is_global_admin(user):
        return "", []
    tid = user.get("tenant_id")
    if tid is None:
        return f"({prefix}tenant_id IS NULL)", []
    return f"({prefix}tenant_id = ? OR {prefix}tenant_id IS NULL)", [int(tid)]


def sql_tenant_and(user: dict[str, Any], table_alias: str = "") -> tuple[str, list[Any]]:
    frag, params = sql_tenant_filter(user, table_alias)
    if not frag:
        return "", []
    return f" AND {frag}", params
