# Metrics

The API exposes **Prometheus** text on **`GET /metrics`** (no auth). Use it for scraping from Prometheus, VictoriaMetrics, or similar.

## Counters

HTTP handlers increment a small set of counters (label `endpoint=…`) for major routes — for example `health`, `ready`, `api_status`, `login`, and detection/job endpoints. Exact names match handler registration in `src/hawk_eye/backend/routes.py`.

## Histogram (latency)

- **`hawk_eye_http_request_duration_seconds`** — wall time per HTTP request as observed by Starlette middleware (no per-path labels, to keep cardinality low). Useful for SLO-style dashboards and slow-request investigation alongside reverse-proxy metrics.

## Standard process metrics

The `prometheus_client` default registry also exports process stats (CPU, memory) where supported by the platform.

## Suggested alerts (examples)

- **`up{job="hawk-eye"}`** — instance reachable.
- **Scrape failures** on `/metrics` or high 5xx rates from your reverse proxy.
- Pair with **`GET /ready`** for bundle/DB presence checks in synthetic monitoring (readiness is also summarized in **`GET /api/v1/status`** for the dashboard).

See [ENVIRONMENT.md](ENVIRONMENT.md) for log and request-ID options that complement metrics.
