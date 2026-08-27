# LLM usage (explanations only)

LLMs are **not** used for primary detection. They may format analyst-facing text from **redacted, deterministic** payloads.

## Flow

1. **`hawk_eye.explain`** (or your pipeline) produces JSON with `top_features` (linear model) or you build a payload from RAG output.
2. **`hawk_eye.llm_format`** sends that JSON to an **OpenAI-compatible** chat API when `OPENAI_API_KEY` or `DEEPSEEK_API_KEY` is set, or returns an **offline stub** when neither is set (CI-safe). Deepseek uses the same `/v1/chat/completions` shape; put the key in `.env` as `DEEPSEEK_API_KEY` (see `scripts/run_api_8000.sh`, which sources `.env`).
3. **Stream sessions:** after a completed **Live stream** job, `POST /api/v1/llm/stream-incident-report` with `{"job_id": <id>}` builds a **student-facing incident narrative** from the job summary + sample Parquet rows (`format_stream_incident_report` in `llm_format.py`). The user payload includes **`grounded_facts`** (key verdict numbers duplicated for anchoring) plus **`stream_summary`** and **`sample_rows`** (attack-like rows sorted first, IPv4 redacted by default). The system prompt (`prompts/incident_report_v1.txt`) expects **`risk_level`**, **`risk_headline`**, **`risk_plain_summary`**, **`known_attack_types`**, and **decision counts** so the text matches the dashboard verdict. Optional tuning: `HAWK_EYE_LLM_TEMPERATURE`, `HAWK_EYE_LLM_MAX_TOKENS_INCIDENT`, etc. (see `docs/ENVIRONMENT.md`). Same env vars and stub behavior.
4. Always run **`hawk_eye.redact`** on payloads before any external API when real identifiers might appear.

## Environment

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | If set, enables live API formatting (takes precedence over `DEEPSEEK_API_KEY`). |
| `DEEPSEEK_API_KEY` | If set and `OPENAI_API_KEY` is empty, uses Deepseek’s API; defaults to `OPENAI_BASE_URL=https://api.deepseek.com/v1` and `OPENAI_MODEL=deepseek-chat` unless you set those explicitly. |
| `OPENAI_BASE_URL` | Default `https://api.openai.com/v1` (or Deepseek URL when only `DEEPSEEK_API_KEY` is set). Use e.g. `http://localhost:11434/v1` for Ollama’s OpenAI-compatible server. |
| `OPENAI_MODEL` | Default `gpt-4o-mini` (or `deepseek-chat` when only `DEEPSEEK_API_KEY` is set). |

## CLI

```bash
# Offline stub (no key required)
python -m hawk_eye.llm_format --input explain.json --no-llm

# Live API (requires key — OpenAI or Deepseek)
export OPENAI_API_KEY=sk-...
# or: export DEEPSEEK_API_KEY=sk-...
python -m hawk_eye.llm_format --input explain.json --out reports/llm_formatted.json
```

## Prompt templates

Versioned templates live under `prompts/` (e.g. `explain_alert_v1.txt`). If the directory is missing (non-editable install), a built-in default system prompt is used.

## RAG column `llm_explanation_json`

`hawk_eye.rag_triage` attaches JSON retrieval summaries to rows under **`llm_explanation_json`**. That name is historical: content is **structured analyst aid**, not necessarily from a generative LLM. You can pass parsed objects through **`llm_format`** if you want natural-language formatting.
