from gffs.mechanism import summarise


def _row(s0e, sce, s0r, scr):
    return {"S0_recent_data_err": s0e, "S0_recent_data_rho": s0r, "SA_err": s0e, "SA_rho": s0r,
            "SB_err": s0e, "SB_rho": s0r, "SC_err": sce, "SC_rho": scr}


def test_summarise_counts_wins_against_recent_data():
    rows = [_row(0.10, 0.05, 0.2, 0.6)] * 7 + [_row(0.05, 0.10, 0.6, 0.2)] * 3
    s = summarise(rows, n_boot=200)
    assert s["SC"]["wins_error"] == 7 and s["SC"]["wins_rho"] == 7
    assert s["SC"]["median_err_diff"] < 0 and s["SA"]["wins_error"] == 0
