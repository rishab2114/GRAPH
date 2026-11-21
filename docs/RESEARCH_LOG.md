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
