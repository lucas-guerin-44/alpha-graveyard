# Equity Pairs Trading (mega-cap cointegration)

**Status**: REJECTED at Phase 2
**Verdict**: REJECT — robust failure. Full-period Sharpe -0.99, return -41%, MDD -44%. All 10 pairs negative, all 5 regime windows negative including calm 2015-2017 (Sharpe -0.56). Not a tuning problem — mega-cap US equity pairs have been non-mean-reverting in this era.

## Thesis (mechanism)

Two fundamentally-linked mega-caps (same industry, similar cost structure, similar customer base) cannot diverge indefinitely. When their price ratio drifts far from its rolling-window mean — due to transient flows (index rebalances, earnings noise, sector rotations, single-stock news) — the divergence tends to revert over days to weeks.

Trade: when the spread's z-score exceeds ±2σ, enter a dollar-neutral long-short (buy the loser, sell the winner, hedge-ratio sized). Exit when |z| < 0.5 (mean reversion) or at a 3σ stop-loss (structural break). Time-stop at 20 bars.

This is **market-neutral by construction** — the long and short legs cancel equity-market beta to the extent the hedge ratio is calibrated. The P&L source is the spread, not the direction of either stock.

## Why retail-accessible

1. **Liquidity is free at mega-cap scale.** Every pair we'll use trades > $1B/day; bid-ask is 1-2 bps. Retail-size orders are rounding error to the book.
2. **Short availability is easy on mega-caps.** KO, PEP, XOM, CVX etc. are all on IB's EasyToBorrow list; borrow costs 25-50 bps annually, not the 5-20% that kills small-cap pairs.
3. **Why hasn't it been arb'd away?** It mostly has — at institutional scale, stat-arb pairs is a Sharpe ~0.3 business post-costs. BUT: institutional stat-arb operates on thousands of pairs with millisecond execution and needs Sharpe 1.5+ to cover infrastructure. A retail book of 10 hand-picked mega-cap pairs on daily bars doesn't compete with them — the retail drag is lower (no collocation cost, no prime broker fee) even if the gross edge is smaller.
4. **Well-documented.** Gatev, Goetzmann & Rouwenhorst (2006) "Pairs Trading: Performance of a Relative-Value Arbitrage Rule" is the canonical reference, ~11% CAGR pre-cost, ~6% net with realistic assumptions, post-2002 decay documented.

## Universe

10 pairs, chosen for tight fundamental linkage AND liquid retail shortability:

| Pair | Sector | Why linked |
|---|---|---|
| KO / PEP | Staples (beverages) | Near-identical product mix + distribution |
| XOM / CVX | Integrated energy | Same crude exposure, same refining cycle |
| JPM / BAC | Big banks | US retail banking + capital markets overlap |
| V / MA | Card networks | Duopoly, identical revenue model |
| HD / LOW | Home improvement | Same customer base, same housing cycle |
| UNH / CI | Managed care | Same regulatory regime + medical-cost trends |
| PG / CL | Staples (home/personal care) | Near-identical product categories |
| WMT / TGT | Big-box retail | Same demographic, same logistics challenges |
| LMT / RTX | Defense | Same DoD budget cycle, similar program mix |
| GS / MS | Investment banks | Same capital-markets + wealth-mgmt revenue mix |

Timeframe: daily bars. Period: 2015-01-01 to 2026-04-18. Data source: Yahoo Finance (split/dividend-adjusted close).

### Pairs deliberately excluded

- **MSFT / GOOGL**: business models have diverged (cloud-heavy vs ads-heavy post-2020). Fundamental link no longer holds.
- **DIS / CMCSA**: streaming-era divergence — Disney vs cable-first Comcast. Not cointegrated post-2019.
- **Any pair requiring hard-to-borrow small-caps**: breaks the "retail-accessible" claim.

## Signal math

```
For each pair (A, B):

  # 60-day rolling OLS hedge ratio — residual hedging, not equal-weight.
  beta[t] = Cov(log(A[t-60:t]), log(B[t-60:t])) / Var(log(B[t-60:t]))

  spread[t]  = log(A[t]) - beta[t] * log(B[t])
  mu[t]      = rolling_mean(spread, 60)
  sigma[t]   = rolling_std(spread, 60)
  z[t]       = (spread[t] - mu[t]) / sigma[t]

Entry (when flat):
  z[t] > +entry_z (2.0)  -> SHORT pair (short A, long beta*B)
  z[t] < -entry_z (2.0)  -> LONG  pair (long A, short beta*B)

Exit (when in position):
  |z[t]| < exit_z (0.5)           -> take profit
  |z[t]| > stop_z (3.5)            -> stop loss (structural break)
  bars_held >= max_hold (20)      -> time stop
```

