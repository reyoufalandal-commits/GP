from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import LabelEncoder

from hawk_eye.anomaly_ae import pick_device


class TabularMLP(nn.Module):
    """Feedforward classifier for preprocessed numeric tabular features."""

    def __init__(
        self,
        n_features: int,
        n_classes: int,
        hidden: tuple[int, ...] = (256, 128),
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        layers: list[nn.Module] = []
        prev = n_features
        for dim in hidden:
            layers.extend(
                [
                    nn.Linear(prev, dim),
                    nn.BatchNorm1d(dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
            )
            prev = dim
        layers.append(nn.Linear(prev, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class TorchTabularClassifier:
    """
    Sklearn-compatible multiclass wrapper: predict / predict_proba / classes_.
    Loads weights on first use; inference defaults to CPU for bundle portability.
    """

    def __init__(
        self,
        *,
        state_dict: dict[str, torch.Tensor],
        label_encoder: LabelEncoder,
        n_features: int,
        hidden: tuple[int, ...],
        dropout: float,
        inference_device: str = "cpu",
    ) -> None:
        self._state_dict = {k: v.cpu().clone() for k, v in state_dict.items()}
        self._label_encoder = label_encoder
        self.classes_ = np.asarray(label_encoder.classes_)
        self._n_features = n_features
        self._hidden = hidden
        self._dropout = dropout
        self._n_classes = len(self.classes_)
        self._inference_device = torch.device(inference_device)
        self._net: TabularMLP | None = None

    def _model(self) -> TabularMLP:
        if self._net is None:
            net = TabularMLP(
                self._n_features,
                self._n_classes,
                hidden=self._hidden,
                dropout=self._dropout,
            )
            net.load_state_dict(self._state_dict)
            net.to(self._inference_device)
            net.eval()
            self._net = net
        return self._net

    def predict_proba(self, X: np.ndarray, *, batch_size: int = 8192) -> np.ndarray:
        net = self._model()
        x = np.asarray(X, dtype=np.float32)
        n = x.shape[0]
        outs: list[np.ndarray] = []
        for i in range(0, n, batch_size):
            chunk = torch.from_numpy(x[i : i + batch_size]).to(self._inference_device)
            with torch.no_grad():
                logits = net(chunk)
                outs.append(torch.softmax(logits, dim=1).cpu().numpy())
        return np.concatenate(outs, axis=0) if outs else np.zeros((0, self._n_classes), dtype=np.float64)

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        idx = np.argmax(proba, axis=1)
        return self.classes_[idx]


def state_dict_cpu(module: nn.Module) -> dict[str, torch.Tensor]:
    return {k: v.detach().cpu().clone() for k, v in module.state_dict().items()}
