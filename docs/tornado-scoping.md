# Stage 2 scoping: a Tornado Cash sanctions dataset (measured 2026-11-22)

**Purpose:** a second, independent, *dated* shift, to test the after-shift lead (`docs/results/e3e4.md`,
`docs/results/mechanism.md`). This note is scoping only. The analysis design will be frozen separately, before any
labelled outcome data is read.

## Data source: free, no account

The **AWS Public Blockchain Data** open bucket (`s3://aws-public-blockchain/v1.0/eth/`) holds daily Parquet files of
Ethereum `transactions`, `logs`, `traces`, `blocks`, `token_transfers` and `contracts`. It reads anonymously, and works
through this environment's proxy. **No BigQuery, no billing.**

## Measurements

| Table, one day | File size | Read cost (only needed columns) | Rows |
|---|---|---|---|
| transactions (2022-08-08) | 415 MB | **3.9 s**, 126 MB in memory (4 columns) | 1.17 M |
| logs (2022-07-01) | 225 MB | **50 s** (4 columns) | 2.07 M |
| traces (2022-08-08) | 1,563 MB | not needed (logs cover withdrawals) | 4.67 M |

**Tornado Cash activity** (the router and the four ETH pools: 0.1, 1, 10 and 100 ETH):

| Day | Transactions to the router | Pool events (Deposit / Withdrawal) |
|---|---|---|
| 2022-07-01 | 739 | 686 (336 / 350) |
| 2022-08-08 (sanctions day) | 828 | – |
| 2022-09-01 | **65** (−91%) | – |

→ **The shift is large and clearly dated:** OFAC designation on 8 August 2022.

## Proposed scope

- **Window:** 2022-02-08 to 2023-02-07 (±6 months). Cutoff: 2022-08-07. Holdout: 2022-08-08 onwards.
- **Labels (positives):**
  - (a) addresses that deposit into a Tornado ETH pool (the depositor is the transaction sender, joined on the hash);
  - (b) withdrawal recipients (the `to` field of the Withdrawal event);
  - (c) Ethereum addresses on OFAC's SDN list (e.g. Lazarus-linked), from the public list.
- **What the labels mean:** these are "mixer-associated", **not** proven illicit. Privacy-seeking users are included.
  Every result must say so.
- **Graph:** weekly address-level ETH transfer graphs (the analogue of an Elliptic time step). To keep it manageable,
  the nodes are the positives, their direct counterparties, and a fixed-seed 1% random sample of other active addresses.
- **Pipeline:** unchanged. The same graph-only detectors and the same stress tests (S0 recent data, S1 graph forecast,
  S2 random pairs, S3 single motifs, and SA/SB/SC-style families where they apply), compared against the real post-sanction
  holdout.

## Cost

| Item | Cost |
|---|---|
| Transactions, 365 days | ~25 min |
| Logs, 365 days | ~5 h (only Tornado events are kept) |
| Storage | only filtered edges and labels are kept, well under 1 GB |
| Money | none |

## Known risks, before building

1. **The label shift is part of the event.** After the sanctions, the remaining mixer users are a different, possibly
   more committed population. A drop in detector recall then mixes behaviour change with label-population change.
2. **Address-level, not transaction-level.** Ethereum is account-based, so the motif definitions transfer, but in- and
   out-degree mean different things (counterparties, not inputs and outputs).
3. **Activity collapses after the sanctions** (−91%), so the holdout has far fewer positives than training. Recall estimates
   will be noisier.
4. **Contract addresses** (exchanges, DEX routers) are giant hubs. They need a pre-specified rule, for example excluding
   addresses with more than N counterparties per week, fixed from pre-cutoff data.
