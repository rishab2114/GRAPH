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

---

## 2026-11-18 19:00 — Step B, design (written before running anything)

**Question.** Are the 8 Elliptic-expressible motifs more common among illicit transactions than licit ones?
If none are, scenarios built from them cannot stress-test a detector, and step 4 needs rethinking.

**Rules, fixed now:**
- **Data:** time steps **1–34 only** (the training period). Steps 35–49 stay untouched for E3/E4.
- **Graph:** `elliptic_txs_edgelist.csv`, a directed transaction → transaction graph. Degrees are counted on the
  whole graph; no edge crosses time steps, so this equals counting within each step.
- **Thresholds:** k = ceil(max(95th percentile of in-degree, 95th percentile of out-degree)) over **all** step 1–34
  transactions, labelled or not. L = ceil(max(95th percentile of peel-run length, 95th percentile of depth)),
  chosen the same way. Labels play no part in choosing thresholds. (Wording clarified before any run.)
- **Motifs per transaction:**
  - fan_in: in ≥ k
  - fan_out: out ≥ k
  - coinjoin: in ≥ k and out ≥ k
  - pass_through: in = 1 and out = 1
  - peel_chain: lies on a run of ≥ L consecutive "peel" transactions (in = 1, out ≤ 2; the last one may have out = 0,
    which matches the vocabulary's "inner transactions" wording)
  - layering: longest path ending here ≥ L
  - mixing: coinjoin, and also next to another coinjoin transaction
  - smurfing: out ≥ k, and two of its successors reach a common transaction within 3 hops
- **Ruling:** the vocabulary defines layering as a path from an *illicit-labelled* source. Using labels in a
  motif would leak the answer into detector inputs, so I use the label-free depth version above.
  *Cost if wrong:* layering is measured as "deep paths" instead of "deep paths from known illicit transactions".
- **Output:** for each motif, its rate among illicit and among licit transactions, the lift (illicit ÷ licit)
  with a 95% Wilson interval for each rate, and how many illicit transactions show each *pair* of motifs. The pair
  counts preview which of the 28 expressible scenario pairs exist at all in real illicit data.

---

## 2026-11-18 19:20 — Step B, results and recheck

**Run.** `python -m gffs.motifs` on time steps 1–34 (136,265 transactions, 156,843 payment links, 34 components,
one per step; 3,462 illicit and 26,432 licit labelled). Thresholds from the frozen rule: **k = 2, L = 200.**
The output is in `results/motifs_elliptic.json`.

**Result under the frozen rules:**

| Motif | Illicit rate | Licit rate | Lift (illicit ÷ licit) |
|---|---|---|---|
| pass_through | 38.9% | 19.6% | **1.98** |
| fan_out | 6.2% | 23.8% | 0.26 |
| fan_in | 3.5% | 23.2% | 0.15 |
| smurfing | 0.1% | 1.7% | 0.07 |
| coinjoin | 0.2% | 3.7% | 0.05 |
| mixing_service | 0.0% | 1.8% | 0.02 |
| peel_chain | 0.0% | 0.2% | 0.00 |
| layering | 0.0% | 1.2% | 0.00 |

**Recheck. Was this a bug?** I looked at the raw distributions by class. This is descriptive only, and not used
to change any rule.

| Feature (95th / 99th percentile) | Illicit | Licit | Unlabelled |
|---|---|---|---|
| in-degree | 1 / 4 | 6 / 23 | 2 / 5 |
| out-degree | 2 / 2 | 2 / 5 | 2 / 5 |
| peel-run length | **182 / 182** | 14 / 74 | 363 / 1,248 |
| path depth | 55 / 147 | 56 / 211 | 171 / 592 |

- **No bug.** The graph is very sparse: half of all transactions have exactly one input link and one output link.
  So k = 2 is genuinely the 95th percentile.
- **The threshold rule was a poor choice for chains.** L = 200 comes mostly from *unlabelled* transactions, whose
  peel runs are much longer. Labelled illicit transactions *do* sit on long peel runs: 5% are on runs of 182 or more,
  against 14 for licit. The frozen L just misses them. **Lesson:** a percentile over all transactions is dominated by the
  77% that are unlabelled. A future rule should be fixed in advance on a principled scale, not a percentile of a skewed mix.
  I am not changing the rule after seeing labels. Any new rule goes in a new versioned design, and is tested only on new data.

**What this finding means.**
- **On Elliptic, illicit transactions look like *chains*, not *hubs*.** They are 2× more often pass-through, they
  sit on long peel runs, and they are 4–40× *less* often fan-in, mixer or CoinJoin hubs.
- **Most of the classic typology motifs are negatively associated with illicit labels here.** One likely reason is that
  Elliptic's labelled illicit set comes from particular categories (scams, malware, ransomware, Ponzi schemes and so on;
  Weber et al. 2019), not from mixing services.

**What this changes for the project:**
1. **Scenarios built from hub motifs** (fan-in, mixing, CoinJoin, smurfing) will look *licit* to a detector trained on
   Elliptic. That is not a failure. It is exactly the **blind spot** the project is meant to expose. But it means the
   stress test will report low recall for them, and E3/E4 will check whether real later illicit activity shows the same blind spot.
2. **Pass-through and long peel chains are the motifs real illicit activity already uses.** Scenarios combining them are
   the "familiar" end of the spectrum. A good stress test should contain both ends.
3. **Next step:** write the E3/E4 design (the detectors, their inputs, how scenarios are injected, the metrics) and
   commit it **before** anything touches steps 35–49.

---

## 2026-11-18 19:35 — Step C: freeze the E3/E4 design before touching steps 35–49

**Why now.** The core experiment is the only step that reads the untouched period. Fixing every choice first
(detectors, thresholds, scenario construction, metrics, what counts as success) is what makes the result
trustworthy. It is also what SynthAML did not do.

**Key choices, and the reasons for them** (full text in `docs/e3e4-design.md`):
- **Graph-only detectors.** Synthetic transactions cannot have Elliptic's anonymised features, and the detector
  must score real and synthetic transactions with the same function. *Cost:* the conclusions cover graph-feature
  detectors only.
- **Three comparison stress tests:** S0 recent data, S2 uniform pairs, S3 single motifs. Beating S0 shows value
  over doing nothing clever. Beating S2 shows that the *forecast* matters, not just "any synthetic motifs".
- **Scenario sizes come from the training-period illicit distributions,** not from a percentile over all
  transactions. This fixes the Step B lesson *in advance*, for data not yet seen.
- **I wrote down the most likely failure in advance:** detectors may flag almost no hub-motif scenarios, which
  would make E3 uninformative.

**Next:** build the parts that do not read steps 35–49: graph-feature detectors, the scenario generator and
injection, and S0/S2/S3. Test them on training-period data. S1 waits for tonight's literature run.

---

## 2026-11-18 19:55 — Step D: E3/E4 harness built; training-only dry run

**Built:** `src/gffs/scenarios.py` (motif subgraphs, pair scenarios, injection, graph features) and
`src/gffs/e3e4.py` (10 graph-only detectors, 5% false-positive thresholds, stress tests S0–S3 and S1, bootstrap
agreement and paired comparisons). 92 tests pass. Each of the 8 generated motifs is checked against the
Step B motif detector, so the generator and the detector cannot silently disagree.

**Not run on steps 35–49.** The design evaluates all stress tests together once S1 exists (after tonight's
literature run). That way no result can be seen before every input is fixed.

**Dry run on steps 1–34 only** (to catch crashes and time the run, about 10 s):
- Graph features for 136,265 training transactions; injection of 200 peel_chain → fan_in instances (16,044
  synthetic transactions).
