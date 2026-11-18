# Phase 0: holdout dataset check, Elliptic

Checked 2026-11-18. Reproduce with `python -m gffs.phase0 --data data/elliptic --out results/`. The raw
output is in `results/phase0_elliptic.json`. Data: the original July 2019 CSVs from the PyTorch Geometric
mirror (`data.pyg.org/datasets/elliptic/`), because Kaggle needs a login. Primary source for every fact
below: Weber et al. 2019, *Anti-Money Laundering in Bitcoin*, [arXiv 1908.02591](https://arxiv.org/abs/1908.02591),
§2.1 and Table 1.

## 1. Dataset facts: all match the paper

| Fact | Published | Observed |
|---|---|---|
| Transactions (nodes) | 203,769 | 203,769 |
| Payment flows (edges) | 234,355 | 234,355 |
| Illicit / licit / unknown | 4,545 / 42,019 / rest | 4,545 / 42,019 / 157,205 |
| Time steps | 49 | 49 |
| Features | 166 (94 local incl. time step + 72 aggregated) | 166 |
| Edges between different time steps | none | 0 |

`tests/test_elliptic_real.py` re-checks this table whenever the data is present.

## 2. Phase 0 criteria (spec §4)

| Criterion | Elliptic | Verdict |
|---|---|---|
| Timestamps | 49 time steps about two weeks apart. These are relative steps, not calendar dates | OK |
| Labels | 23% labelled; illicit = 2% of all transactions | OK |
| Ordinary cases | 42,019 licit transactions | OK |
| A real, untouched later period with a shift | A dark-market shutdown at step 43. See §4 | **Strong** |
| Features that invented scenarios can be written in | All 166 are anonymised **and pre-standardised** (mean 0, sd 1). Only their groups are described | **0% expressible** through features |
| Link to attack techniques | No typology or technique labels on any transaction | **Missing** (review note 1) |

## 3. Reproduction of the paper (train steps 1–34, test 35–49, illicit class)

| Model | Published F1 | Observed F1 | Note |
|---|---|---|---|
| Random forest, all features | 0.788 | 0.815 (0.804–0.821 over 8 seeds) | Close; slightly higher |
| Random forest, local features | 0.694 | 0.788 (0.764–0.790 over 8 seeds) | **Consistently higher. Unexplained** |
| Logistic regression, all features | 0.481 | 0.450 | Close |
| Logistic regression, local features | 0.457 | 0.361 (0.513 without the time-step column) | **Unexplained**. The time-step feature extrapolates badly past step 34 |

The paper's conclusion that random forest is best is reproduced. Two absolute numbers are not. Likely
causes are scikit-learn version differences (2019 vs 2026) and unreported preprocessing. Neither affects
the decisions below.

## 4. The dark-market shutdown: detectors fail after step 43

Recall on illicit transactions, models trained on steps 1–34:

| Detector | F1 (35–49) | Recall, steps 35–42 | Recall, steps 43–49 |
|---|---|---|---|
| extra_trees_af | 0.817 | 0.825 | 0.018 |
| rf_af | 0.815 | 0.852 | 0.018 |
| hgb_af | 0.805 | 0.853 | 0.012 |
| rf_lf | 0.788 | 0.847 | 0.018 |
| mlp_af | 0.564 | 0.714 | 0.030 |
| knn_af | 0.523 | 0.734 | 0.036 |
| tree_af | 0.522 | 0.883 | 0.213 |
| lr_af | 0.450 | 0.819 | 0.124 |
| lr_scaled_af | 0.404 | 0.744 | 0.148 |
| lr_lf | 0.361 | 0.891 | 0.124 |
| nb_af | 0.275 | 0.885 | 0.799 |

This reproduces the paper's claim that all methods perform poorly after the shutdown. The best detectors
go from about 85% recall to about 2%. Only Naive Bayes keeps its recall, at the cost of 16% precision.

## 5. Backtest: does the simplest stress test predict the later period?

The simplest stress test is each detector's score on the last 6 time steps before cutoff T
(trained on 1..T−6). The holdout is the detector trained on 1..T and scored on the next 10 steps.
This is E3 (ranking) and E4 (calibration) with no invented scenarios. **It is the baseline the
graph-generated scenarios must beat.** There are 11 detectors.

| Cutoff T | Test steps | Ranking ρ, F1 | Ranking ρ, precision | Ranking ρ, recall | Recall error (stress − holdout) |
|---|---|---|---|---|---|
| 24 | 25–34 | +0.91 (p<0.001) | +0.94 | +0.07 (n.s.) | −0.119 |
| 29 | 30–39 | +0.91 (p<0.001) | +0.94 | −0.07 (n.s.) | −0.178 |
| 34 | 35–44 | +0.92 (p<0.001) | +0.95 | +0.04 (n.s.) | +0.014 |
| 39 | 40–49 (shutdown) | +0.69 (p=0.019) | +0.74 | +0.14 (n.s.) | **+0.242** |

**Reading:** recent past data ranks detectors well on F1 and precision. It does not rank them on
**recall**: the catch rate is what moves, because the mix of illicit actors changes from window to
window. Across the shutdown, the stress test **overstates recall by 24 percentage points**. That is
exactly the E3/E4 split the spec warned about: the ranking is roughly right while the catch rate is badly wrong.

## 6. Decision (for the owner)

- **Elliptic is a strong holdout for E3/E4.** It is real, dated, labelled, and has a documented shift
  in which detectors fail. It now has a measured baseline: recall ranking ρ ≈ 0, and a +24 pt recall
  error across the shift.
- **It cannot host Stage 4 as specified.** Scenarios cannot be written in its features (0%). It also
  has no technique labels, so ATT&CK combinations do not map onto it.
- **Options:**
  1. *Elliptic + AML typology graph:* build the technique graph from FATF and FinCEN typologies.
     Express scenarios only through the transaction graph (counts, fan-in/fan-out, timing), using
     `elliptic_txs_edgelist.csv`. This is the most faithful to the core question, and the most work.
  2. *Cyber holdout + ATT&CK:* keep the existing graph and look for a dated, labelled host or network dataset.
  3. *Simulation benchmark:* generate data with AMLSim and say so. This drops the real-world transfer claim.
- **Recommendation:** option 1. The backtest above shows the specific target: a stress test that
  predicts **recall**, and its collapse after a shift, better than recent data does.

## Not yet done in Phase 0

- Checks of IEEE-CIS and a cyber holdout.
- The prior-work search (SynthAML, studies of stress-test transfer, hyperbolic forecasting).
