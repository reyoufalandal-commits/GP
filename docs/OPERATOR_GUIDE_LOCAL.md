# Hawk-Eye Local Operator Guide

## 1) Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

**Baseline checklist, CORS, and React dashboard deploy:** see [`docs/DASHBOARD_DEPLOY.md`](DASHBOARD_DEPLOY.md).

**Security, TLS, and environment variables:** [`docs/SECURITY.md`](SECURITY.md), [`docs/ENVIRONMENT.md`](ENVIRONMENT.md).

**Docker:** [`docs/DOCKER.md`](DOCKER.md). **Scaling / HA (design):** [`docs/SCALING.md`](SCALING.md).

### First-run verification (dashboard + API)

**Students / instructors:** assign [STUDENT_QUICKSTART.md](STUDENT_QUICKSTART.md) for a minimal path; full lab narrative is [STUDENT_LAB.md](STUDENT_LAB.md).

| Check | Action |
|-------|--------|
| API up | `curl -s http://127.0.0.1:8000/health` |
| Ready to score | `curl -s http://127.0.0.1:8000/ready` — all `checks.*.exists` should be `true` for Model lab scoring |
| CORS | If the UI runs on another port (e.g. 5174), include it in `HAWK_EYE_CORS_ORIGINS` when starting uvicorn (see `./scripts/run_api_8000.sh`) |
| Users | After first API start, use `scripts/seed_user.py` for non-default accounts |

**Add users (no public sign-up):** after the API has created `data/db/hawk_eye.db` (start the server once or run any command that calls `init_db`):

```bash
python3 scripts/seed_user.py --username analyst1 --password 'change-me' --role analyst
```

Optional `--tenant-id` must reference an existing row in `tenants`.

## 2) Canonical Local Run

```bash
./scripts/run_canonical_local.sh
```

This command validates the run manifest, executes triage, checks production readiness, builds quality report, and evaluates KPI gate.

## 3) Runtime Lab

```bash
python scripts/create_runtime_lab.py --lab-dir ../HawkEye_RuntimeLab --sample-rows 10000
cd ../HawkEye_RuntimeLab
./bootstrap_and_run.sh
```

Outputs are written under `reports/<timestamp>/run_summary.json`.

## 4) Decision Labels

- `KnownAttack`: high-confidence known attack family behavior.
- `AttackUncertain`: attack-like or novelty-like signal requiring analyst triage.
- `BenignOrLowRisk`: low-risk traffic under current thresholds.

## 5) KPI Gate

```bash
python scripts/enforce_kpi_gate.py \
  --scorecard reports/final_rare_scorecard.json \
  --policy config/kpi_policy.json \
  --out reports/kpi_gate.json
```

Exit code `0` means pass, `2` means fail.

## 5.1) External Unknown Profiles (UNSW)

Generate recommended operating profiles:

```bash
python scripts/tune_unsw_external_profiles.py \
  --input reports/unsw_scored_labeled.parquet \
  --out reports/unsw_external_profiles.json
```

- `balanced_profile`: lower analyst load, moderate unknown recall.
- `high_recall_profile`: higher unknown recall, higher alert volume.

Apply a selected profile directly:

```bash
python scripts/run_unsw_profile_pipeline.py \
  --profile balanced \
  --profiles-json reports/unsw_external_profiles.json \
  --input reports/unsw_scored_labeled.parquet
```

Switch to `--profile high_recall` when maximum external unknown capture is preferred.

## 6) API Service

```bash
./scripts/run_api_service.sh
```

Health checks:
- `GET /health`: service process up.
- `GET /ready`: required bundles found and readable.

### Authentication

There is **no public sign-up**. Use **`POST /api/v1/auth/login`** (and refresh/logout/API keys as needed). On first database init, a seeded **`admin`** user exists (password `admin123` unless you change it in the DB). **Create additional users** from your separate admin dashboard or by inserting rows into the SQLite **`users`** table (`username`, `password_hash`, `role`, `tenant_id`). A future protected admin API can be added here if you want user creation over HTTP.

### Detection settings API (modes and UNSW profiles)

