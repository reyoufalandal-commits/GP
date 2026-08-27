from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from hawk_eye import __version__
from hawk_eye.anomaly_ae import MLPAutoEncoder, pick_device
from hawk_eye.anomaly_bundle import save_anomaly_bundle
from hawk_eye.features import FeatureSpec, infer_feature_columns, split_xy
from hawk_eye.io import read_table


def _numeric_preprocessor(feature_columns: list[str]) -> ColumnTransformer:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(transformers=[("num", numeric, feature_columns)], remainder="drop")


def _numeric_X(df: pd.DataFrame, label_col: str, id_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    spec = FeatureSpec(feature_columns=[], label_column=label_col, id_columns=id_cols)
    X_df, _y = split_xy(df, spec)
    cols = infer_feature_columns(df, drop=[label_col, *id_cols])
    X_df = X_df[cols]
    X_df = X_df.select_dtypes(include=[np.number])
    return X_df, list(X_df.columns)


def train_iforest(
    *,
    X_train: pd.DataFrame,
    feature_columns: list[str],
    contamination: float,
) -> tuple[ColumnTransformer, IsolationForest]:
    pre = _numeric_preprocessor(feature_columns)
    Xt = pre.fit_transform(X_train)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    clf = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(Xt)
    return pre, clf


def train_ae(
    *,
    X_train: pd.DataFrame,
    feature_columns: list[str],
    epochs: int,
    batch_size: int,
    lr: float,
    hidden: tuple[int, ...],
    latent: int,
) -> tuple[ColumnTransformer, dict]:
    pre = _numeric_preprocessor(feature_columns)
    Xt = pre.fit_transform(X_train)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    X = np.asarray(Xt, dtype=np.float32)
    n_features = X.shape[1]
    dev = pick_device()
    net = MLPAutoEncoder(n_features, hidden=hidden, latent=latent).to(dev)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    ds = torch.utils.data.TensorDataset(torch.from_numpy(X))
    loader = torch.utils.data.DataLoader(ds, batch_size=batch_size, shuffle=True)
    loss_fn = nn.MSELoss()
    net.train()
    for _ in range(epochs):
        for (batch,) in loader:
            batch = batch.to(dev)
            opt.zero_grad()
            recon = net(batch)
            loss = loss_fn(recon, batch)
            loss.backward()
            opt.step()
    return pre, net.state_dict()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("iforest", "ae"), required=True)
    ap.add_argument("--benign-train", required=True, help="CSV/Parquet with benign rows only (+ Label col).")
    ap.add_argument("--benign-val", required=True, help="Benign-only validation for threshold tuning.")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--id-cols", default="", help="Comma-separated ID columns to drop.")
    ap.add_argument("--out", required=True, help="Output anomaly bundle directory.")
    ap.add_argument("--contamination", type=float, default=0.02, help="IF contamination (expected anomaly rate in train).")
    ap.add_argument("--percentile", type=float, default=99.0, help="Threshold = this percentile of benign-val scores (higher = stricter on FPR).")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--ae-hidden", default="64,32", help="AE hidden dims, comma-separated.")
    ap.add_argument("--ae-latent", type=int, default=16)
    args = ap.parse_args()

    id_cols = [c.strip() for c in args.id_cols.split(",") if c.strip()]
    df_tr = read_table(args.benign_train)
    df_val = read_table(args.benign_val)

    X_tr, feat_cols = _numeric_X(df_tr, args.label_col, id_cols)
    X_v, feat_cols2 = _numeric_X(df_val, args.label_col, id_cols)
    if feat_cols != feat_cols2:
        raise ValueError("Feature mismatch between train and val benign sets.")

    if args.mode == "iforest":
        pre, clf = train_iforest(
            X_train=X_tr,
            feature_columns=feat_cols,
            contamination=args.contamination,
        )
        Xt_val = pre.transform(X_v)
        if hasattr(Xt_val, "toarray"):
            Xt_val = Xt_val.toarray()
        scores = -clf.score_samples(Xt_val)
        thr = float(np.percentile(scores, args.percentile))
        cfg = {
            "model_type": "isolation_forest",
            "bundle_version": __version__,
            "threshold": thr,
            "score_direction": "higher_is_anomaly",
            "percentile": args.percentile,
            "contamination": args.contamination,
            "label_column": args.label_col,
        }
        save_anomaly_bundle(
            bundle_dir=args.out,
            preprocessor=pre,
            feature_columns=feat_cols,
            config=cfg,
            metadata={"n_benign_train": len(X_tr), "n_benign_val": len(X_v)},
            sklearn_model=clf,
        )
    else:
        hidden = tuple(int(x.strip()) for x in args.ae_hidden.split(",") if x.strip())
        pre, state = train_ae(
            X_train=X_tr,
            feature_columns=feat_cols,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            hidden=hidden,
            latent=args.ae_latent,
        )
        Xt_val = pre.transform(X_v)
        if hasattr(Xt_val, "toarray"):
            Xt_val = Xt_val.toarray()
        dev = pick_device()
        net = MLPAutoEncoder(Xt_val.shape[1], hidden=hidden, latent=args.ae_latent).to(dev)
        net.load_state_dict(state)
        net.eval()
        with torch.no_grad():
            t = torch.from_numpy(np.asarray(Xt_val, dtype=np.float32)).to(dev)
            err = net.reconstruction_error(t).cpu().numpy()
        thr = float(np.percentile(err, args.percentile))
        cfg = {
            "model_type": "autoencoder",
            "bundle_version": __version__,
            "threshold": thr,
            "score_direction": "higher_is_anomaly",
            "percentile": args.percentile,
            "ae_hidden": list(hidden),
            "ae_latent": args.ae_latent,
            "n_features": Xt_val.shape[1],
            "epochs": args.epochs,
            "label_column": args.label_col,
        }
        save_anomaly_bundle(
            bundle_dir=args.out,
            preprocessor=pre,
            feature_columns=feat_cols,
            config=cfg,
            metadata={"n_benign_train": len(X_tr), "n_benign_val": len(X_v)},
            ae_weights=state,
        )

    print(json.dumps({"bundle_dir": str(Path(args.out).resolve()), "threshold": thr}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
