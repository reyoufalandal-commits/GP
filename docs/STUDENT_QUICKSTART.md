# Student quickstart (about 5 minutes)

Use this on a **lab machine or VM you control**. For the full lab narrative, see [STUDENT_LAB.md](STUDENT_LAB.md).

## 1. Install and bundles

```bash
cd Hawk-Eye
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/ci_build_minimal_bundles.py
```

This creates small **smoke bundles** under `artifacts/` so scoring works in class without training models.

## 2. Start API and dashboard

**Terminal A — API** (from repo root):

```bash
./scripts/run_api_8000.sh
```

**Terminal B — UI**:

```bash
cd dashboard/frontend && npm install && npm run dev
```

Open the URL Vite prints (often `http://127.0.0.1:5173`). If the browser cannot reach the API, check CORS: [OPERATOR_GUIDE_LOCAL.md](OPERATOR_GUIDE_LOCAL.md) and `scripts/run_api_8000.sh`.

## 3. Log in

Use the credentials your instructor gives you, or the default dev admin described in [SECURITY.md](SECURITY.md) for **local use only**.

## 4. Try scoring (Model lab)

Open **Model lab** (home). Paste a small JSON array of flow rows or upload a file, then run **Score** or **Triage** to see labels.

## 5. Try a live stream (optional)

**Easiest (no Zeek):** generate synthetic `conn.log`:

```bash
python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario mixed --lines 50
```

Then open **Live stream**, pick **1 min**, click **Start streaming**, wait until **completed**, read the verdict and table.

**Real capture:** on the **same machine as the API**, run Zeek (often needs `sudo`):

```bash
sudo ./scripts/zeek_network_capture.sh en0
```

Keep Zeek running for the whole stream window.

## 6. If something breaks

See the [Troubleshooting](STUDENT_LAB.md#troubleshooting) table in [STUDENT_LAB.md](STUDENT_LAB.md), or **Ops / health** in the dashboard.

**Instructors:** assign [STUDENT_LAB.md](STUDENT_LAB.md) for depth; point beginners here first.
