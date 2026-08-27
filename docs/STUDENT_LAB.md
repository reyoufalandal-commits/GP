# Student lab guide — live stream and reports

Use this in a **classroom or VM lab** you control. Do not point tools at networks you are not authorized to test.

**New here?** Start with the short [STUDENT_QUICKSTART.md](STUDENT_QUICKSTART.md). In the dashboard, open **Start here** (`/start`) for links to Model lab, Live stream, and health checks.

## Five-minute path (shortest happy path)

1. `pip install -e ".[dev]"` then `python scripts/ci_build_minimal_bundles.py`
2. `./scripts/run_api_8000.sh` and `npm run dev` in `dashboard/frontend`
3. Log in → **Model lab** to confirm scoring works, or skip to step 4
4. `python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario mixed --lines 50`
5. **Live stream** → **1 min** → **Start streaming** → wait for **completed** → read verdict

## Recommended order (one path through the lab)

1. **Bundles + API + dashboard** — complete [One-time setup](#one-time-setup) so scoring works.
2. **Choose traffic source**
   - **Real network:** run Zeek on an interface (see [Live traffic](#live-traffic-from-your-network-zeek)) so `conn.log` grows on the API host.
   - **Synthetic lab:** generate `data/lab/sim_conn.log` (see [Simulated traffic](#simulated-traffic-no-zeek-required-for-a-quick-test)); no Zeek required for a quick run.
3. **Confirm path** — in **Live stream**, use the readiness strip or paste the absolute path to the `conn.log` the API should read.
4. **Start streaming** — short window first (e.g. 1 min); wait until the job is **completed**.
5. **Read the verdict** — attack vs benign summary, decision counts, sample rows.
6. **Optional:** click **Generate report** (or enable **Generate AI report when stream completes** on that page) for the student incident narrative.

## What you will learn

1. How Hawk-Eye scores **network flows** (Zeek `conn.log` lines) with supervised + anomaly + fusion labels.
2. How to run a **timed live stream** in the dashboard and read the session report.
3. How to optionally get a **plain-language incident narrative** (LLM) after a stream completes.

## One-time setup

1. Install Python deps: `pip install -e ".[dev]"` (see [`OPERATOR_GUIDE_LOCAL.md`](OPERATOR_GUIDE_LOCAL.md)).
2. Build or install **model bundles** under `artifacts/` (use `python scripts/ci_build_minimal_bundles.py` for tiny smoke bundles, or train real ones for meaningful labels).
3. Start the API (e.g. `./scripts/run_api_8000.sh`) and the React app (`npm run dev` in `dashboard/frontend`).
4. Log in (default dev admin is documented in [`SECURITY.md`](SECURITY.md) for local use).

## Live traffic from your network (Zeek)

On the **same machine that runs the Hawk-Eye API**, you can sniff an interface with Zeek and write `conn.log` under the repo:

```bash
chmod +x scripts/zeek_network_capture.sh
sudo ./scripts/zeek_network_capture.sh en0   # replace en0 with your interface
```

Then open **Live stream** in the dashboard, use **Use live capture path** (or set `conn_log_path` to `data/live/conn.log` manually). Zeek must keep running while the stream window is active. Raw capture often requires `sudo`.

## Simulated traffic (no Zeek required for a quick test)

Generate a synthetic `conn.log` slice (legacy preset):

```bash
python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario mixed --lines 50
```

**Scenario files** (time-phased profiles, jitter, bursts) live under `lab_scenarios/` — for example:

```bash
python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/steady_baseline.json --out data/lab/sim_conn.log
```

For a **long classroom mix** (normal baseline, then many synthetic “attack-like” shapes, then baseline again) with **plain-English explanations of each profile**, see **[LAB_SYNTHETIC_PROFILES.md](LAB_SYNTHETIC_PROFILES.md)** and run:

```bash
python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/classroom_full_menu.json --out data/lab/sim_conn.log --seed 42
```

The API will **automatically** use `data/lab/sim_conn.log` under the project root when that file exists and you did not set another path (no env var required). You can still set `conn_log_path` in **Detection settings** or on the **Live stream** page to override.

**While a stream is running**, append more lines in a second terminal — one-off append:

```bash
python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario heavy --lines 20 --append
```

Or run a **daemon** that loops the scenario until you press Ctrl+C (same `conn.log` path the stream reads):

```bash
python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/lab_demo_quick.json --daemon --out data/lab/sim_conn.log
```

Synthetic data only; use only on systems you are allowed to test.

## Run a live stream

1. Open **Live stream** in the sidebar.
2. Choose a short window (e.g. **1 min**) for your first run.
3. Click **Start streaming**. Wait until the timer finishes.
4. Read the **Session report** (label counts, sample table). Check **Ops / health** if `conn_log_path` was wrong.

## AI “final report” after the stream

After the job shows **completed**:

1. Click **Generate report** under **Incident report (LLM)** (uses the same job id), or check **Generate AI report when stream completes** before starting so the UI requests it automatically (preference is stored in the browser session only).
2. With **`OPENAI_API_KEY`** set on the server, you get a structured markdown-style narrative grounded in **risk_level**, **risk_headline**, **known_attack_types**, and decision counts.
3. Without a key, you still get a **deterministic template** so the lab works offline.

See [`docs/llm.md`](llm.md) for API and privacy notes.

## Model quality

“Perfect” detection is not realistic — models depend on training data and thresholds. For coursework, focus on **interpreting** `decision_label`, **comparing** runs, and documenting **limitations** (see [`MODEL_GOVERNANCE.md`](MODEL_GOVERNANCE.md)).

## Troubleshooting

| Symptom | Likely cause | What to do |
|--------|----------------|------------|
| Dashboard shows “cannot reach API” or endless loading | API not running or wrong URL / CORS | Start `./scripts/run_api_8000.sh`. If UI is not on the same origin, set `HAWK_EYE_CORS_ORIGINS` (see [OPERATOR_GUIDE_LOCAL.md](OPERATOR_GUIDE_LOCAL.md), `run_api_8000.sh`). |
| **Ops / health** or `/ready` shows bundles missing | No artifacts under `artifacts/` | Run `python scripts/ci_build_minimal_bundles.py` or install real bundles. |
| **Live stream** readiness never shows “listening” | Zeek not writing, or wrong host | Zeek and `conn.log` must be on the **API host**; path should be `data/live/conn.log` or set in Detection settings. |
| **Score** / **Triage** returns 400 about features | Rows are not Zeek-shaped or bundle columns | Use **Triage via conn.log upload** on Model lab, or paste rows with Zeek `conn` fields (`orig_bytes`, `duration`, …). |
| `/api/v1/detections/stream-hints` 404 in server logs | Old API process or wrong checkout | Restart the API from the same repo you used to build the dashboard. |
| Stream job completes with 0 rows | Empty `conn.log` or path points elsewhere | Confirm file grows during the window; use lab sim append or Zeek on an active interface. |

## Where to go next

- **Model lab** — paste JSON rows or upload a small file for instant triage.
- **Governance** — fusion policy hashes for reproducibility.
- **Full capture path** — real Zeek on your lab VLAN (see [`lab.md`](lab.md)).
- **PCAP replay** — [`ZEEK_REPLAY.md`](ZEEK_REPLAY.md) (`zeek -r` → `conn.log`).
- **Cron / scheduling** — [`SCHEDULING_STREAMS.md`](SCHEDULING_STREAMS.md).
