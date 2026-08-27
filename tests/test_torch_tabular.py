from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import LabelEncoder

from hawk_eye.bundle import load as load_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.preprocessing_supervised import build_numeric_preprocessor
from hawk_eye.torch_tabular import TabularMLP, TorchTabularClassifier, state_dict_cpu


def test_torch_tabular_predict_proba_matches_forward() -> None:
    torch.manual_seed(0)
    np.random.seed(0)
    n = 50
    n_features = 8
    n_classes = 3
    hidden = (16, 8)
    net = TabularMLP(n_features, n_classes, hidden=hidden, dropout=0.0)
    X = torch.randn(n, n_features)
    le = LabelEncoder()
    labels = np.array(["a", "b", "c"])[np.random.randint(0, 3, size=n)]
    le.fit(labels)

    sd = state_dict_cpu(net)
    clf = TorchTabularClassifier(
        state_dict=sd,
        label_encoder=le,
        n_features=n_features,
        hidden=hidden,
        dropout=0.0,
    )
    proba = clf.predict_proba(X.numpy(), batch_size=10)
    net.eval()
    with torch.no_grad():
        ref = torch.softmax(net(X), dim=1).numpy()
    np.testing.assert_allclose(proba, ref, rtol=1e-5, atol=1e-5)

    pred = clf.predict(X.numpy())
    assert pred.shape == (n,)
    assert np.array_equal(pred, le.classes_[np.argmax(proba, axis=1)])


def test_torch_tabular_bundle_save_load_predict(tmp_path) -> None:
    torch.manual_seed(1)
    cols = [f"f{i}" for i in range(5)]
    pre = build_numeric_preprocessor(cols)
    df_fit = pd.DataFrame(np.random.randn(30, 5), columns=cols)
    pre.fit(df_fit)

    n_features = 5
    n_classes = 2
    net = TabularMLP(n_features, n_classes, hidden=(8,), dropout=0.0)
    le = LabelEncoder()
    le.fit(np.array(["benign", "attack"]))
    clf = TorchTabularClassifier(
        state_dict=state_dict_cpu(net),
        label_encoder=le,
        n_features=n_features,
        hidden=(8,),
        dropout=0.0,
    )
    bundle_dir = tmp_path / "torch-bundle"
    save_bundle(
        bundle_dir=bundle_dir,
        model=clf,
        preprocessor=pre,
        feature_columns=cols,
        config={"bundle_version": "test-torch"},
        metadata={},
    )
    bundle = load_bundle(bundle_dir)
    X = pd.DataFrame(np.random.randn(8, 5), columns=cols)
    Xt = bundle.preprocessor.transform(X)
    pred = bundle.model.predict(Xt)
    proba = bundle.model.predict_proba(Xt)
    assert len(pred) == 8
    assert proba.shape == (8, 2)
