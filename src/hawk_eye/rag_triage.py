from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from hawk_eye.io import read_table, write_table
from hawk_eye.redact import redact_obj


@dataclass(frozen=True)
class RAGIndex:
    vectorizer: TfidfVectorizer
    matrix: Any
    docs: list[dict[str, Any]]


def build_rag_index(corpus_jsonl: str | Path, out_index: str | Path) -> dict[str, Any]:
    docs: list[dict[str, Any]] = []
    p = Path(corpus_jsonl)
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if "text" not in obj:
            continue
        docs.append(obj)
    if not docs:
        raise ValueError("Corpus is empty or missing `text` fields.")

    vect = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=20000)
    X = vect.fit_transform([str(d["text"]) for d in docs])
    payload = {"vectorizer": vect, "matrix": X, "docs": docs}
    out = Path(out_index)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, out)
    return {"docs": len(docs), "index": str(out.resolve())}


def load_rag_index(index_path: str | Path) -> RAGIndex:
    payload = joblib.load(Path(index_path))
    return RAGIndex(
        vectorizer=payload["vectorizer"],
        matrix=payload["matrix"],
        docs=payload["docs"],
    )


def retrieve(index: RAGIndex, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
    q = index.vectorizer.transform([query])
    sim = (index.matrix @ q.T).toarray().reshape(-1)
    if len(sim) == 0:
        return []
    idx = np.argsort(-sim)[:top_k]
    out: list[dict[str, Any]] = []
    for i in idx:
        d = dict(index.docs[int(i)])
        d["score"] = float(sim[int(i)])
        out.append(d)
    return out


def _build_query_from_row(row: pd.Series) -> str:
    cols = ["decision_label", "reason_codes", "binary_prediction", "supervised_prediction", "prediction"]
    parts: list[str] = []
    for c in cols:
        if c in row and pd.notna(row[c]):
            parts.append(f"{c}={row[c]}")
    if "suspected_zero_day_pct" in row:
        parts.append(f"suspected_zero_day_pct={float(row['suspected_zero_day_pct']):.2f}")
    if "open_set_ood_score" in row and pd.notna(row["open_set_ood_score"]):
        parts.append(f"open_set_ood_score={float(row['open_set_ood_score']):.3f}")
    return " | ".join(parts)


def explain_row(
    row: pd.Series,
    *,
    index: RAGIndex,
    top_k: int = 4,
) -> dict[str, Any]:
    query = _build_query_from_row(row)
    evidence = retrieve(index, query, top_k=top_k)
    candidates = []
    for e in evidence[:3]:
        candidates.append(
            {
                "name": e.get("family", e.get("title", "unknown")),
                "score": float(e.get("score", 0.0)),
                "source": e.get("source", ""),
            }
        )
    next_steps = [
        "Validate source/destination entities and recurrence in recent window.",
        "Compare top anomalous features against historical baseline.",
        "Map retrieved technique candidates to SOC playbook checks.",
    ]
    return {
        "likely_family_candidates": candidates,
        "confidence_band": "medium" if len(candidates) else "low",
        "why": "Generated from retrieval over curated corpus; treat as analyst aid.",
        "next_investigation_steps": next_steps,
        "citations": [
            {
                "title": e.get("title", ""),
                "source": e.get("source", ""),
                "score": float(e.get("score", 0.0)),
            }
            for e in evidence
        ],
    }


def explain_dataframe(
    df: pd.DataFrame,
    *,
    index_path: str | Path,
    top_k: int = 4,
    only_uncertain: bool = True,
) -> pd.DataFrame:
    idx = load_rag_index(index_path)
    out = df.copy()
    expls: list[str] = []
    for _, row in out.iterrows():
        if only_uncertain and "decision_label" in out.columns:
            if str(row.get("decision_label", "")) != "AttackUncertain":
                expls.append("")
                continue
        payload = explain_row(row, index=idx, top_k=top_k)
        expls.append(json.dumps(redact_obj(payload), ensure_ascii=False))
    out["llm_explanation_json"] = expls
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build/use RAG index for AttackUncertain explanations.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-index")
    b.add_argument("--corpus-jsonl", required=True)
    b.add_argument("--out-index", required=True)

    e = sub.add_parser("explain")
    e.add_argument("--input", required=True)
    e.add_argument("--output", required=True)
    e.add_argument("--index-path", required=True)
    e.add_argument("--top-k", type=int, default=4)
    e.add_argument("--all-rows", action="store_true")
    e.add_argument("--emit-run-summary", default=None)

    args = ap.parse_args()
    if args.cmd == "build-index":
        payload = build_rag_index(args.corpus_jsonl, args.out_index)
        print(json.dumps(payload, indent=2))
        return 0

    df = read_table(args.input)
    out = explain_dataframe(
        df,
        index_path=args.index_path,
        top_k=int(args.top_k),
        only_uncertain=not bool(args.all_rows),
    )
    write_table(out, args.output)
    summary = {
        "rows": len(out),
        "output": str(Path(args.output).resolve()),
        "rows_with_explanations": int((out["llm_explanation_json"].astype(str).str.len() > 0).sum()),
    }
    if args.emit_run_summary:
        Path(args.emit_run_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit_run_summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
