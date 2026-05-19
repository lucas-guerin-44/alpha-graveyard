# DAX Pre-Auction Drift

**Status**: Phase 2 complete 2026-04-20.

**Verdict**: **REJECT — thesis sign inverted**. Baseline Sharpe −0.66, all 3 regimes negative (−0.38 / −0.26 / −1.18). Null-check shows fade Sharpe −0.33 > continuation Sharpe −0.66: direction-gap −0.33 (sign-inverted). The 60-min pre-15-min move on DAX weakly *mean-reverts* into the close, it does not continue. Both directions still lose in absolute terms after 1pt cost, so neither side is tradeable.

**Mechanistic read**: the continuation thesis (institutional pre-auction positioning drives continuation into 17:30 close) is not supported. The weak inversion is consistent with a different mechanism — temporary order-flow imbalance in 16:30-17:15 reverting as liquidity providers pull and reprice in 17:15-17:30 pre-auction. The continuous-session drift and auction-anticipation flow appear to be decoupled at retail M5 granularity.

---

## Results summary

Baseline (continuation, LB=60min, entry=T-15, thr=0.25, EOD exit, cost=1pt):

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | −0.66 | FAIL |
| Max DD | −7.00% | PASS |
| Trades | 693 (1.83/wk) | PASS |
| WR / PF | 44.6% / 0.81 | FAIL |

**Regime breakdown**: −0.38 / −0.26 / **−1.18** (holdout is worst). Monotonic decay.

**Entry-timing sweep**: T-5 no trades (window too short), T-10 −1.94, T-15 −0.66, T-25 −0.48. No positive cell.

**Threshold sweep**: thr=0.0 −1.35, thr=0.25 −0.66, thr=0.5 −0.77, thr=1.0 −0.61. No improvement at higher thresholds (unlike ORB on DAX).

**Cost sweep**: even at 0.5pt Sharpe −0.41. Not a cost issue — gross signal is negative in the continuation direction.

**Null-check**: fade −0.33, continuation −0.66, gap −0.33 (inverted). The fade direction is less-bad but still negative.

**Interpretation**: the existing GER40 ORB T+180 strategy already captures morning-impulse continuation cleanly; the pre-close window exhibits different dynamics (auction-anticipation flow plus retail unwind residual) that are not simple trend-continuation. REJECT as a standalone strategy; would require a fundamentally different signal construction to revive.

---

## Thesis (mechanism)

The Xetra closing auction at 17:30 Berlin concentrates daily institutional rebalancing flow — index funds, ETF creation/redemption, sector rotators. Unlike the NYSE closing cross (which publishes imbalance data at 15:50 ET for 10 minutes of lead-time continuous trading), Xetra's pre-auction call phase opens at ~17:25 with imbalance indications visible to participants. The continuous trading book in the 10-20 min before auction:

1. **Pre-positions against expected auction print.** Market makers and prop desks take liquidity in the direction of indicated imbalance so they can provide liquidity in the auction at a better price, pushing continuous-session price toward the auction clearing price.
2. **Momentum in the final 60 minutes leads the auction.** Large institutional orders that plan to cross in the auction pre-hedge using continuous-session executions, creating a directional drift that continues into the auction.
3. **Net prediction**: continuation of 60-min prior momentum in the 15-min pre-auction window.
4. **Different from EOD-unwind** (tombstoned): unwind thesis predicted fade of the *day* move from retail-leverage exit flow. This thesis predicts continuation of the *short-window* move from institutional pre-auction positioning. Horizon and sign both differ.

## Key reference

- **Cushing & Madhavan (2000)**, "Stock returns and trading at the close." *Journal of Financial Markets* 3(1). Documents pre-close price drift driven by MOC order imbalance on NYSE; mechanism should apply at Xetra with the auction structure amplifying it.
- **Bogousslavsky & Muravyev (2023)**, "Who Trades at the Close? Implications for Price Discovery and Liquidity." Institutional flow dominance at close; pre-close drift is a reliable lead indicator.

## Signal math

```
Parameters:
  LOOKBACK_MIN              = 60    (measure momentum over prior 60 min)
  ENTRY_MIN_BEFORE_CLOSE    = 15    (enter T-15 = 17:15 Berlin)
  MIN_MOVE_ATR              = 0.25  (threshold on |lookback_return|)
  EXIT                      = session_close_bar (last bar 17:25-17:30)
  COST_POINTS_ROUND_TRIP    = 1.0

Per trading day:
  entry_bar  = first bar where minute_of_day >= RTH - ENTRY_MIN_BEFORE_CLOSE
  lookback_bar = entry_bar - (LOOKBACK_MIN / 5)
  r_look = close[entry_bar] / close[lookback_bar] - 1
  atr_m5 = rolling 20-day ATR of single-bar abs return

  if |r_look| < MIN_MOVE_ATR * atr_m5:  skip day
  pos = sign(r_look)  # continuation
  enter at next-bar open, exit at last session bar close

  Max 1 trade per day.
```

Variant sweeps: LOOKBACK_MIN ∈ {30, 60, 90}, ENTRY ∈ {5, 10, 15, 25}, MIN_MOVE ∈ {0.0, 0.25, 0.5, 1.0}, cost ∈ {0.5, 1, 2, 3}pt. Null-check: fade the direction (flip sign).

## Expected performance

Effect size per Cushing-Madhavan: 2-5bps per pre-close 15-min hold on indices, rising to 8-12bps on high-imbalance days. On DAX M5 with 1pt RT cost ≈ 5bps, this is a cost-marginal trade. Expected Sharpe 0.15-0.45, 200-300 trades/year (depending on threshold), MDD 8-15%.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200.
- WR < 48% OR PF < 1.05 (continuation-momentum payoff; expect near-symmetric W/L).
- **Null-check direction-gap < +0.30** (continuation Sharpe − fade Sharpe must exceed +0.30).

Phase 4: Sharpe positive in ≥ 2 of 3 regime windows.
Phase 6: 2023-2026 holdout Sharpe ≤ 0.

## Why this might fail

1. **Effect size likely inside cost envelope** on retail CFD spreads. 1pt RT at DAX 16,000 ≈ 6bps — easily eats a 2-5bps gross edge.
2. **Pre-auction algo competition**: Xetra colo execution makes this well-arbed by institutionals at ms-latency. Retail M5 bar entries have 2-5 min fill latency disadvantage.
3. **Regime dependence**: auction-related flow is strongest on earnings/macro days, weakest on quiet days — a threshold filter may not isolate the right ones.

## Files

- Thesis: this file.
- Demo: `pre_auction_demo.py` — baseline + sweeps + null-check + overnight-confound check.
