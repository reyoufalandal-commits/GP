# Scaling and multi-instance deployment (design notes)

Hawk-Eye defaults to **SQLite**, **in-process** background jobs, and an **in-memory** WebSocket hub (`ws_hub`). That fits single-node, local-first operation.

If you need **high availability**, **horizontal scale**, or **multi-tenant SaaS**, plan explicit changes:

## Database

- **SQLite** is a single-writer store; multiple API replicas contend on the same file.
- **Direction:** introduce a **PostgreSQL** (or similar) backend for users, alerts, cases, jobs, and audit. Keep migrations versioned; abstract DB access behind a thin repository layer so routes stay unchanged.

## Background jobs

- Long **export** and **stream_collect** jobs run in-process today.
- **Direction:** a **queue** (Redis + RQ/Celery/Arq) with worker processes, idempotent job IDs, and heartbeats. The API enqueues; workers update `background_jobs` rows.

## WebSockets

- `ws_hub` holds connected clients in memory; it does not fan out across replicas.
- **Direction:** **Redis pub/sub** or a managed real-time bus; the API publishes audit/alert events and WebSocket handlers subscribe per instance.

## Object storage

- Large Parquet exports under `data/` may move to **S3-compatible** storage with signed URLs.

## When to invest

Prefer shipping **one solid node** (Docker + backups + monitoring) until load or HA requirements justify the operational cost of the stack above.
