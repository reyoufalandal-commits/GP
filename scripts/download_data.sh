#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <owner/slug>"
  echo "Example: $0 someuser/cicids2017"
  exit 2
fi

SLUG="$1"
RAW_DIR="data/raw/${SLUG//\//__}"

if [[ ! -f "${HOME}/.kaggle/kaggle.json" ]]; then
  echo "Missing Kaggle token at ~/.kaggle/kaggle.json"
  echo "Create it via Kaggle Account -> API -> Create New API Token."
  exit 2
fi

mkdir -p "${RAW_DIR}"

python3 -m kaggle datasets download -d "${SLUG}" -p "${RAW_DIR}"

shopt -s nullglob
ZIP_FILES=("${RAW_DIR}"/*.zip)
if [[ ${#ZIP_FILES[@]} -eq 0 ]]; then
  echo "No .zip files found in ${RAW_DIR}. Download may have produced CSV directly."
  exit 0
fi

for z in "${ZIP_FILES[@]}"; do
  unzip -o "${z}" -d "${RAW_DIR}"
done

echo "Downloaded to ${RAW_DIR}"
