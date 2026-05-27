# Structural-flow calendar audit — Phase 0 screen

**Status**: Phase 0 screen — methodology experiment, NOT a single-strategy thesis lock.
**Verdict**: (table populated by run)

---

## Purpose

Surface candidate event×instrument×window cells from the *structural / forced-flow* idea-source category that the existing deploy book under-uses (0 of 6 deploys come from this source per the live-book origin audit, 2026-05-27).

This is **not** a thesis-locked experiment. Each cell in the output table is a *candidate* worth a Phase 2 thesis-lock IF it clears the screen — the screen itself is not a deploy-decision. Surviving cells get their own thesis docs and pre-committed kill criteria in separate experiments.

## What "structural / forced-flow" means

Events on the calendar that move price by **mechanical necessity** — dealer hedging, pension rebalancing, options-OI unwind, month-end fix-flow, futures expiration auctions — rather than discretionary information processing. These flows happen regardless of macro narrative, are scheduled to the day or hour, and are visible to anyone with a calendar but **rarely tested systematically** outside academic event studies.

The repo's only deploy from this family is `event_calendar` (FOMC/CPI/RS/NFP — anticipation-window flow); this audit extends the family across dealer-hedging / month-end / OPEX-adjacent windows that haven't been screened.

## Methodology

For each `(event_type, instrument, window_local_tz)` grid:

1. **Build event date list** rule-based (no external CSV — uses pure calendar rules: last business day of month, Wed before 3rd Fri, etc.).
2. **Compute window return** per event: enter at window_start, exit at window_end (intraday only for v1).
3. **Compute placebo**: same window on same weekday(s) on non-event days within the dataset range.
4. **Null-gap** = event_mean − placebo_mean (the "edge" attributable to the event, not the weekday/time-of-day).
5. **t-stat** of null-gap (Welch's t-test between event and placebo populations).
6. **Cost headroom** = |null_gap_bps| − instrument_cost_floor_bps.
7. **Composite score** = |t-stat| × sign(cost_headroom).

Output: ranked candidate table.

## Cells screened (v1 — intraday only)

| # | Event | Instruments | Window (local) | Calendar rule |
|---|---|---|---|---|
| 1 | JPM Hedged Equity collar reset | SPX500, NDX100 | 15:00-16:00 ET | Last biz day of Mar/Jun/Sep/Dec |
| 2 | Month-end WMR FX fix | EURUSD, USDJPY, GBPUSD | 15:45-16:15 London | Last biz day of every month |
| 3 | VIX SOQ (settlement) | SPX500 | 08:30-09:30 ET | Wed before 3rd Fri |
| 4 | OPEX day-after gamma unwind | SPX500, NDX100 | 09:30-12:00 ET | Mon after 3rd Fri |
| 5 | Quarterly triple-witch closing hour | SPX500, NDX100 | 15:00-16:00 ET | 3rd Fri of Mar/Jun/Sep/Dec |
| 6 | Month-end USD funding squeeze | EURUSD, USDJPY, GBPUSD | 14:00-15:00 ET | Last biz day of every month |
| 7 | Quarter-end pension last-day rebalance | SPX500, NDX100, XAUUSD, EURUSD | 14:00-16:00 ET | Last biz day of Mar/Jun/Sep/Dec |

Total: ~18 grids. Each cell ≥ 15 events → enough power for null-gap t-test at the screen level.

## Multi-day candidates (deferred to v2)

These need a different return-aggregation path (multi-day windows, not intraday). Not in v1:
- Japan fiscal year-end (Mar 31 ± 5d) on USDJPY
- Tax-loss harvesting concentration (Dec 15-31) on equities
- Tax-loss reversal (Jan 2-15) on equities
- ECB TLTRO repayment dates on EURUSD (also needs external calendar)
- PBOC quarterly liquidity ops on AUDUSD/copper (also needs external calendar)

## Decision rules (set before running)

The output table will rank cells by composite score. Surviving-cell thresholds for "worth Phase 2 thesis lock":

| Tier | Threshold | Action |
|---|---|---|
| **Strong** | t-stat > 2.5 AND cost-headroom > 1 bp AND n ≥ 20 | Lock Phase 2 thesis immediately |
| **Medium** | t-stat > 1.8 AND cost-headroom > 0 AND n ≥ 15 | Queue for thesis lock after data-source audit |
| **Weak** | t-stat > 1.3 OR cost-headroom > 2 bp (one of the two) | Mark for refinement (different window / different direction) |
| **Reject** | otherwise | Document and tombstone — won't be re-screened |

## Why this is NOT a thesis-locked experiment

Phase 2 needs pre-committed kill criteria *per strategy*. This audit is a *screen* — it can't pre-commit per-candidate criteria because the candidates don't exist until the screen runs. The screen's own discipline is:

1. Decision rules set before running (above table)
2. Composite score formula fixed before running (|t-stat| × sign(cost_headroom))
3. Universe of events + instruments + windows enumerated before running (table above — no post-hoc additions)
4. Surviving cells get a separate thesis doc with their own pre-commits

This separation prevents the screen from becoming a "fish for any cell that looks good" exercise.

## Cost floor assumptions (Eightcap retail CFD, approximate RT in bps)

| Instrument | Cost floor RT (bps) |
|---|---|
| SPX500 | 5 |
| NDX100 | 4 |
| EURUSD | 1.5 |
| USDJPY | 2 |
| GBPUSD | 2 |
| XAUUSD | 7 |
| GER40 | 4 |

## Files

- [structural_flow_audit.py](structural_flow_audit.py) — single-script screen + ranking
