# BTC weekend / DOW effect — Phase 1 thesis

**Status (2026-05-13):** Phase 2 complete. **REJECT** on pre-committed kill criteria
(MDD -40.6% > 20% bar; only 2/4 regime windows positive). Mechanism is real in W3-W4
(2022+ ETF era, Sharpe +2.11 / +1.81) but dormant in W1-W2 (2018-2021, Sh -0.01 / -0.17).
The "regime activation under institutionalization" story is preserved in STATE.md and
RESEARCH_NOTES as the **mirror image of btc_trend's regime decay** — same driver, opposite
activation.

**Verdict:** REJECT (full-history). Follow-up candidate: a separate Phase 1 thesis with
explicit regime-activation kill criteria (e.g., "fire only post-2022 with regime detector",
"require CME BTC futures OI > threshold"), which would be a clean new pre-commit, not a
refinement of this one.

## Origin

Second BTC daily-frequency thesis following `btc_trend`'s retirement to
KEEP_FOR_REFERENCE. Where btc_trend tested trend continuation (a mechanism
slow-TSMOM is structurally vulnerable to parabola-V transitions and BTC's
institutionalization decay), this thesis tests the **24/7-vs-TradFi-5-day
microstructure boundary** — a mechanism that is *specific to crypto* with
no equivalent in any other instrument the repo holds. Distinct mechanism,
distinct failure modes, distinct correlation profile.

## Thesis (mechanism)

BTC trades 24/7 while CME futures, equities, and most institutional
participants observe a 5-day week. This produces a structural asymmetry at
the weekend boundary:

1. **Friday close (17:00 ET / 22:00 UTC)** — CME Bitcoin futures close
   until Sunday 18:00 ET. The CME→spot basis pricing channel shuts.
   Major institutional desks reduce coverage for the weekend.
2. **Sat-Sun 24/7 spot tape** — dominated by retail order flow, smaller
   crypto-native market makers, and Asia-overnight activity. Lower depth,
   thinner books, higher per-trade impact.
3. **Sunday 18:00 ET CME re-open** — futures reprice to incorporate the
   weekend spot drift; first hours of CME futures often gap-fill or
   gap-extend depending on macro/Asia/regulatory news that broke during
   the weekend.
4. **Monday cash open (00:00 UTC Mon ≈ 19:00 ET Sun)** — large
   institutional re-engagement: rebalancing flows, ETF creation/redemption
   pre-trade prep, US RIA portfolios.

Two competing sub-theses:

**(A) Weekend continuation.** Weekend drift = real information loading
(Asia macro, regulation news, ETF flow expectations). Monday institutional
re-engagement *continues* the weekend direction as the slower-moving
institutional capital re-prices in agreement.

**(B) Weekend fade (reversion).** Weekend drift = retail-driven
overshoot in a thin tape. Monday institutional flow *re-prices the
mispricing*, fading the weekend move.

The literature is split. Caporale, Plastun & Oliinyk (2021) report a
weekend-effect on crypto with sign-inversion across sub-periods.
Aharon & Qadan (2019) document a "DOW effect" on BTC where Mondays carry
abnormal returns. The empirical sign on 2018-2026 BTCUSD is the open
question this thesis tries to answer.

## Why retail-accessible

- D1 cadence, plain BTCUSD CFD on Eightcap, 10 bps/side spread.
- No microstructure dependencies (no order-book reading, no L2, no
  imbalance feed).
- Single-instrument trade triggered once per week.
- Honest cost-model already validated on the broker (10 bps from
  `btc_trend` cost-sensitivity sweep).

## Why this thesis is structurally distinct from `btc_trend`

| dimension | btc_trend | btc_weekend |
|---|---|---|
| Mechanism | Slow trend continuation | Weekend microstructure (24/7-vs-5d) |
| Failure mode (TSMOM) | Parabola-V vulnerability | N/A (different family) |
| Regime exposure | Long during bulls, flat during bears | Symmetric per-weekend |
| Signal lookback | 12 months (slow) | 2 days (weekend only) |
| Trade cadence | 11/year (monthly rebal) | ~52/year (every Monday) |
| Holding period | Weeks to months | 1-3 days max |
| Institutional decay risk | Trend edge halving (W4 +0.50) | Gap-closing risk separate question |

The two strategies could conceptually coexist if both pass — they target
different timeframes on the same instrument, with naturally low
correlation between trend signal (long for months) and weekend signal
(1-3 day micro-bets).

## Key references

- **Caporale, Plastun, Oliinyk (2021)**, "The weekend effect in the
  cryptocurrency market." *Finance Research Letters*. Sign-inversion of
  weekend abnormal returns across 2014-2019 sub-periods on BTC.