- A random forest fitted on steps 1–28 flags **0.2%** of those synthetic transactions at its 5% false-positive threshold.
  → **The weakness predicted in the design is real:** graph detectors trained on Elliptic see these
  scenarios as licit. If this holds across scenarios, stress-test recall will be near 0 for every detector, and
  E3 cannot rank them. This is on record *before* the holdout is read.
- **Bug found:** chain length L was sampled per transaction, so one 182-transaction illicit chain dominated
  (L = 182 in 2 of 6 draws). Fixed so each chain counts once (test first, red then green). Logged as a deviation
  in the design file.

**Next:** review the new code with fresh eyes (bugs, leakage paths), then wait for the 00:10 UTC literature run.

---

## 2026-11-18 20:05 — Step E: leakage review of the E3/E4 harness

I read `e3e4.py` line by line, asking "can anything from steps 35–49 reach a choice?":
- **Thresholds:** from models fitted on steps 1–28 and scored on licit steps 29–34. ✓
- **Final models:** fitted on labelled steps 1–34 only. ✓
- **Scenario sizes:** drawn from labelled steps 1–34. Scenarios are injected into the step 29–34 graph. ✓
- **S2's 10 pairs:** a fixed seed (0), so they don't depend on results. ✓
- **S1's 10 pairs:** the top of the frozen v2 ranking, built from pre-2017 literature only. ✓
- **Holdout features:** computed from the step 35–49 graph alone. Elliptic has no edges between time steps, so
  nothing leaks across the cutoff through the graph. ✓
- **Synthetic transactions** are never used in training. ✓
- **Edge cases:** if every detector has the same recall on a set, Spearman is undefined. The harness reports NaN
  instead of crashing, and the comparisons skip those bootstrap draws.

No leak found. **Waiting on:** the 00:10 UTC literature run, which produces S1. After that, one run of
`python -m gffs.e3e4` gives the core result.

---

## 2026-11-19 00:12 — Step F: v2 literature run (the scheduled reminder fired)

**Checks before running.** The container survived the night: environment, Elliptic data and git all intact. The
first OpenAlex probe at 00:11 returned *"Anonymous search is paused while the search cluster recovers from heavy
load"*, a temporary outage on their side, not our allowance. A minute later the same query returned 200.
OpenAlex now states its limits: without a key, this server's address shares **$0.10/day**; a free key gives $1/day.
The response also invites agents to request a key using the user's email address. **Not done:** the owner declined
a key, and their email is private.

**Run:** `python -m gffs.literature_v2 --out results/`, started 00:12 UTC in the background. Every corpus page is
cached with its cursor, so a run cut off by the limit continues on the next one.

---

## 2026-11-19 00:25 — Step F, first attempt stopped by an OpenAlex outage; early finding

**What happened.** The run fetched 7 of the 14 v1 concept queries, then OpenAlex's search outage returned
(503, "Anonymous search is paused…"). The client gave up after about 30 s of retries. **Fix:** retry this specific
outage for up to about 25 minutes, with waits of 1 to 5 minutes (test first, red then green). The 7 finished queries
are cached, so the rerun does not repeat them.

**Early finding, already important.** Pre-2017 works matching both a v1 concept and an AML/crypto scope term:
peel_chain **0**, fan_in **1**, coinjoin **2**, pass_through **6**, fan_out **11**, mixing_service **45**,
layering **73**. The motif concepts that Elliptic can express barely appear in the pre-2017 literature.

**What this implies, before the run finishes:**
- In the v2 graph, most of the 8 target concepts will be **isolated or nearly isolated nodes.** Many of their 28
  pairs will have no shared neighbours at all, and the scenario ranking among them will rest on almost no data.
- **v2's design anticipated part of this.** Context nodes give the graph structure, and forecasting skill is measured
  on the whole graph. But the *scenario* ranking still only uses target pairs. If most targets have 0–2 works, S1's
  ranking will be close to arbitrary, and E3 will mostly test "motif scenarios in general", not "forecast-chosen" ones.
- **Not changing anything now.** The design is frozen, and this gets reported as a result: *a literature-based
  forecaster cannot rank crypto-laundering motifs before 2017, because the literature hardly mentions them.* That is
  itself evidence on whether the method can work for a new attack domain.

---

## 2026-11-19 00:35 — Step F, second attempt: OpenAlex now requires a key for paging

**What happened.** The rerun cached 13 of 14 concepts. It then stopped on the last one, `cash_out`, which has more
than 200 matching works, with **401 "API key required for cursor paging."** OpenAlex has changed its terms: without
a key, only the **first page (200 works)** of any query can be read. Probes right after this returned 429
("anonymous search is temporarily rate-limited… retry in 37s") for every request style.

**Counts so far** (pre-2017 works matching a concept and a scope anchor):

| Elliptic-expressible | Works | | Not expressible | Works |
|---|---|---|---|---|
| peel_chain | 0 | | structuring | 131 |
| fan_in | 1 | | dusting | 186 |
| coinjoin | 2 | | round_tripping | 9 |
| pass_through | 6 | | dormancy | 9 |
| smurfing | 9 | | velocity | 5 |
| fan_out | 11 | | cash_out | >200 (not fetched) |
| mixing_service | 45 | | | |
| layering | 73 | | | |

**Consequence.** v2 needs the *whole* scope corpus: every pre-2017 AML, crypto and fraud work with its tags.
That is thousands of works, so many pages. **Without a key, the v2 design cannot run from any machine.** Running
from the owner's Mac would not help, because the paging rule applies to every anonymous request.

**Options for the owner** (I am not choosing for them; the design is frozen):
1. **A free OpenAlex key.** The v2 design runs exactly as frozen.
2. **A new v3 design** using only one-page and count queries (OpenAlex `group_by`). Count the co-occurring tags for
   each target concept's works instead of downloading the corpus. This is fewer requests, but it changes the graph
   definition and needs its own frozen file before running. *Being checked now: whether `group_by` still works anonymously.*
3. **Stop the literature arm here** and report: *the 8 motif concepts appear in 0–73 pre-2017 works, so a literature
   graph cannot rank them.* Run E3/E4 with S2 and S3 only, which needs no literature, and keep S1 out.

**Retry reminder:** the 00:10 reminder told me to retry nightly if the *allowance* ran out. This is a different
block, a policy that won't reset overnight, so I am **not** scheduling a nightly retry. The owner has to choose.

**00:40 — group_by probe:** still 429 (anonymous search rate-limited under load, "retry in 32s"). Whether
count-only queries work without a key is **unknown**. The loop is paused: the next step depends on the owner's
choice between options 1–3.

---

## 2026-11-19 01:00 — Step F, third attempt: with the owner's OpenAlex key

**Decision (owner):** add a free OpenAlex key so v2 runs exactly as frozen. Two other options were considered and
recorded: a smaller v3 using the OpenAlex connector's count queries, or dropping the literature arm. The key is
stored as a network secret on the cloud environment and injected by the proxy only into requests to
api.openalex.org. It is not in the code, the logs or git.

**Checks:** cursor paging now works ("money laundering" alone has 7,321 pre-2017 works). The full v2 corpus
(every pre-2017 work matching any v1 scope anchor) is **105,469 works = 528 pages**. Each page is cached as it
arrives, so if the key's daily allowance runs out, the next run resumes. Nothing in the design changes.

---

## 2026-11-19 01:30 — Step F: night 1 progress

- **v1 concepts:** all 14 fetched. `cash_out` has 3,866 pre-2017 works, far more than any other concept. That is
  likely because "cash out" is common in ordinary finance text. It is not Elliptic-expressible, so it doesn't
  affect the scenario pairs, but it will be a hub in the graph.
- **Corpus:** **135 of 528 pages** (about 26%, 79 MB cached) before the key's daily *search* allowance ran out.
  Plain filter queries still work; only search-based ones are capped. That is about 155 search pages per day, so
  about 3 nights remain.
