# Bollinger-Band Reversion on index CFDs (M5)

**Status**: Phase 2 complete 2026-04-19 — **REJECT across all 4 tested instruments.**
**Verdict**: 2σ BB mean-reversion at M5 is not deployable on SPX500 / NDX100 / GER40 / UK100. NDX100 is least-bad (Sharpe -0.34 full, +0.05 holdout, fade-gap +0.50 confirming weak real mean-reversion signal) but still negative at any plausible cost. GER40 has fade-gap -0.55 — confirms DAX's directional bias is trend-continuation (consistent with ORB result), not reversion.
**Kept as**: methodological reference — demonstrates the fade-gap diagnostic correctly separates "direction of edge" from "magnitude of edge".
**Motivation**: cross-instrument ORB testing (see [`experiments/orb/orb.md`](../orb/orb.md)) showed that on NDX100 under tight R:R exits, **fade beats baseline** — short-term mean reversion dominates. This is a seed for a proper mean-reversion thesis. UK100 also failed ORB; might work for mean-reversion. Testing the hypothesis on the same 5 instruments where ORB was evaluated.
**Primary target**: **UK100** (where ORB failed decisively; FTSE's wider sector rotation + less coherent opening-impulse may imply stronger intraday mean reversion than DAX). **Also cross-reference on NDX100** (where tight-R:R fade already showed signal) and run GER40/SPX500/FRA40 for completeness.

## Thesis (mechanism)

After a sharp intraday price move that takes the market to a statistical extreme (close > 2σ from the 20-bar M5 mean), there's a measurable tendency for price to revert toward the mean on the same session, driven by:

1. **Short-term overreaction to news / order flow** — retail and algo-driven chase pushes price past fundamental repricing, then bleeds back as fundamental players arrive.
2. **Intraday liquidity provision by market makers** — when price overshoots at the M5 timescale, MM inventory imbalances create counter-pressure.
3. **Session-bounded mean reversion** — intraday mean reversion is most documented in equity indices during RTH. Overnight leaves the horizon, so intraday is the relevant timescale.

This is a **price-only** strategy — no volume data required, which matters on CFDs where `real_volume = 0`. No VWAP, no Zarattini-style volume filter needed.

## Why retail-accessible

1. **M5 cadence**: ~288 candles/day on a 24h CFD, ~78 during RTH. Plenty of data. Not HFT — retail MT5 execution is fine.
2. **CFD spreads of 0.5-1 pt** on major indices are negligible relative to typical 2σ move (~15-40pt on GER40, ~20-50pt on NDX100).
3. **Mechanically simple**: 20-bar SMA, 20-bar σ, close vs band — three lines of pandas.
4. **Well-documented effect**: mean-reversion on equity-index intraday timescales has been shown in academic literature (Lo/MacKinlay, Jegadeesh). Effect size has eroded over decades but not fully arbitraged.

## Signal math

```
Parameters:
  BB_PERIOD  = 20        # 20 M5 bars = 100 min rolling window
  BB_SIGMA   = 2.0       # band = mean ± 2.0 σ
  ENTRY_CUTOFF_MIN_FROM_OPEN  = 60   # skip first hour (BB needs warm-up + opening noise)
  EXIT_CUTOFF_MIN_BEFORE_CLOSE = 15  # hard flatten 15 min before close
  ONE_PER_DIRECTION_PER_DAY = True   # max 1 long + 1 short per day

Per M5 bar (RTH only):
  mean   = rolling(BB_PERIOD).mean()
  sigma  = rolling(BB_PERIOD).std(ddof=1)
  upper  = mean + BB_SIGMA * sigma
  lower  = mean - BB_SIGMA * sigma

Entry (at M5 bar close, filled at next bar open):
  if close > upper and flat and !long_taken_today:
    SHORT                                      # fade the upper extreme
    stop = entry + stop_atr_mult * ATR(14)     # hard stop above
    target = mean_at_entry                      # take profit on midline touch
  if close < lower and flat and !short_taken_today:
    LONG                                       # fade the lower extreme
    stop = entry - stop_atr_mult * ATR(14)
    target = mean_at_entry

Exit:
  - Stop hit (high >= short_stop or low <= long_stop) → stop out
  - Target hit (price touches midline) → take profit
  - EOD cutoff → flatten at market
```

## Variants to sweep

For Phase 2b after baseline:
- BB period: 10, 20, 40
- BB sigma: 1.5, 2.0, 2.5
- Stop type: fixed ATR mult, opposite-band breach, none (midline-or-EOD only)
- Target type: midline, 1σ from mean, opposite band

## Expected performance

- **UK100**: primary target. If FTSE's commodities-heavy + international mix genuinely lacks DAX's coherent directional opening-impulse, mean reversion should work better here than DAX. Expected Sharpe 0.3-0.8 research, 0.1-0.3 live.
- **NDX100**: secondary. Already showed fade > baseline on ORB under tight R:R. This strategy cleanly tests the same mechanism with proper mean-reversion triggers. Expected Sharpe 0.3-0.7.
- **GER40**: cross-reference. If BB reversion also works on DAX, DAX has BOTH an opening-momentum and a mean-reversion edge — plausible since they operate on different timescales (ORB uses 30-min OR, BB uses 100-min rolling). But more likely DAX is momentum-dominant and BB fails.
- **SPX500**: control. Where ORB failed decisively. If BB also fails here, confirms SPX500 M5 is genuinely a hard instrument for retail mechanical strategies.
- **FRA40**: same data-limitation as ORB. Skip or note inconclusive.

## Fail conditions (pre-committed)

Phase 2 kills if:
- Full-period Sharpe < 0.30 after 1pt/round-trip cost
- Max DD > 25%
- Trade count < 200 over 7 years
- WR < 35% AND PF < 1.15 (higher bar than ORB because mean reversion should have higher WR)
- Fade-test positive — if the "trend-follow" variant (long on upper break, short on lower break) has Sharpe within ±0.2 of the baseline, signal has no directional content

Phase 4 kills if Sharpe positive in ≤ 2 of 3 regime windows (2019-2020 / 2021-2022 / 2023-2026 holdout).

## Why this might fail (red flags)

1. **Mean reversion on intraday indices has decayed for 20+ years.** The Jegadeesh (1990) effect on equity returns was strong in pre-electronic markets; modern HFT inventory management arbitrages a lot of it away. We're betting on residual retail-scale inefficiency.
2. **2σ Bollinger is a simple/exposed signal.** Every retail backtester on YouTube has tested this. If the edge existed cleanly, it'd be on GitHub 100× over. Expect marginal-at-best results.
3. **Trend days are mean-reversion killers.** On strong-trend days (big-news, macro, regime shifts), a 2σ break isn't "overextended" — it's the early leg of a much bigger move. Expect significant losses on those days.
4. **Stop sizing is critical.** Mean-reversion strategies live or die on stop discipline. Too-tight stop = whipsaws. Too-wide stop = catastrophic trend-day losses. ATR-based stops are the retail-common answer but not always optimal.
5. **The "fade beats baseline" on NDX100 under tight R:R in the ORB work was a weak signal**, not a strong green flag. We should expect modest-to-absent signal when we go test it properly.

## Phase 2 result — REJECT across 4 instruments (cross-reference of ORB verdicts)

Ran `bb_reversion_demo.py` on each instrument (FRA40 skipped — broker data issue documented in orb.md). Baseline config: BB period 20, σ 2.0, ATR stop ×1.5, midline target, 1pt/round-trip cost, session-filtered, first hour skipped for BB warm-up, flat 15 min before close.

| Instrument | Full Sh | Holdout Sh | MDD | Trades/wk | Fade-gap | Verdict |
|---|---|---|---|---|---|---|
| UK100 | **-1.96** | -1.81 | -42% | 8.8 | +0.78 | REJECT |
| **NDX100** | **-0.34** | **+0.05** | -20% | 8.2 | **+0.50** | REJECT (closest to viable; still negative at 1pt cost, breakeven at 0.5pt) |
| GER40 | -1.59 | -2.11 | -42% | 8.8 | **-0.55** | REJECT (fade-gap NEGATIVE — trend, not reversion, dominates DAX) |
| SPX500 | -2.16 | -2.25 | -55% | 8.1 | +0.82 | REJECT |

### Cross-reference with ORB results

| Instrument | ORB verdict | BB-reversion verdict | Interpretation |
|---|---|---|---|
| GER40 | PASS (Sh +0.58, T+180min) | REJECT with NEGATIVE fade-gap | **DAX is trend-dominant at M5.** Both tests agree on direction. |
| NDX100 | MARGINAL (Sh +0.03) | REJECT (Sh -0.34) with POSITIVE fade-gap | **NDX has weak mean-reversion tendency.** BB reversion confirms what ORB tight-R:R fade test hinted at. Neither breakout nor reversion is deployable. |
| SPX500 | REJECT (Sh -0.92) | REJECT (Sh -2.16) | **No retail-mechanical edge at M5.** Both fail decisively. |
| UK100 | REJECT (Sh -0.54) | REJECT (Sh -1.96) | **FTSE M5 is mechanically unfavorable.** Wide sector rotation + diffuse flow → neither direction works. |

### Key takeaways

1. **The fade-gap diagnostic is validated as a methodology.** GER40's negative BB-reversion fade-gap (-0.55) correctly tells us DAX wants trend-continuation — which matches what ORB's +1.04 fade-gap already established. Applying the diagnostic to two opposite mechanisms on the same instrument gives consistent direction.

2. **The "direction of edge" and "magnitude of edge" are different questions.** NDX100 BB-reversion has a real directional signal (fade-gap +0.50) but negative absolute Sharpe. Mean reversion IS the right direction on NDX100 — it's just too weak to overcome costs.

3. **Trend vs reversion is a structural property of the instrument, not the strategy.** Two mechanically different strategies (OR breakout, 2σ mean reversion) produce consistent directional verdicts per instrument. That's evidence the tests are measuring something real about the underlying market microstructure.

4. **2σ BB reversion is a retail-saturated setup.** Not a surprising result — this is one of the first strategies every retail trader codes. Residual edge is ≤ cost drag.

### What would salvage this

- **Wider bands + longer mean** (σ=3.0, period=50) to filter only extreme statistical outliers — may fire too infrequently for useful trade count.
- **Volume-weighted mean** instead of equal-weighted SMA — but CFDs lack real volume (see orb.md discussion).
- **Mean reversion to VWAP using tick-volume proxy** — would need the VWAP infrastructure; tick-volume quality varies by broker/instrument.
- **Session-anchored midpoint** (reset BB at session open each day) rather than rolling — might catch intraday reversions better than running-window BB that bleeds across sessions.
- **Filter by regime** — only trade BB reversion on low-VIX days where trend-days are rarer.

All of these are **speculative improvements**, not things the data supports as likely to work. The cleanest read is: M5 BB reversion on index CFDs is a dead mechanism for retail; move on.

## Files

- Thesis: `experiments/bb_reversion/bb_reversion.md` (this file — tombstoned 2026-04-19)
- Demo: `experiments/bb_reversion/bb_reversion_demo.py` (instrument-agnostic, env-var-driven; kept for reference)
- Data: reuses `ohlc_data/{SPX500,NDX100,GER40,UK100}_M5.csv` from the ORB work

## References

- Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns". JoF.
- Lo, A. W., & MacKinlay, A. C. (1990). "When are Contrarian Profits Due to Stock Market Overreaction?" RFS.
- Bollinger, J. (2001). *Bollinger on Bollinger Bands* — retail-practitioner reference.
