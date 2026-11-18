# Review notes on the spec

Problems found while turning [`spec.md`](spec.md) into a build plan. They are ordered by how
much each one threatens the core question. Facts about the datasets are from memory and still
need checking in Phase 0. The [Phase 0 checklist](superpowers/plans/2026-11-18-phase0-1-holdout-and-technique-graph.md#task-0-phase-0-holdout-decision-and-prior-work-note)
lists them.

## 1. The graph source and the holdout candidates are in different domains (blocking)

The graph in Stages 1 and 2 is built from **MITRE ATT&CK**, which covers cyber intrusion
techniques. Both holdout candidates, **Elliptic** (Bitcoin AML) and **IEEE-CIS** (card-not-present
fraud), are financial-fraud datasets. Neither labels its cases with ATT&CK techniques, or with
techniques of any kind. That breaks three things:

- E3 and E4 cannot tell which holdout cases are "new combinations", so the stress test and the
  holdout are not measuring the same thing.
- Stage 4 has no mapping from an ATT&CK technique pair to an Elliptic or IEEE-CIS row.
- The spec says "pick the domain from the holdout". The tool list still fixes ATT&CK as the
  graph, which picks the domain the other way round.

**What to decide:** the graph source and the holdout must come from the same domain.
- *Fraud/AML holdout* → the technique graph has to come from typology documents
  (FATF typology reports, FinCEN advisories), with nodes as typology indicators. These are dated
  by publication but are not versioned like ATT&CK, so "the graph as of T" needs care.
- *Cyber holdout* → keep ATT&CK, but the holdout must be dated, labelled host or network data
  (candidates to check: LANL unified host and network dataset, DARPA OpTC, CIC-IDS2017/2018).
  Most of these are lab or red-team data, which weakens the "real future attacks" claim.

The plan below builds the Phase 1 graph code so that the data source can be swapped. It starts
with an ATT&CK loader because that data is clean and versioned. That only makes sense if Phase 0
chooses the cyber route, or if E1 is run on ATT&CK purely as a test of the method.

## 2. Both fraud holdouts have mostly anonymised features (likely kills Stage 4)

- **Elliptic:** about 203k transactions over 49 time steps. Of its 166 features, roughly 94 are
  local and 72 are aggregated, and all are anonymised. The labels are illicit, licit or unknown,
  with most cases unknown.
- **IEEE-CIS:** `TransactionDT` is an offset in seconds, not a calendar date. Most columns
  (`V1–V339`, `C*`, `D*`, `M*`) are masked.

"Write the invented scenario in the holdout's own features" will probably succeed for close
to 0% of scenarios on both datasets. The spec already says to measure and report this (E2),
which is right. Still, plan for the result to be "almost nothing is expressible". In that case
Stage 4 falls back to our own encoding, and our own encoding is exactly the encoding-bias risk
in section 3 of the spec.

**Point in Elliptic's favour:** published work on this dataset reports that classifiers fail
after a dark-market shutdown late in the time range (around time step 43). That is a real,
dated "untouched later period" in which detectors break, so it fits E3 and E4 well, even if
Stage 4 can only be partly expressed. Worth checking first.

## 3. E3 (Spearman across detectors) needs more detectors than the spec implies

With 4–5 detector variants, Spearman ρ can only take a few values, and even ρ = 1 is
not significant at p < 0.05 with n = 4. Plan for **at least 8 variants**, or report a
bootstrap confidence interval for ρ. Building those variants in Phase 3 adds to the 1-week estimate.

## 4. ATT&CK node identity changed in v7 (July 2020)

ATT&CK added sub-techniques in v7. Many techniques were turned into sub-techniques or
deprecated. Comparing a graph from v6 or earlier with one from v7 or later, node by node, creates
fake "new" and "lost" nodes and edges. The plan collapses every sub-technique to its parent
technique ID (`T1059.001 → T1059`). It also sets the earliest cutoff for training to v8 and later.

## 5. "Newly documented together" in ATT&CK is mostly backfill

When ATT&CK adds a technique to a group's profile, the activity is often years old. An edge
that appears between releases is therefore new to the catalogue, not new in the wild. The spec
already uses the right wording ("newly documented together"). Keep that wording in every result.
E1 tells you how good the forecaster is at predicting **MITRE's documentation**. It does not tell
you how good it is at predicting attacker behaviour.

## 6. Minor

- The pair and triple counts are correct: C(123128, 2) ≈ 7.58 × 10⁹ and
  C(123128, 3) ≈ 3.11 × 10¹⁴.
- The frequency-matched baseline, used as a *ranker*, is the same as preferential attachment
  (score = freq(u) · freq(v)). The plan implements it that way, so it is deterministic and its AUC
  is meaningful.
