# Research log

One entry per step. Each entry says what I was deciding, why I chose the step, what I did, what I
found, and what it changes. Dates are UTC. Earlier work (2026-11-18, before this log) is summarised in
`docs/HANDOFF.md` and `docs/results/`.

---

## 2026-11-18 18:40 — Loop start: choosing the next step

**State.** The v2 literature-graph builder is written and tested (`src/gffs/literature_v2.py`), but it
cannot run. OpenAlex's free shared allowance on this server is used up until 00:00 UTC, and the owner
declined to add an API key. So no step that needs OpenAlex can happen for about 5 hours.

**Options I considered, and why:**

| Option | Needs OpenAlex? | Value | Decision |
|---|---|---|---|
| A. Prior-work search (Phase 0 left this undone: SynthAML, stress-test transfer, hyperbolic forecasting) | No | High. If the core idea is already published, the project's framing changes. Better to know before more building | **Do now** |
| B. Step 4 groundwork: detect the 8 motifs (fan-in, peel chain, ...) on Elliptic's real payment graph, and check whether they are more common among illicit transactions | No | High. If the motifs don't separate illicit from licit at all, scenarios built from them are pointless. This tests that early | **Next** |
| C. Rerun the Impact4Cast control with more random seeds (its random baseline scored 0.530) | No | Low. It doesn't change the conclusion | Later, if time |
| D. Run the v2 literature graph | Yes | High | After 00:00 UTC |

**Order:** A, then B, then D once the allowance resets.

---

## 2026-11-18 18:50 — Step A: prior-work search

**Question.** Has anyone already shown that a stress test built only from data before a cutoff predicts
how detectors perform on a later, untouched period? Was SynthAML's generator really fitted on test-period
data? Has anyone forecast new attack-technique combinations, or used hyperbolic embeddings for that?

**What I found:**

1. **SynthAML** (Jensen et al., *Scientific Data* 2023; [PMC10539331](https://pmc.ncbi.nlm.nih.gov/articles/PMC10539331/)). The spec's rumour is **confirmed**.
   The synthetic generator was fitted on all alerts, *including the 2021 test year*, and the authors say so:
   "Strictly speaking, this introduces a form of target leakage." Their transfer evidence: 6 models
   trained on synthetic 2020 alerts give the **same ranking** when tested on synthetic and on real 2021 data
   (for example, logistic regression 64.10 vs 64.48 AUC, decision tree 52.00 vs 52.26). But real-trained models
   score up to 75.6, and there is one split only.
   → **The closest precedent, and it has exactly the two gaps this project targets:** leakage from the test
   period, and only ranking, not calibration, across one split.
2. **Synthetic tabular generators lose fraud *behaviour*** (Sajja, [arXiv 2604.13125](https://arxiv.org/abs/2604.13125), April 2026).
   CTGAN, TVAE, GaussianCopula and TabularARGN degrade burst, velocity and **multi-account graph-motif** signals
   by 17–100×. They prove that generators which produce each row independently *cannot* reproduce graph motifs.
   → This supports our choice to write scenarios as **explicit transaction-subgraph motifs** instead of
   sampling rows from a generator.
3. **Stress-testing benchmarks without a predictive check:** TransXion ([arXiv 2604.17420](https://arxiv.org/pdf/2604.17420)) is a
   "benchmark for … stress-testing AML detection", and Tide ([arXiv 2603.01863](https://arxiv.org/pdf/2603.01863)) injects new typologies.
   Neither tests whether its stress test *predicts later real performance*. IBM's AMLworld
   ([arXiv 2306.16424](https://arxiv.org/pdf/2306.16424)) argues that synthetic data has complete labels, but its scores are "indicative".
4. **ATT&CK and threat knowledge graphs:** AttackDB-style link prediction infers *which techniques are present*
   from observed evidence. A4CKGE and LLM template work generate multi-step ATT&CK *templates*. I found nothing
   that forecasts *undocumented technique combinations over time* and tests them against later releases, as our E1 does.
5. **Hyperbolic embeddings:** MuRP (NeurIPS 2019) and hierarchy-aware variants do *static* link completion.
   I found nothing on forecasting future links over time with them. → This stays an open "later extension".

**What this changes:**
- **Claim:** the project's distinctive claim becomes clearer, and it is specific. It is not "synthetic AML data"
  (crowded) but **a leakage-free test of whether a pre-cutoff stress test predicts both the ranking *and* the
  calibration of detectors on a later real period**, compared against the plain recent-data stress test
  (Phase 0 baseline: recall ranking ρ ≈ 0, +24 pt error).
- **Write-up:** SynthAML is the paper to cite and contrast against. Its single split with test-period leakage
  is what we improve on.
- **Caveat:** this was a web search, not a systematic review. A paper could still exist that these searches missed.
  Before any submission, run a citation-trail search from SynthAML and Weber et al. 2019.
