# Lab synthetic `conn.log` profiles — test traffic without real attacks

Hawk-Eye’s lab simulator (`scripts/lab_simulate_conn_log.py`) writes **fake Zeek-style** `conn.log` lines for **authorized classroom or VM labs** only. It does **not** launch exploits or scans on the network; it only appends **tab-separated rows** so ML scoring has varied shapes to work on.

Use this doc to understand **what each profile is meant to mimic** and what you might see in the dashboard (**labels depend on your bundles and thresholds** — minimal CI bundles may not match textbook attack names).

## Quick run — many patterns in one file

From the repo root (overwrites `data/lab/sim_conn.log`; use `--append` to add more later):

```bash
python3 scripts/lab_simulate_conn_log.py \
  --scenario-file lab_scenarios/classroom_full_menu.json \
  --out data/lab/sim_conn.log \
  --seed 42
```

Then start a **Live stream** in the dashboard against that path (or rely on the default lab path if configured). For continuous generation while a stream runs:

```bash
python3 scripts/lab_simulate_conn_log.py \
  --scenario-file lab_scenarios/classroom_full_menu.json \
  --daemon --append --out data/lab/sim_conn.log
```

## Profile reference (synthetic behavior → teaching story)

| Profile | What the rows look like (synthetic) | Teaching narrative (not a guarantee of model labels) |
|--------|--------------------------------------|------------------------------------------------------|
| **steady_baseline** / **benign_web** | HTTPS-like TCP: moderate duration, balanced bytes/packets, port 443 | **Normal user browsing** — baseline “no attack” traffic for comparison. |
| **benign** (legacy CLI preset) | Same family as benign web-style rows | Short runs: `--scenario benign --lines N`. |
| **dns_like_udp** | UDP to port 53, small payloads | **DNS-like chatter** — common background; useful to see benign vs scan-like mix. |
| **heavy** / **heavy_transfer** | Very large byte counts and packet counts, short duration | **High-volume transfer** — can resemble bulk exfil or flood-like *statistics* (still synthetic). |
| **scan** / **vertical_scan** | Very short TCP sessions, tiny bytes, **destination port walks** over many ports | **Port-scan-like pattern** in flow features — many connections, different `id.resp_p`. |
| **horizontal_scan** | Short TCP to **port 80**, many **different source IPs** (synthesized in `id.orig_h`) | **Many clients / sweep narrative** — different shape from vertical_scan (lab pedagogy only). |
| **beacon_like** | Similar-sized flows on **443** on a steady rhythm | **Periodic callback** story for class discussion (not a real C2). |
| **noisy_then_scan** | Cycles: mostly benign_web-like, then vertical_scan slices | **Quiet then noisy** — mimics a shift from background to scan-like traffic in one phase. |
| **mixed** (legacy) | Rotates among a few built-in shapes | Simple **kitchen-sink** batch without a JSON file. |
| **mixed_attack_mix** | Cycles through several profiles each line | **Many attack-like shapes in one phase** — good for dense classroom demos. |

## “Normal only” runs

- **Steady normal traffic:** `lab_scenarios/steady_baseline.json` or a phase with only `steady_baseline` / `benign_web`.
- **Legacy one-liner:**  
  `python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario benign --lines 100`

## Interpreting the dashboard

- **Fusion** uses labels like `BenignOrLowRisk`, `KnownAttack`, `AttackUncertain` — see [PROJECT_CAPABILITY_REPORT.md](PROJECT_CAPABILITY_REPORT.md).
- **Supervised family names** (e.g. `PortScan`) appear only if your bundle was trained with those classes and the flow scores as `KnownAttack` with that prediction — see the dashboard help text on **Known attack types**.

## Safety

Synthetic data only; use only on systems and networks you are allowed to test. See also [STUDENT_LAB.md](STUDENT_LAB.md).
