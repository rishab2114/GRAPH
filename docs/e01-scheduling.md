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
