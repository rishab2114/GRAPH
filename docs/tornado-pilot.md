# Tornado Cash pilot: P1–P8 report and go/no-go (pre-sanction data only)

**Written 2026-11-24.** Plan: `docs/tornado-pilot-plan.md`. Corrections ordered by the owner on 2026-11-22 are applied
(P3/P4 edge semantics, independent withdrawal completeness, role attribution, as-of information only).

**Data rules:**
- Every number below comes from Ethereum data dated **before 2022-08-08**.
- Nothing after the sanctions date was read. No model was fitted, and no detector was scored or compared.
- Machine-readable output: `results/tornado_pilot.json`, produced by `python -m gffs.tornado_feasibility`.

**Code:**
- `gffs.ethereum`: readers and event decoders.
- `gffs.tornado_pilot`: logs pass and January frame.
- `gffs.tornado_aux`: transaction status and edge categories, the trace check, the contract registry.
- `gffs.tornado_feasibility`: labels, exclusions and coverage.
- 114 tests pass.

**Window:** 181 days, 2022-02-08 to 2022-08-07, all extracted (main pass and add-on pass both 181/181).

## Decision

**Recommendation: Redesign, as a narrowing, not a restart. Do not Stop.**

| Owner's criterion | Finding | Verdict |
|---|---|---|
| Reliable events | P1 reconciles exactly in both directions, and no label is lost or invented (details below) | **Met** |
| Enough positives | **Depositors:** 698 and 621 first-time depositors in the frame at the two placebo cutoffs; 371 and 314 of them with non-Tornado activity. **Recipients:** 264 and 233; only 130 and 97 active. About 95% of first-time recipients are addresses no pre-cutoff frame contains | **Met for depositors, not for recipients** |
| Usable graph after removing Tornado | Removing Tornado edges isolates only 0–3 positives. The prospective label (first participation *after* the cutoff) already keeps pool interactions out of the features. About half of depositor positives have non-Tornado edges in the 7-day window | **Met, with a removal set that must be widened (P6)** |
| Labels unreliable, or no information in the graph (the Stop condition) | Neither applies | **Not met: no Stop** |

**Why not Proceed as specified.** Three things in the current design would make the held-out study invalid or
uninterpretable:

1. **The recipient target cannot be reached by any label-independent frame.** Only 5.0% and 4.1% of first-time
   recipients are January senders. Adding every sender of the week before the cutoff only raises this to 6.9% and
   6.0%. Recipients are overwhelmingly fresh addresses; that is how the mixer is meant to be used. Predicting them
   "from prior activity" has almost nobody to predict.
2. **The removal and exclusion sets are incomplete.**
   - Positives touch other OFAC-listed Tornado addresses before the cutoff: 2/698 and 6/621 depositors, 1/264 and 0/233
     recipients.
   - Some positives already called the router before the cutoff, most likely for ERC-20 pools: 2/698 and 2/621
     depositors, 8/264 and 1/233 recipients.
   - 128 relayer "worker" addresses send relayed withdrawals without being the event's named relayer.

   Each case is small, but each is a leakage route a reviewer would rightly flag.
3. **Power at the real cutoff is the main risk.** It is not measured, because measuring it needs post-cutoff labels.
   Scoping saw 65 router transactions on 2022-09-01 against 739 on 2022-07-01. If new participation fell by anything
   near that ratio, an 8-week post-sanction horizon would give tens of in-frame active depositors, not hundreds. That
   would be thinner than Elliptic's 169 post-shift positives. This rests on two single days and is a **risk, not a
   finding**. The frozen design needs a pre-registered rule for it.

**Proposed redesign** (for `docs/tornado-design.md`, to be frozen only after the owner agrees):

