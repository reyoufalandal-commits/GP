# Dataset (pinned)

## Local Parquet in `kaggleData/`

If you downloaded **no-metadata** Parquet splits into the project folder `kaggleData/` (e.g. `Benign-Monday-no-metadata.parquet`, `Botnet-Friday-no-metadata.parquet`), train with:

```bash
source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
./scripts/pipeline_kaggle_data.sh
```

Set `MAX_ROWS` (e.g. `MAX_ROWS=800000`) to control how many rows are read across files (memory-friendly). Requires **`pyarrow`** (listed in `requirements.txt`).

---

**Pinned Kaggle slug (reference):** `dhoogla/cicids2017`  
([CIC-IDS2017 on Kaggle](https://www.kaggle.com/datasets/dhoogla/cicids2017))

- **Download:** `./scripts/download_data.sh dhoogla/cicids2017`
- **Raw directory:** `data/raw/dhoogla__cicids2017/` (slashes in the slug become `__` in the folder name)

## Full pipeline (after Kaggle API token)

1. Place `kaggle.json` at `~/.kaggle/kaggle.json` and run `chmod 600 ~/.kaggle/kaggle.json`.
2. From repo root:

```bash
./scripts/run_cicids_pipeline.sh
```

Optional environment variables:

- `KAGGLE_SLUG` — override dataset (default `dhoogla/cicids2017`)
- `MAX_ROWS` — cap rows for faster runs (default `200000`; set empty or very large for full data if memory allows)
- `LABEL_COL` — label column name (default `Label`)

## After download

Record approximate size and `shasum -a 256` of main CSVs in this file for reproducibility.
