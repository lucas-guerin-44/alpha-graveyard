# TSMOM + 200-EMA Trend Filter

**Status**: REJECTED
**Verdict**: REJECT — filter made results WORSE than baseline TSMOM

## Thesis
Apply an EMA(200) trend filter on top of TSMOM signals: only allow long signals when close > EMA(200), only shorts when close < EMA(200). The hope: filter out counter-trend trades in assets with secular drift (equity indices, gold, crypto).

## Key params
- Inherits TSMOM baseline params (lookback=252, skip=21, rebal=21, vol_target=0.15)
- `trend_filter_bars = 200`

## Result (full 2015-2026, equal-weight portfolio)
| Metric | Baseline TSMOM | Filtered |
|---|---|---|
| Return | +5.87% (buggy) | **-4.56%** |
| Sharpe | 0.09 | **-0.02** |
| Max DD | -18.78% | -23.02% |
| Instruments beating B&H | 4/24 | **2/24** |

## Why it failed
The 200-EMA filter whipsaws on FX crosses (range-bound, no secular trend) and blocks legitimate trend resumptions on directional assets. Net effect: fewer trades, worse timing on the trades that do fire, and the signals blocked during drawdowns turn out to have been the ones that would have recovered.

## Files
- Strategy: `research/tsmom_filtered.py`
- Demo/comparison: `experiments/tsmom/tsmom_variants_demo.py`
