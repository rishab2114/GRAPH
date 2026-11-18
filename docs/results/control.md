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

## Result

(filled in after the run)
