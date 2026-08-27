# Analyst feedback loop (optional)

Store analyst labels on alerts to improve thresholds and reporting.

## JSONL row schema (one JSON object per line)

| Field | Type | Description |
|-------|------|-------------|
| `alert_id` | string | Stable ID (flow key, UUID, or hash). |
| `ts` | string ISO8601 | When the decision was recorded. |
| `verdict` | `tp` \| `fp` \| `benign` \| `unknown` | Analyst label. |
| `soc_action` | string | Copy from `soc_policy` output if applicable. |
| `model_version` | string | Bundle version. |

Example:

```json
{"alert_id":"a1","ts":"2026-03-24T12:00:00Z","verdict":"fp","soc_action":"block_candidate","model_version":"0.1.0"}
```

Use [`scripts/store_results_sqlite.py`](store_results_sqlite.py) or append to a secured JSONL file; do not commit live data.
