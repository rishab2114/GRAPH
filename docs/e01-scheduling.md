# E01: first non-financial adapter. Constrained project scheduling (status and next steps)

**Started 2026-11-25** at the owner's request ("both in parallel" with the Stage 2 runner), following the proposal in
`AGENT_DISCUSSION.md` (response to L01–L06). No LLM is used anywhere. The compiler and the exact solver decide
validity and correctness.

## What exists (`src/gffs/sched/`, 10 tests)

| Part | What it does | Evidence |
|---|---|---|
| `spec.py` | Bounded JSON → validated instance, or `Invalid(reason)` (cycles, unknown ids, bad numbers, unknown fields) | Tests |
| `verify.py` | Independent feasibility check: release, deadline, horizon, precedence, lags, per-period capacity with calendars | Tests catch each violation type |
| `solve.py` | Exact time-indexed MILP (scipy HiGHS); infeasibility certificates | **Matches brute force on 25 random tiny instances**, infeasible ones included |
| `atoms.py` | 6 atoms with definitions and source DOIs (Hartmann & Briskorn 2010 and 2022 surveys, PSPLIB; all verified in OpenAlex) | **Mapping status "unverified"** until a person checks each definition against the source text |
| `generate.py` | Seeded generator: composition × DAG template × seed, plus a canonical Weisfeiler-Lehman family hash (name- and order-invariant; needs networkx ≥ 3.5) | Deterministic; renaming leaves the hash unchanged |
| `heuristic.py` | Serial schedule-generation scheme with a deadline priority rule: the first "learner" | Its schedules always pass the verifier |
| `records.py`, `trace.py` | `Combination`, `Scenario` and `Run` records with content-hash ids, and the end-to-end trace | `results/e01_trace.jsonl`, `results/e01_summary.json` |

## First trace (132 scenarios)

11 compositions (the base, plus 0–2 of release dates, deadlines, calendars and lags) × 4 templates × 3 seeds:
- **132 distinct family hashes** (no duplicates); **0 verifier failures**;
- infeasible instances appear wherever deadlines are present: 3, 7, 4 and 1 of 12;
- the heuristic is right on feasibility in 130 of 132 cases, with mean optimality gaps of 0–8%.

**Finding: the instances are too easy** for a learning study. A fixed greedy rule is already near-optimal, so a
learner could not show much.

## Next steps, in order

1. **Harder instances:** 8–12 tasks, tight resources (PSPLIB-style resource strength), more interacting constraints.
   Report how often the critical-path bound equals the optimum (the shortcut check from L03).
2. **Literature scores for the atoms** (OpenAlex, RCPSP anchor, data up to a fixed year): works per atom, pair
   co-occurrence and bridging authors. Then run **L01's acceptance check** before any selector is frozen: at most 20%
   ties at the top-k boundary, and limited D/C overlap.
3. **A learned priority policy**, trained by imitation of exact schedules. Metrics: optimality gap and
   infeasibility-detection balanced accuracy on **unseen composition families** (disjointness proven by canonical
   hash).
4. **Shortcut probes and invariance tests** (style probe; renaming, permutation, irrelevant tasks).
5. **Only then:** the E03 six-arm selection study, with frozen families and metrics.

**Not claimed:** none of this yet shows that "alien" or "coherent" combinations help a learner. That is E03's question.

## L01 pre-check: is the literature signal non-degenerate? (2026-11-25)

Counted in OpenAlex, works published up to 2020-12-31 (`results/e01_literature_counts.json`).

| Atom vocabulary | Works per atom | Pairs never co-occurring | Pairs under 10 works | Median pair |
|---|---|---|---|---|
| Single phrases within the **RCPSP** anchor, 10 atoms | 2–402 | **26 / 45 (58%)** | — | **0** |
| **"Scheduling" anchor, with synonym groups**, 10 atoms | 228–15,737 | **1 / 45** | 13 / 45 | **28** (range 0–1,245) |

**Reading:**
- Phrase atoms inside the narrow RCPSP literature would make availability **degenerate**, as with S4.
- The broad scheduling literature with synonym groups gives a usable spread.

**Rules for using it:**
- the synonym groups are a manual choice, so they must be **frozen before any score is computed**;
- each group is checked against the atom's definition;
- the L01 acceptance check (≤ 20% ties at the top-k boundary, limited D/C overlap) still has to pass on the actual
  candidate pool;
- abstract-level phrase matching is crude: counts are a lower bound, and they mix work that *studies* a combination
  with work that merely *mentions* it (the distinction Cross-engine J07 draws).

**Solver support needed for these 10 atoms:**
- **Already supported:** precedence, release dates, deadlines, calendars, minimum lags.
- **Easy to add:** maximum lags, multiple renewable resources.
- **Moderate:** multi-mode activities with nonrenewable resources (mode-choice variables); preemption (a different
  time-indexed model).
- **Setup times:** only the sequence-independent form, which folds into durations. The sequence-dependent form is out
  of scope for E01.

