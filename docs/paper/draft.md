# Can a graph-forecast stress test predict how fraud detectors will fail?

*Working draft, 2026-11-19. Section 4.5 (the core result) is a placeholder until the frozen E3/E4 experiment runs.
Every number here comes from a file in `results/` or `docs/results/`; each section names its source.*

## Abstract (draft)

Fraud and intrusion detectors are usually evaluated on the past, but deployed against the future. We ask whether a
**stress test built only from information available before a cutoff** can predict how detectors will perform on
a later, untouched period: both their *ranking* and their *calibration*. We take a concept-graph forecaster from
the science-of-science literature (shared-neighbour link prediction, as in SciMuse and Impact4Cast) and retarget it to
attack techniques.

1. **On MITRE ATT&CK** (3 rolling splits × 3 edge definitions, 8 methods), the forecaster does **not** beat a
   popularity baseline. The same code on a sparse research-concept graph **does** (+0.049 AUC, 95% CI
   [+0.040, +0.058]). So graph density, not the method, explains the failure.
2. **On the Elliptic Bitcoin dataset,** the simplest stress test (recent data) ranks detectors well on precision and F1,
   but not on recall (Spearman ρ between −0.07 and +0.14). Across a documented dark-market shutdown, it overstates
   recall by 24 percentage points.
3. **Illicit transactions on Elliptic look like chains, not hubs.** Most textbook laundering motifs are *rarer* among
   illicit transactions than licit ones.
4. **[Core result pending]:** whether motif scenarios chosen by a literature-graph forecast predict later detector
   recall better than recent data, random motif pairs or single motifs.

All designs were frozen in the repository before the data they test was read.

## 1. Introduction

- **The gap.** Detectors are chosen and thresholded on historical data. Attackers change. A team needs to know two
  things *before* deployment: which detector will hold up, and how far its catch rate will fall.
- **The idea.** Research-forecasting systems (Gu & Krenn: SciMuse, Impact4Cast) predict which never-studied
  concept pairs will be studied next, using shared neighbours in a time-stamped concept graph. Replace "research
  concepts" with "attack techniques", forecast unseen combinations, turn them into synthetic attacks, and use those as a stress test.
- **What is new here.** (a) A **leakage-free** protocol: graph, generator, detectors and thresholds all use only
  pre-cutoff data. (b) Evaluating a stress test on **both ranking (E3) and calibration (E4)** against a later real
  period, compared with the plain recent-data stress test. (c) **Negative results reported as such,** plus a control
  that explains them.

## 2. Related work

- **Concept-graph forecasting:** SciMuse (Gu & Krenn, 2024), Impact4Cast (Gu & Krenn, 2025); popularity versus
  similarity (Papadopoulos et al., 2012); higher-order link prediction (Benson et al., 2018); Swanson's ABC model.
- **Synthetic AML data:** SynthAML (Jensen et al., *Scientific Data* 2023) is the closest precedent. Six models keep the
  same ranking on synthetic and real 2021 alerts, but the generator was fitted on alerts that include the test year
  (the authors call this "target leakage"), and only one split is used. IBM AMLworld (Altman et al., 2023), Tide (2026)
  and TransXion (2026) offer synthetic data and stress tests, but none tests whether the stress test *predicts later
  real performance*.
- **Why explicit motifs:** row-independent tabular generators provably cannot reproduce multi-account graph motifs
  (Sajja, 2026). We therefore write scenarios as explicit transaction subgraphs.
- **Threat knowledge graphs:** link prediction and embeddings over ATT&CK, CAPEC and CVE infer techniques from evidence
  or generate templates (AttackDB, A4CKGE). We did not find work that forecasts undocumented technique combinations
  over time.

## 3. Method

1. **Technique graph at cutoff T:** nodes are techniques (or concepts); an edge joins two that appear together.
   ATT&CK uses the release published at T, not today's catalogue filtered by date. Sub-techniques are collapsed to their parent.
2. **Forecaster:** shared-neighbour pair features (common neighbours, Jaccard, Adamic–Adar, resource allocation,
   weighted common neighbours), plus popularity features. Pre-specified variants: logistic regression, gradient
   boosting, the best single feature chosen on training data, and an untrained structural rank. Trained on the
   window (T−k → T), tested on (T → T+k).
3. **Baselines:** **popularity** (freq(u)·freq(v)) and uniform random.
4. **Popularity-stratified AUC:** AUC computed only between pairs in the same popularity decile. A score that only
   tracks popularity gets about 0.5. This isolates the structural signal.
5. **Scenarios to data:** each forecast motif pair becomes a synthetic transaction subgraph in which motif A's
   output feeds motif B. It is injected into real pre-cutoff graph components. Sizes are drawn from pre-cutoff
   illicit transactions.
6. **Detectors:** graph-feature models, the same features for real and synthetic transactions. Alert thresholds are
   fixed on pre-cutoff licit data, at a 5% false-positive rate.

## 4. Results

