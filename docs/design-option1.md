# Design: Option 1, Elliptic holdout + AML typology graph

Chosen by the owner on 2026-11-18. This note sets out the design and the one problem that has to be
settled before building.

## The problem: dates

The leakage rule (spec §5) says the typology graph may only use knowledge that existed at cutoff T.

- **Elliptic's time steps have no published calendar dates.** There are 49 steps about two weeks apart,
  so the data covers about 2 years. Its txIds are anonymised, so the steps cannot be matched to block
  times. The paper was released in July 2019, so the data predates that. A plausible span is
  2016–2017, but **this is unconfirmed**.
- **The main crypto-AML typology source is later:** FATF's *Virtual Assets Red Flag Indicators*
  (14 Sept 2020) draws on more than 100 case studies **from 2017 onward**.

If the graph is built from 2020 typologies, the stress test uses knowledge from after the period it is
tested on. That breaks the revised core question: "a stress test built only from data available
before a cutoff".

## Options for the graph source

| | Graph source | Dated? | Leakage | Effort |
|---|---|---|---|---|
| **A (recommended)** | **Research literature:** how often a fixed set of AML and crypto-crime concepts co-occur in paper titles and abstracts (OpenAlex), using only papers published before 2017. This is the SciMuse method itself | Yes, by publication year | Small: only the *choice of vocabulary* is informed by later documents | Medium. Uses the OpenAlex API, so no bulk download |
| B | Pre-2017 regulatory documents only (FATF 2014 and 2015 virtual-currency reports, FinCEN 2013 guidance, Europol IOCTA 2014–16) | Yes | None | Medium; a sparse graph from about 10 documents |
| C | FATF 2020 red-flag indicators + case studies | Yes, but after Elliptic | **Large**. Must be labelled as a leak, and the core claim weakens | Lowest |

## Fixed parts (any graph source)

- **Nodes:** red-flag indicators that can be observed in a transaction graph: fan-in, fan-out, peel
  chain, mixing-like many-to-many, rapid pass-through, round-trip, dust or structuring, sudden
  dormancy then activity. The vocabulary is written down and committed before any counting.
- **Holdout:** real Elliptic transactions, using the paper's split (train steps 1–34, test 35–49). The
  dark-market shutdown at step 43 is the shift.
- **Scenarios** are written as **transaction-subgraph motifs** using `elliptic_txs_edgelist.csv`, not in
  the anonymised features (0% expressible, see Phase 0). Detectors for E3/E4 use graph features that
  we compute the same way for real and synthetic transactions. The real holdout stays independently
  observed data, as spec §3 requires.
- **Bar to beat** (Phase 0 §5): the recent-window stress test has recall ranking ρ ≈ 0 and overstates
  recall by 24 points across the shutdown.

## Open risk carried forward

Elliptic labels say illicit or licit, never *which* typology. So E3 and E4 can only test whether
detectors that catch the invented motifs also catch real illicit transactions later on. They cannot
test whether the forecast *combinations* themselves appeared.
