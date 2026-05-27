# Gold trend following (XAUUSD TSMOM)

**Status**: REJECT (Phase 2, 2026-05-27)
**Verdict-summary**: Multi-horizon 12-1 TSMOM on XAUUSD D1, 2015-01-02 → 2026-03-31 (2,902 bars). All 4 pre-committed kill criteria PASS technically (best variant MH-LO-Pyramid: Sh +0.80 / MDD −16.5% / 85 trades / +127% total), but **two pre-committed fail conditions trip and the direction null-check fails**. Don't deploy.

- **Fail #2 (vs B&H)**: Sh +0.80 < XAU buy-and-hold +0.85 → strategy doesn't earn its costs over passive exposure.
- **Fail #5 (regime concentration)**: ALL returns come from the 2023-2026 holdout (Sh +1.59); 2015-2017 −0.14, 2018-2019 +0.10, 2020-2021 +0.46, 2022 −0.21. Four of five regimes negative or flat.
- **Direction null-check FAIL**: inverted-signal long-only (NULL-LO) also makes money — Sh +0.54, MDD −7.2%. Sig vs null gap **+0.21** (below the +0.30 convention threshold). The signal has weak directional content — most of the positive Sharpe is just sampling the positive gold drift on a 62%-long-bias strategy.
- **L/S → L-only diagnostic**: MH-LS Sh +0.45 vs MH-LO Sh +0.75 → short side LOSES money. Signal does not predict negative returns. Consistent with the null-check reading.

## Mechanism (Phase 1, retained for reference)

Gold is one of the most trend-prone liquid instruments. Drivers are slow-moving
macro regimes: real-rate cycles, DXY direction, central-bank reserve flows,
inflation expectations, and crisis/flight-to-quality demand. These forces
persist over months-to-years, which shows up empirically as autocorrelation of
sign over horizons of 3-12 months (same phenomenon Moskowitz/Ooi/Pedersen 2012
documented across 58 futures; gold is one of their strongest series).

We apply canonical time-series momentum: sign of trailing past returns over
1M/3M/12M lookbacks → averaged into a multi-horizon signal in [-1, 1],
vol-targeted at 15% ann, monthly rebal. Iteration 2 added a Turtle-style
ATR-pyramid sizing variant.

## Universe

- Single instrument: **XAUUSD** (spot gold, D1).
- Period: **2015-01-02 → 2026-03-31** (11.2 years, 2,902 daily bars).
- Cash leg when flat: 0% (XAUUSD CFD; no natural "BIL" equivalent).

## Signal math

```
mh_signal_t = mean(sign(r_1M), sign(r_3M), sign(r_12M))       # values in {-1, -2/3, -1/3, 0, 1/3, 2/3, 1}
realized_vol_t = ann_stdev(daily_returns, lookback=60)
position_t = mh_signal_t × min(0.15 / realized_vol_t, 1.0)
```

Rebalance every 21 bars. Pyramid variants enter at 1/K of full size, add 1/K
per +ATR_MULT × ATR favorable move; exit fully on flip or flat.

Parameters (defaults, no optimization):

| Param | Value |
|---|---|
| lookbacks | (21, 63, 252) — 1M/3M/12M |
| rebal_bars | 21 |
| vol_lookback | 60 |
| vol_target_ann | 0.15 |
| cost_bps_per_side | 5 |
| pyramid_steps | 3 |
| pyramid_atr_mult | 1.0 |
| atr_lookback | 14 |

## Phase 2 results

### Full-sample (2015-01-02 → 2026-03-31, 5 bp/side cost)

| variant | trades | Sharpe | CAGR | MDD | Calmar |
|---|---:|---:|---:|---:|---:|
| MH long-only | 90 | +0.75 | +7.02% | −15.9% | +0.44 |
| MH long-only + pyramid | 85 | **+0.80** | +7.55% | −16.5% | +0.46 |
| MH long/short | 104 | +0.45 | +4.29% | −26.5% | +0.16 |
| MH long/short + pyramid | 97 | +0.57 | +5.65% | −22.5% | +0.25 |
| **NULL long-only (-signal)** | 47 | **+0.54** | +2.20% | −7.2% | +0.31 |
| NULL long/short (-signal) | 104 | −0.51 | −5.84% | −59.6% | −0.10 |
| **XAU buy & hold** | n/a | **+0.85** | +12.94% | −21.4% | +0.61 |

### Pre-committed kill criteria (best variant MH-LO-P)