- **Scheduled:** a resume at 00:10 UTC on 2026-11-20 (a stored reminder, outside the container). Each night
  re-schedules the next until the corpus is complete, or until 2026-11-25. When the corpus completes, the reminder
  also runs the frozen core experiment.

---

## 2026-11-19 02:10 — Loop 2 start: the owner asked for the write-up draft and the seed check

**Plan, in order of value while the literature download waits for 00:10 UTC Nov 20:**
1. **Control seed check (running).** The control's random baseline scored AUC 0.530, about 3 standard errors from
   0.5. Rebuild the exact test pairs (same rng and draw order as `run_control`), confirm seed 0 gives 0.530, then
   score seeds 1–20. *Why:* a random scorer above 0.5 would mean a bug, such as score order linked to labels through
   sorted pairs. If seeds 1–20 centre on 0.5, seed 0 was chance.
2. **Write-up draft** (`docs/paper/draft.md`): what is known now, with the core result left as a clearly marked
   placeholder. *Why:* writing exposes gaps in the argument early, and the draft can be finished quickly once E3/E4 runs.
3. **Dashboard:** add the motif findings and the prior-work context.
4. **Then:** a review pass over everything new.

**02:25 — write-up draft written** (`docs/paper/draft.md`). Every number cites its source file; the core result
(§4.5) is a marked placeholder.
*Gaps the draft exposed, now on the to-do list:*
1. The abstract's headline result is still pending.
2. §4.4's lesson (a percentile threshold) should become a rule written in advance for any future motif work.
3. The related-work search was a web search, not a systematic review. A citation-trail check is needed before submission.

**02:40 — control seed check done** (`scripts/control_seed_check.py`, `results/control_seed_check.json`).

| | Value |
|---|---|
| Seed 0 (rebuilt pairs and labels) | 0.5297, matching the logged 0.530, so the rebuild is exact |
| Seeds 1–20, mean | 0.501 |
| Seeds 1–20, standard deviation | 0.0089 |
| Theoretical null standard error | 0.0095 (928 positives) |

**Conclusion:** the random scorer is unbiased, and seed 0 was a draw about 3.1 standard deviations high. This is not
a bug: the pair order (sorted by id) does not correlate with the labels through the scores. `control.md` and the
draft are updated. The control's conclusions are unchanged, since every method beat random by far more than this.

**02:40 — dashboard:** added "What illicit transactions look like" (8 motifs, illicit vs licit share, from
`results/motifs_elliptic.json`). The page is now version 3. Its built-in check is read below.

---

## 2026-11-19 02:55 — Citation-trail search (through the OpenAlex connector)

**Why:** the draft flagged that the prior-work search was a web search, not a systematic check. A citation
trail from the two anchor papers is the cheapest way to find the most relevant later work.

**Done:**
- **All 45 works citing SynthAML,** listed in full.
- **The 124 works citing Weber et al. 2019 that mention stress tests, drift, shift, synthetic data or unseen
  typologies** (top 40 read).
- **A targeted search** for "stress test / synthetic" × "fraud / AML / intrusion" × "predict future performance /
  out-of-time / temporal holdout" since 2018: 3 hits, none relevant.