| # | Change | Reason (pilot evidence) |
|---|---|---|
| R1 | **Primary target: first-time ETH-pool depositors.** Recipients reported descriptively only | P5: recipient frame coverage 4–7% under every label-free frame tried |
| R2 | **Population: January senders ∪ senders in the 7 days before the cutoff**, both fixed before any label is attached. Eligibility: no Tornado participation before the cutoff | The union frame raises the depositor positives captured from 698 to 978 and from 621 to 914 (coverage 29% and 25%), with no label used |
| R3 | **Removal set, all as of each cutoff:** all 38 Tornado addresses on OFAC's 2022-08-08 list that were created before the cutoff, plus relayers *and* relayed-withdrawal senders seen before the cutoff | P6: other OFAC addresses, router calls and worker senders are measured leakage routes |
| R4 | **"First-time" over the whole pool history** (from deployment, Dec 2019), not only from 2022-02-08. Any earlier successful router, proxy or pool call counts as prior participation | Lookback limited to the window is the largest remaining label-definition gap (estimated cost about 2 h of reads, all pre-cutoff) |
| R5 | **Typed graph:** three layers (`simple_transfer`, `value_call`, `call`); failed transactions excluded; layers never merged | P4: the categories are exclusive, and the owner's correction forbids mixing contract calls with value transfers |
| R6 | **Pre-registered power rule:** count in-frame eligible depositors in the post-sanction horizon *once, as a count, before any score is computed*. If the count is below a pre-set minimum, extend the horizon once, to a pre-set maximum. If it is still below, stop and report "underpowered", with no detector results looked at | Risk 3 above |
| R7 | **Placebo cutoffs with non-overlapping horizons:** for example 2022-04-08 and 2022-06-08 (horizons ending 06-03 and 08-03) | The current placebos (05-08 and 06-08) have horizons that overlap by four weeks, so they are not independent |

## Measurements

### P1: Are pool events parsed correctly? **Pass.**

| Check | Result |
|---|---|
| Events decoded | 44,293 Deposits, 42,334 Withdrawals; **0** undecoded pool events; **0** deposits without a sender |
| Deposit completeness (leaf indices, per pool) | **0 missing, 0 duplicated** in all four pools: 0.1 ETH 6,942 (leaves 18,439–25,380); 1 ETH 15,858 (35,353–51,210); 10 ETH 13,360 (31,353–44,712); 100 ETH 8,133 (21,743–29,875) |
| Deposit amounts | Implied by the contract: `require(msg.value == denomination)` (tornado-core `ETHTornado.sol`) |
| Nullifiers | **0** duplicates among 42,334 withdrawals |
| Event-transaction success | 86,627 of 86,627 event transactions have a successful receipt |
| Withdrawals, events → traces | 42,285 exact matches (recipient gets denomination − fee and relayer gets fee, ±1e6 wei); **0** amount mismatches; **0** events without a payment |
| Withdrawals, traces → events (completeness) | **0** successful pool payments in successful transactions without a Withdrawal event |
| Reconciliation | 42,334 recipient payments + 39,828 fee payments = **82,162 expected** = 82,113 status-1 traces + 49 status-0 traces, **exactly** |

**Two trace-table quirks, investigated rather than accepted:**
- **49 matched payments carry `status = 0`** inside successful transactions that emitted the event. The pool `require`s
  both payments to succeed, so the event could not exist if one had failed. These are status-field errors in the
  traces table.
- **1 pool payment marked `status = 1` sits inside a reverted transaction** (2022-02-08, `0x232b84…`; the root ran out
  of gas). No ETH moved and no event exists. The completeness check therefore uses **receipt status**, and there is a
  test for this case.

The source argument relies on the repository code; the deployed bytecode was not compared.

### P2: Where does each label come from? **Pass.**

Every positive traces to a transaction hash and a day. Roles are kept separate:

| Role | Definition | Distinct addresses |
|---|---|---|
| Depositor | Sender of the transaction that emitted Deposit | 12,862 (0 are contracts) |
| Recipient | `recipient` field of Withdrawal | 19,358 (59 are contracts created before 2022-08-08) |
| Relayer | `relayer` field of Withdrawal, non-zero | 640 |
| Withdrawal sender | Sender of the withdrawal transaction | see attribution below |

**Withdrawal attribution:**
- 37,969 relayed, with the sender equal to the named relayer;
- **4,112 relayed with a sender different from the named relayer** (128 distinct "worker" senders; see R3);
- 253 self-withdrawals (no relayer, the sender is the recipient).

2,253 relayed withdrawals paid a zero fee.

**Overlaps between roles:**
- 1,883 addresses are both depositors and recipients;
- 579 recipients are also relayers;
- 90 depositors are also relayers.

