from datetime import date

import numpy as np
import pytest

from gffs.tornado_study import (ApprovalRequired, block_recall_draws, infrastructure, labels_for_task, participation,
                                require_approval)

H = [{"day": "2022-01-05", "tornado_txs": [{"sender": "u1", "to": "0xpool"}],
      "deposits": [{"depositor": "d1", "pool": "p", "tx": "1"}],
      "withdrawals": [{"recipient": "r1", "fee_payee": "rel1", "tx_sender": "rel1", "payees": ["r1", "rel1"], "ambiguous": False},
                      {"recipient": None, "fee_payee": None, "tx_sender": "w9", "payees": ["q1", "q2", "q3"], "ambiguous": True}]},
     {"day": "2022-03-01", "tornado_txs": [], "deposits": [{"depositor": "d2", "pool": "p", "tx": "2"},
                                                            {"depositor": "d1", "pool": "p", "tx": "3"}],
      "withdrawals": [{"recipient": "r2", "fee_payee": "rel2", "tx_sender": "wrk", "payees": ["r2", "rel2"], "ambiguous": False}]}]


def test_participation_and_infrastructure_use_only_days_before_t():
    prior, rel, senders = participation(H, date(2022, 2, 1))
    assert {"u1", "d1", "r1", "rel1", "q1", "q2", "q3"} <= prior and "d2" not in prior
    assert rel == {"rel1"} and senders == {"rel1", "w9"}
    inf = infrastructure(date(2022, 2, 1), {"0xpool": "2019-12-16", "0xlate": "2022-05-01"}, rel, senders)
    assert "0xpool" in inf and "0xlate" not in inf and "rel1" in inf


def test_labels_are_first_deposits_in_horizon_by_eligible_addresses_with_week_index():
    eligible = {"d2", "d1", "x"}
    pos = labels_for_task(H, eligible, t=date(2022, 2, 21), weeks=8)
    assert pos == {"d2": 1}                      # d1 deposited before t (and is not eligible anyway in practice)


def test_gate_refuses_post_cutoff_reads_without_an_approval_file(tmp_path):
    with pytest.raises(ApprovalRequired):
        require_approval(date(2022, 8, 9), approval_file=tmp_path / "missing.md")
    require_approval(date(2022, 8, 7), approval_file=tmp_path / "missing.md")     # pre-cutoff: allowed


def test_block_draws_resample_whole_weeks():
    import itertools
    weeks = np.array([0, 0, 1, 1, 1, 2]); flags = np.array([[1], [1], [0], [0], [0], [1]], dtype=float)
    hits, size = {0: 2, 1: 0, 2: 1}, {0: 2, 1: 3, 2: 1}
    possible = {round(sum(hits[w] for w in c) / sum(size[w] for w in c), 9)
                for c in itertools.combinations_with_replacement(range(3), 3)}
    d = block_recall_draws(flags, weeks, n_weeks=3, draws=300, rng=np.random.default_rng(0))
    got = set(np.round(d[:, 0], 9))
    assert d.shape == (300, 1) and got <= possible and len(got) > 3     # only whole-week mixtures, and they vary
    node_level = {round(k / 6, 9) for k in range(7)}
    assert got - node_level, "draws should include values impossible under node-level resampling of 6 nodes"


def test_evaluate_reports_block_primary_iid_secondary_baselines_and_paired_contrasts():
    from gffs.tornado_study import evaluate
    rng = np.random.default_rng(0); D = 10
    r_h = np.linspace(0.05, 0.5, D)
    H = (rng.random((400, D)) < r_h).astype(float); hw = rng.integers(0, 8, 400)
    S0 = (rng.random((600, D)) < r_h + 0.15).astype(float); s0w = rng.integers(0, 8, 600)
    syn = {s: ((rng.random((900, D)) < r_h + 0.02).astype(float), np.repeat(np.arange(300), 3)) for s in ("S1", "S2", "S3")}
    r = evaluate([f"d{i}" for i in range(D)], S0, s0w, syn, H, hw, boots=200)
    c = r["contrasts"]["SYN-S0"]
    assert c["e4_diff"] < 0 and c["ci_block"][1] < 0 and "ci_iid" in c
    assert r["metrics"]["B_shrink"]["e4"] > r["metrics"]["SYN"]["e4"]
    assert set(r["metrics"]) >= {"S0", "S1", "S2", "S3", "SYN", "B_const", "B_shrink", "B_zero"}


