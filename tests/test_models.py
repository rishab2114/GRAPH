import numpy as np
import pandas as pd
import pytest

from gffs.features import FEATURES
from gffs.models import MODELS, fit_model


@pytest.fixture
def xy():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((300, len(FEATURES))), columns=FEATURES)
    y = (X["weighted_cn"] + 0.1 * rng.random(300) > 0.6).astype(int).to_numpy()
    return X, y


@pytest.mark.parametrize("name", sorted(MODELS))
def test_every_model_scores_every_row(name, xy):
    X, y = xy
    s = fit_model(name, X, y)(X)
    assert s.shape == (300,) and np.isfinite(s).all()


def test_best_single_picks_feature_with_best_training_auc(xy):
    X, y = xy
    scorer = fit_model("train_best_single", X, y)
    assert np.array_equal(scorer(X), X["weighted_cn"].to_numpy())


def test_popularity_model_ignores_structure(xy):
    X, y = xy
    X2 = X.copy(); X2["weighted_cn"] = 0.0; X2["jaccard"] = 0.0
    scorer = fit_model("logreg_popularity", X, y)
    assert np.allclose(scorer(X), scorer(X2))
