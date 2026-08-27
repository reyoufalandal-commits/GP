# Roadmap and scope

This file states **intent**, not a release calendar. For security reporting, see [SECURITY.md](SECURITY.md) (repository root) and [docs/SECURITY.md](SECURITY.md).

## In scope

- Zeek `conn.log`-style flow features, batch and stream scoring, fusion labels (`KnownAttack`, `AttackUncertain`, `BenignOrLowRisk`).
- Optional LLM **narratives** from structured JSON (not primary detection) — see [llm.md](llm.md).
- Local-first deployment: SQLite, file-backed bundles, optional Docker.
- Classroom / lab workflows: Model lab, live stream jobs, export markdown/worksheet.

## Out of scope (today)

- Certified “zero-day” or APT attribution; novelty paths are **heuristic** — see [MODEL_GOVERNANCE.md](MODEL_GOVERNANCE.md).
- Full SIEM replacement, PCAP reassembly, or host EDR.
- Native SSO/SAML inside the API (use a reverse proxy with OIDC if needed — future consideration).
- Managed multi-region SaaS.

## Near-term directions

- Optional OpenTelemetry export behind a feature flag.
- Further hardening as deployment threat models require (e.g. more tenant-scoped integration coverage).

**Done / in progress in tree:** operator backup script, request IDs + optional JSON access logs, Prometheus histogram + counters, password minimum length env, sample tenant isolation tests, session/token summary in [AUTH_TOKENS.md](AUTH_TOKENS.md).

Suggestions: open a GitHub Discussion or Issue in this repository’s tracker.
