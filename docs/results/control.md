# Control: the same forecaster on the Impact4Cast concept graph

## Prediction, written before the run (2026-11-18)

**Why this control exists:** on ATT&CK, structure-based forecasters did not beat the popularity
baseline (`study.md`). The proposed reason is density: 49–66% of all ATT&CK technique pairs are already
linked, so shared neighbours mostly restate popularity. The research-concept graph the method comes
from is large and sparse.

**Design:** the Impact4Cast optics and quantum-physics concept graph (37,960 concepts; Zenodo
10.5281/zenodo.10692137). The edge between two concepts counts the papers in which they appear together.
Train on the 2016 graph with links new by 2019. Test on the 2019 graph with links new by 2022, which is the
paper's own time-travel set-up. Use 200,000 uniformly sampled unlinked pairs per window. The 8 methods,
metrics and bootstrap are the same as in the ATT&CK study, with the code unchanged.

**If density explains the ATT&CK failure,** structure-based methods (`logreg_all`, `structural_rank_mean`)
should beat `frequency`, with the 95% interval above 0. Stratified AUC should also be clearly
higher than ATT&CK's 0.53–0.63.

**If they do not beat it here either,** the density explanation is weakened. The method, or our implementation,
becomes the more likely cause.

## Result (run 2026-11-18)

Graph at 2019: 37,901 active concepts, 22,841,349 linked pairs, **density 0.032**
(ATT&CK: 0.49–0.66). From 200,000 sampled unlinked pairs, 928 became linked by 2022 (base rate
0.46%). There were 765 positives in the 2016→2019 training sample.

| Method | AUC | AUC − popularity [95% CI] | Stratified AUC | Precision@1000 |
|---|---|---|---|---|
| frequency | 0.873 | +0.000 [+0.000, +0.000] | 0.610 | 0.101 |
| random | 0.530 | -0.343 [-0.365, -0.321] | 0.529 | 0.004 |
| logreg_all | 0.922 | +0.049 [+0.040, +0.058] | 0.806 | 0.126 |
| logreg_popularity | 0.871 | -0.002 [-0.006, +0.002] | 0.635 | 0.095 |
| hgb_all | 0.927 | +0.054 [+0.046, +0.063] | 0.811 | 0.121 |
| train_best_single | 0.922 | +0.049 [+0.043, +0.056] | 0.802 | 0.134 |
| structural_rank_mean | 0.901 | +0.028 [+0.022, +0.034] | 0.740 | 0.119 |
| hybrid_rank_exploratory | 0.895 | +0.022 [+0.019, +0.025] | 0.732 | 0.112 |

**The prediction is confirmed.** On the sparse concept graph, every structure-based method beats the
popularity baseline with an interval above zero: `logreg_all` +0.049, `hgb_all` +0.054, untrained
`structural_rank_mean` +0.028. The popularity-only model does **not** beat it (−0.002, interval spans 0), so the
gain comes from structure, not from a better popularity model. Within popularity deciles, the structural
methods reach a stratified AUC of 0.74–0.81, against 0.61 for popularity and 0.48–0.64 for the same methods on ATT&CK.
Supervised models trained on 2016→2019 also **transfer** to 2019→2022 here, unlike on ATT&CK.

**What this means:** the method and our code work where the method was designed to work. The ATT&CK failure is
best explained by the graph: about 190 nodes with half of all pairs already linked. It is not a broken pipeline.
For the AML literature graph (14 concepts, 91 pairs), expect the same problem as ATT&CK, only worse. This supports
the decision recorded in `docs/HANDOFF.md`: report a saturated graph as a result rather than enlarge the vocabulary.

**Caveats:**
- One time split only.
- The random baseline scored AUC 0.530, about 3 standard errors above 0.5. **Checked (2026-11-19, `results/control_seed_check.json`):** seeds 1–20 on the same pairs and labels give a mean AUC of 0.501 (standard deviation 0.0089, against a theoretical 0.0095). The random scorer is unbiased, and seed 0 was an unlucky draw.
- Pairs are sampled uniformly. Impact4Cast's own evaluation restricted pairs by degree and measured impact, not just
  whether a link appears, so these AUCs are not comparable to their published figures.
- Precision@1000 is low for every method because the base rate is under 0.5%. Relative to that base rate, the structural methods' top 1,000 are 24–29× richer in positives, and popularity's are 22×.
