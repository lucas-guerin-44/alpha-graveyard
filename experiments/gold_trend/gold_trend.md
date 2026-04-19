# Gold trend following (XAUUSD TSMOM) — Phase 1 thesis

## Mechanism

Gold is one of the most trend-prone liquid instruments. Drivers are slow-moving
macro regimes: real-rate cycles, DXY direction, central-bank reserve flows,
inflation expectations, and crisis/flight-to-quality demand. These forces
persist over months-to-years, which shows up empirically as autocorrelation of
sign over horizons of 3-12 months (same phenomenon Moskowitz/Ooi/Pedersen 2012
documented across 58 futures; gold is one of their strongest series).

We apply canonical time-series momentum: sign of the trailing 12-1 past
return → +1/0/−1 position, vol-targeted, monthly rebalance.

## Why retail-accessible

- **Monthly cadence, long horizon.** HFT and stat-arb shops don't compete here.
- **No crowding at retail scale.** TSMOM is a $100B+ institutional factor (CTAs,
  managed futures) and has been published for 14+ years; the fact that it still
  works is evidence it's not an arbitrage edge but a structural risk premium
  and/or behavioral under-reaction premium.
- **XAUUSD specifically** is tradeable via CFDs / futures / GLD at retail scale
  with tight spreads (5 bps per side on CFD, < 1 bp on GLD ETF).

## Universe

- Single instrument: **XAUUSD** (spot gold, D1).
- Period: **2015-01-02 → 2026-03-31** (11.2 years, 2,903 daily bars).
- Cash leg when flat: 0% (XAUUSD CFD; no natural "BIL" equivalent). This is
  conservative — live implementation would park cash in a money-market fund or
  risk-free proxy.

## Signal math

```
past_return_t = (close_{t - skip} - close_{t - lookback}) / close_{t - lookback}

signal_t = +1 if past_return_t > 0
          -1 if past_return_t < 0 (long/short variant)
           0 if past_return_t < 0 (long-only variant)
           0 if |past_return_t| < min_abs_return (optional threshold)

position_t = signal_t × (vol_target_ann / realized_vol_ann_t)
```

Parameters (defaults, no optimization):

| Param | Value | Rationale |
|---|---|---|
| lookback_bars | 252 | ~12 months |
| skip_bars | 21 | 1-month skip (classic 12-1) |
| rebalance_bars | 21 | Monthly |
| vol_lookback | 60 | ~3 months (MOP standard) |
| vol_target_ann | 0.15 | 15% per position (standard TSMOM) |
| cost_bps_per_side | 5 | XAUUSD CFD: ~$2/oz at $4000 price |

## Expected Sharpe range (from literature)

- MOP (2012) gold-only TSMOM, 1985-2009: Sharpe ~0.5 gross.
- Hurst/Ooi/Pedersen (2017), 200+ years of trend following across asset
  classes: Sharpe 0.3-0.7 net at institutional costs.
- **Our Phase 2 target**: Sharpe > 0.30 net of 5bps/side costs on the
  2015-2026 sample.

## Fail conditions (pre-committed)

1. **Sharpe ≤ 0 on full sample** → reject outright.
2. **Sharpe < buy-and-hold XAUUSD** → yellow flag. The signal has to earn its
   costs vs passive exposure; gold has had a strong run 2019-2026 that a
   trivial long-only strategy would have captured.
3. **Max DD > 30%** → reject (worse than passive gold DD in recent history).
4. **< 50 trades** over 11 years → reject (insufficient data for inference).
5. **All returns come from 2019-2024 gold bull run** → investigate via regime
   split; if 2015-2018 and 2025+ are flat-or-negative, the strategy is
   regime-dependent and will fail when gold ranges.
