# Hawk-Eye — Project capability report

**Purpose:** Explain what this system is *for*, how it turns **live network traffic** into **attack vs benign**-style conclusions, and how to run it responsibly on a network you control.

This document complements the engineering handbook in [`README.md`](../README.md) and the student workflow in [`STUDENT_LAB.md`](STUDENT_LAB.md).

**Recommended lab sequence (short):** install bundles → start API and dashboard → point **Live stream** at a `conn.log` (Zeek live file or synthetic `data/lab/sim_conn.log`) → run a timed stream → read **risk_level** and decision counts → optionally generate the **incident report** (LLM or offline template). Details and scenario-based simulation are in [`STUDENT_LAB.md`](STUDENT_LAB.md).

---

## 1. Why this project exists

Enterprise and research teams need a **repeatable** way to:

1. **Observe** connections (flows) from the network, not guess from a single packet.
2. **Score** those flows with **trained models** (supervised + anomaly + fusion), under a **versioned bundle**.
3. **Summarize** whether the window looks **mostly normal** or contains **attack-like** or **uncertain** behavior worth review.

Hawk-Eye is **local-first**: the models and SQLite database stay on **your** machine or lab VM; you control data retention and access.

It is **not** a replacement for a commercial SOC platform, EDR, or IDS certification. It is a **transparent ML pipeline** with an API and dashboard for teaching, prototyping, and small-scale operations.

---

## 2. What “live stream on my network” actually means

| Step | What happens |
|------|----------------|
| **Capture** | **Zeek** (Bro) listens on a network interface you choose and writes **`conn.log`** (one line per connection, with bytes, duration, endpoints). |
| **Ingest** | The Hawk-Eye API reads that file on a **timer** for a **fixed window** (e.g. 10 minutes). It only reads what Zeek wrote; it does not replace Zeek. |
| **Feature mapping** | Zeek fields are mapped into the **feature contract** your bundle expects (see bundle `feature_columns.json`). |
| **Model scoring** | **Binary** (benign vs attack), **supervised multiclass** (attack family labels), and **benign-trained anomaly** scores run together. |
| **Fusion** | [`decision_fusion`](../src/hawk_eye/decision_fusion.py) produces **`decision_label`**: `BenignOrLowRisk`, `KnownAttack`, or `AttackUncertain`. |
| **Report** | The dashboard shows a plain-language **attack vs benign** summary, label counts, optional **known-attack family** breakdown, and sample rows. |

**“Scanning” clarification:** Hawk-Eye does not run port scans. Zeek **passively** observes traffic that **already crosses** the interface (e.g. your Wi‑Fi or lab tap). You must be **authorized** to monitor that network.

---

## 3. How to run live analysis on your current network (short checklist)

Only on networks and devices you **own or are explicitly allowed** to monitor.

1. **Install Zeek** on the same host as the API (e.g. `brew install zeek` on macOS).
2. **Pick the interface** carrying your traffic (e.g. `en0` on Mac; `ip link` / `networksetup` for names).
3. From the repo, run **`./scripts/zeek_network_capture.sh <iface>`** (often requires `sudo`). Zeek writes **`data/live/conn.log`**.
4. Start the API (`./scripts/run_api_8000.sh`) and the dashboard (`npm run dev` in `dashboard/frontend`).
5. Open **Live stream**, confirm the **readiness strip** shows a **default path** (or paste the absolute path to `conn.log`).
6. Choose a duration (start with **1 min**), click **Start streaming**, wait for completion.
7. Read **“Attack vs benign (this window)”** at the top of the report, then the technical counts and table.

If **zero rows** score, lengthen the window, verify Zeek is receiving traffic, and confirm the path matches the file Zeek is updating.

---

## 4. How to read “attack or not”

The UI and API expose:

- **`risk_level`:** `low` — no `KnownAttack` or `AttackUncertain` in the window; `elevated` — at least one such flow; `unknown` — nothing was scored.
- **`attack_indicators`:** `none` or `present` (aligned with fusion outputs).
- **`risk_headline` / `risk_plain_summary`:** Short, stakeholder-friendly text.
- **`decision_counts`:** Raw counts per `decision_label`.
- **`known_attack_types`:** When flows are `KnownAttack`, supervised **family** names (e.g. dataset labels) aggregated.

**Important:** A **`low`** window does not prove the network is “clean forever” — only that **this model configuration** did not raise attack-style labels for **scored flows in that time range**. False positives and false negatives exist; see [`MODEL_GOVERNANCE.md`](MODEL_GOVERNANCE.md).

---

## 5. Adding logs “to the model”

In this architecture, you do **not** retrain inside the live stream path. You:

- **Score** with **existing bundles** under `artifacts/` (binary, supervised, anomaly).
- **Retrain** offline using [`train.py` / `train_torch.py`](../README.md) when you have new labeled data.

To make live traffic more meaningful, train or calibrate bundles on data that matches your **feature pipeline** (Zeek-mapped or CICIDS-style, per your bundle contract).

---

## 6. Security, privacy, and ethics

- Capture only where **policy and law** allow.
- `conn.log` can reveal hosts, ports, and timing — treat it as **sensitive**.
- The **LLM incident report** is optional; do not paste classified data into third-party APIs without approval.

---

## 7. What to improve next (product direction)

- **Richer reports:** PDF export, SIEM webhook templates, scheduled windows.
- **Drift monitoring:** Compare live score distributions to training baselines (see governance docs).
- **Bundle quality:** Retrain on Zeek-aligned features for deployment scenarios that do not use CICIDS CSVs.

---

## 8. Document map

| Doc | Audience |
|-----|----------|
| [`README.md`](../README.md) | Engineers — full handbook |
| This report | Stakeholders, course leads, operators |
| [`STUDENT_LAB.md`](STUDENT_LAB.md) | Classroom lab steps |
| [`ENVIRONMENT.md`](ENVIRONMENT.md) | Env vars and defaults |
| [`MODEL_GOVERNANCE.md`](MODEL_GOVERNANCE.md) | ML accountability |

---

*Generated as a capability overview for Hawk-Eye; revise version strings and bundle names as your deployment evolves.*
