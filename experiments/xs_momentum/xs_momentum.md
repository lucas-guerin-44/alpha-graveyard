# Cross-Sectional Momentum (XS-mom)

**Status**: LIVE (paper — QuantConnect)
**Verdict**: KEEP — primary live strategy

## Thesis
At each rebalance, rank a multi-asset universe by trailing 12-1 month return and long the top K equal-weight. Captures the *relative* winners at each point in time, avoiding the "stuck long a fading asset" problem that kills time-series trend following. Documented across asset classes in Asness, Moskowitz & Pedersen (2013) "Value & Momentum Everywhere".

## Key params (IS-optimal, selected on 2015-2022 only)
- `lookback_bars = 189` (~9 months)
- `skip_bars = 42` (~2 months — avoids short-term reversal)
- `rebalance_bars = 63` (quarterly)
- `top_k = 5` (equal-weight long-only)

## Universe
24 instruments: FX crosses (11) + commodities (6: softs + gold/oil) + equity indices/ETFs (6) + BTC.

## Result (full-period 2015-2026)
| Metric | Value |
|---|---|
| Return | +259.75% |
| Sharpe | 0.92 |
| Max DD | -23.12% |
| Avg turnover/rebal | 0.95 |

## Validation
- **Regime stability**: 4/4 windows Sharpe positive (weakest 0.43, strongest 1.48)
- **Parameter sensitivity**: robust — all 10 top-IS configs positive OOS, mean OOS Sharpe 1.54, std 0.16
- **IS-only re-baseline**: IS Sharpe 0.59, OOS Sharpe 1.33, degradation -0.75 (robust)
- **Statistical tests**: not yet wired — TODO, run `compute_statistical_report` with `n_trials=180`

## Live (QuantConnect, Interactive Brokers)
Universe adapted: FX via OANDA, equity CFDs → SPY/QQQ/EWG ETFs, gold/oil → GLD/USO, softs as futures, no BTC.

| Metric | Research | QC Live |
|---|---|---|
| CAGR | 11.5% | 8.43% |
| Sharpe | 0.92 | 0.35 |
| Max DD | -23% | -27% |
| Beta vs SPY | — | 0.00 |
| Alpha vs SPY | — | 0.00 |

Gap explained by: softs futures not trading (likely constant name issue), no BTC, ETF vs CFD.

## Correlation
- vs TSMOM long-only: **+0.69 daily** (too high — no blending value)
- vs FX Carry: +0.29 daily (mechanically independent)
- vs FX MR: +0.13 daily (mechanically independent)

## Files
- Demo: `experiments/xs_momentum/xs_momentum_demo.py`
- Validation: `experiments/xs_momentum/xs_momentum_validation.py`
- Re-baseline: `experiments/xs_momentum/xs_momentum_rebaseline.py`
- Live: `deploy/qc_xs_momentum.py`

## References
- Asness, Moskowitz, Pedersen (2013) "Value and Momentum Everywhere", JoF
