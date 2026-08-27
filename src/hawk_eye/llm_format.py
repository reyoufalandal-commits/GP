"""
Optional LLM formatting for analyst-facing explanations.

- With ``OPENAI_API_KEY`` or ``DEEPSEEK_API_KEY`` set, calls an OpenAI-compatible ``/v1/chat/completions`` API
  (Deepseek uses the same wire format; see ``_resolve_openai_compatible_settings``).
- Without a key (or ``use_llm=False``), returns a deterministic stub string so CI and
  air-gapped runs stay green. Detection remains non-LLM per ``docs/llm.md``.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)


def _resolve_openai_compatible_settings(
    *,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[str, str, str]:
    """
    API key: explicit arg, else ``OPENAI_API_KEY``, else ``DEEPSEEK_API_KEY``.

    When only ``DEEPSEEK_API_KEY`` is set (and ``OPENAI_API_KEY`` is empty), default
    base URL and model to Deepseek's OpenAI-compatible endpoint.
    """
    key = (api_key or "").strip()
    if not key:
        key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()
    only_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()) and not os.environ.get(
        "OPENAI_API_KEY", ""
    ).strip()

    url = (base_url or os.environ.get("OPENAI_BASE_URL") or "").strip()
    if not url:
        url = "https://api.deepseek.com/v1" if only_deepseek else "https://api.openai.com/v1"

    mdl = (model or os.environ.get("OPENAI_MODEL") or "").strip()
    if not mdl:
        mdl = "deepseek-chat" if only_deepseek else "gpt-4o-mini"

    return key, url, mdl


def llm_capabilities() -> dict[str, Any]:
    """
    Safe JSON for dashboards: whether an API key is configured, provider label, host, default model.
    Never exposes secrets.
    """
    key, url, mdl = _resolve_openai_compatible_settings(api_key=None, base_url=None, model=None)
    only_deepseek = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip()) and not os.environ.get(
        "OPENAI_API_KEY", ""
    ).strip()
    if key:
        provider: str = "deepseek" if only_deepseek else "openai"
    else:
        provider = "none"
    host = urlparse(url).netloc or url[:80]
    return {
        "llm_available": bool(key),
        "provider": provider,
        "base_url_display": host,
        "model_default": mdl,
    }


def redact_ipv4_in_str(s: str) -> str:
    return _IPV4.sub("[redacted-ip]", s)


def redact_sample_rows_for_llm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mask dotted-quad IPv4s in string cell values before sending to an external LLM."""
    out: list[dict[str, Any]] = []
    for r in rows:
        nr: dict[str, Any] = {}
        for k, v in r.items():
            if isinstance(v, str):
                nr[k] = redact_ipv4_in_str(v)
            else:
                nr[k] = v
        out.append(nr)
    return out


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _max_tokens_for(kind: str) -> int:
    """Per-task ceiling; optional env overrides (see docs/ENVIRONMENT.md)."""
    if kind == "explain":
        raw = (os.environ.get("HAWK_EYE_LLM_MAX_TOKENS_EXPLAIN") or "").strip()
        if raw:
            try:
                return max(256, int(raw))
            except ValueError:
                pass
    if kind == "incident":
        raw = (os.environ.get("HAWK_EYE_LLM_MAX_TOKENS_INCIDENT") or "").strip()
        if raw:
            try:
                return max(512, int(raw))
            except ValueError:
                pass
    fallback = (os.environ.get("HAWK_EYE_LLM_MAX_TOKENS") or "").strip()
    if fallback:
        try:
            return max(256, int(fallback))
        except ValueError:
            pass
    return 2048 if kind == "explain" else 4096


