#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_manifest(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    paths = manifest.get("paths", {})
    required_reports = manifest.get("required_reports", [])
    if not isinstance(paths, dict):
        raise ValueError("manifest.paths must be an object")
    if not isinstance(required_reports, list):
        raise ValueError("manifest.required_reports must be an array")

    checked_paths: dict[str, dict[str, Any]] = {}
    for key, rel in paths.items():
        p = (root / str(rel)).resolve()
        checked_paths[key] = {"path": str(p), "exists": p.exists()}

    checked_reports: list[dict[str, Any]] = []
    for rel in required_reports:
        p = (root / str(rel)).resolve()
        checked_reports.append({"path": str(p), "exists": p.exists()})

    all_required_exist = all(v["exists"] for v in checked_paths.values()) and all(
        x["exists"] for x in checked_reports
    )
    return {
        "manifest_version": str(manifest.get("manifest_version", "")),
        "seed": int(manifest.get("seed", 0)),
        "all_required_exist": bool(all_required_exist),
        "paths": checked_paths,
        "required_reports": checked_reports,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate canonical local run manifest and required artifacts.")
    ap.add_argument("--manifest", default="config/run_manifest.local.json")
    ap.add_argument("--out", default="reports/run_manifest_validated.json")
    ap.add_argument(
        "--root",
        default=None,
        help="Directory used to resolve relative paths in manifest.paths and required_reports "
        "(default: repository root — parent of scripts/).",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    manifest_arg = Path(args.manifest)
    if manifest_arg.is_absolute():
        manifest_path = manifest_arg.resolve()
    else:
        manifest_path = (repo_root / manifest_arg).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    resolve_root = Path(args.root).resolve() if args.root else repo_root

    manifest = _load_json(manifest_path)
    payload = validate_manifest(manifest, root=resolve_root)
    out_arg = Path(args.out)
    if out_arg.is_absolute():
        out = out_arg.resolve()
    else:
        out = (repo_root / out_arg).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_required_exist"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
