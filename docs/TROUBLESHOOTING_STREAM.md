# Live stream troubleshooting

Symptoms map to checks on the **API host** (the machine running `uvicorn`, not your browser).

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| **0 rows scored** / empty Parquet | No new lines appended to `conn.log` during the window | Confirm Zeek or `lab_simulate_conn_log.py` is writing to the **same path** the job uses. Extend duration or generate traffic. |
| **Wrong path** | `conn_log_path` in the UI or Detection settings points elsewhere | Use **Ops / health** and **stream hints** on the Live stream page; copy the resolved default path. |
| **API can’t see Zeek** | Dashboard runs in the browser; Zeek runs on the server | Zeek must run on the **same host as the API** (or mount the log file into the container). |
| **404 on stream-hints** | API version mismatch or wrong port | Restart the backend from this repo; ensure Vite proxies to the same port as [vite.config.ts](../dashboard/frontend/vite.config.ts). |
| **Job failed** | Missing bundles, bad JSON settings, permissions | Read the error on the Live stream page; run `/ready` and fix `artifacts/` paths. |
| **Stuck “listening”** | `conn.log` not updating | Check file mtime; for lab sim use `--daemon --append` so lines keep appending. |

## UI hints (same as Live stream page)

The **Live stream** page repeats these ideas inline:

- **Traffic source on the API host** — Zeek must write `conn.log` where the API can read it; the browser only drives the dashboard.
- **404 on stream-hints** — Backend and UI must be built from the **same repo/version**; restart `uvicorn` after pulling changes.
- **Stream capture strip while live** — When the job is running, the page shows whether `conn.log` exists and whether its mtime looks “active” (recent writes).

For Docker, bind-mount host log directories with `docker-compose.lab.yml` (see [DOCKER.md](DOCKER.md)).

See also [STUDENT_LAB.md](STUDENT_LAB.md), [QUICKSTART_LAB.md](QUICKSTART_LAB.md), and [ENVIRONMENT.md](ENVIRONMENT.md).