| criterion | bar | actual | verdict |
|---|---|---|---|
| Sharpe > 0.30 | +0.30 | +0.80 | PASS |
| Max DD < 30% | 30% | 16.5% | PASS |
| Trades ≥ 50 | 50 | 85 | PASS |
| Total return > 0 | 0% | +127% | PASS |
| **Beats XAU B&H** (fail #2) | +0.85 | +0.80 | **FAIL** |
| **Null-gap > 0.30** (convention) | +0.30 | +0.21 | **FAIL** |

### Regime breakdown (MH long-only — best variant, same shape on others)

| regime | Sharpe | CAGR | MDD |
|---|---:|---:|---:|
| 2015-2017 | −0.14 | −1.0% | −14.4% |
| 2018-2019 | +0.10 | +0.3% | −6.4% |
| 2020-2021 | +0.46 | +4.3% | −10.0% |
| 2022 | −0.21 | −1.4% | −9.3% |
| **2023-2026 holdout** | **+1.59** | **+24.5%** | −11.2% |

4 of 5 regimes are flat or negative. The full-sample +0.75 is entirely the holdout
sub-period (XAU went from $1,800 to $4,700 — the strategy was 62% long, that's it).

### Direction null-check regime breakdown

The inverted-signal long-only (NULL-LO) variant is actually POSITIVE in 4 of 5
regimes — including 2015-2017 (+1.44) and 2022 (+0.89) where MH-LO is negative.
This is the smoking gun: the multi-horizon signal mis-times the 2015-2022 regimes
and only catches the 2023-2026 trend because that trend was strong enough to
overwhelm signal noise on a 62%-long-bias strategy.

| regime | MH-LO Sh | NULL-LO Sh |
|---|---:|---:|
| 2015-2017 | −0.14 | **+1.44** |
| 2018-2019 | +0.10 | +0.33 |
| 2020-2021 | +0.46 | −0.02 |
| 2022 | −0.21 | **+0.89** |
| 2023-2026 holdout | +1.59 | +0.98 |

## Mechanistic interpretation

The "TSMOM works on gold" literature (MOP 2012, Hurst/Ooi/Pedersen 2017) is
correct on the 30-200-year futures sample, but the **post-2014 retail-CFD-tradeable
sample is dominated by a single macro regime (the 2023+ central-bank-buying +
inflation-hedge bull run) and produces a passive-beta-with-extra-steps result**.
Three convergent findings:

1. **Strategy doesn't beat buy-and-hold** even at conservative 5 bp/side cost.
   On a 62%-long-bias mechanism vol-targeted to 15%, the only way to lose to
   B&H is for the *signal-conditional* return to be weaker than the
   *unconditional* return. That happens when the signal mis-times the regime
   (which the NULL-LO regime split shows it does in 2015-2017 and 2022).

2. **Null-check has only a +0.21 Sharpe gap** to the inverted signal — below
   the +0.30 convention threshold. Inverted-signal LO Sh +0.54 over the full
   sample, positive in 4 of 5 regimes. The mechanism has *some* directional
   content (long is +0.75, anti-long is +0.54, real edge ~+0.21 Sh) but
   that's below deploy bar and below convention floor.

3. **L/S vs L-only diagnostic**: short side loses money cleanly (NULL-LS
   −0.51, MH-LS Sh +0.45 vs MH-LO +0.75 → −0.30 Sh contribution from the
   short side). The signal has no negative-direction skill — the asymmetry
   is "gold sometimes trends up, ranges otherwise, never trends down for
   extended periods at this horizon on this sample."

## What this means for the broader book

- **TSMOM family on retail-CFD universe**: the existing `tsmom` 24-instrument
  basket already PASSES (Sh +0.40 / holdout +1.14 / MDD −15.5%) and crucially
  beats null because diversification across 24 instruments dilutes
  single-regime-driven gold-style passes. Single-instrument TSMOM on gold
  adds nothing: it's already in `tsmom`, and standalone it doesn't beat B&H.
- **Lesson #29 reaffirmed**: walk-forward / regime-split kills single-window
  TSMOM passes. Add to that: **single-instrument-TSMOM on retail samples
  cannot be evaluated without a B&H benchmark and a directional null check**.
  Pre-committing both is now a Phase 0 gate for single-instrument-TSMOM theses.

## Fail conditions (pre-committed, retained for audit)

1. Sharpe ≤ 0 on full sample → reject outright. **PASS (+0.75 best L-only).**
2. **Sharpe < buy-and-hold XAUUSD → yellow flag. ACTIVATED (+0.75 < +0.85).**
3. Max DD > 30% → reject. **PASS (−16% best L-only, −27% L/S worst).**
4. < 50 trades over 11 years → reject. **PASS (85 best L-only).**
5. **All returns come from 2019-2024 gold bull run → investigate via regime
   split. CONFIRMED — actually 2023-2026 holdout, but mechanism identical.**

## Files

- Thesis: `experiments/gold_trend/gold_trend.md`
- Demo: `experiments/gold_trend/gold_trend_demo.py` (iteration 2 + null check)
- Phase 2 run log: `experiments/gold_trend/run_phase2.log`

## References

- Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", JFE.
- Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following Investing."
