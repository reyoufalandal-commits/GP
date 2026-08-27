from __future__ import annotations

import torch
import torch.nn as nn


class MLPAutoEncoder(nn.Module):
    def __init__(self, n_features: int, hidden: tuple[int, ...] = (64, 32), latent: int = 16):
        super().__init__()
        h = list(hidden)
        enc_layers: list[nn.Module] = []
        prev = n_features
        for dim in h:
            enc_layers.extend([nn.Linear(prev, dim), nn.ReLU()])
            prev = dim
        enc_layers.append(nn.Linear(prev, latent))
        self.encoder = nn.Sequential(*enc_layers)
        dec_layers: list[nn.Module] = []
        prev = latent
        for dim in reversed(h):
            dec_layers.extend([nn.Linear(prev, dim), nn.ReLU()])
            prev = dim
        dec_layers.append(nn.Linear(prev, n_features))
        self.decoder = nn.Sequential(*dec_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.encoder(x)
        return self.decoder(z)

    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        xhat = self.forward(x)
        return ((x - xhat) ** 2).mean(dim=1)


def pick_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")
