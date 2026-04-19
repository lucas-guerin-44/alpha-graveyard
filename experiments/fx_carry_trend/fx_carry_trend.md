# FX Carry + Trend (Asness-style)

**Status**: REJECTED
**Verdict**: REJECT — filter did NOT rescue carry. Sharpe still -0.38, DD worsened to -50%.

## Thesis
Filter carry signal with a 63-day price trend. Only take a long-carry position when 3-month momentum is also positive; only short-carry when 3-month momentum is negative. Hypothesis: cuts out the "stuck long carry while spot craters" disasters that killed pure carry.

## Key params
- Same as pure carry (monthly rebalance, ±0.5% carry threshold, 15% vol target)
- Added: `trend_lookback = 63` bars (3-month momentum sign)

## Result (full 2015-2026)
| Metric | Pure Carry | Carry + Trend |
|---|---|---|
| Return | -29.41% | **-37.21%** |
| Sharpe | -0.38 | **-0.38** |
| Max DD | -39.81% | **-50.18%** |

## Why it failed (diagnosis)
- The filter fired ~50% of the time on worst-offender pairs (EURNOK, USDZAR), but the ~49% where trend + carry *agreed* were still net losers. Carry signal was directionally wrong so often that "confirming with trend" just meant losing with more conviction.
- Signals became sparse post-filter → fewer positions with higher concentration → worse drawdown even though gross exposure capped.
- 63-day lookback lags carry regime changes by months; when yields flip, trend stays long for weeks while the new carry signal flips — holding stale losers.

## Correlation
- vs XS-mom: +0.16 daily / +0.20 monthly (more uncorrelated than pure carry, but moot since Sharpe is negative)

## What might work (not pursued)
- Shorter trend lookback (21-42 days) to react faster
- Higher carry threshold (±1.0%) to only trade large differentials
- Drop EURGBP/EURNOK from the universe (small-carry DM-EU crosses)
- Rank-weighted carry + momentum blend (not hard-AND gate)

## Files
- Demo: `experiments/fx_carry_trend/fx_carry_trend_demo.py`

## References
- Asness, Moskowitz, Pedersen (2013) "Value and Momentum Everywhere" — original carry+trend combo framing
