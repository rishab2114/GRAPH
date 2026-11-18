# Graph-Forecast Fraud Scenarios: Project Plan

Nov 19, 2026 · @lord

> Source spec, copied from the original planning note. Reviewer comments live in
> [`review-notes.md`](review-notes.md); the step-by-step build plan lives in
> [`superpowers/plans/`](superpowers/plans/).

## Overview

AI can now map all of published research as a network of concepts and forecast which concepts that have never been studied together will come together next. This project takes that forecasting engine, retargets it from research ideas to attack techniques, and uses it to invent attack scenarios nobody has recorded yet. Those scenarios become test data for fraud and cybersecurity detection models. The aim is to find a detector's blind spots before real attackers do, and to check whether invented scenarios are a fair stand-in for real future attacks.

## How we got here: discussion notes

**Starting question.** Is there research where AI takes two distant fields (say A = tech and B = financial history), checks how topics relate and how coherent they are, and proposes a new field C that sits far from both? Several papers do this. The closest match is SciMuse (Gu & Krenn).

### How the graph works

- **Nodes are concepts.** Edges link two concepts that appear in the same paper. Each edge carries a year and citation counts, so the graph can be rewound to any year.
- **"New" means a missing edge:** two concepts never studied together. There are about 7.6 billion possible pairs among 123,128 concepts, so being new is easy and choosing is the hard part.
- **"Interesting" is learned from history.** Freeze the graph at 2016, see which missing pairs got connected and cited by 2019, train a model on that, then run it on today's graph.
- **Coherence comes from shared neighbours:** two concepts that have never met but both link to the same third concepts have a plausible bridge. Good ideas are far apart in the graph but have a few such bridges. Too close is obvious; no bridge is nonsense.
- An LLM then writes the chosen combination up as a research idea.

**What it actually forecasts.** What researchers will study next, not what is true or possible. For attacks, the equivalent is "plausible given past patterns", not "will happen".

### Our extensions to the method

- **Multiple nodes, not pairs.** Grow a combination one concept at a time while it stays coherent. Known in network science as higher-order link prediction. Harder because combinations explode (triples: about 3.1 × 10^14) and data is sparser.
- **The circle (disk) idea.** Place every concept in a disk: angle = topic, radius = popularity (broad concepts near the centre, niche ones at the edge). Nodes close in the disk are likely to link next. This matches the popularity vs similarity model (Papadopoulos et al., Nature 2012). A coherent multi-node idea becomes a tight group of points.
- **From research ideas to fraud.** Nodes become attack techniques and data signals; edges become techniques seen together in real cases. Forecast unseen combinations, turn them into synthetic data, and test whether a detector trained only on known attacks catches them.

### What we found in the original code

- The SciMuse repo does not include the idea-generation code, only the data and analysis.
- Impact4Cast's graph covers only optics and quantum physics.
- SciMuse's concept list is mostly science and engineering: "monetary policy", "economic history" and "fintech" do not appear. So we build our own graph rather than reuse theirs.

### Domains we considered

| Domain | Fit | Note |
|---|---|---|
| Cybersecurity (MITRE ATT&CK) | Candidate | Cleanest free data; co-occurrence graph nearly ready-made |
| Banking fraud and money laundering | Candidate (better fit, harder data) | Best fit with economics; FATF reports and AMLSim |
| Market manipulation | Strong alternative | ABIDES market simulator; spoofing, pump-and-dump |
| Academic fraud (paper mills, citation rings) | Most original | Graph and data are the same papers |
| E-commerce abuse | Practical | Fake reviews, refund and promo abuse |
| Insurance claims fraud | Weaker | Data exists, less novel |
| Social bot networks | Weaker | Messy to simulate |

## 1. Goal

Build a knowledge graph of attack techniques, use it to forecast attack combinations that have not been seen yet, turn those forecasts into synthetic data, and measure whether a detection model can catch attack types it was never trained on.

**Core research question (revised):** Can a stress test built only from data available before a cutoff predict how detectors will perform on a genuinely untouched later period?