def test_event_minus_placebo_contrast():
    from gffs.tornado_study import shift_contrast
    d = shift_contrast(np.full(100, -0.05), np.full(100, 0.01), np.full(100, 0.03))
    assert abs(d["D"] - (-0.07)) < 1e-12 and d["ci"][1] < 0


def test_compact_history_reproduces_participation_and_labels_exactly():
    from gffs.tornado_study import compact_history, labels_compact, participation_compact
    ch = compact_history(H)
    for t in (date(2022, 1, 1), date(2022, 2, 1), date(2022, 3, 2)):
        assert participation_compact(ch, t) == participation(H, t)
    eligible = {"d2", "d1", "x"}
    assert labels_compact(ch, eligible, date(2022, 2, 21), 8) == labels_for_task(H, eligible, date(2022, 2, 21), 8)


def test_hash_keyed_sample_is_deterministic_uniform_and_streamable():
    from gffs.tornado_study import sample_keys, smallest_keys
    a = [f"0x{i:040x}" for i in range(5000)]
    k1, k2 = sample_keys(a, "2022-01-01"), sample_keys(a, "2022-01-01")
    assert (k1 == k2).all() and not (k1 == sample_keys(a, "2022-02-01")).all()
    # streaming top-k over two halves equals top-k over the whole
    whole = set(smallest_keys(a, k1, 100))
    part = smallest_keys(a[:2500], k1[:2500], 100) + smallest_keys(a[2500:], k1[2500:], 100)
    pk = dict(zip(a, k1))
    assert set(sorted(part, key=lambda x: pk[x])[:100]) == whole


def test_module_entry_point_is_last_so_every_function_exists_when_run_as_a_script():
    # The rehearsal crashed with NameError: the __main__ block sat above later definitions (2026-11-26).
    import ast, inspect
    import gffs.tornado_study as m
    tree = ast.parse(inspect.getsource(m))
    last = tree.body[-1]
    assert isinstance(last, ast.If) and "__main__" in ast.unparse(last.test)


def test_evaluate_handles_instance_ids_numbered_across_sets():
    # Real runs number instances across sets (S2 starts at 2000): ids are not positions (rehearsal IndexError, 2026-11-26).
    from gffs.tornado_study import evaluate
    rng = np.random.default_rng(1); D = 4
    r_h = np.linspace(0.1, 0.4, D)
    H = (rng.random((200, D)) < r_h).astype(float); hw = rng.integers(0, 8, 200)
    S0 = (rng.random((300, D)) < r_h).astype(float); s0w = rng.integers(0, 8, 300)
    syn = {s: ((rng.random((600, D)) < r_h).astype(float), np.repeat(np.arange(200) + off, 3))
           for s, off in (("S1", 0), ("S2", 2000), ("S3", 5000))}
    r = evaluate([f"d{i}" for i in range(D)], S0, s0w, syn, H, hw, boots=50)
    assert np.isfinite(r["contrasts"]["SYN-S0"]["ci_block"]).all()


def test_post_cutoff_history_build_refuses_without_approval(tmp_path, monkeypatch):
    import gffs.tornado_study as ts
    monkeypatch.setattr(ts, "APPROVAL", tmp_path / "missing.md")
    with pytest.raises(ApprovalRequired):
        ts.build_post_cutoff_history(date(2022, 10, 3), approval_file=tmp_path / "missing.md")
