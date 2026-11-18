"""Cross-reference against the published dataset facts (Weber et al. 2019, section 2.1).
Runs only when the real Elliptic CSVs are present in data/elliptic/."""
from pathlib import Path

import pytest

from gffs.elliptic import PUBLISHED_FACTS, compute_facts, load

DATA = Path(__file__).resolve().parents[1] / "data" / "elliptic"
pytestmark = pytest.mark.skipif(not (DATA / "elliptic_txs_features.csv").exists(), reason="Elliptic data not downloaded")


def test_real_data_matches_published_facts():
    facts = compute_facts(load(DATA))
    for k, v in PUBLISHED_FACTS.items():
        assert facts[k] == v, k
    assert facts["n_unknown"] == 203_769 - 4_545 - 42_019
