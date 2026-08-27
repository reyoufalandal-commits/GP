from __future__ import annotations

import json
import time
from typing import Any

from fastapi import Depends, Header, HTTPException

from hawk_eye.backend.db import get_db
from hawk_eye.backend.passwords import api_key_hash


def _ts() -> int:
    return int(time.time())


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid authorization format")
    return parts[1].strip()


def current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    if x_api_key:
        key_hash = api_key_hash(x_api_key)
        with get_db() as db:
            row = db.execute(
                """
                SELECT u.id, u.username, u.role, u.tenant_id, k.revoked
                FROM api_keys k
                JOIN users u ON u.id = k.user_id
                WHERE k.key_hash = ?
                """,
                (key_hash,),
            ).fetchone()
        if not row or int(row["revoked"]) == 1:
            raise HTTPException(status_code=401, detail="invalid api key")
        d = dict(row)
        d.pop("revoked", None)
        d["auth"] = "api_key"
        return d

    token = _extract_bearer(authorization)
    with get_db() as db:
        row = db.execute(
            """
            SELECT u.id, u.username, u.role, u.tenant_id, t.expires_at, t.revoked
            FROM auth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token = ?
            """,
            (token,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="invalid token")
    if int(row["revoked"]) == 1 or int(row["expires_at"]) <= _ts():
        raise HTTPException(status_code=401, detail="expired/revoked token")
    d = dict(row)
    d["auth"] = "bearer"
    return d


def require_roles(*roles: str):
    allowed = set(roles)

    def _dep(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return _dep
