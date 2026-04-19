# Blended Portfolio (TSMOM LO + XS-mom)

**Status**: INVESTIGATED, not useful in current form
**Verdict**: REJECT as-is — TSMOM-LO and XS-mom correlation is +0.69, so blending just interpolates. Not enough diversification value.

## Thesis
Combine two validated momentum strategies into a blended portfolio. Different signal horizons (TSMOM monthly, XS-mom quarterly) and different mechanics (time-series vs. cross-sectional) should provide some diversification.

## Blend configurations tested
- 50/50
- 60/40 (TSMOM-heavy)
- 40/60 (XS-mom-heavy)
- Risk-parity (inverse realized-vol weighting)

## Result (full 2015-2026)
| Config | Return | Sharpe | Max DD | Calmar |
|---|---|---|---|---|
| TSMOM-LO alone | +44% | 0.40 | -15.53% | 0.11 |
| **XS-mom alone** | **+260%** | **0.66** | **-23.12%** | **0.26** |
| 50/50 blend | +152% | 0.64 | -17.62% | 0.25 |
| 60/40 TSMOM | +130% | 0.62 | -17.18% | 0.23 |
| 40/60 XS-mom | +174% | 0.65 | -18.08% | 0.26 |
| Risk-parity | +112% | 0.60 | -16.85% | 0.21 |

## Key finding
**Correlation of daily returns = +0.69**. The two "different" momentum strategies are substantially the same bet. No blend beats XS-mom standalone on Sharpe; all blends interpolate between the two individual Sharpes.

The 40/60 XS-heavy variant has essentially equal Calmar (0.263 vs 0.264) with meaningfully lower DD (-18.08% vs -23.12%) — arguably the more retail-survivable choice if you're drawdown-sensitive.

## What this tells us
Blending needs genuinely uncorrelated factors to add value. Momentum-on-same-universe doesn't qualify regardless of how the signal is computed (time-series vs. cross-sectional). The real diversification hunt should target different factors entirely (carry, MR, vol premium, event-driven) or different markets (equity single-name, crypto funding, etc.).

## Files
- Demo: `experiments/blended_portfolio/blended_portfolio_demo.py`
