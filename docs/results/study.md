# Multi-split study: does graph structure forecast new ATT&CK technique pairs beyond popularity?

**Short answer: mostly no.** Across 9 settings (3 rolling time splits × 3 edge definitions),
a baseline that only uses how common each technique is ("frequency") is matched or beaten by
every supervised graph model. Shared-neighbour structure does carry a small, consistent signal
*within* popularity bands. An untrained blend of popularity and structure gains up to 0.03 AUC,
but it was designed after seeing the data and does worse at the top of the ranking.
A pre-registered prospective test is set out in [`PREREGISTRATION.md`](../../PREREGISTRATION.md).

Reproduce: `python -m gffs.study --config config/study.toml --out results/`. Raw numbers are in
`results/study.json` and the full table is in `results/study_table.md`. The run takes about 5 minutes on a laptop.

## Design

| Split | Train window (graph → labels) | Cutoff T | Test window labels |
|---|---|---|---|
| S1 | v8.0 (2020-10) → v12.0 | v12.0 (2022-10) | v16.0 (2024-10) |
| S2 | v10.0 (2021-10) → v14.0 | v14.0 (2023-10) | v18.0 (2025-10) |
| S3 | v12.0 (2022-10) → v16.0 | v16.0 (2024-10) | v20.0 (2026-10) |

- **Edges:** `all` = intrusion sets + malware + tools + campaigns. `groups` = intrusion sets + campaigns.
  `software` = malware + tools. Sub-techniques are collapsed to their parent, and revoked or deprecated objects are dropped.
- **Positives:** unlinked pairs at T that are **newly documented together** by the test release.
  The base rate is 6–23%.
- **Methods, all fixed before the results were seen:**
  - `frequency`: freq(u)·freq(v).
  - `random`.
  - `logreg_all`: logistic regression on all 9 features.
  - `logreg_popularity`: the same model on popularity features only. This is the ablation.
  - `hgb_all`: gradient boosting on all 9 features.
  - `train_best_single`: the single feature with the best AUC on the training window.
  - `structural_rank_mean`: the average rank of the 5 shared-neighbour features. No fitting.
  - **Exploratory, added afterwards:** `hybrid_rank_exploratory` = the mean of the popularity rank and the structural rank.
- **Metrics:**
  - AUC and precision@100.
  - **Popularity-stratified AUC:** AUC computed only between pairs in the same decile of
    freq(u)·freq(v). A score that only tracks popularity gets about 0.5, so this isolates
    signal beyond popularity.
  - **AUC − frequency**, with a 95% paired-bootstrap interval (1,000 resamples).

## Results

### 1. AUC gain over the frequency baseline (95% CI). Bold = interval excludes 0

| Setting | Density at T | Freq. AUC | logreg_all | logreg_popularity | structural_rank_mean | hybrid (exploratory) |
|---|---|---|---|---|---|---|
| S1 all | 0.66 | 0.728 | **−0.059** [−.080, −.042] | **+0.014** [+.003, +.025] | +0.004 [−.014, +.023] | **+0.027** [+.018, +.036] |
| S1 groups | 0.64 | 0.742 | **−0.033** [−.046, −.020] | **−0.011** [−.015, −.007] | **−0.023** [−.042, −.003] | **+0.015** [+.005, +.026] |
| S1 software | 0.52 | 0.753 | **−0.023** [−.031, −.014] | **−0.018** [−.025, −.011] | **−0.041** [−.062, −.022] | −0.000 [−.012, +.010] |
| S2 all | 0.62 | 0.722 | −0.004 [−.014, +.005] | **+0.012** [+.003, +.021] | **−0.017** [−.032, −.002] | **+0.013** [+.005, +.020] |
| S2 groups | 0.60 | 0.731 | −0.003 [−.008, +.003] | **−0.007** [−.012, −.001] | **−0.047** [−.061, −.032] | −0.001 [−.009, +.007] |
| S2 software | 0.49 | 0.789 | **−0.028** [−.038, −.017] | **−0.012** [−.021, −.002] | **−0.024** [−.044, −.005] | **+0.012** [+.002, +.022] |
| S3 all | 0.64 | 0.749 | **+0.023** [+.014, +.034] | **+0.015** [+.006, +.025] | **−0.031** [−.045, −.017] | **+0.010** [+.002, +.017] |
| S3 groups | 0.62 | 0.747 | **−0.016** [−.024, −.008] | −0.001 [−.008, +.006] | **−0.051** [−.067, −.035] | −0.001 [−.009, +.008] |
| S3 software | 0.49 | 0.760 | **−0.028** [−.037, −.018] | **−0.012** [−.017, −.006] | **−0.062** [−.078, −.045] | −0.008 [−.016, +.000] |

