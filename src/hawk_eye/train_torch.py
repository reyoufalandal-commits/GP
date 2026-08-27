from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, TensorDataset

from hawk_eye import __version__
from hawk_eye.anomaly_ae import pick_device
from hawk_eye.bundle import save as save_bundle
from hawk_eye.features import FeatureSpec, infer_feature_columns, split_xy
from hawk_eye.io import read_table
from hawk_eye.preprocessing_supervised import build_numeric_preprocessor
from hawk_eye.torch_tabular import TabularMLP, TorchTabularClassifier, state_dict_cpu


def _parse_hidden(s: str) -> tuple[int, ...]:
    parts = [x.strip() for x in s.split(",") if x.strip()]
    return tuple(int(x) for x in parts)


def _load_xy(
    path: str | Path,
    *,
    label_col: str,
    id_cols: list[str],
) -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    df = read_table(path)
    spec = FeatureSpec(feature_columns=[], label_column=label_col, id_columns=id_cols)
    X_df, y = split_xy(df, spec)
    feature_columns = infer_feature_columns(df, drop=[label_col, *id_cols])
    X_df = X_df[feature_columns]
    X_df = X_df.select_dtypes(include=[np.number])
    numeric_columns = list(X_df.columns)
    if not numeric_columns:
        raise ValueError(
            "No numeric feature columns after dropping label/IDs. "
            "Check column names and dtypes in your CSV."
        )
    return X_df, y, numeric_columns


def _load_val_xy(
    path: str | Path,
    *,
    label_col: str,
    id_cols: list[str],
    numeric_columns: list[str],
) -> tuple[pd.DataFrame, np.ndarray]:
    df = read_table(path)
    spec = FeatureSpec(feature_columns=[], label_column=label_col, id_columns=id_cols)
    X_df, y = split_xy(df, spec)
    missing = [c for c in numeric_columns if c not in X_df.columns]
    if missing:
        raise ValueError(f"Validation data missing columns: {missing}")
    X_df = X_df[numeric_columns].select_dtypes(include=[np.number])
    if list(X_df.columns) != numeric_columns:
        raise ValueError("Validation numeric columns differ from training (dtype/order).")
    return X_df, y


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Training CSV/Parquet with features + label.")
    ap.add_argument("--label-col", default="label", help="Label column name.")
    ap.add_argument("--id-cols", default="", help="Comma-separated ID columns to drop.")
    ap.add_argument("--out", required=True, help="Output bundle directory.")
    ap.add_argument("--dataset-slug", default="", help="Optional dataset slug for metadata.")
    ap.add_argument("--val-data", default="", help="Optional validation set for early stopping.")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", default="256,128", help="Comma-separated hidden layer sizes.")
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument(
        "--class-weight",
        choices=("balanced", "none"),
        default="balanced",
        help="Inverse-frequency weights for CrossEntropyLoss.",
    )
    ap.add_argument("--early-stopping-patience", type=int, default=0, help="0 = disabled.")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    id_cols = [c.strip() for c in args.id_cols.split(",") if c.strip()]
    X_df, y, numeric_columns = _load_xy(args.data, label_col=args.label_col, id_cols=id_cols)
    feature_columns = numeric_columns

    pre = build_numeric_preprocessor(numeric_columns)
    Xt = pre.fit_transform(X_df)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    X = np.asarray(Xt, dtype=np.float32)

    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    n_classes = len(le.classes_)
    n_features = X.shape[1]

    hidden = _parse_hidden(args.hidden)
    dev = pick_device()
    net = TabularMLP(n_features, n_classes, hidden=hidden, dropout=args.dropout).to(dev)

    if args.class_weight == "balanced":
        cw = compute_class_weight("balanced", classes=np.arange(n_classes), y=y_enc)
        weight = torch.tensor(cw, dtype=torch.float32, device=dev)
    else:
        weight = None

    opt = torch.optim.AdamW(net.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss(weight=weight)

    ds = TensorDataset(torch.from_numpy(X), torch.from_numpy(y_enc.astype(np.int64)))
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, drop_last=False)

    val_loader: DataLoader | None = None
    if args.val_data:
        Xv_df, yv = _load_val_xy(
            args.val_data,
            label_col=args.label_col,
            id_cols=id_cols,
            numeric_columns=numeric_columns,
        )
        Xvt = pre.transform(Xv_df)
        if hasattr(Xvt, "toarray"):
            Xvt = Xvt.toarray()
        Xv = np.asarray(Xvt, dtype=np.float32)
        yv_enc = le.transform(yv)
        vds = TensorDataset(
            torch.from_numpy(Xv),
            torch.from_numpy(yv_enc.astype(np.int64)),
        )
        val_loader = DataLoader(vds, batch_size=args.batch_size, shuffle=False)

    best_state: dict[str, torch.Tensor] | None = None
    best_val_loss = float("inf")
    patience_left = args.early_stopping_patience

    for epoch in range(args.epochs):
        net.train()
        for xb, yb in loader:
            xb = xb.to(dev)
            yb = yb.to(dev)
            opt.zero_grad()
            logits = net(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()

        if val_loader is not None:
            net.eval()
            total = 0.0
            n_seen = 0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb = xb.to(dev)
                    yb = yb.to(dev)
                    logits = net(xb)
                    loss = loss_fn(logits, yb)
                    total += float(loss.item()) * xb.shape[0]
                    n_seen += xb.shape[0]
            val_loss = total / max(n_seen, 1)
            if val_loss < best_val_loss - 1e-6:
                best_val_loss = val_loss
                best_state = state_dict_cpu(net)
                patience_left = args.early_stopping_patience
            elif args.early_stopping_patience > 0:
                patience_left -= 1
                if patience_left <= 0:
                    break

    final_state = best_state if (val_loader is not None and best_state is not None) else state_dict_cpu(net)

    model = TorchTabularClassifier(
        state_dict=final_state,
        label_encoder=le,
        n_features=n_features,
        hidden=hidden,
        dropout=args.dropout,
        inference_device="cpu",
    )

    out_dir = Path(args.out)
    cfg = {
        "bundle_version": __version__,
        "model_type": "torch_mlp",
        "label_column": args.label_col,
        "id_columns": id_cols,
        "dataset_slug": args.dataset_slug,
        "classes": list(le.classes_),
        "hidden": list(hidden),
        "dropout": args.dropout,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "class_weight": args.class_weight,
        "early_stopping_patience": args.early_stopping_patience,
        "seed": args.seed,
    }
    metadata = {
        "n_rows": int(X_df.shape[0]),
        "n_features": n_features,
    }

    save_bundle(
        bundle_dir=out_dir,
        model=model,
        preprocessor=pre,
        feature_columns=feature_columns,
        config=cfg,
        metadata=metadata,
    )

    print(json.dumps({"bundle_dir": str(out_dir.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
