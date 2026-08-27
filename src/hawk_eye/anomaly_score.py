from __future__ import annotations

import numpy as np
import pandas as pd
import torch

from hawk_eye.anomaly_ae import MLPAutoEncoder, pick_device
from hawk_eye.anomaly_bundle import AnomalyBundle


def isolation_forest_scores(model: object, X: np.ndarray) -> np.ndarray:
    """Higher = more anomalous (negated sklearn score_samples)."""
    ss = model.score_samples(X)
    return -np.asarray(ss, dtype=np.float64)


def autoencoder_scores(
    bundle: AnomalyBundle,
    X: np.ndarray,
    *,
    input_dim: int,
    hidden: tuple[int, ...],
    latent: int,
) -> np.ndarray:
    dev = pick_device()
    net = MLPAutoEncoder(input_dim, hidden=hidden, latent=latent).to(dev)
    state = torch.load(bundle.ae_state_path, map_location=dev)
    net.load_state_dict(state)
    net.eval()
    xt = torch.from_numpy(X.astype(np.float32)).to(dev)
    with torch.no_grad():
        err = net.reconstruction_error(xt)
    return err.cpu().numpy()


def score_frame_anomaly(
    df: pd.DataFrame,
    bundle: AnomalyBundle,
) -> np.ndarray:
    # Allow Label / extra columns: only use feature_columns for scoring.
    X_df = df[bundle.feature_columns]
    Xt = bundle.preprocessor.transform(X_df)
    if not hasattr(Xt, "shape"):
        Xt = np.asarray(Xt)
    mt = bundle.config.get("model_type")
    if mt == "isolation_forest":
        assert bundle.model is not None
        return isolation_forest_scores(bundle.model, Xt)
    if mt == "autoencoder":
        hid = tuple(bundle.config.get("ae_hidden", [64, 32]))
        lat = int(bundle.config.get("ae_latent", 16))
        n_in = int(bundle.config.get("n_features", Xt.shape[1]))
        return autoencoder_scores(bundle, Xt, input_dim=n_in, hidden=hid, latent=lat)
    raise ValueError(f"Unknown model_type: {mt!r}")