Settings are persisted in SQLite (`data/db/hawk_eye.db`, table `detection_settings`).

- `GET /api/v1/settings/detection` (authenticated): returns `active_dual_mode` (`stream` or `batch`), `active_unsw_profile` (`balanced` or `high_recall`), optional per-scope artifact directory overrides, resolved effective paths, and a `fusion_defaults_preview` derived from `reports/unsw_external_profiles.json` when that file exists (plus `reports/thresholds_fusion_selected.json` defaults).
- `PATCH /api/v1/settings/detection` (analyst or admin): updates the same fields. Global admins may use query parameter `?tenant_id=<id>` to read or write a tenant-specific override; otherwise the caller’s tenant (or global defaults for a global admin) applies.

`POST /api/v1/detections/score` and `POST /api/v1/detections/triage` use these stored defaults when `binary_dir`, `supervised_dir`, or `anomaly_dir` are omitted from the request body. Triage passes profile-derived fusion thresholds into `fuse_decisions`. Responses include an `applied` object describing what was used.

The `stream` vs `batch` value is a **declared operating mode** for clients and dashboards; it does not start or stop the Zeek-based `run_dual_detection.py` worker. Use the scripts in section 7 below for actual stream or batch runs.

### Timed stream collection (API)

`POST /api/v1/detections/stream-session` inserts a row into SQLite **`background_jobs`** and runs the collection in the background. For a **user-selected duration** (e.g. `30s`, `1m`, `2m`, `1h`, `1d`, or integer seconds), the worker **polls a Zeek `conn.log` file**, appends new rows as they appear, runs the same scoring + fusion stack as triage, and writes **`data/stream_sessions/job_<id>_scored.parquet`** plus a JSON summary at `result_path` when the job completes. **Job state lives only in SQLite** (`status`, `result_path`, `error` on that row). Use **`GET /api/v1/jobs/{job_id}`** (reads `background_jobs`) or inspect the DB file directly—there is no WebSocket or separate progress channel for stream jobs.

- Set **`conn_log_path`** on the request or persist it with **`PATCH /api/v1/settings/detection`** (`conn_log_path`, optional `stream_poll_seconds`, `stream_duration_default_seconds`).
- After **`status`** is **`completed`**, **`GET /api/v1/jobs/{job_id}/stream-summary`** returns the same JSON written next to the Parquet under `data/stream_sessions/` (row counts, `decision_counts`, output paths). The Model lab polls the job and loads this automatically.
- Max duration is **7 days** (`604800` seconds). The HTTP request returns immediately; long windows run in the server process via FastAPI `BackgroundTasks`.

## 7) Dual Detection Modes (Stream + Batch)

Batch mode (ready dataset):

```bash
python scripts/run_dual_detection.py \
  --mode batch \
  --input data/processed/val.csv \
  --output reports/dual_mode_scored.parquet \
  --alert-log reports/live_alerts.jsonl
```

Stream mode (current network via Zeek `conn.log` updates):

```bash
python scripts/run_dual_detection.py \
  --mode stream \
  --conn-log /path/to/zeek/conn.log \
  --output reports/dual_mode_stream_scored.parquet \
  --state-path reports/live_stream_state.json \
  --alert-log reports/live_alerts.jsonl
```

Optional webhook in both modes:

```bash
--webhook-url http://127.0.0.1:8000/alerts
```

## 8) Timed stream → model → results (full operator checklist)

This section matches the **stream_collect** API path: Zeek `conn.log` → polling window → scoring + fusion → Parquet + summary.

### 8.1 Prerequisites (before first run)

1. **`GET /health`** and **`GET /ready`**: binary, supervised, and anomaly bundle directories exist and are readable (same as dashboard Model lab).
2. **Zeek** (or replay) so **`conn.log`** exists and the **same OS user as uvicorn** can **read** it.
3. **Feature contract**: Streams use **`zeek_to_bundle_contract`** in [`src/hawk_eye/live/dual_mode.py`](../src/hawk_eye/live/dual_mode.py); training must align with mapped CICIDS-style columns expected by your bundles.
4. **Permissions**: The API user needs **read** on `conn.log` and **read/write** on **`data/stream_sessions/`** (Parquet, `job_<id>_state.json`, summary JSON).

