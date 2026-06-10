# NDX Intraday Semi Divergence — Phase 2 thesis

**Status**: Phase 2 complete, 2026-06-10.

**Verdict**: REJECT — mechanism inverted; divergence mean-reverts, does not trend-extend.

---

## Thesis (mechanism)

1. NDX sector sub-indices diverge from the headline index during intraday trading because sector-level institutional flow (portfolio rebalancing, sector rotation) executes on constituent stocks before the program-trade / ETF-arb propagation reaches the full index basket.
2. The semi-conductor cohort (NVDA, AMD, AVGO, MRVL, QCOM) is the highest-beta, highest-0DTE-OI cohort within NDX — their intraday momentum is driven by concentrated institutional flow that precedes broader index movement.
3. When the semi basket's cumulative return diverges from NDX's cumulative return by >1σ of their 20-bar rolling spread, the NDX index converges to the semi direction within 1-2 hours. The lag exists because: (a) sector ETFs (SMH) rebalance at T+1 settlement, not real-time; (b) index arbitrage desks require >1σ dispersion before committing capital; (c) the propagation of sector-level flows through the 100-name basket takes 15-45 minutes of continuous trading.

## Key reference

- Chordia, Roll & Subrahmanyam (2002). "Order imbalance, liquidity, and market returns." *JFE* 65(1).
- Cont & Kukanov (2017). "Optimal order placement in limit order books." *MML* 3(1).
- **Repo lesson #77** (same-bar look-ahead guard)
- **Repo lesson #78** (paired basket experiments)
- **Repo lesson #49** (universe extension robustness)

## Signal math

```
Semi basket (equal-weighted price index, re-capped daily):
  SEMI = mean(NVDA, AMD, AVGO, MRVL, QCOM)

Every M5 bar after 10:00 ET (post-opening vol):
  spread_bar    = semi_close - ndx_close
  spread_series = roll(spread_bar over trailing 20 bars)
  divergence    = z-score(spread_bar, spread_series)

  ENTRY:
    LONG  if divergence < -THRESHOLD    (semis outperforming, NDX lagging)
    SHORT if divergence > +THRESHOLD    (semis underperforming, NDX lagging)

  EXIT: divergence crosses 0, or 120min time stop, or cash close.

  RET = direction * (exit - entry) / entry - cost
```

**Threshold sweep**: THRESHOLD ∈ {1.0, 1.5, 2.0, 2.5} σ.
**Exit sweep**: 0-cross OR time-stop (60/90/120/180 min) OR cash close.
**Look-ahead guard**: signal uses bar[t-1] close for both semi and NDX — never bar[t].

## Universe

- NDX100 M5 CFD (same vehicle as `lunch_fade`, `ndx_trend_day`, `event_calendar`)
- Semi components: NVDA, AMD, AVGO, MRVL, QCOM — M5 data already on disk
- Window: 09:30-16:00 ET US cash RTH, 2019-01-01 → present
- Pre-filter: skip 09:30-10:00 ET (opening vol has unreliable leader-follower dynamics)

## Expected performance (prior)

Sharpe +0.2 to +0.6 if mechanism exists. Divergence events estimated 1-3 per week (80-200/yr). Per-trade gross on captured divergences ~15-30 bps — enough to clear NDX 1pt (~0.8 bp) RT cost. Low cost to test.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < +0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 100 over 7 years.
- **Direction null-check**: fade variant (trade AGAINST the divergence) produces dir-gap < +0.40 vs baseline.
- **Corr to existing NDX strategies** > +0.30 vs `lunch_fade` OR vs `ndx_trend_day` (binding for deploy recommendation, not for standalone PASS).
- W3 holdout (2023-2026) Sharpe ≤ 0.

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows (2019-2020 / 2021-2022 / 2023-2026).

## Why this might fail (red flags)

