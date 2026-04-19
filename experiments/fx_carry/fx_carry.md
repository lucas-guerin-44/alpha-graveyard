# FX Carry Trade

**Status**: REJECTED
**Verdict**: REJECT — negative Sharpe in 2015-2026. Correlation with XS-mom is low (+0.29 daily) so it WOULD be a diversifier if it worked, but it doesn't.

## Thesis
For each FX cross, `carry = rate_base - rate_quote`. Long pairs with positive carry (collect yield), short pairs with negative carry. Classic retail strategy — persistent UIP violation means high-yield currencies historically outperform what rate differentials alone predict.

## Key params
- Monthly rebalance (21 bars)
- Carry threshold: ±0.5% annualized
- Vol-target 15% per position
- Gross exposure cap 2.0x

## Universe
11 FX pairs with rate data from FRED: USD, EUR, GBP, JPY, AUD, NZD, CAD, NOK, ZAR currencies.

## Result (full 2015-2026)
| Metric | Value |
|---|---|
| Return | -29.41% |
| Sharpe | -0.38 |
| Max DD | -39.81% |
| Calmar | -0.076 |

## Biggest losers
- EURNOK: -10.84% (always-on long NOK, EUR stayed weak vs NOK spot)
- USDZAR: -5.31%
- NZDCAD: -5.23%

These are the "perpetual carry" pairs where the signal is always one direction, so when spot moves against you it's a guaranteed bleed.

## Why it failed (regime explanation)
2015-2026 has been a graveyard for classic carry:
- 2015-2019: global rate convergence (Fed hiking, others flat)
- 2020 COVID: carry currencies (AUD, NZD, ZAR) crushed
- 2022-2024: Fed hiked fastest, USD became "high-yielder" but EM spot moved against it
- 2024+: Japan started hiking, every long-carry-vs-JPY trade wrecked

## Correlation
- vs XS-mom: +0.29 daily / +0.24 monthly (would be a complement if it had positive Sharpe)

## Files
- Data fetcher: `scripts/fred_fetch.py` (FRED policy rates)
- Demo: `experiments/fx_carry/fx_carry_demo.py`

## References
- Fama (1984) "Forward and Spot Exchange Rates"
- Lustig, Roussanov, Verdelhan (2011) "Common Risk Factors in Currency Markets"