`hgb_all` and `train_best_single` (full table in `results/study_table.md`) are below frequency in
8 of 9 settings. `random` sits at AUC ≈ 0.50 everywhere.

### 2. Signal beyond popularity: AUC within popularity deciles

| Setting | frequency | structural_rank_mean | hybrid (exploratory) |
|---|---|---|---|
| S1 all | 0.527 | 0.629 | 0.630 |
| S1 groups | 0.525 | 0.588 | 0.592 |
| S1 software | 0.526 | 0.554 | 0.559 |
| S2 all | 0.543 | 0.599 | 0.603 |
| S2 groups | 0.507 | 0.565 | 0.563 |
| S2 software | 0.550 | 0.605 | 0.614 |
| S3 all | 0.564 | 0.599 | 0.606 |
| S3 groups | 0.540 | 0.577 | 0.579 |
| S3 software | 0.528 | 0.528 | 0.534 |

### 3. Precision at top 100: what a scenario short-list would get

| | S1 all | S1 grp | S1 sw | S2 all | S2 grp | S2 sw | S3 all | S3 grp | S3 sw |
|---|---|---|---|---|---|---|---|---|---|
| frequency | 0.45 | 0.43 | 0.37 | 0.67 | 0.68 | 0.37 | 0.71 | 0.62 | 0.45 |
| hybrid (exploratory) | 0.48 | 0.35 | 0.30 | 0.66 | 0.64 | 0.31 | 0.62 | 0.61 | 0.35 |
| random | 0.10 | 0.15 | 0.05 | 0.18 | 0.22 | 0.07 | 0.25 | 0.21 | 0.15 |

## Findings

1. **Popularity explains most of what is predictable.** The frequency baseline reaches an AUC of
   0.72–0.79 in all 9 settings. This answers spec sub-question 1: **no**, the simple graph
   forecaster does not reliably beat the frequency-matched baseline.
2. **Supervised structure models do not transfer across time.** `logreg_all` beats frequency in
   1 of 9 settings. Adding structural features to a popularity-only model (`logreg_all` vs
   `logreg_popularity`) helps in only 2 of 9. Coefficients learned in one 2-year window do not
   carry over to the next.
3. **Structure carries a real but small signal at fixed popularity.** Within popularity deciles,
   the untrained structural score beats frequency in all 9 settings (0.53–0.63 vs 0.51–0.56). In S3 software the margin is negligible (0.528 vs 0.528 at three decimals).
   The Swanson-style "shared bridge" idea is not empty here. It is just much weaker than popularity.
4. **The exploratory blend helps AUC but not the short list.** It gains in 5 of 9 settings, with
   CIs excluding 0 and gains of 0.010–0.027. However, it has a **lower precision@100 in 8 of 9**.
   Picking scenarios needs a good short list, so this matters more than AUC. Not confirmed; see the pre-registration.
5. **A sparser edge definition does not rescue the method.** `software`-only graphs (density
   about 0.5) give structure *less* of an edge, not more.

**Likely reason.** The concept graph in SciMuse has about 123k nodes and is far sparser. There,
"far apart but bridged" picks out rare, informative pairs. ATT&CK has only about 180 parent
techniques, and 50–66% of all pairs are already linked. Almost every unlinked pair is bridged
many times over, so shared neighbours mostly re-encode popularity.

## Threats to validity

- **What is being predicted is MITRE's documentation, not attacker behaviour.** Many new edges
  are backfills of older activity.
- **Splits overlap.** S2's windows overlap S1's and S3's, so the 9 settings are not independent.
  They show robustness, not 9 replications.
- **The test windows were looked at.** The hybrid was designed after the results were seen. Only the
  pre-registered prospective test can confirm it.
- **One data source.** Fraud typologies (FATF) may behave differently. Review note 1 still applies:
  E3 and E4 need a holdout from the same domain as the graph.

## What this means for the project plan

- **Stage 2:** use the frequency baseline as the default ranker. Use structure only to re-rank
  *within* a popularity band, for example to choose non-obvious pairs among rare techniques. That
  is where the signal is.
- **The core research question (E3/E4)** is still untested. It needs Task 0's holdout decision.
  This study does not answer whether invented scenarios predict detector performance.