Position sizing:
- Equal dollar-risk per active pair: target 1% of equity per pair at 2σ-worth of move.
- Gross exposure capped at 3x equity (at most 10 pairs × ~0.3x gross each).
- Hedge ratio β is rolling 60-day; re-evaluated daily, locked at entry.

Costs (per leg, retail):
- 1 bps commission (IB fixed-tier)
- 4 bps slippage (mid to aggressor, mega-cap)
- 30 bps/yr borrow on short leg (0.12 bps/day × 20-day avg hold)
- Total roundtrip per pair: ~12 bps + 3 bps borrow drag ≈ **15 bps all-in**

## Expected Sharpe range

Literature benchmarks (retail-realistic):
- Gatev/Goetzmann/Rouwenhorst 1962-2002 (full history): Sharpe 1.3 gross, 0.6 net.
- Do & Faff (2010) — 2003-2008 post-cost: Sharpe 0.3-0.5 at retail scale.
- Krauss (2017) survey — post-2010 persistence: Sharpe 0.2-0.5 on standard z-score rules.

**Expected for this 10-pair, 2015-2026, retail-net**: Sharpe **0.4-0.7**, CAGR **8-12%**, Max DD **8-12%**.

Correlation vs XS-mom: **near zero by construction** (long-short market-neutral). This is the real prize — even a modest Sharpe here is additive to the book.

## Fail conditions (pre-committed)