- **Aharon & Qadan (2019)**, "Bitcoin and the day-of-the-week effect."
  *Finance Research Letters*. Abnormal Monday returns documented.
- **Eross, McGroarty, Urquhart, Wolfe (2019)**, "The intraday dynamics of
  Bitcoin." *Research in International Business and Finance*. Liquidity
  patterns across day-of-week with weekend dip.
- **Makarov & Schoar (2020)**, "Trading and arbitrage in cryptocurrency
  markets." *JFE*. Cross-exchange arbitrage opportunities most pronounced
  during low-institutional-flow windows (weekends specifically).

## Signal math

```
Parameters:
  HOLD_DAYS               = 1            (default exit: Mon close)
  MIN_DRIFT_PCT           = 1.0          (threshold on |weekend_drift|)
  COST_BPS_PER_SIDE       = 10.0         (honest BTC CFD)
  TRADE_DAY               = "Monday"     (entry weekday)

Per week:
  prev_friday_close   = close on Fri (last D1 bar with dow == Friday)
  this_monday_open    = open on Mon (first D1 bar with dow == Monday after prev_friday_close)
  weekend_drift_pct   = (this_monday_open / prev_friday_close - 1) * 100

  if |weekend_drift_pct| < MIN_DRIFT_PCT:  skip the week
  
  # Continuation direction:
  pos_cont = sign(weekend_drift_pct)
  # Fade direction (null/alternative):
  pos_fade = -sign(weekend_drift_pct)

  enter at Mon open, exit at close of bar (Mon + HOLD_DAYS - 1).
```

Variants:
- `MIN_DRIFT_PCT` ∈ {0.0, 0.5, 1.0, 2.0, 3.0, 5.0}
- `HOLD_DAYS` ∈ {1, 2, 3, 5}
- `COST_BPS_PER_SIDE` ∈ {5, 10, 20}
- Direction: continuation as primary; fade run alongside as null AND as
  alternative-hypothesis (per `gap_continuation` lesson #1 — fade can be
  the primary hypothesis in disguise; report both honestly).

## Universe

- **BTCUSD D1** on Eightcap MT5 (datalake cache).
- Period: **2018-01-01 → 2026-03-31** (8.25 years, ~430 Mondays).
- 24/7 confirmed by user 2026-05-13; weekend bars present 2022+ in local
  cache but Monday open captures weekend drift across all years (verified
  by Mon-vs-prior-Fri-close diff: avg |drift| 2.5-3.9% in 2018-2021,
  1.2-1.4% in 2022-2026).

## Expected performance

- **Magnitude of the underlying drift is HALVING** (3% → 1.4% from 2018-21
  to 2022+). Independent evidence of institutional arb pressure on the
  weekend microstructure. This is the load-bearing red flag.
- Phase 2 Sharpe target: **+0.30 to +0.60** in a winning direction, with
  fade-gap > +0.50.
- Trade count target: 200-300 over 8 years after threshold filter
  (~25-40 trades/year if filter clears ~50-75% of weeks).
- MDD target: < 15%.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:

1. **Sharpe < +0.30** at honest 10 bps/side cost in the best direction.
2. **Max DD > 20%**.
3. **Trade count < 200** over 2018-2026.
4. **Fade-gap < +0.50** (best-direction Sharpe minus opposite-direction
   Sharpe). Per `gap_continuation` lesson — if both directions lose
   similarly, no directional content. If both win, structural artifact.
5. **Cost-zero Sharpe < +0.30** — separates "no edge" from "edge eaten
   by friction" per lesson #26.

Phase 4 kills if Sharpe **positive in ≤ 2/4 regime windows**:
- W1 2018-2019 (early-retail crypto, futures-only institutional)
- W2 2020-2021 (parabola + COVID liquidity)
- W3 2022-2023 (FTX collapse + bear)
- W4 2024-2026 (ETF era, institutional 24/7 desks)

