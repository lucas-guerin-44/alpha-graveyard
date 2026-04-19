# Time-Series Momentum (TSMOM)

**Status**: VALIDATED, not deployed live
**Verdict**: KEEP in long-only variant — too correlated with XS-mom (+0.69) to blend, but mechanically sound

## Thesis
Long an asset when its trailing 12-1 month return is positive, short when negative (or flat in long-only mode). Holds until signal flips. Classical "slow trend-following" — Moskowitz, Ooi & Pedersen (2012). Works because investors under-react to slow-moving news; trends persist on multi-month horizons.

## Key params
- `lookback_bars = 252` (~12 months)
- `skip_bars = 21` (~1 month skip — classic 12-1)
- `rebalance_bars = 21` (monthly)
- `vol_lookback = 60` (~3 months for vol-targeting)
- `vol_target_annual = 0.15` (15% per position)
- `long_only = True`

## Universe
Same 24-instrument universe as XS-mom.

## Result (long-only, full 2015-2026)
| Metric | Value |
|---|---|
| Return | +44.19% |
| Sharpe | 0.40 |
| Max DD | -15.53% |
| Trades | 384 |

## Validation
- **Regime stability**: 3/4 windows Sharpe positive (weakest 2017-2020 at -0.06)
- **Parameter sensitivity**: robust across 4 param sweeps (lookback, skip, rebal, vol_target)
- **True holdout** (2015-2022 IS / 2023+ OOS): IS Sharpe 0.27, OOS Sharpe 1.14, degradation -0.87 — OOS outperforms IS (regime-flattering post-2022)
- **Statistical tests**: not yet wired — TODO

## Historical bug (fixed)
Before fix: `manage_position` returned early when signal went to 0, so long-only positions never closed on flip-to-neutral. Equity curve was mathematically valid (mark-to-market) but trade accounting showed 0 trades. **Fix**: close on signal ≠ position_side (including 0). Committed in the move to research repo.

## Correlation
- vs XS-mom: **+0.69 daily** — too high to blend
- vs carry/MR: ~0.1-0.3 (independent but those strategies lost money)

## Why long-only-only
Full long/short version loses on this 2015-2026 universe: shorts got caught in V-recoveries (SPX March 2020, BTC 2022 bottom, etc.). Removing shorts eliminated the disaster cases without sacrificing much upside — 16/24 instruments beat B&H in long-only vs 4/24 in long/short.

## Files
- Strategy: `research/tsmom.py`
- Demo: `experiments/tsmom/tsmom_demo.py`
- Variants: `experiments/tsmom/tsmom_variants_demo.py`
- Validation: `experiments/tsmom/tsmom_lo_validation.py`

## References
- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum", JFE
- Hurst, Ooi, Pedersen (2017) "A Century of Evidence on Trend-Following Investing"