def _danger_verdict_hint(stream_summary: dict[str, Any]) -> str:
    """
    Machine-readable tag for prompts; aligns with risk_level + decision_counts.
    """
    rs = stream_summary.get("rows_scored")
    try:
        nrs = int(rs) if rs is not None else None
    except (TypeError, ValueError):
        nrs = None
    if nrs is not None and nrs == 0:
        return "no_traffic_scored"
    rl = str(stream_summary.get("risk_level") or "").lower()
    dc = stream_summary.get("decision_counts") or {}

    def _i(k: str) -> int:
        try:
            return int(dc.get(k) or 0)
        except (TypeError, ValueError):
            return 0

    ka, au = _i("KnownAttack"), _i("AttackUncertain")
    if rl == "unknown":
        return "unclear_insufficient_signal"
    if rl == "low" and ka == 0 and au == 0:
        return "no_significant_danger_in_window"
    if rl == "elevated" or ka > 0 or au > 0:
        return "potential_danger_review_recommended"
    return "mixed_review_recommended"


def _plain_language_danger_line(stream_summary: dict[str, Any]) -> str:
    """One sentence for the LLM — must stay consistent with grounded numbers."""
    tag = _danger_verdict_hint(stream_summary)
    lines = {
        "no_traffic_scored": "No flows were scored in this window, so we cannot judge whether danger was present.",
        "no_significant_danger_in_window": "In this window the model did not flag strong attack-style activity; still treat as lab output, not proof of safety.",
        "potential_danger_review_recommended": "The model saw elevated risk or attack-style labels — this deserves a human review and validation with your own tools.",
        "unclear_insufficient_signal": "There is not enough signal in this summary to say clearly whether danger was present.",
        "mixed_review_recommended": "Signals are mixed; use the counts and samples below before deciding how serious this is.",
    }
    return lines.get(tag, lines["mixed_review_recommended"])


def grounded_facts_for_stream_session(stream_summary: dict[str, Any]) -> dict[str, Any]:
    """
    Compact, explicit facts for the incident LLM — repeat numbers the model must not contradict.
    """
    dc = stream_summary.get("decision_counts") or {}
    kat = stream_summary.get("known_attack_types") or {}
    return {
        "mode": stream_summary.get("mode"),
        "duration_seconds": stream_summary.get("duration_seconds"),
        "rows_scored": stream_summary.get("rows_scored"),
        "alerts_emitted": stream_summary.get("alerts_emitted"),
        "risk_level": stream_summary.get("risk_level"),
        "attack_indicators": stream_summary.get("attack_indicators"),
        "risk_headline": stream_summary.get("risk_headline"),
        "risk_plain_summary": stream_summary.get("risk_plain_summary"),
        "decision_counts": dc,
        "known_attack_types": kat,
        "scored_output_path": stream_summary.get("output"),
        "state_path": stream_summary.get("state"),
        "danger_verdict_hint": _danger_verdict_hint(stream_summary),
        "plain_language_danger_hint": _plain_language_danger_line(stream_summary),
    }