### 4.1 Forecasting new ATT&CK technique pairs (`docs/results/study.md`)

- **Design:** 3 rolling splits (cutoff T = v12, v14, v16; test windows up to v20) × 3 edge sets × 8 methods.
- **The popularity baseline's AUC is 0.72–0.79** in all 9 settings.
- **Logistic regression on all features** beats it in 1 of 9; gradient boosting in 0 of 9.
- **Within popularity deciles,** the untrained structural score beats popularity in 9 of 9 (0.53–0.63 vs 0.51–0.56):
  the signal is real, but small.
- **An exploratory popularity + structure blend** gains up to +0.027 AUC, but has a lower precision@100 in 8 of 9 settings.
  A prospective test is pre-registered (`PREREGISTRATION.md`).

### 4.2 Control: the same code on a sparse research graph (`docs/results/control.md`)

- **The graph:** Impact4Cast's physics concepts (37,901 active nodes; **3%** of pairs linked, against 49–66% in ATT&CK).
  The graph at 2019 is used to predict links new by 2022.
- **Structure beats popularity:**
  - logistic regression +0.049 [+0.040, +0.058];
  - gradient boosting +0.054;
  - untrained structural rank +0.028.
- **The popularity-only model gains nothing** (−0.002).
- **Within-popularity AUC** is 0.74–0.81, against 0.61 for popularity.
- **The prediction was committed before the run.**
- **Seed check of the random baseline:** [pending, `results/control_seed_check.json`].

### 4.3 Elliptic: a real holdout with a shift (`docs/phase0-decision.md`)

- **The data matches the paper:** 203,769 transactions, 234,355 edges, 4,545 illicit, 42,019 licit, 49 steps.
- **Main finding reproduced:** random forest is best, F1 0.815 against 0.788 published. Two absolute values from the
  paper do not reproduce, and we report them.
- **After the dark-market shutdown** (step 43), the best detectors' recall falls from about 85% to about 2%.
- **The recent-data stress test** (last 6 steps before the cutoff → next 10 steps, 11 detectors):
  - ranking: ρ = +0.69 to +0.95 on F1 and precision, but −0.07 to +0.14 on recall;
  - calibration: across the shutdown, recall is overstated by **+24 points**.

### 4.4 What illicit transactions look like (`results/motifs_elliptic.json`)

Steps 1–34 only:

| | Illicit vs licit |
|---|---|
| Pass-through (one in, one out) | **2× more common** |
| Long peel runs (95th percentile) | 182 vs 14 |
| Fan-in, mixing, CoinJoin, smurfing | **4–40× less common** |

A rule fixed in advance, a percentile over all transactions, was dominated by unlabelled ones and missed the
peel-chain signal. We report this as a lesson, not a corrected result.

### 4.5 Core result: does the graph-forecast stress test predict later recall? [PENDING]

- **Status:** the design is frozen in `docs/e3e4-design.md`.
- **Stress tests compared:** S1 graph forecast (top 10 expressible motif pairs from the pre-2017 AML literature
  graph), S0 recent data, S2 uniform pairs, S3 single motifs.
- **Holdout:** real illicit transactions in steps 35–49, and 43–49 separately.
- **Detectors:** 10 graph-only detectors.
- **Metrics:** Spearman ρ with a bootstrap CI, recall error, and paired comparisons.
- **Waiting on:** the literature corpus download (105,469 pre-2017 works; 135 of 528 pages done).
- **Expected weakness, written down in advance:** in a training-only dry run, detectors flagged only 0.2% of synthetic
  hub scenarios. The ranking may be uninformative.
- **Literature sparsity, already observed:** the 8 drawable motifs appear in only 0–73 pre-2017 works each
  (peel chain 0, fan-in 1, CoinJoin 2).

## 5. Discussion and limits

- **Density decides whether the method works.** Shared-neighbour forecasting needs a large, sparse graph. Small
  technique catalogues (about 190 ATT&CK techniques) are too dense; there, popularity is the honest baseline to beat.
- **What is forecast is documentation, not behaviour.** New ATT&CK edges are often old activity documented late.
  Literature co-mentions are research attention, not attacker practice.
- **Graph-only detectors.** Elliptic's features are anonymised and cannot be written for synthetic transactions,
  so conclusions cover graph-feature detectors only.
- **One dataset for the holdout,** and its time steps have no calendar dates.
- **Dual use:** the repository holds technique IDs, motif shapes and metrics only.

## 6. Reproducibility

- **Location:** everything is at github.com/rishab2114/graph (`main`).
- **Run order:** `gffs.study` → `gffs.concept_control` → `gffs.phase0` → `gffs.motifs` → `gffs.literature_v2` → `gffs.e3e4`.
- **Design files**, committed before their data was read: `PREREGISTRATION.md`, `docs/e3e4-design.md`,
  `config/aml_vocabulary*.toml`, and the prediction in `docs/results/control.md`.
- **Decision record:** `docs/RESEARCH_LOG.md`.