### P3: Contracts and infrastructure. **Pass, with "unknown" preserved.**

**Contract evidence** comes only from the `contracts` table, as creations dated before the evaluation cutoff. The
registry was built for 3,393,824 addresses of interest and finds 146,242 contracts created before 2022-08-08, keeping the
earliest creation per address. It was validated four ways:
- the table equals the set of successful `create` traces on a sample day (7,229 = 7,229);
- none of the 5.4 million January senders is in it;
- no creation is dated on or after the cutoff;
- the four pools and the router carry their known deployment dates.

The scan read 2,558 daily partitions. The 8 absent days (2015-07-30 to 08-06) fall in Frontier's thawing period, when no
transaction could be made.

**Classification at each cutoff c:**
- **contract**, if created before c;
- **EOA**, if seen sending a transaction before c (in the January frame or the feature week);
- **unknown** otherwise.

`gas_used` is **not** used as contract evidence.

| Neighbours of frame addresses | contract | EOA | unknown |
|---|---|---|---|
| Feature week before 2022-05-08 | 68,749 | 1,018,943 | 250,595 (18.7%) |
| Feature week before 2022-06-08 | 59,166 | 802,681 | 223,256 (20.6%) |

"Unknown" is mostly receive-only addresses. It is kept as its own class, not guessed.

**Infrastructure** is the 4 pools, the router, and the relayers seen before c (375 and 455 relayers).

### P4: Which graph? **Typed edges, exclusive categories.**

Each successful top-level transaction falls into exactly one category:
- **`simple_transfer`:** value > 0 and gas = 21,000, a restricted category. It is **not** "all ETH transfers".
- **`value_call`:** value > 0 and gas ≠ 21,000. It carries ETH, but the destination type is *not* inferred from gas.
- **`call`:** value = 0.
- **`failed`:** receipt status ≠ 1, excluded.

| Category | All 181 days (tx) | Week before 05-08: tx / distinct edges / nodes | Week before 06-08: tx / distinct edges / nodes |
|---|---|---|---|
| call | 95,843,158 | 3,603,368 / 1,777,132 / 936,438 | 3,502,934 / 1,866,385 / 776,341 |
| simple_transfer | 73,763,316 | 2,758,066 / 2,194,469 / 1,690,187 | 2,267,182 / 1,763,384 / 1,369,467 |
| value_call | 29,262,560 | 1,180,573 / 567,327 / 413,199 | 1,201,483 / 590,558 / 394,038 |
| failed (excluded) | 7,276,940 | 260,460 / 122,959 / 108,618 | 411,478 / 218,796 / 133,660 |

**Choice:** keep three typed layers, without merging them (R5). Only `simple_transfer` is an unambiguous
account-to-account payment. ETH that moves inside contracts (internal transfers) and ERC-20 token transfers are **not**
in these edges (limitation 3).

### P5: Label-independent frame and positives. **Enough depositors; recipients fail.**

- **Frame:** the 5,402,274 senders of any transaction in January 2022, fixed before labels are attached.
- **Positives at cutoff c:** frame members whose *first* participation in the window falls in [c, c + 8 weeks), with
  no participation between 2022-02-08 and c. Earlier participants are excluded from the eligible set.
- **Over the whole window:** 3,107 of 12,862 depositors (24%) and 1,153 of 19,358 recipients (6%) are in the frame.

| Cutoff (horizon end) | Role | First-time participants | In January frame (coverage) | With non-Tornado activity in feature week | Union frame* |
|---|---|---|---|---|---|
| 2022-05-08 (07-03) | depositor | 3,380 | **698** (20.7%) | **371** | 978 (28.9%) |
| | recipient | 5,260 | 264 (5.0%) | 130 | 364 (6.9%) |
| 2022-06-08 (08-03) | depositor | 3,718 | **621** (16.7%) | **314** | 914 (24.6%) |
| | recipient | 5,674 | 233 (4.1%) | 97 | 341 (6.0%) |

\* Union frame = January senders ∪ senders of a successful transaction in the 7 days before c (1.65 million and 1.32
million addresses). The 7-day frame alone gives 648 and 605 depositor positives.

