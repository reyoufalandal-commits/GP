# Binary classification: Benign vs Attack

Train a **two-class** model: everything that matches `--benign-label` (repeatable, case-insensitive) becomes **`Benign`**; all other labels become **`Attack`**.

## Train

```bash
python3 -m hawk_eye.train \
  --data data/processed/train.csv \
  --label-col Label \
  --out artifacts/hawk-eye-binary \
  --binary-benign-vs-attack \
  --benign-label Benign \
  --model-type hist_gradient_boosting \
  --logistic-balanced \
  --calibration-data data/processed/val.csv \
  --calibration-method sigmoid
```

For CIC-style data, `--benign-label Benign` is enough (defaults also include `benign`, `BENIGN` if you omit repeats).

`config.json` will include `"binary_benign_vs_attack": true`.

## Score

`hawk_eye.score` sets **`score`** and **`p_attack`** to the predicted probability of **`Attack`** (not column index 1 by accident).

## Evaluate

Use `hawk_eye.evaluate` with **binary** ground truth: map your validation `Label` the same way in a small script, or export a CSV with a column that is only `Benign` / `Attack` and `--label-col` pointing to it.

## Arabic (ملخص)

- **التدريب ثنائي:** `--binary-benign-vs-attack` + تحديد التصنيفات البريئة بـ `--benign-label`.
- **التقييم:** قارن التوقعات مع أعمدة أرضية ثنائية (Benign/Attack) بعد نفس القاعدة.
- **ليس zero-day حقيقي:** هذا يميّز هجومًا عن بريء؛ كشف “غير معروف” يبقى مع `detect_novel` + أنومالي.
