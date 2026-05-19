# DAX Gap Fade

**Status**: Phase 2 complete 2026-04-20.

**Verdict**: **REJECT — thesis sign inverted**. Baseline fade Sharpe −1.04, all regimes negative (−0.89 / −1.45 / −1.25). Null-check (continuation) Sharpe **+0.12** > fade −1.04, gap **−1.16** (strongly inverted). **DAX gaps continue, they don't fade.**

**Mechanistic read**: the "auction overshoots → first hour fills gap" literature-based thesis is falsified on DAX M5 CFD. The continuation-positive result (+0.12 gross is weakly positive even before cost considerations) says gap-opens carry real information that is *under-priced* at the 09:00 auction and gets extended in the subsequent 30 min. Consistent with: (a) news-driven gaps on DAX are large-institutional-driven, not retail-panic, so auction prices are approximately efficient; (b) the first-30-min continuous session sees additional institutional pile-on rather than fade. The proposed "thin-auction-book" structural inefficiency either doesn't exist on Xetra's opening auction, or is too small to detect at M5 granularity.

**Leg split shows small asymmetry**: fade-LONG (i.e., long after down-gap) Sh −0.60 vs fade-SHORT (short after up-gap) Sh −0.90. Both losing, but down-gap-fade loses less. Consistent with secular DAX up-drift helping the long side even when the signal is wrong.

---

## Results summary

Baseline (fade, gap_min=0.5×ATR, hold=30min, cost=1pt):

| Metric | Value |
|---|---|
| Sharpe | −1.04 |
| Max DD | −13.98% |
| Trades | 995 (2.63/wk) |
| WR / PF | 44.3% / 0.68 |

**Threshold sweep**: 0.25 −1.21, 0.5 −1.04, 1.0 −0.92, 1.5 −1.31, 2.0 −0.92. All negative, no improvement at higher thresholds.

**Hold-window**: 15min −1.50, 30min −1.04, 60min −0.84, 120min −0.72. Longer hold is less-bad — the gap continuation is fastest in the first 15-30 min (fade takes immediate losses).

**Leg split**: both −1.04, fade-long −0.60, fade-short −0.90. Both losing.

**Null-check**: continuation +0.12, fade −1.04, direction-gap −1.16 (inverted). Continuation is real at ~zero Sharpe gross — a 0.5-1.0pt-cost retail CFD would still net negative. The mechanism exists but cannot survive friction.

**Possible revival**: a *continuation* variant with a wider hold (120min+) and a threshold on overnight-news-event days only might reach tradeable Sharpe — but requires external news-event data and would essentially be a news-momentum strategy, not a gap-fade strategy. Different thesis entirely.

---

## Thesis (mechanism)

The Xetra opening auction at 09:00 Berlin aggregates overnight orders from 17:30 prior-close to the next morning. Large overnight news (US after-hours earnings from DAX constituents' US ADRs, overnight ECB/Fed-adjacent wires, weekend geopolitical headlines) creates directional gap-opens. Literature (Fama 1965, Amihud/Mendelson 1987 on open-vs-continuous noise, more recent Gao/Han/Li/Zhou 2018 on gap-filling) suggests opening auction prices on single-venue markets systematically over-react relative to continuous-session equilibrium:

1. **Thin auction book on surprise news**: not all liquidity providers participate in the call auction, so extreme gap-opens settle at prices wider than continuous-session fair value.
2. **Retail order flow**: overnight-accumulated retail orders (stop-outs, panic-adds) participate in the auction and get filled at unfavourable prices that continuous-session market makers don't arb in the first 5 minutes.
3. **Net prediction**: on large-gap-open days (|gap| > threshold × ATR), first 30-60 minutes should fade the gap direction and close a portion of it.
4. **Different from ORB**: ORB entries require a *breakout* post-09:30 continuation; gap-fade entries trigger *at the open* when gap is already large — these are conditional-opposites and should filter to different days.

## Key references

- **Amihud & Mendelson (1987)**, "Trading Mechanisms and Stock Returns: An Empirical Investigation." *JF* 42(3). Opening-auction prices show higher noise and partial reversion in the first hour of continuous trading.
- **Fleming, Kirby & Ostdiek (1998)**, "Information and volatility linkages in the stock, bond, and money markets." *JFE* 49(1). Opening-hour reversion after news gaps.
- **Hendershott, Livdan & Rösch (2020)**, "Asset pricing: A tale of night and day." *JFE* 138(3). Structural model of night-return vs day-return cross-section.

## Signal math

```
Parameters:
  GAP_MIN_ATR              = 0.5    (only trade when |gap| >= GAP_MIN_ATR * ATR_daily)
  ENTRY_MODE              = "open_next_bar"   (enter at 09:05 open, second M5 bar of day)
  HOLD_MIN                 = 30     (exit 30 min after entry, configurable: 15/30/60)
  COST_POINTS_ROUND_TRIP   = 1.0

Per trading day d:
  prev_close = close of last bar of day d-1
  today_open = open of first bar of day d   (09:00-09:05 bar open)
  gap_px = today_open - prev_close
  atr = rolling 20-day ATR of daily close-to-close abs

  if |gap_px| < GAP_MIN_ATR * atr:  skip day
  pos = -sign(gap_px)  # fade
  enter at day d's second bar open (09:05)
  exit at open-of-bar-at HOLD_MIN-minutes-after-entry

  Max 1 trade per day.
```

Variant sweeps: GAP_MIN_ATR ∈ {0.25, 0.5, 1.0, 1.5, 2.0}, HOLD_MIN ∈ {15, 30, 60, 120}, cost ∈ {0.5, 1, 2, 3}pt. Null-check: trade *continuation* (same sign as gap) as direction-null. Also test directional asymmetry (up-gap-only, down-gap-only).

## Expected performance

Gap-fade literature on US equities 1990-2010 finds Sharpe 0.4-0.8 on unfiltered small-cap gaps, degrading to 0.2-0.4 post-2010 with liquidity. Index gaps are smaller and more efficient. Expected on DAX CFD net of 1pt RT: Sharpe 0.15-0.40 at threshold 0.5-1.0×ATR. 100-300 trades/year depending on threshold.

**Complementary to ORB**: ORB-LONG fires on break-above-OR-high (continuation of morning strength); gap-fade fires on large down-gaps that close. Trade correlation expected near-zero — useful blend-component even at modest Sharpe.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 150 (wider bar — high-threshold gap fades are infrequent by design).
- WR < 50% OR PF < 1.10 (mean-reversion payoff profile).
- Null-check direction-gap < +0.30 (fade - continuation).

Phase 4: ≥ 2 of 3 regime windows positive.
Phase 6: 2023-2026 holdout Sharpe ≤ 0.

## Why this might fail

1. **Gaps correlate with trending days**: large down-gap often starts a trending-down day (COVID March 2020, 2022 Russia-Ukraine gap, 2023 SVB weekend gap). Fade gets run over.
2. **DAX CFD gap liquidity** at 09:00-09:05 may have 2-5pt slippage on large-gap days that swamps the expected 10-30bp edge.
3. **Post-2020 regime**: central bank dovishness compressed DAX macro-news gaps dramatically 2020-2022; post-2022 gaps are more varied but could be structurally different from literature-era data.

## Files

- Thesis: this file.
- Demo: `gap_fade_demo.py` — baseline + threshold/hold sweeps + null-check + up-only/down-only split.