### Sub-questions

1. Does one simple graph forecaster pick unseen combinations better than a frequency-matched baseline (random combinations that use techniques as often as they really occur)?
2. **Ranking:** does the stress test rank detectors in the same order as the later holdout? This is what a team needs to choose a model.
3. **Calibration:** how far is the stress test's predicted catch rate from the real later catch rate? A test can rank correctly and still overstate every catch rate.

Questions 2 and 3 decide whether the project is useful, so the data needed to answer them is secured in week one, not week six. If no real dated, labelled holdout can be found, the project is framed as a simulation benchmark and real-world transfer stays an open question. The disk embedding and multi-node growth move to Later extensions.

## 2. Background

| Work | What it does | What we borrow |
|---|---|---|
| SciMuse (Gu & Krenn, 2024) | Concept graph from 58M papers; picks unconnected concept pairs; GPT-4 writes research ideas; 100+ group leaders rated 4,400 ideas | Pair selection, LLM write-up, learning from human ratings |
| Impact4Cast (Gu & Krenn, 2025) | Forecasts which unconnected concept pairs become high-impact, using node, pair and citation features on a time-evolving graph | Feature set, time-travel test (freeze at year T, predict T+3) |
| Popularity vs similarity (Papadopoulos et al., Nature 2012) | Places nodes in a disk: radius = popularity, angle = similarity; new links form between nearby nodes | Disk embedding as a forecaster |
| Higher-order link prediction (Benson et al., PNAS 2018) | Predicts when groups of three nodes come together | Multi-node combinations |
| Swanson ABC model (1980s) | Two literatures that share a third set of papers hide an unknown link | The shared-neighbour coherence idea |

**Key limitation carried over:** these methods forecast what will be studied or recorded next, not what is true. For attacks, a forecast means "plausible given past patterns", not "will happen".

**Not yet checked:** (1) whether a stress test built only from earlier data has been shown to predict detector performance in a later untouched period; (2) the SynthAML paper, reported to compare synthetic and real anti-money-laundering alerts, where the generator is said to have used alerts from the test period (a useful precedent if confirmed); (3) whether hyperbolic embeddings have been used to forecast research or attack combinations. All three go into the Phase 0 prior-work search.

## 3. System design

Five stages. Each one can be tested on its own.

| Stage | Input | Output | Notes |
|---|---|---|---|
| 1. Technique graph | The data source's records as they existed at cutoff year T | Nodes = techniques; edges = techniques documented together | For ATT&CK, use the release published at T, not today's catalogue filtered by date |
| 2. Forecaster | Graph at T | Ranked list of unseen combinations | One simple method (shared-neighbour pair features), plus a frequency-matched baseline and a uniform random baseline |
| 3. Plausibility filter | Top-ranked combinations | Kept or rejected, with a reason | Checks that a description makes sense; it does not show the test predicts real performance |
| 4. Scenario to data | Kept combinations | Labelled synthetic cases written in the holdout dataset's own features | If a scenario cannot be expressed in those features, it is dropped |
| 5. Detector test | Training data before T; stress test; real holdout after T | Ranking agreement and catch-rate error | Alert threshold fixed on data before T |

**Why technique-level events for Stage 4.** Simulating real network traffic is a large project in itself. Instead, the detector sees sequences of abstract events (for example: new login location, privilege change, unusual data volume), each tied to a technique. This keeps the build feasible on a laptop and keeps the scenarios descriptive rather than operational.

**Encoding bias (the main validity risk).** If the generated scenarios and the real cases are both converted into data by our own rules, a detector can score alike on both simply because it recognises our encoding. A strong match would then prove little. So the real holdout must be independently observed data (real records with their own features, ordinary cases and labels), never real campaign reports re-encoded by us.

**Scope.** The core build uses one graph method. The disk embedding and multi-node growth are listed under Later extensions and are added only once we know what the simple method misses.

## 4. Phases

