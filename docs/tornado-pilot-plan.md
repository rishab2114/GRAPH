# Tornado Cash pilot plan (pre-sanction data only)

**Rule:** the pilot reads only data dated **before 2022-08-08**. It produces *measurements of feasibility*, never a
detector score on post-cutoff data. Written 2026-11-22, following `docs/review-2026-11-22.md`.

## Questions the pilot must answer

| # | Question | Measured how | Pass condition |
|---|---|---|---|
| P1 | Are pool events parsed correctly? | Decode Deposit and Withdrawal events for the four ETH pools (and the router), 2022-02-08 to 2022-08-07. Check that deposits ≈ withdrawals over time, and that the 4 pool denominations match `value`. | ≥ 99% of events decode; denominations consistent |
| P2 | Where does each label come from? | One row per positive: address, role (depositor or recipient), evidence (transaction hash or log id), date | 100% of positives traceable |
| P3 | Can contracts and infrastructure be identified? | Flag addresses with code (the `contracts` table or `receipt_contract_address`), and Tornado relayers (callers of the router `withdraw`) | A documented list; every relayer accounted for |
| P4 | Interaction graph or value-transfer graph? | Weekly sizes (nodes, edges, density) of: (a) all transactions; (b) transactions with value > 0 between non-contract addresses | Choose one, with a stated reason |
| P5 | Is there a label-independent sampling frame with enough positives? | Frame = externally owned addresses active in a reference period before the window (e.g. January 2022), sampled at random with a fixed seed. Count how many frame members become positives in Feb–Aug 2022 | Enough positives per role, a threshold fixed in the pre-registration (e.g. ≥ 200 per role before the cutoff) |
| P6 | Does removing Tornado edges remove the trivial signal? | After deleting every edge to or from Tornado contracts, router and relayers: what share of positives become isolated nodes, and how degree distributions shift | Reported (no pass/fail); informs the motif definitions |
| P7 | Which historical sanctions records apply? | Collect OFAC's 2022 actions with dates (8 Aug 2022 designation; 8 Nov 2022 re-designation; earlier Lazarus/Ronin addresses, 14 Apr 2022) from Treasury press releases | A dated list with sources |
| P8 | Placebo dates? | Choose 2 placebo cutoffs inside the pre-period (e.g. 2022-05-08 and 2022-06-08). Confirm the pipeline runs at them | They run (results only in the frozen study) |

## Outputs

- `docs/tornado-pilot.md`: measurements for P1–P8 and the decisions they lead to.
- `src/gffs/ethereum.py`: readers and event decoding, test-first. Only filtered, pre-cutoff extracts are kept locally.

## Then

Freeze `docs/tornado-design.md`, which fixes:
- the targets (depositor and recipient, reported separately);
- the eligible population and sampling frame;
- the graph type and the Ethereum motif definitions;
- the edges removed;
- the alert-rate threshold rule on unlabelled controls;
- the stress tests (S0, S1, S2, S3);
- the primary comparison, the placebo cutoffs, and the success criteria with intervals.

Only then build the full year and run once.