def _sort_sample_rows_for_incident_llm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Put highest-signal flows first (attack labels, then p_attack)."""

    def rank(r: dict[str, Any]) -> tuple[int, float]:
        label = str(r.get("decision_label", ""))
        if label == "KnownAttack":
            tier = 2
        elif label == "AttackUncertain":
            tier = 1
        else:
            tier = 0
        p = r.get("p_attack")
        try:
            pf = float(p) if p is not None else 0.0
        except (TypeError, ValueError):
            pf = 0.0
        return (tier, pf)

    out = list(rows)
    out.sort(key=rank, reverse=True)
    return out


def _parse_llm_http_error_body(detail: str) -> str:
    """Extract human message from OpenAI-compatible JSON error bodies."""
    try:
        j = json.loads(detail)
        if isinstance(j, dict):
            err = j.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if j.get("message"):
                return str(j["message"])
    except json.JSONDecodeError:
        pass
    return detail[:2000]


def _llm_http_error_hint(code: int, message: str) -> str:
    m = message.lower()
    if code == 401:
        return " — Verify OPENAI_API_KEY or DEEPSEEK_API_KEY in the server .env and restart the API."
    if code == 402 or "insufficient balance" in m or "payment required" in m:
        return " — Account balance or billing: top up at https://platform.deepseek.com for Deepseek keys."
    if code == 429:
        return " — Rate limited; retry after a short wait."
    return ""


def stream_summary_to_markdown(
    stream_summary: dict[str, Any],
    incident_markdown: str | None = None,
) -> str:
    """Exportable Markdown from a stream job summary (+ optional LLM/stub narrative)."""
    lines = [
        "# Hawk-Eye stream session report",
        "",
        "## Verdict",
        "",
        f"- **risk_level:** {stream_summary.get('risk_level', '—')}",
        f"- **attack_indicators:** {stream_summary.get('attack_indicators', '—')}",
        f"- **risk_headline:** {stream_summary.get('risk_headline', '—')}",
        f"- **risk_plain_summary:** {stream_summary.get('risk_plain_summary', '—')}",
        "",
        "## Counts",
        "",
        f"- **rows_scored:** {stream_summary.get('rows_scored', '—')}",
        f"- **decision_counts:** `{json.dumps(stream_summary.get('decision_counts') or {}, ensure_ascii=False)}`",
        f"- **known_attack_types:** `{json.dumps(stream_summary.get('known_attack_types') or {}, ensure_ascii=False)}`",
        "",
    ]
    if stream_summary.get("output"):
        lines.extend(["## Artifacts", "", f"- **scored_parquet:** `{stream_summary.get('output')}`", ""])
    if incident_markdown and str(incident_markdown).strip():
        lines.extend(["## Incident narrative", "", str(incident_markdown).strip(), ""])
    else:
        lines.extend(
            [
                "## Incident narrative",
                "",
                "_Generate via the dashboard or `POST /api/v1/llm/stream-incident-report`._",
                "",
            ]
        )
    lines.extend(["## Raw summary JSON", "", "```json", json.dumps(stream_summary, indent=2, default=str), "```", ""])
    return "\n".join(lines)


def stream_worksheet_html(stream_summary: dict[str, Any]) -> str:
    """Single-page printable classroom worksheet (browser Print to PDF)."""
    title = "Hawk-Eye lab worksheet"
    rl = html.escape(str(stream_summary.get("risk_level", "—")))
    rh = html.escape(str(stream_summary.get("risk_headline", "—")))
    dc = html.escape(json.dumps(stream_summary.get("decision_counts") or {}, indent=2))
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{title}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 1.5rem auto; color: #111; }}
  h1 {{ font-size: 1.25rem; }}
  .box {{ border: 1px solid #ccc; padding: 0.75rem; margin: 0.75rem 0; min-height: 4rem; }}
  pre {{ white-space: pre-wrap; font-size: 0.85rem; }}
  @media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>{title}</h1>
<p><strong>Name:</strong> __________________ &nbsp; <strong>Date:</strong> __________</p>
<p><strong>risk_level:</strong> {rl}</p>
<p><strong>risk_headline:</strong> {rh}</p>
<h2>Observations</h2>
<div class="box"></div>
<h2>decision_counts</h2>
<pre>{dc}</pre>
<h2>Limitations (student)</h2>
<div class="box"></div>
  <p style="font-size:0.85rem;color:#555">ML scores are not proof of compromise. Document assumptions.</p>
</body></html>"""


def _repo_prompts_dir() -> Path | None:
    # .../repo/src/hawk_eye/llm_format.py -> repo is parents[2]
    here = Path(__file__).resolve()
    for i in range(2, min(6, len(here.parents))):
        candidate = here.parents[i] / "prompts"
        if candidate.is_dir():
            return candidate
    cwd = Path.cwd() / "prompts"
    return cwd if cwd.is_dir() else None


def load_incident_report_prompt(filename: str = "incident_report_v1.txt") -> str:
    d = _repo_prompts_dir()
    if d:
        p = d / filename
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return (
        "You are a security analyst. Given grounded_facts (including danger_verdict_hint and plain_language_danger_hint), "
        "stream_summary, and sample_rows JSON, write a conversational Markdown incident briefing. "
        "Start with a TL;DR: is there danger in this window? Use warm, plain language; do not invent IPs or CVEs."
    )


