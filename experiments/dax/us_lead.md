# DAX US → DAX Lead-Lag

**Status**: Phase 2 complete 2026-04-20.

**Verdict**: **REJECT — thesis sign inverted**. Baseline Sharpe −0.48, all 3 regimes negative (−0.12 / −0.94 / −0.45). Null-check (fade US lead) Sharpe −0.07 > continuation −0.48, gap −0.42 (inverted). DAX *fades* the US-open direction in its 15:45-17:15 Berlin window rather than continuing it.

**Mechanistic read**: by 15:45 Berlin the DAX has already absorbed the 09:30-09:45 ET SPX impulse through futures/ETF arb during the 15:30-15:45 overlap — so DAX is over-extended in the SPX direction at entry time, and mean-reverts toward fair value over the subsequent 90 min. This *is* a real mechanism (fade-gap is non-trivial at +0.42 magnitude, just with the wrong sign to the original thesis), but fade Sharpe of −0.07 at 1pt cost is not tradeable and gross-fade-direction is barely positive even ignoring cost. Arb efficiency at the 15:30-15:45 handoff is the likely culprit.

**Data bug flag**: the variant sweep cell `window=30min` shows Sharpe +1.60 — this is a **look-ahead artifact**. At 30min signal window, SPX close at 10:00 ET = 16:00 Berlin = 15 minutes *after* the DAX 15:45 entry. The 5min and 15min cells are time-legitimate (both complete before 15:45 Berlin); the 30min cell is not and should be ignored.

---

## Results summary

Baseline (continuation, SPX 15m signal, DAX 15:45-17:15, thr=0.25, cost=1pt):

| Metric | Value |
|---|---|
| Sharpe | −0.48 |
| Max DD | −19.05% |
| Trades | 1,470 (3.88/wk) |
| WR / PF | 47.6% / 0.90 |

**Regime breakdown**: −0.12 / −0.94 / −0.45. Worst in 2021-2022, holdout also negative.

**Signal-window sweep**: 5min −0.45, 15min −0.48, 30min +1.60 (**look-ahead — discard**). The 5min/15min cells are the legitimate ones and both fail.

**Hold-window sweep** (exit time): 16:45 −0.41, 17:15 −0.48, 17:25 −0.30. Modestly better with longer hold through pre-close, but still negative.

**Threshold sweep**: thr=0.0 −0.49, thr=0.25 −0.48, thr=0.5 −0.42, thr=1.0 −0.06. Only the extreme-move filter (thr=1.0, 690 trades) approaches zero — consistent with the fade interpretation: large SPX moves over-shoot DAX and have the strongest reversion.

**Cost sweep**: 0.5pt −0.35, 1pt −0.48, 2pt −0.76, 3pt −1.03. Monotonic worsening.

**Null-check**: fade −0.07, continuation −0.48, gap −0.42 (inverted). Fade is directionally real but absolutely near-zero — arbed down close to noise.

---

## Thesis (mechanism)

The DAX cash session (09:00-17:30 Europe/Berlin) overlaps with the NYSE RTH session (15:30-22:00 Berlin = 09:30-16:00 ET) for 2 hours. The first 15-30 minutes of NY RTH on most days contains significant overnight-information resolution — the SPX/ES direction at 09:30-09:45 ET is typically the most information-dense 15-min window of the global day outside of scheduled macro releases. Transmission from US equity futures into European cash indices during this overlap:

1. **Correlation lags**: DAX ETFs and futures are arbitraged to US futures at ms-latency, but DAX CFD retail and cash-equity flow reacts on minutes-to-hours timescales.
2. **Direction informativeness**: a decisive SPX first-15-min move resolves overnight uncertainty and typically persists for 1-3 hours on both indices due to institutional position-building.
3. **Net prediction**: the sign of SPX 09:30-09:45 ET return predicts DAX 15:45-17:15 Berlin return, with magnitude proportional to SPX |return| scaled by prior-day ATR.
4. **Distinct from ORB** (the existing DAX deploy candidate): ORB entries are at 09:30-12:00 Berlin on DAX's own opening impulse. This thesis uses *external* signal (US open) and trades a *different window* (15:45-17:15 Berlin). The two strategies are structurally non-overlapping and potentially combinable.