About 8 weeks at part-time pace, one domain only. Week one decides whether the core question can be answered at all.

| Phase | Weeks | Work | Deliverable |
|---|---|---|---|
| 0. Holdout data decision | 1 | Find a dataset with timestamps, labels, ordinary cases, and features that invented scenarios can be written in. Candidates: Elliptic Bitcoin dataset (crypto AML), IEEE-CIS card fraud. Pick the domain from this, not the other way round. Prior-work search in parallel | Chosen dataset and domain, or a decision to frame as a simulation benchmark; one-page prior-work note |
| 1. Graph and baselines | 2–3 | Build the technique graph as it stood at cutoff T. One simple forecaster; frequency-matched and random baselines | Forecaster vs baselines on combinations documented together after T |
| 2. Scenario generator | 4 | Plausibility filter; write kept combinations in the holdout's features | Reviewed scenario set, with the share that could and could not be expressed |
| 3. Detectors | 5 | Train several detector variants on data before T; fix thresholds on validation data before T | Detector set ready for testing |
| 4. Core experiment | 6–7 | Score detectors on the stress test and on the real later holdout | Ranking agreement, catch-rate error, real false-positive rate |
| 5. Write-up | 8 | Results, limits, what a team could do with them | Short paper or blog post; code repo |

Optional, off the critical path: reproduce the original method on a small OpenAlex graph to learn how it works.

## 5. Evaluation

| Experiment | Question | Metric |
|---|---|---|
| E1. Forecasting | Does the forecaster pick combinations that were newly documented together after T? | AUC and precision at top 100, against frequency-matched and random baselines |
| E2. Plausibility | How many forecasts survive review and can be written in the holdout's features? | Share kept; share expressible |
| E3. Ranking agreement | Does the stress test order detectors the same way as the real holdout? | Rank correlation (Spearman) across detector variants |
| E4. Calibration | How far off are the stress test's catch rates? | Absolute error in recall, in percentage points |
| E5. Real alert cost | Does the threshold set before T hold up later? | False positive rate actually produced on the holdout |

Example of why E3 and E4 are separate: the stress test gives two detectors 80% and 70% recall, the holdout gives 50% and 40%. Ranking is correct, but both catch rates are overstated by 30 points.

**Baselines.** A frequency-matched baseline (random combinations drawn in proportion to how often each technique really occurs) and a uniform random baseline. If the graph only beats uniform random, common techniques may explain the whole gain.

**Leakage rule.** Every stage uses only information that existed at cutoff T: the data source's release at T (not today's version filtered by date), training data before T, thresholds tuned before T. Outcomes are described as "newly documented together", not "happened". Generated scenario types used for testing never appear in training.

## 6. Tools and data sources

| Need | Choice | Cost |
|---|---|---|
| Attack technique data | MITRE ATT&CK versioned releases on GitHub (use the release that existed at each cutoff) | Free |
| Fraud typologies (Phase 5) | FATF typology reports | Free |
| Research papers (Phase 1) | OpenAlex API | Free |
| Graph work | Python, networkx, pandas | Free |
| Forecasting models | scikit-learn, XGBoost | Free |
| Disk embedding | gensim Poincaré model, or geoopt with PyTorch | Free |
| Fraud data simulator (Phase 5) | AMLSim (IBM) or PaySim | Free |
| LLM for filter and write-up | Local model through Ollama, or an API key | Free locally; API costs a few dollars |
| Machine | Your Mac | Enough for all phases at this scale |
| Real holdout candidates | Elliptic Bitcoin dataset; IEEE-CIS card fraud (Kaggle) | Free |

Reference code: SciMuse and Impact4Cast repos (artificial-scientist-lab on GitHub, MIT licence).

## 7. Risks and guardrails