def load_explain_prompt(filename: str = "explain_alert_v1.txt") -> str:
    d = _repo_prompts_dir()
    if d:
        p = d / filename
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return (
        "You are a security analyst assistant.\n"
        "Given structured feature contributions, write a short plain-language summary "
        "and 1-2 investigative next steps. Do not invent IPs or hostnames.\n"
    )


def explain_payload_to_stub_text(payload: dict[str, Any]) -> str:
    """Offline, deterministic narrative from ``hawk_eye.explain`` JSON."""
    tops = payload.get("top_features") or []
    parts = [
        "Summary (offline stub — set OPENAI_API_KEY for API formatting):",
        f"Row index: {payload.get('row_index', 0)}; model bundle: {payload.get('model_version', '')!s}.",
    ]
    if tops:
        parts.append("Top contributing features (linear approximation):")
        for t in tops[:8]:
            parts.append(
                f"  • {t.get('name')}: value={t.get('value')}, contribution={float(t.get('contribution', 0.0)):.4f}"
            )
    else:
        parts.append("No linear top_features available (non-linear model or empty).")
    parts.append("Next steps: validate entities in SIEM; compare against baseline; map to playbook.")
    return "\n".join(parts)


def stream_incident_stub_text(
    stream_summary: dict[str, Any],
    sample_rows: list[dict[str, Any]],
) -> str:
    """Offline narrative for a completed stream job (no API key)."""
    rows_scored = stream_summary.get("rows_scored", stream_summary.get("total_rows"))
    dc = stream_summary.get("decision_counts") or {}
    kat = stream_summary.get("known_attack_types") or {}
    rl = stream_summary.get("risk_level")
    ai = stream_summary.get("attack_indicators")
    danger_tag = _danger_verdict_hint(stream_summary)
    plain_danger = _plain_language_danger_line(stream_summary)
    parts = [
        "## Executive summary (offline template — set OPENAI_API_KEY on the server for natural-language prose)",
        "",
        "## Is there danger? (plain answer)",
        "",
        f"**Short answer:** {plain_danger}",
        "",
        f"- **Verdict tag (internal):** `{danger_tag}` — same logic the dashboard uses with `risk_level` and `decision_counts`.",
        f"- **risk_level:** {rl!s} — `low` usually means no attack-style labels in the window; `elevated` means review; `unknown` means little or nothing was scored.",
        f"- **attack_indicators:** {ai!s}",
        f"- **risk_headline:** {stream_summary.get('risk_headline', '—')}",
        f"- **risk_plain_summary:** {stream_summary.get('risk_plain_summary', '—')}",
        f"- **Rows scored in window:** {rows_scored!s}",
        f"- **decision_counts:** {json.dumps(dc, indent=2) if dc else 'none'}",
        f"- **known_attack_types** (supervised multiclass on KnownAttack rows only): "
        f"{json.dumps(kat, indent=2) if kat else 'none'}",
        "",
        "## What we can say in human terms",
        "Think of this as a **lab assistant**: it labels each flow with **BenignOrLowRisk**, **AttackUncertain**, or **KnownAttack**. "
        "That is not proof of a real breach — it is a fusion of ML scores on Zeek features. "
        "If you see **KnownAttack** or **AttackUncertain** counts, treat the window as *worth a second look*; if everything is benign and risk is low, the window still might miss things the model was not trained for.",
        "",
        "## Sample rows (truncated)",
    ]
    if not sample_rows:
        parts.append("_No sample rows were provided._")
    else:
        for i, row in enumerate(sample_rows[:8], 1):
            label = row.get("decision_label", "?")
            parts.append(f"{i}. decision_label={label!r} — keys: {', '.join(list(row.keys())[:10])}…")
    parts.extend(
        [
            "",
            "## Limitations",
            "Lab ML scores are not proof of real compromise; they depend on bundles and thresholds.",
            "",
            "## Next steps",
            "- Confirm Zeek (or the lab simulator) appends to the same `conn.log` path the server reads.",
            "- Try a longer window if you saw zero rows.",
            "- Compare decision_counts and risk_level to your ground-truth lab script (if you labeled the run).",
        ]
    )
    return "\n".join(parts)