**Relevant finds:**
1. **Maganti 2026, *When Graph Structure Becomes a Liability*** ([arXiv 2604.19514](https://arxiv.org/abs/2604.19514)).
   - **Leakage-free Elliptic evaluation:** random forest on raw features scores **F1 = 0.821**. This independently
     confirms our reproduction (0.815, Phase 0).
   - **Graph features fail under shift:** "randomly wired graphs outperform the real transaction graph" under
     temporal shift. **This bears directly on E3/E4:** our detectors are graph-only, so they may be weak on 35–49.
     That raises the chance that E3 is uninformative, as already predicted in the design.
   - **Test-period adjacency leakage:** they report a 39.5-point F1 gap from training-time exposure to test-period
     edges. Our design already avoids this: holdout features come from the step 35–49 graph alone, and models are fitted on 1–34.
2. **Graph-only Elliptic detectors exist:** "FT-TDGCL … unlike approaches that depend on the 166 anonymized Elliptic
   attributes" (2024). This is precedent for a graph-only detector family.
3. **Drift reviews:** "Money Laundering and Fraud detection under concept drift: A Systematic Review" (2025);
   "Explainability … in Concept and Data Drift" (2025). Both are general, with no predictive stress-test check.
4. **Generators and benchmarks citing SynthAML:** AMLgentex (2025), Tide (2026), TransXion (KDD 2026). None tests
   whether a stress test predicts later real performance.

**Conclusion:** the specific claim (a leakage-free pre-cutoff stress test, checked for both ranking and
calibration against a later real period, against a recent-data baseline) still appears unaddressed. Maganti 2026
becomes a key citation, both as a check on our Elliptic numbers and as a warning about graph-only detectors.
`docs/paper/draft.md` §2 is updated.

---

## 2026-11-19 03:10 — Harness: robustness cutoffs built in (still not run on the holdout)

**Why:** the frozen design says the rolling cutoffs (24, 29, 39) are "a robustness check, reported with the main
result". Building them now means the single real run produces everything, so there is no second look at the
holdout and no temptation to pick a cutoff afterwards.

**Change:** `e3e4.run_cutoff(d, cutoff, holdout_end, …)` does one frozen run per cutoff:
- **Thresholds:** fitted on steps up to cutoff − 6, set at a 5% false-positive rate on licit steps cutoff − 5 to cutoff.
- **Models:** refitted on steps up to the cutoff.
- **Scenarios:** injected into the graph of steps cutoff − 5 to cutoff.
- **Holdout:** steps cutoff + 1 to holdout_end, split into before and after the shutdown when the window contains step 43.

`main()` runs the main result (cutoff 34, holdout 35–49) plus cutoffs 24, 29 and 39 (each with the next 10 steps).
S2's pairs are unchanged (same seed and order). New test: `test_run_cutoff_on_tiny_data_produces_every_stress_test`.
94 tests pass.

**Not a design change:** this implements what the design already lists. It is noted here so the record shows the
cutoffs were fixed before any result existed.

---

## 2026-11-19 03:20 — Loop 2 ends: everything that doesn't need the literature data is done

**Done this loop:**
- **Control seed check:** seed 0's 0.530 was chance (seeds 1–20 average 0.501).
- **Write-up draft:** `docs/paper/draft.md`.
- **Dashboard:** a motif card.
- **Citation-trail search:** Maganti 2026 confirms our random-forest result, and warns about graph-only features.
- **Harness:** robustness cutoffs built in.
- **Handoff refreshed.**

**What remains is driven by data, not by more work here.** The stored reminder resumes the corpus download at
00:10 UTC each night. When it completes, it builds the graph, runs the frozen core experiment once, logs, pushes
and reports. The hourly timer is stopped, because ticking while the only remaining input is rate-limited would
change nothing.

---

## 2026-11-20 13:22 — Night 2 resume (the reminder reached the session 13 h late)

The stored reminder fired at 00:10 UTC but reached this session at 13:21. The container survived: the environment,
the Elliptic data and the 135 cached corpus pages are all intact. Today's search allowance was untouched, so the resume
started at 13:22. The late delivery costs nothing except wall-clock time, because the allowance is daily. **Lesson for the
remaining nights:** the reminder can arrive hours late, so each night's run may start late. That doesn't affect the
result, only the finish date.

**13:24 — night 2 done:** the corpus reached **296 of 528 pages** (161 today) before the daily search allowance ran
out. About 232 pages remain, so about 2 more nights. A night-3 resume is scheduled for 00:10 UTC on 2026-11-21.

---

## 2026-11-21 00:55 — Step F complete: v2 literature graph built

**Download:** finished on night 3. 529 pages and 105,533 pre-2017 works. The tag source is `concepts`, OpenAlex's
legacy tags, which is first in the frozen preference order. **500 context nodes** passed the frozen filters. 80,689
works link at least one node. Output: `results/literature_graph_v2.json`.

**Forecasting test** (graph at 2013, pairs newly linked by 2016; trained on 2010 → 2013; all pre-cutoff literature):

| | Value |
|---|---|
| Nodes at 2013 | 512 |
| Density | **0.37** (between ATT&CK's 0.49–0.66 and the Impact4Cast control's 0.03) |
| Candidates / positives | 82,710 / 6,182 |

| Method | AUC | Gain over popularity [95% CI] | Within-popularity AUC | P@100 |
|---|---|---|---|---|
| frequency (popularity) | 0.576 | – | 0.518 | 0.05 |
| random | 0.505 | −0.072 | 0.504 | 0.08 |
| **logreg_all** | **0.818** | **+0.241 [+0.234, +0.249]** | 0.814 | 0.46 |
| hgb_all | 0.816 | +0.240 [+0.232, +0.247] | 0.811 | 0.48 |
| train_best_single | 0.794 | +0.218 | 0.802 | 0.55 |
| structural_rank_mean | 0.789 | +0.213 [+0.207, +0.219] | 0.792 | 0.56 |
| logreg_popularity | 0.729 | +0.153 | 0.727 | 0.44 |
| hybrid (exploratory) | 0.714 | +0.138 | 0.788 | 0.30 |

**Primary hypothesis: holds.** Both logreg_all and structural_rank_mean beat popularity, with intervals far above 0.
So, by the frozen rule, **scenarios are ranked by logreg_all.**

**On pairs involving an Elliptic-expressible concept** (2,871 candidates, only 60 positives): structural_rank_mean
reaches AUC 0.808, against 0.724 for popularity. This is the same direction, but with few positives, so it is weaker evidence.

**Why it works here but not on ATT&CK.** The density story holds again: 37% linked here, against 49–66% for ATT&CK.
Unusually, the popularity baseline is weak here (0.58, against 0.72–0.79 on ATT&CK). In the research literature,
popular concepts like "Money laundering" or "Internet" already link to almost everything, so the remaining unlinked
pairs are not the popular ones.

**Caveat (concept quality):** OpenAlex's legacy concept tagger assigns some nonsensical context nodes, for example
"Government (linguistics)", "Context (archaeology)" and "State (computer science)". They passed the frozen filters,
so they stay. They add noise, which works *against* finding structure, so the result is conservative in that respect.

**Scenario ranking at 2016:** 25 of the 28 expressible pairs are still unlinked (3 were already co-mentioned). The top 10
go into S1:
1. mixing_service + smurfing
2. pass_through + smurfing
3. fan_out + layering
4. layering + pass_through
5. coinjoin + layering
6. fan_out + mixing_service
7. fan_in + layering
8. fan_in + mixing_service
9. layering + peel_chain
10. mixing_service + pass_through

**Next:** the frozen core experiment (`docs/e3e4-design.md`), run once.

---

## 2026-11-21 01:05 — Step G: frozen core experiment run once (E3/E4/E5)

**Run:** `python -m gffs.e3e4 …` (main cutoff 34 plus robustness cutoffs 24, 29, 39), about 4 minutes, run once.
Full write-up: `docs/results/e3e4.md`.

**Against the frozen success criteria: not met.** S1 (the graph forecast) never beats both S0 (recent data) and S2
(random pairs). Against S2 alone, S1 ranks better in 2 of 7 windows, both where all synthetic sets rank poorly. It is no
better in the post-shift windows, and never better on calibration. *(Corrected 01:15: an earlier version of this entry
said "indistinguishable from S2 everywhere". The comparison table shows that overstated it.)* The forecast picks motif pairs well as a
forecaster, but the chosen pairs are not a better stress test than random ones.

**Pattern found within the pre-specified windows:**
- *Before or without a shift,* recent data is the better stress test (ρ 0.62–0.99, against roughly 0 for synthetic sets).
- *After the dark-market shutdown,* all synthetic motif sets beat recent data on calibration (cutoff 34: error 0.047 against
  0.120, CI of the difference [−0.085, −0.056]). At cutoff 39 they also beat it on ranking (Δρ +0.18 [+0.08, +0.58]).
- *Mechanism:* linear detectors both flag unfamiliar synthetic shapes and survive the shift. Tree ensembles do neither.

**Status:** reported honestly as **not pre-registered** (the hypothesis was about S1, not "any synthetic set"). It rests
on one shift event at two overlapping cutoffs, so it is a lead for a prospective test.

**Pre-registered risk:** partly realised. Synthetic recall is low (about 8–10% on average), but the spread across
detectors kept the ranking informative.

**Next:** update the draft (§4.5 and abstract), the dashboard and the handoff, then push.

---

## 2026-11-21 19:30 — Option 1 scoping: a second dataset to confirm the after-shift lead

**Requirement:** a money-flow graph (so motifs can be injected), labels, timestamps, and a *dated, documented* shift that
is independent of Elliptic's dark-market shutdown. That is the minimum for a test that isn't circular or post hoc.

**What I found (two web searches):**
- **Elliptic2 (2024):** 122K labelled subgraphs. The search turned up no timestamp field for a temporal split, so no shift can be tested.
- **Elliptic++:** the same 49 steps and the same shutdown, so not independent.
- **IBM AMLworld:** synthetic, and its laundering is *generated from motifs*. Testing motif stress tests on it is circular.
  It could only check the mechanism, under a designed shift.
- **Ethereum phishing graphs:** timestamps and labels, but no documented shift event.
- **Ethereum around the Tornado Cash sanctions (OFAC, 8 Aug 2022):** a real, dated regulatory shock to laundering
  behaviour (NY Fed Staff Report 1112; arXiv 2510.09443). But there is no labelled illicit dataset. Labels would have to
  be built from sanctions lists and on-chain heuristics, and "labelled mixing addresses are exceptionally scarce"
  (arXiv 2505.09892). It needs public chain data (e.g. BigQuery `crypto_ethereum`) and weeks of work.
- **DGraph-Fin:** a contact graph, not money flows, so motifs don't apply.

**Assessment:** no off-the-shelf dataset gives a clean, independent confirmation. Asking the owner to choose between
(a) building the Tornado Cash sanctions dataset (best evidence, biggest effort), (b) a mechanism check on synthetic
AMLworld with a designed shift (fast, but not real-world confirmation), and (c) reporting the lead as unconfirmed.

---

## 2026-11-21 19:45 — Owner's choice: mechanism check → Tornado Cash dataset → later crypto events

**Reasoning before building:** a naive synthetic check would be circular. If the world's new attacks use the same
motifs as the stress test, the test sees the future by construction. So the check separates two explanations:
H-gen (unfamiliar shapes expose over-specialised detectors) and H-match (scenarios resemble the new attacks). It does
this by keeping a motif family (C) out of both the training and the post-shift attacks. Predictions and thresholds are
frozen in `docs/mechanism-design.md`, which was committed before any generator code was written.

**Stage 3 note:** "recent crypto updates" is read as later dated shocks, for example the **lifting of the Tornado Cash
sanctions in March 2025**. That would be a second, opposite shift. To confirm with the owner before stage 3.

---

## 2026-11-21 20:10 — Mechanism check built (`gffs.synthworld`, `gffs.mechanism`)

- **Generator:** 40-step Elliptic-like worlds. Licit flows are chains and trees with some fan-in. Illicit activity is
  motif instances from a family. Labelled shares: 30% of licit, 80% of illicit. The training period is identical across
  W0, W1 and W2 for a given seed (tested).
- **Harness:** `run_cutoff` now accepts caller-defined stress sets (SA, SB, SC). The defaults are unchanged.
- **Tests:** 101 pass.
- **Timing:** about 10 s per world, so 120 runs (20 worlds × 3 types × 2 family splits) take about 20 minutes.
- **One-world smoke run (W1, seed 0):** SB ρ 0.93, SC ρ −0.71, S0 ρ 0.02. *Not evidence:* one world, logged only so the
  record shows what was seen before the full batch.

---

## 2026-11-21 20:35 — Mechanism check results (`docs/results/mechanism.md`)

**Against the frozen predictions:**
- **W0 no shift:** recent data wins. ✓ (SC wins 0/40.)
- **H-match:** matching scenarios beat recent data after a plain shift. ✓ (40/40, on both error and ranking.)
- **H-gen:** unfamiliar scenarios beat recent data after a plain shift (≥14/20). ✗ (Ranking wins 2/20 and 6/20; error
  wins 8/20 and 20/20, depending on the split.)
- **SA ≈ S0** (no injection artefact). ✓

**Not predicted:** under shift *with camouflage* (W2), unfamiliar scenarios beat recent data in 38–40 of 40 worlds on
both metrics, and out-rank the matching scenarios.

**Consequence for the Elliptic lead:** "any synthetic scenarios beat recent data after a shift" is too strong. The
supported version is: scenarios that *cover the future attack shapes* beat recent data after a shift, and unfamiliar
shapes add value when attackers camouflage. That makes the forecasting step matter in principle, because it is what aims
coverage. On Elliptic, though, the literature forecast didn't beat random pairs (§4.5).

**Next (stage 2):** Tornado Cash sanctions dataset. It needs Ethereum chain data (BigQuery public dataset) and labels.
Billing needs the owner's confirmation before any setup.

---

## 2026-11-22 — Stage 2 scoping: Tornado Cash dataset (owner chose "scope it down first")

**Problem:** BigQuery needs a Google service-account key inside the environment. There are no credentials here,
and even free dry runs need authentication.

**Alternative found:** the AWS Public Blockchain Data open bucket. Ethereum daily Parquet files, anonymous reads,
no billing.

**Measured:**
- **Transactions:** 3.9 s per day for 4 columns.
- **Logs:** 50 s per day.
- **Traces:** not needed.
- **Tornado router transactions:** 739 (1 Jul) → 828 (8 Aug, sanctions day) → 65 (1 Sep), a **−91% collapse**. A clear,
  dated shift.

**Full scope** (`docs/tornado-scoping.md`): ±6 months around 2022-08-08, mixer-associated labels plus OFAC SDN addresses,
weekly address graphs, the same pipeline. About 5.5 h of one-time reading, at no cost.

**Risks written down before building:** the label-population change at the shift, the account-vs-UTXO difference,
the sparse post-sanction positives, and the contract hubs.

**Next:** the owner approves the scope. Then I freeze the analysis design, then build.

---

## 2026-11-22 — External review evaluated (`docs/review-2026-11-22.md`)

The owner shared an external review. Checked claim by claim against git and the data:
- **Verified:** every factual claim, including all commit times.
- **Rejected:** nothing.
- **Accepted and fixed now:** the density-causation overstatement (draft, `control.md`, dashboard v4) and the "last rush"
  wording.
- **Accepted for stage 2:** a mixer-participation target only; Tornado edges removed from detector inputs;
  label-independent sampling; unlabelled controls with alert rates instead of a false-positive rate; Ethereum-specific
  graph and motifs; depositors and recipients reported separately; historical OFAC records; placebo dates.
- **Added by the cross-check:** this log's clock times are approximate, and **git commit times are authoritative**;
  post-shift n = 169; no multiplicity correction; the forecast arm was starved of literature; the mechanism worlds share
  generators with the stress tests.

**Next:** the Tornado pilot on pre-sanction data only (`docs/tornado-pilot-plan.md`), then a frozen design, then the full build.

**Note on this log's timestamps:** entries before this one give approximate times written from memory. Where they
differ from `git log`, git is correct.

---

## 2026-11-22 — Tornado pilot started (owner approved; `docs/tornado-pilot-plan.md`)

**Built, test-first** (107 tests pass):
- **`gffs.ethereum`:** anonymous reads of AWS open data; decoding of Tornado Deposit and Withdrawal events.
- **`gffs.tornado_pilot`:** a resumable per-day extractor. A check in the code makes it impossible to read any date on or
  after 2022-08-08.

**Checks on the method:**
- **Event identifiers verified independently:** the keccak hashes of `Deposit(bytes32,uint32,uint256)` and
  `Withdrawal(address,bytes32,address,uint256)` equal the topic0 values seen in the 2022-07-01 logs. *I caught and fixed
  a vacuous version of this test,* which compared a constant with itself.
- **Plain transfer vs contract call:** a plain ETH transfer between accounts uses exactly 21,000 gas. This splits the
  interaction graph from the value-transfer graph (P4), and flags contract callees (P3), without reading contract code.
- **Sampling frame (P5):** transaction *senders* in January 2022, before the window. Senders are always externally owned
  accounts, and no label enters the frame's definition.

**Running:** the frame (31 days), then 2022-02-08 to 2022-08-07 (181 days), about 3 h, in the background.

**P7 (historical OFAC records), answered from primary sources:** OFAC Recent Actions pages fetched and saved as
dated snapshots in `config/ofac/`.
- **2022-08-08:** 38 Ethereum addresses. **All 4 ETH pools and the router used in the pilot are on it** (checked
  address by address).
- **2022-11-08:** delisting and redesignation (with a DPRK basis), 91 addresses, including all 38 originals.
- **2025-03-21:** Tornado Cash removed (relevant to stage 3).

**Summary code:** `gffs.tornado_pilot_summary` answers P1–P6 and P8. Its key P1 check is **leaf-index continuity**:
each pool numbers its deposits 0, 1, 2, …, so any gap reveals missed events. 108 tests pass.

---

## 2026-11-22 — Pilot corrections, planned before any code change (owner's review of P1–P8)

**Bug found first:** the AWS `transactions.value` column is a **double**, but the extractor's sample-week code compared
it with the string `"0"`. pyarrow raises `ArrowNotImplementedError`, so the run would have crashed on 2022-03-07. I
stopped it after 20 completed days (2022-02-08 to 2022-02-27). Those files are kept and will not be redone. Separately,
wei values above 2^53 lose precision as doubles. The pool denominations are exact (checked), and the pilot never relies
on exact non-denomination amounts.

**Corrections, and the reasoning for each:**

1. **Contract evidence (P3).** `gas_used > 21000` does *not* prove that the recipient is a contract: calldata to an
   ordinary account also costs gas. Replace it with **historical contract evidence**: the AWS `contracts` table, which
   records every contract with its creation block and time. An address is classified **as of date d** as:
   - **contract:** created before d;
   - **EOA:** seen as a transaction sender on or before d (only externally owned accounts can send transactions in 2022);
   - **unknown:** neither. This class is kept, never folded into either of the others.

   The old `*.callees.parquet` files are relabelled "destinations of non-simple transactions (type unknown)" and are
   **not used as contract evidence**.
2. **Edge categories (P4).** `gas_used == 21000 ∧ value > 0` identifies only *simple transfers*: no calldata, and the
   destination ran no code. It is **not** every ETH value transfer. Each successful transaction is put in **exactly one** of:
   - **simple_transfer:** 21,000 gas, value > 0;
   - **value_call:** value > 0 and more than 21,000 gas (ETH sent with calldata or to code);
   - **call:** value = 0;
   - failed transactions (`receipt_status = 0`) are excluded and counted separately.

   Contract calls and value transfers are never mixed.
3. **Withdrawal completeness (P1).** Leaf-index continuity covers deposits only. Independent checks for withdrawals:
   - **(a)** nullifier uniqueness;
   - **(b)** on sample days, the **traces** table: every successful ETH transfer out of a pool contract should correspond
     to a decoded Withdrawal. The recipient should receive `denomination − fee`, and the relayer should receive `fee`;
   - **(c)** every withdrawal and deposit transaction must have `receipt_status = 1`.
4. **Role attribution (P2).** Four roles, kept apart:
   - transaction sender;
   - depositor (the sender of the deposit transaction);
   - withdrawal recipient (the event's `to` field);
   - relayer (the event's `relayer` field, zero address excluded).

   Self-withdrawals (sender = recipient, fee 0, zero relayer) are counted separately.
5. **No future information at an evaluation cutoff (P5/P6/P8).** For each cutoff c (placebos 2022-05-08 and 2022-06-08):
   - **Relayer set:** only relayers seen *before* c.
   - **Contract/EOA classification:** as of c.
   - **Features:** the non-Tornado graph of the 7 days *before* c.
   - **Outcome:** *first* Tornado participation in the 8 weeks *after* c, by frame addresses with no participation seen
     between the window start and c. Nothing after c enters features or sampling.
6. **Sampling frame (P5).** Measure how many eventual participants were already active in January, and how many are
   **new addresses** that the frame cannot represent.
7. **Feasibility of prospective detection.** At each placebo cutoff, compare *descriptive* pre-cutoff non-Tornado
   activity between future participants and other frame addresses. This means shares and degree distributions, plus
   one pre-specified univariate AUC (non-Tornado degree), on pre-sanction data only. **No model is fitted, no detector is
   compared, and nothing after 2022-08-08 is read.**
8. **Placebo pipeline (P8):** run steps 5–7 end to end at both placebo cutoffs, not only check that files exist.

**Order:** fix the extractor and resume it (logs, about 2.5 h) → build the contracts registry and the add-on
transactions pass (with status and edge categories) in parallel → trace checks on sample days → summary and report → go/no-go.

**Corrections built** (`gffs.tornado_aux`, 110 tests pass):
- Exclusive edge categories: `simple_transfer`, `value_call`, `call`, `failed`.
- Independent withdrawal matching against traces: the recipient gets `denomination − fee`, the relayer gets `fee`, and
  any unexplained pool outflow is counted as an orphan.
- Event-transaction success status.
- Feature-week edges, the 7 days before each placebo cutoff.
- An as-of-date contract registry, built only from contracts created before 2022-08-08 and only for the addresses the
  pilot uses.

**Contract evidence validated:** on 2022-06-01, the contracts table holds 7,229 unique addresses, exactly the set of
successful `create` traces (0 missing either way). So it includes factory-created contracts. There were 7,247 rows for
7,229 addresses: a few addresses appear twice, likely redeployment at the same address. The registry keeps the
*earliest* creation.

**Costs measured:** contracts ≈ 0.7 s per day; traces ≈ 3.4 s per day (6 columns).

**Withdrawal check corrected (2026-11-22).** The first trace check on 2022-02-08 reported 6,481 "unexplained" pool
outflows. Investigated rather than accepted: **6,480 were `delegatecall`s** (the pool delegating into its hasher during
Merkle insertion). In these traces a delegatecall carries the transaction's value in its `value` field but moves no ETH.
With only real `call`s on that day:
- **317 outflows, 314 explained;** every withdrawal transaction has a real outflow.
- **2 withdrawals had a payment trace marked failed (status 0)** inside a successful transaction with an emitted event.
  Tornado's pool requires both payments to succeed, so this is most likely a status-labelling quirk in the ETL. These are
  counted as `status_anomaly`, not as missing events.

The check is restructured into **two directions**:
- **events → traces:** exact matches, status anomalies, amount mismatches, events without any outflow;
- **traces → events:** transactions with a successful real pool outflow but **no decoded Withdrawal**. This is the
  completeness measure; it should be 0.

The 7 add-on outputs computed with the flawed filter were deleted and are being recomputed. The main extractor's daily
files were not touched. 110 tests pass.

---

### 2026-11-22 — Pilot run completed; three more corrections before the report

**Container restart.** The session's container restarted while the extractor and the aux pass were running. The
completed daily files had been written to disk, so nothing was lost: 174 of the 181 main days and 144 aux days were on
disk. Both jobs are resumable and were restarted without redoing completed days. The main extraction is now
**complete: 181 days, 2022-02-08 to 2022-08-07, 44,293 deposits, 42,334 withdrawals, 0 undecoded pool events,
0 deposits without a sender.**

**Deviation from the plan in item 7 above: no univariate AUC.** I had planned one descriptive AUC (non-Tornado degree)
at each placebo cutoff. It was **removed before it was ever computed**, for two reasons:
- the pilot plan (P8) says the placebo cutoffs' *results belong only to the frozen study*;
- the owner's instruction says *no detector comparisons* yet.

A degree score is a baseline detector, so computing its AUC at the placebo dates would leak study results into the
design. **What I did see:** a dry run of the report printed coverage numbers that include the share of future
participants with any non-Tornado activity in the feature week, alongside the same share for the rest of the frame
(≈50% vs ≈10%). That contrast is a crude signal reading at the placebo dates. I disclose it here. It will not be used as
evidence in the study, and the frozen design must not cite it.

**Correction 1: the contract-registry step had never run.** The address-collection line used a pandas method on an
Arrow array and crashed. This was found when the chain first reached it, so no registry was ever built with it. Two
changes:
- **Membership test.** The registry needs 3,393,824 addresses (feature-week edge nodes plus every depositor, recipient,
  relayer and withdrawal sender). Rebuilding an Arrow lookup for that set for each of ~2,560 days was replaced by one
  Python set, built once.
- **Missing partitions are listed, never silently skipped.** The bucket has no `contracts` partition for 2015-07-30 to
  2015-08-06, 8 days. That matches Frontier's thawing period: until about 7 Aug 2015 the gas limit allowed no
  transactions, so no contracts can exist there. Every other day in [2015-07-30, 2022-08-08) is present.

  A sanity run on 2019-12-14..21 found the 0.1, 1 and 10 ETH pools created on 2019-12-16, consistent with their known
  deployment.

**Correction 2: the "orphan" pool outflow was a reverted transaction.** With all days checked, exactly **1** transaction
had a successful real pool outflow and no Withdrawal event (2022-02-08, `0x232b84…`). I inspected it rather than
accepting it as a missed event:
- the root call is marked `Reverted`, because a later subcall ran out of gas;
- yet the traces table still marks the pool's child payment `status = 1`.

In a reverted transaction no ETH moves and no logs survive, so this is not a missed event. The completeness check now
uses the **receipt status of the transaction** (`tx_ok`), and outflows inside reverted transactions are counted
separately (`outflows_in_reverted_tx`). There is a test for exactly this case (114 tests pass).

The 181 aux outputs computed before the fix were moved aside (scratchpad, `aux_oldcode/`) and are being recomputed with
the corrected check. The main daily files and the feature-week edge files are not affected.

**Correction 3: the 44 `status_anomaly` withdrawals are explained, not just labelled.** All 44 are in transactions whose
receipt succeeded and that emitted the Withdrawal event. The ETH pool source (tornado-core `ETHTornado.sol`,
`_processWithdraw`) has `require(success)` on **both** the recipient payment and the relayer payment. A failed payment
would revert the whole transaction, and the event would not exist. So status 0 on those traces is an inconsistency in
the traces table's status field, not a failed withdrawal.

Two cautions:
- this argument rests on the repository source; the deployed bytecode was not compared here;
- the same file has `require(msg.value == denomination)` for deposits. That is why a decoded Deposit implies the
  denomination, and why deposit completeness is checked by leaf-index continuity rather than by amounts.

**P6 measure added.** The report now counts future participants active in the feature week *before* Tornado edges are
removed, and how many become isolated *only because of* the removal.

---

### 2026-11-24 — Pilot report P1–P8 and go/no-go: **Redesign (narrowing), not Stop**

Full report: `docs/tornado-pilot.md`; numbers: `results/tornado_pilot.json`. All data are pre-2022-08-08. No model was
fitted and no detector was compared.

**What was run.**
- The add-on pass was recomputed on all 181 days with the receipt-status completeness check.
- The contract registry was built: 146,242 contracts among 3,393,824 addresses of interest. Validation: 0 January
  senders in it, 0 creations after the cutoff, and the pools and router carry their known dates. The 100 ETH pool's
  creation (2019-12-25) was confirmed separately, after a scan that started a week too late had missed it.
- The feasibility report ran at both placebo cutoffs (P8).

**Reasoning for the decision.**
1. **Events are reliable (P1).** Deposit leaf indices are contiguous in all four pools. Withdrawal payments reconcile
   exactly: 82,162 expected = 82,113 successful traces + 49 status-field errors. There is no missed event in either
   direction. So this is not a Stop on label grounds.
2. **Depositors have enough positives; recipients do not (P5).** At the two placebo cutoffs there are 698 and 621
   depositor positives, 371 and 314 of them active. Recipients have 264 and 233, of which 130 and 97 are active. Only
   4–7% of first-time recipients fall in any sender-based frame. They are fresh addresses, so a prospective,
   label-free design cannot reach them. **Recipients are dropped as a primary target.**
3. **The graph is usable after removal (P6).** Removal isolates 0–3 positives. Leakage is indirect (other OFAC
   addresses, router calls, 128 relayer worker senders), and each route is small but real. **The removal set widens**
   to the full 2022-08-08 OFAC list, created before c, plus as-of relayers and worker senders.
4. **Power at the real cutoff is the main unmeasured risk.** It is inferred only from scoping's single-day router
   counts and was not measured, because that would read post-cutoff labels. A **pre-registered power rule** handles it.

**Measured to inform the population choice (counts only, no contrast):** a frame of January senders ∪ senders of the 7
days before c captures 978 and 914 depositor positives, against 698 and 621 for January alone, still label-free.

**Proposed redesign R1–R7** (in the report): depositor target; union frame; widened as-of removal set; whole-history
"first-time"; typed three-layer graph; power rule; non-overlapping placebo horizons.

**Not done, deliberately:**
- `docs/tornado-design.md` is not drafted until the owner accepts or amends R1–R7.
- No post-cutoff data is read until the design is frozen.

---

### 2026-11-24 — Owner accepted R1–R7; Stage 2 design frozen (`docs/tornado-design.md`)

The owner chose "Accept R1–R7". The design is frozen **before any post-2022-08-08 data is read and before any detector
is fitted on Ethereum data**.

**Key choices and their reasons:**
- **Primary test (H1).** There is one confirmatory test: across the sanctions shift, does the pooled synthetic stress
  test (SYN = mean of S1, S2, S3 recalls per detector) predict post-shift recall with smaller E4 error than recent data
  (S0)? Success requires the 95% bootstrap interval of the difference to lie entirely below 0. This is the Elliptic lead
  as actually observed (all three synthetic sets alike), not the failed S1-specific hypothesis.
- **Shift specificity.** Placebos P1 = 2022-04-08 and P2 = 2022-06-08 have non-overlapping horizons. A 4-row
  interpretation table is fixed in advance, including "beats S0 but not shift-specific".
- **Replication fidelity.**
  - The same 10 detectors as Elliptic.
  - The same scenario sets: S1 is the identical 2016 forecast pairs, S2 the identical seed-0 pairs, S3 the 8 motifs,
    built by the same generator, with accounts as nodes and payment edges.
  - The same threshold-then-refit procedure.
  - The threshold is a 1% alert rate on unlabelled eligible addresses, not an FPR.
- **Operational detail of R2 (flagged to the owner).** The frame uses the last full calendar month ending at least 8
  days before each task date, plus the feature week. That is a *rolling* month, not a fixed "January". Training tasks
  and P1 start before or around January 2022, so a fixed January frame would use information from after their own
  dates. In the pilot's window this rule gives exactly January.
- **Power rule (R6).** At least 100 eligible positives in 8 weeks; otherwise extend once to 26 weeks; otherwise stop
  as "underpowered", without looking at any score.
- **Approval gate.** Post-cutoff reads happen only behind an explicit switch, after the owner approves this design.

**Next:** pre-cutoff builds only (history from 2019-12-16, 7 monthly frames, 15 feature weeks, the labels check), the
code test-first, and a dry run on training and calibration tasks.

---

### 2026-11-24 — Label-rule fix before the data pass; "Alien Space of Science" evaluated (not adopted now); STATUS.md

**Smoke test caught two bugs in the new pre-cutoff builder (before the full pass).** The test day was 2022-02-21,
inside the logs window, compared against the pilot's Deposit and Withdrawal events.
1. **Value rule over 38 OFAC addresses.** It counted 29 payments of 0.1 or 1 ETH to *another* listed Tornado contract
   (`0xca08…`) as ETH-pool deposits.
2. **Withdrawal roles by amount.** In 4 withdrawals the relayer fee was more than half of 0.1 ETH, so recipient and
   relayer were swapped.

**Fix.**
- **Deposits** = successful-transaction calls paying a pool exactly its denomination, from traces. This covers every
  entry contract.
- **Withdrawal roles** follow call order (the contract pays the recipient first).
- Both rules now match the logs exactly on that day: 144/144 and 160/160, with 0 extra.
- Recorded as a dated **deviation** in `docs/tornado-design.md`. Tests were written first (119 pass).

**Paper evaluated at the owner's request.** Artiles et al., *The Alien Space of Science*, arXiv:2603.01092, NeurIPS
2026. I read the main text (pp. 1–11), not the 48 appendix pages. **Not adopted into the current work:**
- Stage 2 is frozen;
- our expressible space is only 28 motif pairs;
- availability needs large author histories;
- the paper itself cautions against low-availability search in dual-use fields.

Two points of real relevance:
- its note that hypergraph methods collapse in dense fields is independent, consistent evidence for our density
  observation;
- it suggests a reading of Elliptic's "S1 ≈ S2": forecasting the *available* region. That is a hypothesis.

It is proposed as a later, separately pre-registered **S4 "alien scenarios"** experiment
(`docs/alien-space-evaluation.md`).

**`STATUS.md`** was added at the repository root: a short status page for GitHub, updated with each milestone.

---

### 2026-11-24 — Owner: "inspect their code and build an S4 prototype"; S4 pre-registered before any score

- **Code inspected** (read-only, never executed). `alejandrohdez00/alien-space-of-science` at `a55d660`, MIT licence:
  - formulas confirmed (coherence = mean atom NLL; availability = median of the top-10 author cosine scores; fusion
    with z-scores and β = 0.7);
  - trained models are not reusable (another domain);
  - the training stack is too heavy for a 28-pair space.
  - Details: `docs/alien-space-evaluation.md`.
- **Prototype** `gffs.alien_s4`, with 6 tests (125 in total pass):
  - coherence = cosine of PPMI-SVD concept embeddings;
  - availability = log1p(number of pre-cutoff authors holding both concepts);
  - the paper's fusion rule;
  - a recovery metric and the Vendi score.
- **Pre-registration** `docs/s4-alien-prereg.md` is committed **before** the authorship fetch finishes and before any
  S4 score:
  - pool = S1's 25 pairs, literature ≤ 2016, β = 0.7, top 10;
  - exploratory comparisons against S1, S2 and S0 on the Stage 2 data only;
  - a transparency note was added to the Stage 2 deviations;
  - H1 is unchanged.
- **Data:** an OpenAlex authorship fetch for the cached corpus (OpenAlex now reports 106,707 works against 105,533
  cached; only cached works are used).

---

### 2026-11-25 — Codex review processed; Elliptic lead weakened by the reanalysis

**Codex reviewed the repository** (`docs/CODEX_REVIEW_2026-11-24.md`, ledger `AGENT_DISCUSSION.md`). All seven
findings were checked against the code and agreed (G06 is wider than stated: it also affects the Stage 1
literature-v2 validation).

**Done:**
- **G04 labeller.**
  - A call counts only if no ancestor failed. The dataset stores "no error" as the *string* "None", and the root
    `trace_address` likewise. Both were found when the first attempt dropped every call.
  - One withdrawal per pool call frame; ambiguous frames are quarantined.
  - The first 3 validation days reconcile exactly with the logs. The full window is running.
- **Stage 2 Amendment A1**, before any evaluation: common model, instance bootstrap, tie policy and rounding, a
  shift-specific contrast with a power simulation, cheap baselines, and an accurate label name.
- **Elliptic reanalysis** (`docs/results/e3e4-reanalysis.md`). Verified reproduction (the one difference is
  float jitter at tied thresholds, 14 of 920).
  - **The after-shift calibration advantage keeps its point estimate under one common model, but its time-block
    interval includes 0.**
  - **The ranking advantage is not robust.**
  - Recent data beating synthetic without a shift is robust. S1 ≈ S2 is unchanged.
  - The published `knn` operating point flagged 9.2%, not 5%.
- **S4** (`docs/results/s4.md`): degenerate in the motif space. The literature validation shows coherence 3.4×, and
  unavailability is distinct from rarity.
- **G07:** README corrected; dependencies declared; clean install verified.

**What this means.** The project's only positive lead is now weaker. **I said earlier that synthetic sets "predict
post-shutdown catch rates better"; with time dependence accounted for, that is not statistically established on
Elliptic.** Stage 2 becomes the deciding test, and its power simulation must include time-block dependence.

**G04 verified (2026-11-25).** Full-window reconciliation of the corrected trace labeller against the logs, 181 days:
- **deposits** 44,293 / 44,293;
- **withdrawals** 42,334 / 42,334;
- 0 missed, 0 extra, 0 ambiguous frames;
- 0 calls dropped by the ancestry rule (no caught reverts occurred in this window);
- 1 payment inside a reverted transaction, correctly excluded.

The design's §3 check (≤ 1% missed) passes, with no extras. **Residual risk:** history before 2022-02-08 uses the same
rule but has no log ground truth.

**Literature-v2 reanalysis (G06, 2026-11-25).** The published validation chose its ~500 context nodes using works up
to 2016, while forecasting from 2013. With the vocabulary chosen from works up to 2013 only:
- **logreg_all** AUC 0.824;
- the **popularity baseline** rises from 0.576 to 0.612;
- the **margin** falls from **+0.241 to +0.212 [+0.203, +0.219]**.

The forecaster's advantage survives the correction, smaller by about 0.03; the leak had mostly been holding back the
baseline. The correction is noted in `docs/paper/draft.md`, `docs/HANDOFF.md` and `docs/results/e3e4.md`, and the
draft's after-shift claims are annotated with the E3/E4 reanalysis.

**G05 power simulation and Amendment A2 (2026-11-25, before any Stage 2 score).** Simulated the H1 statistic with
Elliptic's common-model recalls as the template, 8 weekly blocks, and instance-clustered synthetic positives.
- **Finding:** the interval frozen in A1 (holdout positives resampled one by one) **rejects a true null in 19–32% of
  simulations** under strong week dependence. The week-block interval stays at or below 4%.
- **Amendment A2:** the block interval becomes primary for H1.
- **Power:** an Elliptic-size effect is detected with probability 0.77–1.00. A half-size effect is detected with
  probability **0.59–0.82**, and under strong dependence this barely improves with more positives (8 blocks).
- **Consequence:** a null Stage 2 result cannot rule out a modest effect. A longer horizon (more blocks) would help
  more than more positives; that is left open for the owner and Codex.

---

### 2026-11-25 — Owner: "both in parallel". E01 scheduling core and trace; Stage 2 account features

- **E01** (`docs/e01-scheduling.md`):
  - compiler, independent verifier, and an exact MILP **verified against brute force**;
  - 6 atoms with verified-DOI sources (mapping still unverified);
  - generator with a canonical family hash; a heuristic learner; records; an end-to-end trace.
  - **Trace:** 132 scenarios, 132 distinct families, 0 verifier failures, infeasible cases where deadlines exist.
  - **Finding:** the instances are too easy (the greedy rule is near-optimal). Harder instances come before any
    learning study.
- **Stage 2 runner, part 1:** account features (design §4). The reconvergence join is chunked over integer ids so it
  fits a real week (7.0M edges, 467k accounts) in 147 s and 6.5 GB.

---

### 2026-11-26 — E01: certification gate, extended solver, Codex L07–L10 fixed; atom evidence; registry

- **Codex L07–L10:** all four reproduced and fixed, test-first (see `AGENT_DISCUSSION.md`). The key one: a solver
  timeout had been reported as "infeasible". There are now four outcomes, and gaps use certified optima only.
- **Extended solver:** multiple resources, maximum lags, multi-mode activities with budgets, all brute-force verified.
- **Certification gate on a harder generator:** 99.4% coverage, 0 flips. **No-go by the pre-stated per-family rule**
  (93.75%). The one uncertified instance certifies at 300 s, so two-stage solving was adopted *post hoc* (disclosed).
  Headroom is modest (mean greedy gap 3.3%).
- **Atom evidence sheet** (`docs/e01-atom-evidence.md`), for human review. It exposed **community mixing** in the
  broad-anchor counts: "deadlines" and "preemption" are mostly computing literature. The non-degenerate signal is
  partly an artefact of mixed meanings. **Decision:** define the corpus by venue or topic, frozen before scoring.
- **Stage 2:** the pre-cutoff build is complete; the contract registry is built (699,165 contracts; 37/38 listed
  addresses dated; the remaining one is an externally owned account, so a deviation was logged); the dry run is in
  progress.

---

### 2026-11-26 — Stage 2: dry run, Amendment A3, rehearsal (three bugs caught before any post-cutoff read)

- **Dry run** (`results/tornado_dry_run.json`; training and calibration only):
  - 584–957 positives per task; 6.3–8.2M eligible addresses per task;
  - alert rates on target for 8 detectors;
  - **the tree and k-NN degenerate** (0% at the operating point, because their top tied score holds more than 1%).
- It needed **two memory fixes**: one process per cutoff; compact history plus streamed tasks with hash-keyed uniform
  samples (tests prove equivalence).
- **Amendment A3:** detectors degenerate on calibration data are excluded from H1–H4 and reported separately (8
  remain).
- **Rehearsal** (the calibration week stands in for the evaluation week; structure only, no metric values). It caught:
  1. the `__main__` block above later definitions (NameError);
  2. the bootstrap using instance id values as positions (IndexError when ids are numbered across sets).

  Both are fixed, with regression tests. **The final rehearsal passes:** all arms and contrasts produced; E4 and every
  contrast interval finite; ρ undefined only for the constant baselines; 1,000 block draws.
- **The post-cutoff label build** sits behind the approval gate (`build_post_cutoff_history`; refusal tested).
  `docs/tornado-approval.md` does not exist, so **nothing after 2022-08-07 has been read.**
