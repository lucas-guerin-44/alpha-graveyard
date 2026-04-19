# FX Short-Term Mean Reversion

**Status**: REJECTED
**Verdict**: REJECT — negative Sharpe across ALL 12 param configs. Robust rejection, not noise.

## Thesis
FX crosses are mostly range-bound (no secular drift). Short-term overshoots after news/policy events partially reverse over 3-10 bars. Signal: fade z-score extremes vs. 20-day mean.

## Key params
- `ma_window = 20` bars
- `entry_z = 1.5` (enter when price > 1.5σ from mean)
- Exit when `|z| < 0.25`, max hold 10 bars, stop-loss at ±3σ from entry
- Vol-target 15% per position

## Universe
Same 11 FX pairs as carry.

## Result (baseline, full 2015-2026)
| Metric | Value |
|---|---|
| Return | -5.95% |
| Sharpe | -0.17 |
| Max DD | -13.28% |
| Trades | 2,093 |
| Win rate | 58.5% |
| Avg hold | 8.0 bars |

## Sensitivity grid (robust rejection)
Swept `entry_z ∈ {1.0, 1.5, 2.0, 2.5}` × `ma ∈ {10, 20, 40}` — 12 configs. **All 12 produced negative Sharpe** (range -0.10 to -0.48). Best cell: entry_z=2.0, ma=40, Sharpe -0.105. No rescue config available.

## Why it failed
- 58.5% win rate *before costs* suggests raw signal has some predictive value.
- But 12 bps round-trip × 2,093 trades = ~25% of equity bled into frictions.
- Pairs that *would* have made money on raw signal (USDZAR, EURUSD, NZDJPY — wide-vol pairs) had their gains eaten by G10 commodity-bloc crosses (AUDNZD, NZDCAD, GBPNZD) where MR fights real carry/rate-diff trends.

## Correlation
- vs XS-mom: +0.13 daily / +0.08 monthly (genuinely independent — but uneconomic)

## Files
- Demo: `experiments/fx_mean_reversion/fx_mean_reversion_demo.py`