| Risk | Effect | Mitigation |
|---|---|---|
| No usable holdout | Core question cannot be answered | Week-one data decision; fall back to a simulation benchmark and say so |
| Encoding bias | Stress test and holdout agree only because both use our rules | Holdout must be independently observed data, not re-encoded reports |
| Scenarios cannot be written in real features | Real datasets often use anonymised columns | Measure and report the share expressible; drop the rest |
| Forecasts are fantasy | Detector tested on attacks that cannot happen | Plausibility filter; frequency-matched baseline |
| Thin data | Attackers do not publish, so the graph is sparse | Report confidence; do not over-claim |
| Time leakage | Results look better than they are | Releases as of T; strict cut-off at every stage |
| Train and test on the same imagination | Score becomes meaningless | Hold out whole generated scenario types from training |
| Idea already published | Less original than hoped | Phase 0 prior-work search |
| Dual use | Scenario set could read as an attack playbook | Describe what an attack looks like in data only; no exploit code or step-by-step methods; review before sharing publicly |

## Later extensions

Added only after the core result, and only if the simple method visibly misses something.

- **Disk (circle) embedding:** angle = topic, radius = popularity; forecast links between nearby nodes (popularity vs similarity model).
- **Multi-node growth:** start from a strong pair, add the technique that keeps the group tightest, stop when coherence drops.
- **Second domain:** port the pipeline to another domain, as a separate project rather than a final-week add-on.

## 8. Open decisions and next steps

### Decisions needed

- [ ] Holdout dataset and therefore the domain (Elliptic, IEEE-CIS, or another dated labelled source)
- [ ] LLM: local model through Ollama, or an OpenAI or Claude API key
- [ ] Output target: CV project, blog post on The Capital Letter, or a research paper with a supervisor
- [ ] Weekly time budget, which sets whether 8 weeks is realistic

### Next steps

1. Check Elliptic and IEEE-CIS: timestamps, labels, ordinary cases, and whether invented scenarios can be written in their features
2. Prior-work search, including SynthAML and stress-test transfer studies
3. Set up the project folder and Python environment on the Mac

## Papers and references

### Core papers for this project

| Paper | Why it matters here |
|---|---|
| Gu & Krenn, *Interesting Scientific Idea Generation using Knowledge Graphs and LLMs* (SciMuse) | The method we adapt: concept graph, pair selection, LLM write-up, expert ratings |
| Gu & Krenn, *Forecasting high-impact research topics via machine learning on evolving knowledge graphs* (Impact4Cast) | Forecasting features and the time-travel test |
| Papadopoulos et al., *Popularity versus similarity in growing networks* (Nature, 2012) | The disk (circle) model for forecasting links |
| Benson et al., *Simplicial closure and higher-order link prediction* (PNAS, 2018) | Predicting multi-node combinations |
| Nickel & Kiela, *Poincaré embeddings for learning hierarchical representations* (2017) | How to learn disk coordinates from a graph |

### Related work we looked at

| Paper | Idea |
|---|---|
| Sourati & Evans, *Accelerating science with human-aware AI* | Tunes AI to avoid where human experts already work, producing "alien" hypotheses far from current research |
| Kargupta et al., *Sparking Scientific Creativity via LLM-Driven Interdisciplinary Inspiration* (Idea-Catalyst, 2026) | Finds distant source fields that can solve problems in a target field; reports gains in novelty and insightfulness |
| Frohnert et al., *Discovering emergent connections in quantum physics research via dynamic word embeddings* | Forecasts research directions with word embeddings that change over time |
| GYWI: author knowledge graphs plus retrieval for idea generation | Traces which papers inspired an LLM's research idea |
| Tshitoyan et al., word embeddings of materials science abstracts (Nature, 2019) | Predicted useful materials years before they were studied |
| Swanson, literature-based discovery (1980s) | The original idea: two literatures sharing a third hide an unknown link |
| KIT materials science knowledge network (Marwitz, Friederich, 2026) | LLM-extracted concepts and link-trend forecasting in materials science |

### Code and data

- SciMuse repo and Impact4Cast repo (MIT licence)
- SciMuse knowledge graph: Zenodo 10.5281/zenodo.13900962
- Impact4Cast graph and datasets: Zenodo 10.5281/zenodo.10692137