Phase 2 kills if:
- Full-sample Sharpe < 0.30.
- Max DD > 15% (this is meant to be the *controlled-DD* strategy — more than 15% means the risk model is broken).
- Trades < 100 across 11 years × 10 pairs (would imply signal rarely fires — not enough to estimate edge).
- Single pair contributes > 40% of total P&L (too dependent on one pair's quirks).
- Any pair has > 5 consecutive stop-outs at 3σ (that pair's fundamental link broke — needs review, not automatic reject).

Phase 4 kills if:
- Sharpe positive in ≤ 2 of 4 regime windows.

Phase 6 kills if:
- OOS 2023+ Sharpe ≤ 0.

## Known risks to the mechanism

1. **Structural breaks.** Any industry can have a pair decouple permanently (telecoms + 5G capex, banks + fintech, etc.). The 3σ stop + per-pair review catches this eventually but after some damage.
2. **Earnings timing.** Earnings releases create the biggest dislocations — great signal — but also the biggest stop-out risk if the divergence is information-driven. Option: skip entries within ±3 days of either name's earnings. Start without this filter (simpler) and see if it's needed.
3. **Cointegration assumption is weak.** We're using rolling z-score, not a formal Engle-Granger test. If β drifts too fast, the spread becomes non-stationary and "mean reversion" is a fiction. A 60-day rolling β handles slow drift OK; a Kalman filter would be better but adds complexity. Start simple.
4. **Mega-cap pairs correlations broke in 2020.** COVID-era cross-sectional dispersion was extreme. 2020 is in-sample — we'll see in the regime split whether it was a blowup year.
5. **Factor risk (not isolated).** Long-short of KO/PEP is still partly a "staples factor" bet; XOM/CVX is an "integrated-major" bet. We aren't getting pure idiosyncratic risk, we're getting residual-factor risk with the direction hedged. Shouldn't change the Sharpe story much but worth noting.

## Phase 2 — actual result (REJECT)

Ran `experiments/equity_pairs/equity_pairs_demo.py` with baseline params (2σ entry, 0.5σ exit, 3.5σ stop, 20-bar time stop, 60-bar rolling β, 0.30× gross per pair, 12 bps roundtrip + 30 bps/yr borrow).

### Kill-criteria scorecard

| Criterion | Actual | Status |
|---|---|---|
| Full Sharpe > 0.30 | **-0.99** | FAIL (by 1.3 Sharpe — enormous miss) |
| Max DD < 15% | **-43.59%** | FAIL (by 3×) |
| Total trades ≥ 100 | 540 | pass |
| No pair > 40% of P&L | 24.9% | pass |
| Full return | **-41.44%** | target was +10%/yr |
| Worst single day | -3.49% | OK |

### Per-pair contribution (rank by total return)

| Pair | Total ret | Sharpe | MDD | Win% |
|---|---|---|---|---|
| HD/LOW | +1.30% | +0.10 | -2.97% | 50.8% |
| KO/PEP | -2.43% | -0.20 | -6.04% | 43.4% |
| JPM/BAC | -3.15% | -0.25 | -4.07% | 48.3% |
| GS/MS | -4.40% | -0.34 | -6.11% | 36.2% |
| XOM/CVX | -4.86% | -0.35 | -6.91% | 35.6% |
| LMT/RTX | -4.96% | -0.33 | -7.49% | 46.2% |
| PG/CL | -5.54% | -0.43 | -7.91% | 42.9% |
| V/MA | -6.24% | -0.61 | -6.98% | 36.0% |
| UNH/CI | -8.32% | -0.28 | -13.84% | 40.3% |
| WMT/TGT | -12.80% | -0.62 | -14.39% | 32.7% |

**9 of 10 pairs negative.** Only HD/LOW cleared zero, and barely.

### Regime breakdown

| Window | Sharpe | Return |
|---|---|---|
| 2015-2017 (calm) | -0.56 | -6.0% |
| 2018-2019 | -2.11 | -18.1% |
| 2020 (COVID) | -1.51 | -8.2% |
| 2021-2022 | -0.73 | -5.9% |
| 2023-2026 | -0.65 | -12.1% |

**All 5 windows negative**, including the calm low-vol 2015-2017 period where pairs should be easiest.

### Why it failed (diagnosis)

Trade-exit distribution across pairs (aggregated): ~25% mean-reversion exits, ~55% time-stops, ~20% stop-losses. Translation: **2σ deviations didn't revert**. They either kept widening (stop-out) or drifted sideways for 20 bars (time-stop). That's trend-continuation behavior, not mean-reversion.

Root cause — modern mega-cap equity pairs are **not stationary** at the 60-day window:
1. **Persistent capital flows**: passive indexing, factor tilts, and ESG overlays push flow into sector leaders independent of spread mean.
2. **Slow fundamental divergence**: V vs MA margin gaps, XOM vs CVX energy-transition positioning, UNH vs CI Medicare Advantage mix — these create multi-quarter drifts that look like "temporary dislocations" on a 60-bar window but aren't.
3. **Rolling β re-fits absorb the reversion signal**: when the spread drifts, the rolling OLS β shifts to accommodate it — the "reset" happens through hedge recalibration rather than price mean-reversion, nullifying the signal.

### Why the thesis was wrong

The literature I cited (Gatev/Goetzmann/Rouwenhorst 2006) showed the effect on **1962-2002 US equities** and explicitly called out **post-2002 decay**. Do & Faff (2010) already measured Sharpe dropping toward 0 on US large-caps. I wrote "Sharpe 0.4-0.7 expected" — that was ~1 full Sharpe point too optimistic for this universe in this era. Should have weighted the decay warning more heavily against the headline number.

### No fix attempt

Unlike VIX VRP (where one fix was worth trying because the mechanism was visibly still present in 2015-2017), here the 2015-2017 window itself was negative (-0.56 Sharpe). No param tweak fixes a mechanism that isn't working in the most favorable regime. **REJECT without fix attempt.**

## Files

- Thesis: `experiments/equity_pairs/equity_pairs.md` (this file)
- Demo: `experiments/equity_pairs/equity_pairs_demo.py`
- Data fetcher: `scripts/tiingo_fetch.py` (Tiingo adjusted daily bars)
- Data: `ohlc_data/{KO,PEP,XOM,CVX,JPM,BAC,V,MA,HD,LOW,UNH,CI,PG,CL,WMT,TGT,LMT,RTX,GS,MS}_D1.csv`

## Files

- Thesis: `experiments/equity_pairs/equity_pairs.md` (this file)
- Data: pull via `scripts/yahoo_fetch.py --symbols KO,PEP,XOM,CVX,JPM,BAC,V,MA,HD,LOW,UNH,CI,PG,CL,WMT,TGT,LMT,RTX,GS,MS --timeframes D1 --from 2015-01-01`
- Demo: `experiments/equity_pairs/equity_pairs_demo.py` (TBD)

## References

- Gatev, Goetzmann, Rouwenhorst (2006) "Pairs Trading: Performance of a Relative-Value Arbitrage Rule", RFS.
- Do & Faff (2010) "Does Simple Pairs Trading Still Work?", FAJ.
- Krauss (2017) "Statistical Arbitrage Pairs Trading Strategies: Review and Outlook", JES.
- Vidyamurthy (2004) *Pairs Trading: Quantitative Methods and Analysis*.
