from gffs.tornado_pilot_summary import leaf_gaps


def test_leaf_gaps_finds_missing_deposit_indices_per_pool():
    deps = [{"pool": "p", "leaf_index": i} for i in (5, 6, 7, 9)] + [{"pool": "q", "leaf_index": i} for i in (0, 1)]
    g = leaf_gaps(deps)
    assert g == {"p": {"first": 5, "last": 9, "count": 4, "missing": 1, "duplicates": 0},
                 "q": {"first": 0, "last": 1, "count": 2, "missing": 0, "duplicates": 0}}
