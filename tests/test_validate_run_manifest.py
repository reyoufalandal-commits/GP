from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

def test_validate_manifest_reports_missing(tmp_path: Path) -> None:
    root = tmp_path
    (root / "data").mkdir()
    (root / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (root / "data" / "processed" / "val.csv").write_text("a,b\n1,2\n")
    manifest = {
        "manifest_version": "1.0",
        "seed": 42,
        "paths": {"input_val": "data/processed/val.csv"},
        "required_reports": ["reports/a.json"],
    }
    mpath = root / "manifest.json"
    mpath.write_text(json.dumps(manifest))
    outp = root / "out.json"
    cmd = [
        sys.executable,
        "scripts/validate_run_manifest.py",
        "--manifest",
        str(mpath),
        "--out",
        str(outp),
        "--root",
        str(root),
    ]
    p = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert p.returncode == 2
    out = json.loads(outp.read_text())
    assert out["paths"]["input_val"]["exists"] is True
    assert out["all_required_exist"] is False

