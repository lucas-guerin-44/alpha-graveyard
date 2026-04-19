# Dual Momentum (Antonacci)

**Status**: ARCHIVED (rejected)
**Verdict**: REJECT — IS period (2015-2022) total return is **-13.62%** and the cash-allocation filter actively HURTS performance.

## Thesis
Combine relative momentum (rank within asset class) with absolute momentum (require positive trailing return, else go to cash). Class-diversified version: top-1 per asset class, 4 sleeves, 25% each. From Antonacci (2014) "Dual Momentum Investing".

## Key params
- Monthly rebalance
- 12-1 momentum (same as TSMOM)
- Asset classes: FX crosses, commodities, equities, crypto
- Absolute filter: require signal > 0 else CASH

## Result (full 2015-2026)
| Variant | Return | Sharpe | Max DD | % time in cash |
|---|---|---|---|---|
| Class-diversified | +54.90% | 0.39 | -31.13% | 91.45% |
| Single-universe (top-1 of 24) | +48.63% | 0.28 | -69.94% | 0% |

## Why it failed validation
- **IS period (2015-2022) total return is -13.62%.** You'd have quit the strategy in 2022. The positive full-sample number relies entirely on the 2023+ bull.
- **Cash filter hurts**: removing the absolute-momentum check (pure top-pick-per-class) yields +60.6% / 0.42 Sharpe — better than +54.9% / 0.39 with the filter.
- Fragile on skip_bars and rebalance_bars — longer horizons monotonically better, so the baseline is NOT on a stability plateau.
- 81% of PnL comes from Equities sleeve alone. FX sleeve is -8%, Crypto 0%. Not diversified in practice.

## Files
- Demo: `experiments/_archived/dual_momentum_demo.py`
- Validation: `experiments/_archived/dual_momentum_validation.py`

## References
- Antonacci (2014) "Dual Momentum Investing"