def format_stream_incident_report(
    stream_summary: dict[str, Any],
    sample_rows: list[dict[str, Any]],
    *,
    use_llm: bool | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    redact_ips: bool | None = None,
) -> dict[str, Any]:
    """
    Student-facing narrative for a completed ``stream_collect`` job.
    Returns ``{"source", "text"}`` like :func:`format_model_explanation`.
    """
    key, url, mdl = _resolve_openai_compatible_settings(api_key=api_key, base_url=base_url, model=model)

    dc = stream_summary.get("decision_counts") or {}

    known_attack_count = int(dc.get("KnownAttack") or 0)
    uncertain_attack_count = int(dc.get("AttackUncertain") or 0)

    if known_attack_count == 0 and uncertain_attack_count == 0:
        return {
            "source": "skipped_benign",
            "text": "",
        }

    do_redact = redact_ips if redact_ips is not None else os.environ.get("HAWK_EYE_LLM_REDACT_IPS", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    slice_rows = sample_rows[:50]
    rows_for_llm = redact_sample_rows_for_llm(slice_rows) if do_redact else slice_rows
    rows_for_llm = _sort_sample_rows_for_incident_llm(rows_for_llm)

    if use_llm is False or not key:
        return {"source": "deterministic_stub", "text": stream_incident_stub_text(stream_summary, sample_rows)}

    user_obj = {
        "grounded_facts": grounded_facts_for_stream_session(stream_summary),
        "stream_summary": stream_summary,
        "sample_rows": rows_for_llm,
    }
    user = json.dumps(user_obj, indent=2, default=str)
    if len(user) > 80_000:
        user = user[:80_000] + "\n… [truncated]"
    system = load_incident_report_prompt()
    inc_temp = _env_float("HAWK_EYE_LLM_TEMPERATURE_INCIDENT", 0.42)
    text = _chat_completions_openai_compatible(
        base_url=url,
        api_key=key,
        model=mdl,
        system=system,
        user=user,
        max_tokens=_max_tokens_for("incident"),
        temperature=inc_temp,
    )
    return {"source": "openai_compatible", "text": text}


def _chat_completions_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout_s: int = 120,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    temp = _env_float("HAWK_EYE_LLM_TEMPERATURE", 0.15) if temperature is None else temperature
    mt = max_tokens if max_tokens is not None else _max_tokens_for("explain")
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temp,
            "max_tokens": mt,
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        msg = _parse_llm_http_error_body(detail)
        hint = _llm_http_error_hint(e.code, msg)
        raise RuntimeError(f"LLM HTTP {e.code}: {msg}{hint}") from e
    try:
        return str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected LLM response shape: {data!r}") from e


def format_model_explanation(
    payload: dict[str, Any],
    *,
    use_llm: bool | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """
    Return ``{"source": "openai_compatible"|"deterministic_stub", "text": ...}``.

    If ``use_llm`` is None, uses LLM when ``api_key`` or ``OPENAI_API_KEY`` / ``DEEPSEEK_API_KEY`` is set.
    """
    key, url, mdl = _resolve_openai_compatible_settings(api_key=api_key, base_url=base_url, model=model)

    if use_llm is False or not key:
        return {"source": "deterministic_stub", "text": explain_payload_to_stub_text(payload)}

    user = json.dumps(payload, indent=2)
    system = load_explain_prompt()
    text = _chat_completions_openai_compatible(
        base_url=url,
        api_key=key,
        model=mdl,
        system=system,
        user=user,
        max_tokens=_max_tokens_for("explain"),
    )
    return {"source": "openai_compatible", "text": text}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Format explain.json with optional OpenAI-compatible LLM.")
    ap.add_argument("--input", required=True, help="Path to explain JSON (e.g. from hawk_eye.explain).")
    ap.add_argument("--out", default=None, help="Write {\"source\",\"text\"} JSON here.")
    ap.add_argument("--no-llm", action="store_true", help="Force deterministic stub.")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    args = ap.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = format_model_explanation(payload, use_llm=not args.no_llm, model=args.model, base_url=args.base_url)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