**Walk-forward Phase 6 (applied from Phase 2 per lesson #29):**
5 rolling 3y-IS / 2y-OOS splits. Kill if mean degradation > +0.5
OR fewer than 3/5 splits with OOS Sharpe > 0.

**Holdout-decay kill (per lesson #28):** if W4 (2024-2026) Sharpe is
more than +0.5 below W1 (2018-2019) Sharpe, the institutionalization
narrative is killing the edge and the strategy is regime-dependent on
the pre-ETF era — REJECT regardless of full-sample Sharpe.

## Why this might fail (red flags)

1. **Weekend |drift| is halving as BTC institutionalizes.** The 3% →
   1.4% drop from 2018-2021 to 2022+ is the same institutionalization
   signal that killed btc_trend's W4. If the underlying drift continues
   to halve, the per-trade gross drops below the 10 bps/side cost floor.
   This is the most likely structural killer.
2. **Sign-inversion track record.** "Fade overshoot" theses on equity
   indices have sign-inverted four times in this repo (DAX gap, DAX
   US-lead, DAX pre-auction, VWAP fade NDX). BTC weekend continuation
   vs fade has the same structural ambiguity — empirical sign is the
   open question.
3. **CME futures gap-close.** Sunday 18:00 ET CME re-open re-prices
   Saturday-Sunday spot drift. Most of the "weekend information"
   may already be priced into futures by Monday open, leaving no edge
   for spot CFDs.
4. **ETF flow expectations.** Since the 2024 spot ETF approval,
   weekend price action may simply be early-positioning for Monday ETF
   creation/redemption — meaning Monday institutional flow *confirms*
   the weekend direction (continuation should win), but with edge that
   decays as ETF arb becomes more efficient.
5. **0% null hypothesis.** Plain "Monday is a positive day on BTC" or
   "Monday is a negative day" could be the true distribution, with
   weekend_drift adding zero signal. The cost-zero Sharpe diagnostic
   (lesson #26) is the test.
6. **Phase 1 cherry-picking.** Two competing literature directions are
   cited; either one passing alone could be a 2-trial cherry-pick. The
   fade-gap criterion is the safeguard.

## Phase 1 → 2 plan

- [x] Thesis written
- [ ] Phase 2 baseline + threshold sweep + hold-period sweep + cost sweep
- [ ] Phase 4 regime breakdown (4 windows)
- [ ] Phase 5 parameter sensitivity (drift threshold, hold period)
- [ ] Phase 6 walk-forward (5 rolling 3y-IS/2y-OOS splits)
- [ ] Null check (fade direction as alternative hypothesis)
- [ ] Holdout-decay diagnostic (W1 vs W4 Sharpe difference)
- [ ] Verdict + STATE.md update

## Files

- Thesis: this file.
- Demo: `experiments/btc_weekend/btc_weekend_demo.py`.
- Data: `ohlc_data/BTCUSD_D1.csv` (cached from datalake).

---

## Phase 2 results (2026-05-13)

Run config: BTCUSD D1 2018-01-01 → 2026-03-31, 428 Mondays available, continuation
direction (long when weekend_drift > +threshold; short when < -threshold), `MIN_DRIFT_PCT=1.0`,
`HOLD_DAYS=1`, `COST_BPS_PER_SIDE=10.0`. Script: `btc_weekend_demo.py`.

### Phase 2 — baseline kill criteria

| metric | value | bar | verdict |
|---|---|---|---|
| Sharpe @ 10 bps | +0.61 | > +0.30 | PASS |
| MDD | **-40.56%** | < 20% | **FAIL** |
| Trades | 233 | ≥ 200 | PASS |
| Fade-gap | +1.86 (cont +0.61 vs fade -1.25) | > +0.50 | PASS |
| Cost-zero Sharpe | +0.93 | > +0.30 | PASS |
| **Phase 2 OVERALL** | — | — | **FAIL** (MDD) |

### Phase 4 — regime breakdown (continuation direction)

| window | trades | total ret | Sharpe | MDD | WR |
|---|---|---|---|---|---|
| W1 2018-2019 (early retail) | 72 | -7.83% | **-0.01** | -31.55% | 38.9% |
| W2 2020-2021 (parabola+COVID) | 66 | -14.94% | **-0.17** | -31.40% | 53.0% |
| W3 2022-2023 (FTX + bear) | 37 | +60.70% | **+2.11** | -11.53% | 59.5% |
| W4 2024-2026 (ETF era) | 57 | +57.34% | **+1.81** | -14.74% | 61.4% |

**Phase 4 verdict: FAIL.** Only 2/4 windows positive (need ≥ 3). The mechanism is dormant
in W1-W2 and active in W3-W4. Holdout-decay diagnostic: W1 Sh -0.01, W4 Sh +1.81,
decay **-1.82** — inverted (recent regime is best). Per lesson #25 (holdout-best pattern)
this is normally the strongest possible signal, but pre-2022 dormancy means the early-period
40% drawdown is a real risk in live deployment if the mechanism reverts to dormant.

Fade direction also lost in every window (W1 -0.61, W2 -0.40, W3 -2.71, W4 -2.65) — the
mechanism wasn't inverted in W1-W2, just weak (small fade-gap then, huge gap now).

### Phase 5 — parameter sensitivity (continuation)

| drift threshold | trades | Sharpe | MDD | CAGR |
|---|---|---|---|---|
| 0.0% | 428 | +0.300 | -61.1% | +4.62% |
| 0.5% | 318 | +0.410 | -56.5% | +6.05% |
| **1.0%** | 233 | **+0.613** | -40.6% | +8.37% |
| 2.0% | 143 | +0.374 | -41.5% | +2.39% |
| 3.0% | 98 | +0.041 | -49.8% | -1.48% |
| 5.0% | 47 | +0.530 | -29.8% | +1.56% |

| hold period | Sharpe | MDD |
|---|---|---|
| **1d** | **+0.613** | -40.6% |
| 2d | +0.138 | -64.7% |
| 3d | +0.204 | -66.4% |
| 5d | +0.054 | -83.8% |

**Edge is concentrated intra-Monday only.** 2d and longer destroy it.

| cost bps/side | Sharpe |
|---|---|
| 0 | +0.93 |
| 5 | +0.77 |
| **10 (honest)** | **+0.61** |
| 15 | +0.45 |
| 20 | +0.30 |
| 30 | -0.02 |

Cost-linear collapse: ~0.16 Sh drop per +5 bps. Breakeven near 30 bps. 10 bps is the
right operating point.

### Phase 6 — walk-forward (5 rolling 3y-IS / 2y-OOS splits)

| split | IS window | OOS window | IS Sh | OOS Sh | degradation |
|---|---|---|---|---|---|
| S1 | 2018-2020 | 2021-2022 | +0.02 | +0.30 | -0.28 |
| S2 | 2019-2021 | 2022-2023 | -0.11 | **+2.11** | -2.22 |
| S3 | 2020-2022 | 2023-2024 | +0.24 | **+3.60** | **-3.36** |
| S4 | 2021-2023 | 2024-2025 | +0.73 | **+2.39** | -1.65 |
| S5 | 2022-2024 | 2025-Q1 2026 | +2.82 | -0.57 | **+3.39** |

| metric | value | bar | verdict |
|---|---|---|---|
| Mean degradation | -0.826 | < 0.5 | PASS strongly |
| Median degradation | -1.653 | — | PASS |
| Splits w/ deg < 0.5 | 4/5 | ≥ 3 | PASS |
| Splits w/ OOS Sh > 0 | 4/5 | ≥ 3 | PASS |
| **Walk-forward OVERALL** | — | — | **PASS** |

Walk-forward strongly endorses the recent-era performance: S2-S4 all have OOS Sharpe
+2.1 / +3.6 / +2.4 with IS-only Sharpe near zero — meaning the strategy went from
"basically no edge" in IS-2018-2021 to "very strong edge" in OOS-2022-2025. S5's reversal
(IS +2.82 in 2022-2024 era → OOS -0.57 in 2025-Q1 2026) suggests the recent bull-top
parabola disrupted the mechanism, but the OOS slice is only 15 months including the
late-2025 mania.

### Verdict (2026-05-13): **REJECT** (full-history; two pre-committed criteria fail)

| phase | verdict |
|---|---|
| Phase 2 (MVI honest costs) | **FAIL on MDD** (-40.6% > 20%) |
| Phase 4 (regime stability) | **FAIL** (2/4 windows positive, need ≥ 3) |
| Phase 5 (parameter sensitivity) | PASS (clean plateau at 1% threshold) |
| Phase 6 (walk-forward) | PASS strongly (mean deg -0.826) |
| Null check (fade direction) | PASS (fade-gap +1.86) |
| Holdout-decay diagnostic | PASS (inverted — recent regime best) |

**Mechanism is real but regime-conditional.** The institutionalization narrative from
btc_trend appears in mirror image here: same driver, opposite mechanism activation.
btc_trend's edge halved as BTC matured (W4 Sh +0.50 vs +1.38/+1.61 earlier); btc_weekend's
edge appeared because BTC matured (W4 +1.81 vs W1 -0.01).

Pre-commit fails by two independent criteria, both rooted in the W1-W2 dormancy:
1. **MDD -40.56%** is the realized drawdown during the dormant period.
2. **Only 2/4 windows positive** because W1 and W2 lost money.

A live deployment would inherit the realized W1-W2 drawdown risk if the mechanism reverts
to dormant (e.g., regulatory shift retracting ETF status, CME futures volume collapse,
post-bubble institutional pullback). The post-2022 era is structurally compelling but
not structurally guaranteed.

**Per lumber_oats lesson — not a refinement candidate.** A "2022+-only with regime
detector" thesis is a separate Phase 1 with its own pre-committed criteria. Don't move
goalposts on this one.

**Cross-experiment finding (also written to RESEARCH_NOTES.md):** btc_trend and
btc_weekend are mirror images. Same BTC institutionalization driver, opposite mechanism
activation. The institutionalization narrative is now corroborated by TWO independent
strategy verdicts — making it a structural property of post-2022 BTC, not a single-thesis
artifact.
