# BTC trend following (BTCUSD MH-LO + pyramid) — Phase 1 thesis (pivot)

## Origin

Pivoted from `experiments/gold_trend/` after a single-instrument scan across 26
trend-prone instruments. BTCUSD topped the scan on Sharpe (+0.93) and alpha
vs B&H (+0.27), at a 5 bps/side cost assumption. The gold experiment itself
concluded that TSMOM on XAUUSD doesn't beat buy-and-hold, but the same
mechanics flagged BTCUSD as the best single-instrument candidate in the
scanned universe.

## Mechanism

BTC has exhibited extreme regime-conditional trends:

- **Trends up:** flagship bull runs 2019-2021 and 2023-2025, driven by
  adoption cycles + halvings + macro liquidity.
- **Trends down:** 2018 and 2022 crypto winters, large multi-month drawdowns
  (-75% to -80% peak-to-trough) driven by deleveraging cascades, exchange
  failures, and regulatory shocks.

TSMOM should particularly help on the downside: buy-and-hold absorbed full
80%+ MDDs, whereas a trend-following rule goes flat during bear signals.
The scan bore this out — the edge comes almost entirely from cutting
drawdowns, not from enhanced returns.

## Why retail-accessible

- Monthly rebalance cadence, not microstructure.
- Crypto is retail-dominated; institutional TSMOM programs haven't scaled
  into this market meaningfully (compliance/custody frictions).
- BTCUSD is tradable retail via CFDs, perps, or spot — deep liquidity,
  24/7 markets, ~10 bps/side spreads typical on CFDs.

## Universe / Period

- Single instrument: **BTCUSD** (spot, D1).
- Period: **2018-01-01 → 2025-08-31** (7.7 years, 2,456 daily bars).
- Cash leg when flat: 0%.

## Signal + sizing

Inherited from gold_trend:
- **Multi-horizon** TSMOM: average of `sign(r_1M)`, `sign(r_3M)`, `sign(r_12M)`.
- **Pyramid**: K=3 units, ATR(14) × 1.0 favorable trigger per add, cap at
  full vol-target (cap = 1.00× — the path-only variant).
- **Vol-target**: 15% annualized.
- **Rebalance**: monthly (21 bars).
- **Cost**: 10 bps/side (honest BTCUSD CFD — *up from 5 bps in the scan,
  which overstated the edge*).

## Expected Sharpe range

- Scan (5 bps/side): 0.93.
- Expected at honest 10 bps/side: 0.80-0.90. If it drops below 0.70, the
  "edge" was mostly cost-subsidized.
- Institutional crypto TSMOM programs (AQR, Man): reported 0.7-1.0 Sharpe
  since 2018.

## Fail conditions (pre-committed)

1. **Sharpe ≤ 0.50 at honest 10 bps/side** → reject; effectively uninvestible.
2. **Phase 3 Deflated Sharpe p > 0.05** with n_trials_tested = 35 (scan + 
   pyramid configs): we picked the best of 26 instruments + explored 9 
   pyramid configs; must survive the cherry-picking correction.
3. **Phase 4: Sharpe positive in ≤ 2/4 windows, OR one window > 80% of return**
   → reject; regime-dependent.
4. **Phase 6: OOS Sharpe ≤ 0, OR degradation > 0.5** → reject; doesn't 
   generalize across the 2018-2021 → 2022-2025 split.
5. **Alpha vs B&H collapses (< +0.10 Sharpe)** at honest costs → reject;
   no reason to run the strategy over just buying and HODLing.
