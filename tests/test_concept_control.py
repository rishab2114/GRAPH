import networkx as nx
import numpy as np
import pandas as pd
import pytest

from gffs.concept_control import (adjacency_at, day_of_year_end, pair_labels, sample_unconnected,
                                  sparse_pair_features)
from gffs.features import FEATURES, pair_features


@pytest.fixture
def edges():
    # one row per (concept pair, paper); time = days since 1990-01-01
    d16, d19 = day_of_year_end(2016), day_of_year_end(2019)
    rows = [(0, 1, d16), (0, 1, d16), (1, 2, d16), (0, 3, d16), (3, 2, d16), (2, 4, d16), (5, 6, d16),
            (0, 2, d19), (4, 5, d19)]
    return pd.DataFrame(rows, columns=["v1", "v2", "time"])


def test_day_of_year_end():
    assert day_of_year_end(1990) == 364 and day_of_year_end(2016) == 9861


def test_adjacency_counts_papers_and_cuts_by_time(edges):
    A = adjacency_at(edges, day_of_year_end(2016), n=7)
    assert A[0, 1] == 2 and A[1, 0] == 2 and A[0, 2] == 0
    assert adjacency_at(edges, day_of_year_end(2019), n=7)[0, 2] == 1


def test_sparse_features_match_networkx_features(edges):
    A = adjacency_at(edges, day_of_year_end(2016), n=7)
    g = nx.Graph()
    for u, v in zip(*A.nonzero()):
        if u < v:
            g.add_edge(str(u), str(v), weight=float(A[u, v]))
    for n in g:
        g.nodes[n]["freq"] = float(A[int(n)].sum())   # popularity = paper-weighted degree
    pairs = [(0, 2), (1, 3), (0, 4), (1, 4)]
    ours = sparse_pair_features(A, np.array([p[0] for p in pairs]), np.array([p[1] for p in pairs]))
    ref = pair_features(g, [(str(u), str(v)) for u, v in pairs])
    assert list(ours.columns) == FEATURES
    np.testing.assert_allclose(ours.to_numpy(), ref.to_numpy(), rtol=1e-9)


def test_sample_unconnected_only_returns_unlinked_canonical_pairs(edges):
    A = adjacency_at(edges, day_of_year_end(2016), n=7)
    u, v = sample_unconnected(A, 10, np.random.default_rng(0))
    assert (u < v).all() and len(u) == len(set(zip(u, v)))
    assert all(A[a, b] == 0 for a, b in zip(u, v))


def test_pair_labels(edges):
    A16, A19 = adjacency_at(edges, day_of_year_end(2016), n=7), adjacency_at(edges, day_of_year_end(2019), n=7)
    assert pair_labels(A19, np.array([0, 1, 4]), np.array([2, 3, 5])).tolist() == [1, 0, 1]


def test_sample_unconnected_rejects_impossible_request(edges):
    A = adjacency_at(edges, day_of_year_end(2016), n=7)   # 7 nodes, 6 links -> 15 unlinked pairs
    with pytest.raises(ValueError, match="only 15 unlinked pairs"):
        sample_unconnected(A, 16, np.random.default_rng(0))


def test_streamed_parquet_adjacency_matches_in_memory(edges, tmp_path):
    from gffs.concept_control import adjacencies_from_parquet
    path = tmp_path / "g.parquet"
    edges.assign(ct=0).to_parquet(path, row_group_size=4)   # several row groups
    years = [2016, 2019]
    got = adjacencies_from_parquet(path, years, n=7)
    for y in years:
        want = adjacency_at(edges, day_of_year_end(y), n=7)
        assert (got[y] != want).nnz == 0


def test_run_control_reports_methods(tmp_path):
    from gffs.concept_control import run_control
    from gffs.models import MODELS
    rng = np.random.default_rng(1)
    n = 80
    # growing graph with triadic closure, so later links are partly predictable
    links = {(i, i + 1) for i in range(n - 1)}
    adj = {}
    for year in (2016, 2019, 2022):
        for _ in range(60):
            a = int(rng.integers(n)); nb = [y for x, y in links if x == a] + [x for x, y in links if y == a]
            if nb:
                b = int(rng.choice(nb)); nb2 = [y for x, y in links if x == b] + [x for x, y in links if y == b]
                c = int(rng.choice(nb2))
                if c != a:
                    links.add((min(a, c), max(a, c)))
        rows = pd.DataFrame(sorted(links), columns=["v1", "v2"]).assign(time=day_of_year_end(year))
        adj[year] = adjacency_at(rows, day_of_year_end(year), n)
    r = run_control(adj, train=(2016, 2019), test=(2019, 2022), n_pairs=400, n_boot=20, seed=0)
    assert set(r["methods"]) == set(MODELS) | {"frequency", "random"}
    assert r["graph"]["test_positive"] > 0 and 0 < r["graph"]["density_t"] < 1