1. **HFT arb**: Sector lead-lag may be closed at sub-M5 resolution. At M5 aggregation, the signal may be stale. cross_asset_lead_lag found no M5 lead-lag across assets; intra-index may differ.
2. **0DTE gamma**: Post-2022, 0DTE may cause NDX to track the semi cohort so tightly that divergence never reaches 1σ for >15 min.
3. **Regime dependence**: Semi dominance of NDX (NVDA alone ~8% weight) is recent. Leader-follower may be stronger post-2022, zero pre-2022.
4. **Component data risk**: If any of the 5 target symbols lack clean M5 history over the full window, substitute or drop to 3-name basket.
5. **Same-bar look-ahead**: Must use bar[t-1] close for ALL signal computation (lesson #77).

## Results (Phase 2, 2026-06-10)

**Data coverage**: 2021-12-10 → 2026-05-28 (4.5y, 1,117 days, 83,472 bars). 2019-2020 window had insufficient data for semi components.

| Metric | Baseline (2σ, 1pt) | Fade (null-check) | Pass? |
|--------|-------------------|-------------------|-------|
| Sharpe (post-cost) | **−1.08** | +0.16 | FAIL |
| CAGR | −3.69% | +0.73% | FAIL |
| Max DD | −17.19% | −13.53% | PASS |
| Trades | 1,108 (4.77/wk) | 1,108 | PASS |
| Win rate | 12.9% | 35.5% | FAIL |
| Profit factor | 0.70 | 1.03 | FAIL |
| Dir-gap (base − fade) | **−1.23** | — | FAIL (< +0.40) |

**Regime breakdown**:
| Window | CAGR | Sharpe | MDD | Trades |
|--------|------|--------|-----|--------|
| 2021-2022 vol | −7.22% | −1.35 | −9.29% | 263 |
| 2023-2026 holdout | −2.58% | −1.02 | −10.68% | 845 |

**Threshold sweep** (Sharpe at 1pt cost):
- 1.0σ: −1.11 / 1.5σ: −0.59 / 2.0σ: −1.08 / 2.5σ: −0.49 / 3.0σ: −0.92

**Cost sensitivity** (baseline Sharpe):
- 0.0pt: −0.64 / 0.5pt: −0.86 / 1.0pt: −1.08 / 2.0pt: −1.51 / 3.0pt: −1.93

### Mechanistic interpretation

The semi-NDX spread **mean-reverts at M5 resolution**, it does not trend-extend. Trading WITH the divergence produces a 12.9% win rate (many small losses, rare large wins). Trading AGAINST the divergence (fade) yields positive (but sub-threshold) Sharpe +0.16, consistent with the spread being stationary.

Three likely structural drivers:
1. **HFT arbitrage closes the gap within the same 5-min bar** — the 1-bar execution delay means the entry is after reversion has already begun. The signal fires on bar[t] close; by bar[t+1] close (entry), the reversion is partially complete.
2. **Intraday mean reversion of the semi-NDX pair trade** dominates over momentum. The sector rotation thesis incorrectly assumed persistence when the dominant regime is intraday pair-trading mean reversion.
3. **The prior was directionally wrong** — semis outperforming NDX is a sell signal at M5, not a buy. Even the fade doesn't reach threshold (+0.16 vs +0.30 bar), so there's no deployable anti-signal either.

**Lesson**: Sector-lead-lag at M5 is mean-reverting, not momentum-extending. The thesis's red flag #1 (HFT arb closes at sub-M5) was the correct concern. Any future intra-index lead-lag thesis must test both directions pre-commit.

## Files

- Thesis: this file (`experiments/ndx_semi_divergence/ndx_semi_divergence.md`)
- Demo: `experiments/ndx_semi_divergence/ndx_semi_divergence_demo.py`
- Data: `ohlc_data/NDX100_M5.csv`, `ohlc_data/NVDA_M5.csv`, `ohlc_data/AMD_M5.csv`, `ohlc_data/AVGO_M5.csv`, `ohlc_data/MRVL_M5.csv`, `ohlc_data/QCOM_M5.csv`
- Run: `venv/Scripts/python.exe experiments/ndx_semi_divergence/ndx_semi_divergence_demo.py`
