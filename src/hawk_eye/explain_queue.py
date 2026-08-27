from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from hawk_eye.rag_triage import explain_dataframe


def enqueue(rows: list[dict[str, Any]], *, queue_path: str | Path) -> Path:
    p = Path(queue_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps({"rows": rows}) + "\n")
    return p


def worker_once(*, queue_path: str | Path, out_dir: str | Path, rag_index_path: str | Path) -> dict[str, Any]:
    p = Path(queue_path)
    if not p.exists():
        return {"processed_jobs": 0}
    lines = p.read_text().splitlines()
    if not lines:
        return {"processed_jobs": 0}
    first, rest = lines[0], lines[1:]
    p.write_text("\n".join(rest) + ("\n" if rest else ""))

    job = json.loads(first)
    rows = job.get("rows", [])
    df = pd.DataFrame(rows)
    out = explain_dataframe(df, index_path=rag_index_path, only_uncertain=False)
    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)
    n = len(list(outp.glob("*.json")))
    file = outp / f"job_{n:06d}.json"
    file.write_text(json.dumps({"rows": out.to_dict(orient="records")}, ensure_ascii=False))
    return {"processed_jobs": 1, "output": str(file.resolve())}


def main() -> int:
    ap = argparse.ArgumentParser(description="Simple queue for asynchronous LLM/RAG explanation jobs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    enq = sub.add_parser("enqueue")
    enq.add_argument("--input", required=True, help="CSV/Parquet with rows to explain.")
    enq.add_argument("--queue-path", default="reports/queue/explain_jobs.jsonl")

    wrk = sub.add_parser("worker-once")
    wrk.add_argument("--queue-path", default="reports/queue/explain_jobs.jsonl")
    wrk.add_argument("--out-dir", default="reports/queue/results")
    wrk.add_argument("--rag-index-path", required=True)

    args = ap.parse_args()
    if args.cmd == "enqueue":
        df = pd.read_csv(args.input) if str(args.input).endswith(".csv") else pd.read_parquet(args.input)
        out = enqueue(df.to_dict(orient="records"), queue_path=args.queue_path)
        print(json.dumps({"queue": str(out.resolve()), "rows_enqueued": len(df)}))
        return 0

    payload = worker_once(
        queue_path=args.queue_path,
        out_dir=args.out_dir,
        rag_index_path=args.rag_index_path,
    )
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
