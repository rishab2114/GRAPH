from reports.build_report import summary


def _m(auc, lo, hi, p=0.5, strat=0.5):
    return {"auc": auc, "precision_at_k": p, "strat_auc": strat, "vs_frequency": {"diff": (lo + hi) / 2, "lo": lo, "hi": hi}}


def test_summary_counts_wins_only_when_interval_excludes_zero():
    row = {"graph": {"density_t": 0.6}, "methods": {
        "frequency": _m(0.70, 0, 0, p=0.5, strat=0.52),
        "logreg_all": _m(0.72, 0.01, 0.03), "hgb_all": _m(0.71, -0.01, 0.03),
        "structural_rank_mean": _m(0.69, -0.02, 0.0, strat=0.60),
        "hybrid_rank_exploratory": _m(0.73, 0.02, 0.04, p=0.4)}}
    s = summary([row, row])
    assert s["LOGREG_WINS"] == "2" and s["HGB_WINS"] == "0"
    assert s["STRAT_WINS"] == "2" and s["HY_P100_LOSE"] == "2"
    assert s["FREQ_RANGE"] == "0.70–0.70" and s["HY_MAX"] == "+0.030"