Base rates are tiny. Taking the January frame and **all** depositor positives, 698 of 5.40 million eligible addresses is
0.013%. Restricting to addresses active in the feature week (11.2% of the frame, about 604 thousand) and to the **371
active** positives gives about 0.06%. Hence the alert-rate reporting already adopted.

### P6: Does removing Tornado edges remove the trivial signal? **Yes, mostly by design. The set must be widened.**

| Cutoff | Distinct edges removed | Addresses excluded | Depositor positives active before → after removal | Recipient positives before → after |
|---|---|---|---|---|
| 2022-05-08 | 1,051 | 380 | 373 → 371 | 131 → 130 |
| 2022-06-08 | 869 | 460 | 317 → 314 | 97 → 97 |

Removal isolates almost nobody, because positives by definition have no pool event before c. The leakage left over is
the indirect kind measured in the Decision section:
- other OFAC addresses;
- router calls, likely ERC-20 pools;
- worker senders: 81 and 87 as of each cutoff; 0 depositor positives and 1 recipient positive among them.

R3 and R4 close these routes.

### P7: Historical sanctions records. **Done earlier.**

The OFAC snapshots are in `config/ofac/`:
- 2022-08-08: 38 ETH addresses, including all four pools, the router and the older proxy;
- 2022-11-08: 91 addresses.

The delisting on 2025-03-21 is noted for Stage 3.

### P8: Do the placebo cutoffs run? **Yes, end to end, at 2022-05-08 and 2022-06-08.**

At each placebo cutoff the full chain ran: labels, as-of relayers, as-of contract classes, Tornado removal and coverage.
**No detector result was computed.**

**Disclosure.** The coverage output also showed the share of positives with any non-Tornado activity against the rest of
the frame (about 50% vs 9–11%), and median degrees (3–4 vs 2). That contrast is a crude signal reading at the placebo
dates. It was seen, is disclosed in the log, and **must not be cited as evidence** in the study. A planned univariate
AUC was removed before it was computed.

## Leakage audit (owner's request: nothing after a cutoff may shape earlier features or sampling)

| Item | Information used | As of |
|---|---|---|
| Frame | Transaction senders, January 2022 (union option: the 7 days before c) | Before every cutoff |
| Features | Successful top-level transactions in [c − 7d, c − 1d] | Before c |
| Relayers excluded | Withdrawal events dated before c | Before c |
| Contract / EOA / unknown | Creation before c; sending before c | Before c |
| Labels | Prior participation before c is excluded; positives come only from [c, c + 8w), which ends before 2022-08-08 | Outcome window only |
| Registry lookup list | Includes addresses seen later in the window | Used only as lookup keys. A *classification* always uses creation < c. |

## Limitations

1. "First-time" is measured from 2022-02-08, not over the pools' whole history (R4).
2. Labels cover the four ETH pools only. ERC-20 pool users are unlabelled controls.
3. **Top-level transactions only.** Internal ETH transfers and ERC-20 token transfers are absent. The Elliptic-derived
   motifs (peel chains, layering) must be redefined for accounts before any stress test is built.
4. Receive-only addresses can never be in a sender-based frame. That is the structural reason recipients fail.
5. The "depositor" is the transaction sender. It is the economic owner only when the sender does not act for someone
   else.
6. The traces table's status field is unreliable (49 + 1 cases). Receipt status is used instead.
7. The ETH-pool source argument rests on the repository code, not on verified bytecode.
8. There is one data provider (the AWS public blockchain ETL). The internal two-direction reconciliation is exact, but
   no second source was compared.
9. The two placebo horizons overlap by four weeks (R7).
10. Post-sanction volume is unknown by design (risk 3).

## What happens next

1. The owner chooses: accept the redesign (R1–R7), amend it, or decline.
2. Then `docs/tornado-design.md` is drafted and frozen: targets, population, removal set, typed graph, account-level
   motifs, alert-rate thresholds on unlabelled controls, stress tests S0–S3, primary comparison, placebos, success
   criteria with intervals, and the R6 power rule.
3. Only after the freeze: R4's lookback (pre-cutoff), the placebo feature weeks, then post-2022-08-08 data, read once.
