import numpy as np

from gffs.tornado_power import simulate


R_H = np.linspace(0.02, 0.40, 10)


def test_null_scenario_rarely_rejects_and_effect_scenario_rejects_more_with_more_positives():
    r0 = R_H + 0.10; rsyn_null = r0.copy(); rsyn_eff = R_H + 0.02
    null = simulate(R_H, r0, rsyn_null, n_hold=300, n_s0=600, tau=0.0, sims=60, boots=120, seed=1)
    small = simulate(R_H, r0, rsyn_eff, n_hold=50, n_s0=600, tau=0.0, sims=60, boots=120, seed=1)
    big = simulate(R_H, r0, rsyn_eff, n_hold=500, n_s0=600, tau=0.0, sims=60, boots=120, seed=1)
    assert null["power_iid"] <= 0.15
    assert big["power_iid"] >= small["power_iid"] and big["power_iid"] >= 0.8


def test_week_dependence_widens_block_intervals():
    r0 = R_H + 0.10; rsyn = R_H + 0.02
    lo = simulate(R_H, r0, rsyn, n_hold=200, n_s0=600, tau=0.0, sims=40, boots=100, seed=2)
    hi = simulate(R_H, r0, rsyn, n_hold=200, n_s0=600, tau=1.0, sims=40, boots=100, seed=2)
    assert hi["mean_ci_width_block"] > lo["mean_ci_width_block"]
