# E3/E4 design: does the graph-forecast stress test predict real later detector performance?

**Frozen 2026-11-18, before any code reads Elliptic time steps 35–49 for this experiment.** The Phase 0
backtest (`docs/phase0-decision.md`) already used those steps with the *paper's feature-based* detectors. This
experiment uses different detectors (graph-only, below) and has not looked at their scores on 35–49.
Any change after this commit goes in a dated "Deviations" section at the end, with the reason.

## Question

Spec §1, sub-questions 2 and 3, on Elliptic:

- **E3 (ranking):** across detectors, does stress-test recall rank them in the same order as recall on real
  illicit transactions in steps 35–49?
- **E4 (calibration):** how far is each detector's stress-test recall from its real recall in steps 35–49?
- **Compared with what:** the recent-data stress test (each detector's recall on steps 29–34) and two other
  scenario generators (below). The graph-forecast stress test is useful only if it beats these.

## Detectors: graph-only, so real and synthetic transactions are scored the same way

Elliptic's 166 features cannot be written for invented transactions (Phase 0: 0% expressible). So every
detector here sees only **features computed from the payment graph**, the same function for real and synthetic
transactions (`gffs.motifs.node_features`, plus 1-hop neighbour aggregates: the mean and max in-degree, out-degree
and depth of predecessors and successors).

- **The 10 model types** are the Phase 0 detectors minus the two that exist only to reproduce the paper
  (`lr_lf`, `rf_lf`), plus `rf_balanced` (a random forest with balanced class weights). That gives 10, above the
  minimum of 8 in review note 3.
- **Training data:** real labelled transactions from steps 1–34 only. No synthetic data is used in training,
  ever (spec: "generated scenario types used for testing never appear in training").
- **Alert threshold:** for each detector, chosen on steps 29–34 (models fitted on 1–28) so that the false-positive
  rate on licit transactions is 5%. It is then fixed, and the model is refitted on 1–34 with that threshold.

**Limit:** the conclusions apply to graph-feature detectors. Whether they carry over to detectors that also use
Elliptic's anonymised features is a separate question that this experiment cannot answer.

## Stress tests being compared

Each stress test is a set of illicit transactions that a detector should flag. A detector's stress-test recall is
the share it flags at its fixed threshold.

| Name | Illicit transactions in it | Uses information after step 34? |
|---|---|---|
| **S0 recent data** (baseline) | real illicit transactions in steps 29–34, scored by models fitted on 1–28 | No |
| **S1 graph forecast** (the method) | synthetic transactions built from the **top 10** expressible motif pairs in the v2 literature ranking at 2016 | No |
| **S2 uniform pairs** (control) | synthetic, from 10 pairs drawn uniformly from the 28 expressible pairs (seed 0) | No |
| **S3 single motifs** (control) | synthetic, from each of the 8 motifs on its own | No |

S1 depends on the v2 literature run. If that run fails, or yields fewer than 10 unlinked expressible pairs,
S1 uses all the ones it does yield, and the result says so.

## Writing a scenario as transactions

- **Motif pair (A, B):** one synthetic subgraph per instance, where motif A's output feeds motif B's input.
  For example, a peel chain whose last hop feeds a fan-in hub. Example forms for each motif:
  - fan_in: k_A sources → hub
  - fan_out: node → k_A sinks
  - peel_chain: a path of length L_A
  - pass_through: 1 → node → 1
  - coinjoin and mixing: a node or two linked nodes with in, out ≥ k_A
  - smurfing: a split that reconverges
  - layering: a path of depth L_A
- **Sizes are drawn from training-period data:** k from the in- and out-degrees of real illicit hub transactions
  in steps 1–34. L from real illicit peel-run lengths in steps 1–34. This avoids the percentile-over-everything
  problem found in Step B.
- **Context:** each instance is attached to a random real step 29–34 component by one edge from a random real
  transaction, so its neighbour features look like real ones. Each instance is scored on its own copy of that
  graph, so instances do not interact.
- **Scale:** 200 instances per scenario pair, seed 0. All transactions in the subgraph are labelled illicit.

## Real holdout

Real labelled illicit transactions in steps 35–49, scored by the detectors fitted on 1–34. Also reported
separately: steps 35–42 and 43–49 (before and after the dark-market shutdown). Graph features for these steps are
computed from their own steps' edges, exactly as for training.

## Metrics, and what counts as success

- **E3:** Spearman ρ between each stress test's recall and holdout recall across the 10 detectors, with a 95%
  bootstrap interval. The bootstrap resamples holdout and stress-test transactions 1,000 times.
- **E4:** the mean absolute recall error across detectors, in percentage points, with its signed version.
- **E5:** the false-positive rate actually produced on licit transactions in steps 35–49, at the fixed thresholds.
- **Success for S1:**
  - E3: a higher ρ than S0 **and** S2, with the bootstrap interval of the difference above 0.
  - E4: a smaller error than S0 and S2.
  - Reported for 35–49, and separately for 43–49.
- **Anything else is a negative or mixed result, and is reported as such.**

## Known weaknesses, stated in advance

- **S1's 10 pairs come from 14 concepts' literature.** The forecast may simply rank the common motifs first, so S1
  may end up close to S3.
- **Step B showed that most hub motifs are rare among real illicit transactions.** Graph detectors may barely flag
  S1/S2 scenarios at all. Then stress-test recall is near 0 for every detector, the ranking is uninformative, and
  E3 fails by design. This would be a real finding about these scenarios, not a bug.
- **One dataset and one cutoff** (34) for the main result. The rolling cutoffs from Phase 0 (24, 29, 39) are a
  robustness check, reported with the main result.