### 8.2 Run a timed stream (API / Model lab)

1. Set **`conn_log_path`**: **`PATCH /api/v1/settings/detection`** and/or the stream-session request body / Model lab **conn_log_path** field.
2. Choose **`duration`** (`30s`, `2m`, `1h`, integer seconds; max **7 days**).
3. **`POST /api/v1/detections/stream-session`** — record **`job_id`**.
4. Poll **`GET /api/v1/jobs/{job_id}`** until **`completed`** or **`failed`** (inspect **`error`**).
5. **Summary:** **`GET /api/v1/jobs/{job_id}/stream-summary`** — `rows_scored`, `decision_counts`, paths.
6. **Row preview (no SSH):** **`GET /api/v1/jobs/{job_id}/scored-preview?limit=...`** (limit 1–500) — last *limit* rows from **`job_<id>_scored.parquet`**. Large Parquets are read fully server-side; cap `limit` for API sanity.
7. **Optional:** `alert_log_path` (JSONL on disk), `webhook_url` (HTTP POST per alert-like row) — exposed in **Model lab** or API body.

### 8.3 Operations reality checks

| Check | Notes |
|-------|--------|
| **Zero traffic** | Job may **`complete`** with **`rows_scored` = 0** if Zeek adds no new lines in the window. |
| **Growing log** | Worker tracks **`line_offset`** in **`job_<id>_state.json`**; only new lines after the offset are scored each poll. |
| **Long runs** | Plan disk for Parquet growth; monitor job status. |
| **Failures** | Common: bad path, permission denied, bundle mismatch, corrupt Zeek line. |
| **Log rotation** | If Zeek rotates `conn.log` in a way that breaks whole-file reads, validate behavior in your environment. |
| **Concurrent jobs** | Multiple `stream_collect` jobs on the **same** `conn.log` can duplicate work—prefer one job per log path. |

### 8.4 Labels and tuning (not ground truth)

- **`decision_label`** comes from **fusion + thresholds**, not verified ground truth. See §4 and [`reports/thresholds_fusion_selected.json`](../reports/thresholds_fusion_selected.json) / [`reports/unsw_external_profiles.json`](../reports/unsw_external_profiles.json) and **`active_unsw_profile`** in detection settings.
- **Zeek / training drift** harms scores; resample `conn.log` and re-validate periodically.

### 8.5 Security (beyond lab)

- **Webhook / JSONL** may contain sensitive flow fields — use HTTPS, auth, and allowlists.
- Replace default **`admin` / `admin123`** and SHA-256-at-rest before internet exposure; use TLS and a reverse proxy.

### 8.6 Zeek cookbook (lab / replay)

**Live host (paths vary by install):**

- Linux packages often log under something like **`/var/log/zeek/`** or the Zeek **spool** directory configured in `node.cfg`.
- macOS Homebrew: often under **`$(brew --prefix)/var/spool/zeek`** or similar — run `zeek -e ...` or deploy Zeek per your distro docs.

**Demo without a live NIC — PCAP → Zeek:**

```bash
# Example: turn PCAP into conn.log style logs with your Zeek install, then point conn_log_path
# at the generated log. Exact commands depend on Zeek version and package layout.
zeek -r /path/to/capture.pcap /path/to/local.zeek
# Then set conn_log_path to the resulting conn.log (directory depends on Zeek CWD / policy).
```

Use **`POST /api/v1/detections/triage`** with batch rows, or **`run_dual_detection.py --mode batch`**, when you do not need a **timed tail** (same model stack).

## 9) Stream API quick reference

| Step | Method / path |
|------|----------------|
| Start window | `POST /api/v1/detections/stream-session` |
| Job status | `GET /api/v1/jobs/{id}` |
| Summary JSON | `GET /api/v1/jobs/{id}/stream-summary` |
| Last N scored rows | `GET /api/v1/jobs/{id}/scored-preview?limit=N` |
