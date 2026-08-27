# Lab testing (authorized only)

Only test on systems and networks you own or are explicitly authorized to test.

## Network setup

- Use local VMs on an **isolated** network (host-only VLAN or cloud lab VPC).
- Capture with **tcpdump** / **Zeek** / **Suricata** as needed for your toolchain.

## Feature contract (Kaggle / CICIDS-trained models)

The supervised bundle lists required columns in **`feature_columns.json`** (e.g. under `artifacts/current/`). Every scored row must provide those **numeric** columns with the same meaning as in training (per-flow CICIDS-style statistics).

**Path A — Full parity (recommended for current models)**

1. Produce PCAP from the lab or read from a SPAN port.
2. Run **CICFlowMeter** (or another tool that exports **CICIDS-compatible** per-flow CSV) so column names align with `feature_columns.json` (rename columns in a small script if the tool uses different names).
3. Validate, then score:

   ```bash
   python3 scripts/validate_feature_schema.py --input flows.csv --model-dir artifacts/current
   python3 -m hawk_eye.score --input flows.csv --output scored.parquet --model-dir artifacts/current \
     --predictions --proba-all
   ```

**Path B — Zeek only**

[`scripts/convert_zeek_conn.py`](../scripts/convert_zeek_conn.py) maps `conn.log` to a **small** feature set. It does **not** reproduce all CICIDS columns used by the default Kaggle-trained model. To use Zeek-only features you must **retrain** on data built the same way (`train.py` / `train_torch.py` with that schema).

## Ground truth in the lab

If you label runs (e.g. scripted attack vs benign), add a `Label` column and use [`hawk_eye.evaluate`](../src/hawk_eye/evaluate.py) for metrics. Extra columns like `Label` are ignored by `score` for alignment.

## See also

- [`docs/evaluation.md`](evaluation.md) — fair comparison between training runs.
- [`docs/runbook.md`](runbook.md) — bundle paths and env vars.