## Key references

- **Becker, Finnerty & Friedman (1995)**, "Economic news and equity market linkages between the U.S. and U.K." Early cross-market lag evidence.
- **Brooks, Rew & Ritson (2001)**, "A trading strategy based on the lead-lag relationship between the spot index and futures contract for the FTSE 100." Quantifies minute-scale lag; reports edge erosion 1990s-2000s on FTSE.
- **Rapach, Strauss & Zhou (2013)**, "International Stock Return Predictability: What Is the Role of the United States?" *JF* 68(4). US returns predict non-US market returns at weekly horizons; the intraday analog is the working hypothesis here.

## Signal math

```
Parameters:
  SPX_SIGNAL_WINDOW_MIN     = 15     (measure SPX return over first 15 min of ET RTH)
  ENTRY_BERLIN_TIME         = 15:45  (= 09:45 ET, one SPX_SIGNAL_WINDOW_MIN past open)
  EXIT_BERLIN_TIME          = 17:15  (90-min hold on DAX)
  MIN_MOVE_ATR              = 0.25   (threshold on |spx_return| / ATR_spx_m5)
  COST_POINTS_ROUND_TRIP    = 1.0

Per trading day d (both SPX and DAX must trade):
  spx_first_bar  = first SPX M5 bar with ET time >= 09:30
  spx_signal_bar = first SPX M5 bar with ET time >= 09:45
  r_spx = close[spx_signal_bar] / open[spx_first_bar] - 1

  atr_spx = rolling-20-day ATR of SPX first-15-min absolute return

  if |r_spx| < MIN_MOVE_ATR * atr_spx:  skip day
  pos = sign(r_spx)  # continuation

  dax_entry_bar = first DAX bar with Berlin time >= 15:45
  dax_exit_bar  = first DAX bar with Berlin time >= 17:15
  enter DAX at dax_entry_bar + 1 open, exit at dax_exit_bar close.

  Max 1 trade per day.
```

Variant sweeps: SPX_SIGNAL_WINDOW ∈ {5, 15, 30}, hold ∈ {60, 90, 120, 150}min, threshold ∈ {0.0, 0.25, 0.5, 1.0}, cost ∈ {0.5, 1, 2, 3}pt. Null-check: trade opposite sign (fade the US lead).

## Expected performance

Cross-market intraday lag studies 2010-2020 typically find 1-3bps per 60-90min hold net of ms-latency arb. Retail CFD at 1pt RT (~6bps) would likely be adverse. Expected Sharpe -0.1 to +0.3 — *not* a slam dunk; the interesting cell is whether threshold + regime filter can make it viable.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200.
- WR < 48% OR PF < 1.05.
- Null-check fade-gap < +0.30 (continuation - fade Sharpe).

Phase 4: ≥ 2 of 3 regime windows positive.
Phase 6: 2023-2026 holdout Sharpe ≤ 0.

## Why this might fail

1. **Heavily arbed at institutional timescales**. CFD M5 latency is a 5+ minute disadvantage vs a futures colo shop.
2. **Days when DAX already moved in same direction before US open**: if overnight futures already priced the US information, the 09:30 ET move is noise on remaining DAX continuation.
3. **DAX close-auction crossover risk**: the 17:15-17:30 window has pre-auction flow that may overwhelm the lag signal. Exit at 17:15 is conservative but tight.
4. **Data-alignment edge cases**: US holidays (MLK, July 4, Thanksgiving) when DAX trades but SPX doesn't — must skip those days, shouldn't bias results.

## Files

- Thesis: this file.
- Demo: `us_lead_demo.py` — loads both SPX500 and GER40 M5, signal-from-SPX with DAX execution.
