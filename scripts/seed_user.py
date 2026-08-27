#!/usr/bin/env python3
"""Insert or update a user in hawk_eye SQLite (no HTTP sign-up in the API)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _db_path() -> Path:
    return _repo_root() / "data" / "db" / "hawk_eye.db"


def _ensure_schema() -> None:
    try:
        from hawk_eye.backend.db import init_db

        init_db()
    except ImportError:
        print("Install the package first: pip install -e .", file=sys.stderr)
        raise SystemExit(1) from None


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed or update a Hawk-Eye dashboard user.")
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--role", default="analyst", choices=("admin", "analyst", "viewer"))
    ap.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Optional tenant id (must exist in tenants table).",
    )
    args = ap.parse_args()

    _ensure_schema()
    from hawk_eye.backend.passwords import hash_password
    from hawk_eye.backend.password_policy import validate_new_password

    try:
        validate_new_password(args.password)
    except ValueError as e:
        raise SystemExit(str(e)) from e

    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    h = hash_password(args.password)
    now = int(time.time())

    with sqlite3.connect(p) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        if args.tenant_id is not None:
            row = conn.execute("SELECT id FROM tenants WHERE id = ?", (args.tenant_id,)).fetchone()
            if not row:
                raise SystemExit(f"tenant id {args.tenant_id} does not exist; create tenant first (API or SQL).")
        cur = conn.execute("SELECT id FROM users WHERE username = ?", (args.username,))
        existing = cur.fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET password_hash = ?, role = ?, tenant_id = ? WHERE username = ?",
                (h, args.role, args.tenant_id, args.username),
            )
            print(f"updated user {args.username!r} role={args.role}")
        else:
            conn.execute(
                "INSERT INTO users(username, password_hash, role, tenant_id, created_at) VALUES(?, ?, ?, ?, ?)",
                (args.username, h, args.role, args.tenant_id, now),
            )
            print(f"created user {args.username!r} role={args.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