## Update 2026-11-25: Codex L07–L10 fixed

- **L07, solver outcomes:** `optimal` (certified, exact gap 0), `infeasible` (proven), `feasible` (uncertified
  incumbent), `unknown` (no incumbent). Gaps use certified optima only. Trace: 102 optimal, 30 infeasible, 0 feasible,
  0 unknown.
- **L08, keys:** `family_id` (typed mechanism set; the split unit) and `instance_fingerprint` (parallel relations kept).
  - The generator now guarantees that every listed atom is present.
  - **This changed the instance distribution:** 30 infeasible instead of 17. The first trace's numbers above describe
    the earlier generator.
- **L10, input boundary:** typed rejections for malformed specs; size limits; integer-only schedules.
- **Extensions:** multiple renewable resources, maximum lags, multi-mode activities with nonrenewable budgets. All are
  cross-checked against brute force.

## Certification gate on a harder generator (2026-11-26)

- **Setup** (`python -m gffs.sched.certify`, `results/e01_certification.json`): 176 instances; 10–12 tasks; tight
  resources; 11 composition families × 4 templates × 4 seeds; 30 s limit.

| Measure | Result |
|---|---|
| Outcomes | 115 certified optimal, 60 proven infeasible, **1 uncertified** (feasible incumbent) |
| Coverage | **99.4%** overall; 100% in the tight, moderate and greedy-fails bands, 98.8% in the hard band |
| Minimum coverage by family | **93.75%** (1 of 16), below the 95% gate |
| Re-solve of 10% at 10× the limit | **0 status flips** |
| Headroom | Greedy optimal in 66% of certified cases (was about 100% on the easy generator); mean greedy gap 3.3% |
| Shortcut check | The critical-path bound equals the optimum in only 23% of certified cases |

**Verdict by the pre-stated rule: no-go at 30 s.** The single uncertified instance (calendar + minimum lags, parallel
template, 12 tasks) **certifies at 300 s** with the same makespan, 38.

**Policy adopted after seeing this result, and disclosed as such:** two-stage solving, 30 s and then 300 s for anything
uncertified. Anything still uncertified is excluded from learner comparisons. Under this policy the development set
is fully certified.

**Headroom is real but modest** (a mean greedy gap of 3.3%). A learned priority rule could show only small absolute
gains here. Larger or tighter instances would add headroom, but would also raise certification cost, a trade-off to
decide before E03.

## Evidence sheet and a validity problem in the L01 pre-check (2026-11-26)

`docs/e01-atom-evidence.md` lists, for each atom, the three most-cited matching works and the abstract sentence that
contains the term, **for human review** (studied, mention only, or unclear). No atom is marked verified.

**The sheet exposed a problem with my pre-check.** Under the broad "scheduling" anchor, the top "deadlines" works are
**real-time CPU scheduling and control systems**, not project scheduling. Re-counted with computing and networking
terms excluded:

| Anchor | Works per atom | Zero pairs | Pairs under 10 | Median pair |
|---|---|---|---|---|
| Scheduling + synonyms | 228–15,737 | 1 / 45 | 13 | 28 |
| … excluding computing and networking terms | 115–3,891 | 2 / 45 | 19 | **12** |

**What this shows:**
- 75% of the "deadlines" hits and 71% of the "preemption" hits came from computing.
- Part of the earlier non-degenerate spread came from **mixing communities where the words mean different things**.
- The exclusion list is itself flawed. It drops "network", but "project network" is core project-scheduling
  vocabulary.

**Decision for the frozen E03 design:** define the corpus **by venue or topic** (for example operations-research and
production journals, or OpenAlex topics for project and production scheduling), not by hand-tuned keyword exclusions.
Freeze it with the synonym groups before any score. The current counts are diagnostics only.

## Learner v0: protocol fixed before any result (2026-11-26)

- **Data** (`gffs.sched.dataset`): 11 families × 4 templates × 20 seeds = 880 hard instances. Labels come from the
  two-stage certified solver (30 s, then 300 s). Uncertified instances are excluded.
- **Split:** *compositional axis only* in v0. Sort the six two-extension families by name and hold out every third:
  **deadlines + resource_calendar** and **release_dates + resource_calendar**. Every single atom still appears in
  training. Family overlap between train and test must be 0.
- **Learner** (`gffs.sched.learn`): a linear priority rule for the serial schedule-generation scheme, fitted by
  logistic pairwise ranking on 11 task features. The target is the order of certified optimal start times.
- **Compared with:** the deadline rule (the earlier heuristic), latest finish, most successors, and random (seed 0).
- **Metrics on the held-out families:**
  - mean optimality gap against **certified optima only**;
  - share optimal;
  - share of feasible instances where a schedule is found;
  - share of infeasible instances detected (no schedule found);
  - in-distribution results reported alongside.
- **Not claimed:** a single compositional split and one seed. This is a feasibility check that learning beats fixed
  rules, not the E03 selection study.
