# BTC volatility breakout (Crabel-style, D1) — Phase 1 thesis

**Status (2026-05-13):** Phase 2 complete. **REJECT** — one-window wonder driven entirely
by W2 2020-2021 (parabola + COVID). MDD -51.69% > 20% bar; W4 Sharpe +0.18 < +0.20 floor;
walk-forward mean deg +0.55 with 2/5 OOS positive. Per the BTC institutionalization
finding (RESEARCH_NOTES #30) and the user's deploy-discipline rule, strategies whose
edge is concentrated in a single anomalous pre-institutionalization window aren't
deployable regardless of full-sample Sharpe.

## Origin

Third BTC daily-frequency thesis following the closed btc_trend
(KEEP_FOR_REFERENCE; slow-trend, decay side of institutionalization) and
btc_weekend (REJECT; microstructure, activation side). This thesis sits
on a third time-scale — **daily vol-expansion event triggering 1-5 day
short-term continuation**.

Per the BTC institutionalization mirror-image finding (RESEARCH_NOTES #30),
this mechanism is *expected* to live on the **decay side**: short-term
post-event continuation is exactly the kind of multi-day price drift that
HFT/institutional flow compresses into intraday or even sub-second
arbitrage. The pre-commit reflects that expectation — W3-W4 must still
pass the deploy-relevant bars, not just W1-W2.

## Thesis (mechanism)

Vol-clustering on BTC is well-documented (GARCH(1,1) alpha+beta ≈ 0.95
on daily returns 2014-2024). The vol-clustering itself isn't directly
tradeable — it predicts the *magnitude* of future moves, not their
*direction*. What this thesis tests is whether vol-expansion days carry
**directional information** that persists for 1-5 days:

1. **Information-event days** (FOMC, ETF flow, regulatory news, macro
   shocks) tend to produce large daily moves with a clear direction.
2. **Slow institutional re-positioning** — large institutional positions
   (ETF creation/redemption, OTC desk inventory rebalancing) take
   multiple days to fully execute through limit-order books; their flow
   continues to push price for 1-3 sessions after the initial vol event.
3. **Retail attention asymmetry** — retail tends to chase post-vol moves
   on day T+1 and T+2, amplifying the continuation in the same direction
   as the day-T move.
4. **Crabel-classical asymmetry** — historically on commodities and
   indices, vol expansion is associated with trend resumption rather
   than reversal (NR4-breakout, opening-range-breakout literature).
   The fade direction is the null check.

## Why retail-accessible

- D1 cadence, plain BTCUSD CFD, 10 bps/side honest cost.
- No microstructure dependencies; trigger fires on yesterday's bar data.
- Rare events (high-vol days are tail observations) → low trade cadence,
  ~50-150 trades over 8 years — borderline but acceptable per lesson #25
  precedent (NDX lunch_fade deployed at 117 trades over 7 years).

## Why this thesis is structurally distinct from btc_trend / btc_weekend

| dimension | btc_trend | btc_weekend | **btc_volbreak** |
|---|---|---|---|
| Trigger | 12-1 monthly direction | Fri-Mon boundary | Daily vol-expansion |
| Hold | months | 1 day | 1-5 days |
| Signal lookback | 252 days | 2 days | 20 days (ATR) |
| Trade cadence | ~11/yr | ~28/yr (filtered) | ~10-20/yr (rare event) |
| Mechanism family | Slow autocorrelation | Microstructure boundary | Short-term momentum |
| Inst. side (predicted) | **decay** (observed) | **activation** (observed) | **decay** (predicted) |

If the mechanism activates contrary to expectation (W3-W4 stronger than
W1-W2), that would be a meaningful finding — short-term continuation
either resists institutional arb or has been replaced by a different
mechanism in the recent era.

## Key references

- **Toby Crabel (1990)**, *Day Trading with Short Term Price Patterns
  and Opening Range Breakout*. NR4/NR7 narrowest-range setups as
  vol-contraction → expansion triggers.
- **Larry Williams (1979)**, *How I Made $1,000,000 Trading Commodities
  Last Year*. Volatility-breakout systems on commodity futures.
- **Cont (2001)**, "Empirical properties of asset returns: stylized
  facts and statistical issues." *Quantitative Finance*. Volatility
  clustering documented across asset classes including emerging markets
  (analogous to BTC pre-2018).
- **Bali, Engle, Murray (2016)**, *Empirical Asset Pricing*, ch. 12.
  Short-term reversal vs continuation distinction conditional on
  information-event proxies.
- **Bouchaud, Bonart, Donier, Gould (2018)**, *Trades, Quotes and
  Prices*. Institutional order-flow persistence in limit-order books.

## Signal math

```
Parameters:
  ATR_LOOKBACK              = 20         # ATR window (days)
  VOL_MULT                  = 1.5        # today's TR must exceed VOL_MULT * ATR
  MIN_RETURN_PCT            = 1.0        # today's |return| must exceed this
  HOLD_DAYS                 = 3          # exit at close of day T+HOLD
  COST_BPS_PER_SIDE         = 10.0

Per day T (using only data through T's close):
  TR_t       = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)
  ATR_yest   = rolling-mean(TR over t-ATR_LOOKBACK..t-1)
  ret_t      = (C_t - C_{t-1}) / C_{t-1}

  vol_expansion = TR_t / ATR_yest > VOL_MULT
  direction_clear = |ret_t * 100| > MIN_RETURN_PCT

  if vol_expansion AND direction_clear:
      pos_cont = sign(ret_t)       # continuation: ride direction of vol day
      pos_fade = -sign(ret_t)      # fade null
      enter at C_t close, exit at C_{t+HOLD} close

Skip rule:
  if a new vol-expansion fires while a prior trade is open, the prior
  trade exits and the new one opens at the same close (no overlapping).
```

Variants:
- `VOL_MULT` ∈ {1.0, 1.25, 1.5, 2.0, 2.5}
- `HOLD_DAYS` ∈ {1, 2, 3, 5, 7}
- `MIN_RETURN_PCT` ∈ {0.0, 0.5, 1.0, 2.0}
- `COST_BPS_PER_SIDE` ∈ {0, 5, 10, 20}
- Direction: continuation as primary; fade as null AND alternative
  hypothesis (per gap_continuation lesson).

## Universe

- **BTCUSD D1** on Eightcap MT5 (datalake cache).
- Period: **2018-01-01 → 2026-03-31** (8.25 years, 2,665 D1 bars).

## Expected performance

Per the institutionalization-decay prediction:
- W1 (2018-2019) and W2 (2020-2021) are the high-vol-of-vol periods.
  Expected Sharpe +1 to +2 in these windows.
- W3 (2022-2023) and especially **W4 (2024-2026)** are the binding
  constraint. Realistic post-institutionalization Sharpe target:
  +0.30 to +0.70.
- Full-sample Sharpe target: +0.50 to +0.80 (weighted by trade counts
  across periods).
- Trade cadence: 80-150 trades over 8 years if `VOL_MULT=1.5`,
  `MIN_RETURN_PCT=1.0`. Below 100 likely fails Phase 2 trade-count bar.
- MDD target: < 20%.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:

1. **Sharpe < +0.30** at honest 10 bps/side cost in the best direction.
2. **Max DD > 20%**.
3. **Trade count < 100** over 2018-2026 (lower bar than btc_weekend
   because vol-expansion is a rare event by design).
4. **Fade-gap < +0.40** (slightly lower than btc_weekend's +0.50 because
   short-term post-event signals are noisier).
5. **Cost-zero Sharpe < +0.30**.

Phase 4 kills if Sharpe **positive in ≤ 2/4 windows**.

**Holdout-decay pre-commit (per the decay-side expectation):** if
**W4 (2024-2026) Sharpe ≤ +0.20** at honest costs, REJECT regardless of
full-sample. The deploy-relevant question is "does the mechanism still
work post-institutionalization", and W4 is the most recent forward-look.
This is the lesson from `vix_term_structure` (full-sample +0.31,
holdout -0.45, REJECT despite passing the bare full-sample bar) and the
warning from `btc_trend`'s W4 +0.50 (which was barely tolerable).

**Walk-forward Phase 6 (applied from Phase 2 per lesson #29):**
5 rolling 3y-IS / 2y-OOS splits. Kill if mean degradation > +0.5 OR
fewer than 3/5 splits with OOS Sharpe > 0.

## Why this might fail (red flags)

1. **Decay-side prediction.** Short-term post-event continuation is the
   exact mechanism HFT arb compresses. W4 is the binding window.
2. **Vol clustering ≠ direction signal.** GARCH alpha+beta near 1 means
   *magnitudes* persist; that doesn't imply *signs* do. The directional
   continuation hypothesis is the real bet.
3. **Trade cadence borderline.** Vol expansion is rare. If the filter
   bites too hard, trade count drops below 100 and the strategy
   statistically can't differentiate from noise.
4. **0DTE-options analog.** Just as 0DTE flow killed VWAP-fade and EOD
   strategies (sign-inverted post-2022), BTC options on CME/Deribit/IBKR
   have grown dramatically post-2022 and may be arbitraging short-term
   continuation in similar ways.
5. **Crashes vs rallies asymmetry.** Vol expansions on the downside
   (LUNA, FTX, banking crisis Mar 2023) may behave differently from
   upside vol expansions (Bitcoin halving runs). Long-only or
   asymmetric variants may matter — but the baseline tests symmetric
   first to avoid in-sample optimization.

## Phase 1 → 2 plan

- [x] Thesis written
- [ ] Phase 2 baseline + vol-mult sweep + hold-period sweep + cost sweep
- [ ] Phase 4 regime breakdown (4 windows)
- [ ] Phase 5 parameter sensitivity
- [ ] Phase 6 walk-forward (5 rolling 3y-IS / 2y-OOS)
- [ ] Null check (fade direction as alternative hypothesis)
- [ ] Holdout-decay diagnostic (W1 vs W4 Sharpe + W4 absolute floor)
- [ ] Verdict + STATE.md update

## Files

- Thesis: this file.
- Demo: `experiments/btc_volbreak/btc_volbreak_demo.py`.
- Data: `ohlc_data/BTCUSD_D1.csv` (cached from datalake).

---

## Phase 2 results (2026-05-13)

Run config: BTCUSD D1 2018-01-01 → 2026-03-31, VOL_MULT=1.5, HOLD_DAYS=3,
MIN_RETURN_PCT=1.0, ATR_LOOKBACK=20, COST_BPS_PER_SIDE=10.0.

Vol-expansion fires: 388 days of 2,665 (~14.6%). After overlap suppression, 261 trades.
Mean TR/ATR ratio on fire days: 2.32. Mean |return| on fire days: 6.01%.

### Phase 2 kill criteria

| metric | value | bar | verdict |
|---|---|---|---|
| Sharpe @ 10 bps | +0.40 | > +0.30 | PASS |
| MDD | **-51.69%** | < 20% | **FAIL** |
| Trades | 261 | ≥ 100 | PASS |
| Fade-gap (cont +0.40 vs fade -0.77) | +1.17 | > +0.40 | PASS |
| Cost-zero Sharpe | +0.58 | > +0.30 | PASS |
| W4 Sharpe (decay floor) | **+0.18** | > +0.20 | **FAIL** by 0.02 |
| **Phase 2 OVERALL** | — | — | **FAIL** |

### Phase 4 — regime breakdown (continuation)

| window | trades | total | Sharpe | MDD | WR |
|---|---|---|---|---|---|
| W1 2018-2019 | 51 | -21.83% | **-0.12** | -41.33% | 47.1% |
| W2 2020-2021 (parabola+COVID) | 57 | **+177.92%** | **+1.58** | -23.59% | 57.9% |
| W3 2022-2023 (FTX+bear) | 70 | -22.52% | **-0.26** | -36.30% | 47.1% |
| W4 2024-2026 (ETF era) | 77 | +2.91% | **+0.18** | -27.90% | 48.1% |

**W2 IS the entire strategy.** Outside the 2020-2021 parabola + COVID-liquidity window,
vol-expansion-day directional content is essentially noise (W1 -0.12, W3 -0.26, W4 +0.18 —
all under +0.20 bar). 3 of 4 Phase 4 windows fail individually.

Fade direction lost in every window (-0.14, -1.89, -0.19, -0.70). Strong fade-gap +1.17
confirms the mechanism is directional, not symmetric noise. But "directional" is only
useful if it's also persistent across regimes, which it isn't.

### Phase 5 — parameter sensitivity (continuation)

| VOL_MULT | trades | Sharpe | MDD |
|---|---|---|---|
| 1.00 | 523 | -0.20 | -78.66% |
| 1.25 | 371 | +0.26 | -75.37% |
| **1.50** | **261** | **+0.40** | **-51.69%** |
| 2.00 | 133 | +0.20 | -45.81% |
| 2.50 | 75 | +0.17 | -35.55% |

| HOLD_DAYS | Sharpe | MDD |
|---|---|---|
| 1 | +0.15 | -37.27% |
| 2 | +0.19 | -45.71% |
| **3** | **+0.40** | **-51.69%** |
| 5 | +0.33 | -67.21% |
| 7 | +0.05 | -67.39% |

Peak at the chosen baseline — no robust plateau. The optimum-VOL_MULT (1.5) and
optimum-HOLD (3d) are the only configurations that even cross +0.30 Sharpe at honest cost,
which is classic in-sample peak-picking. Most parameter neighborhoods are at or below the
+0.30 kill floor.

| cost (bps/side) | Sharpe |
|---|---|
| 0 | +0.58 |
| 5 | +0.49 |
| **10** | **+0.40** |
| 15 | +0.30 |
| 20 | +0.21 |
| 30 | +0.02 |

Cost-linear collapse, breakeven near 30 bps. Honest 10 bps puts the strategy at +0.40 —
above the +0.30 bar, but only because W2's contribution is so large.

### Phase 6 — walk-forward (5 rolling 3y-IS / 2y-OOS splits)

| split | IS window | OOS window | IS Sh | OOS Sh | degradation |
|---|---|---|---|---|---|
| S1 | 2018-2020 | 2021-2022 | +0.43 | **+0.93** | -0.50 |
| S2 | 2019-2021 | 2022-2023 | +1.00 | -0.26 | +1.26 |
| S3 | 2020-2022 | 2023-2024 | +1.20 | -0.54 | **+1.74** |
| S4 | 2021-2023 | 2024-2025 | +0.38 | -0.25 | +0.63 |
| S5 | 2022-2024 | 2025-Q1'26 | -0.19 | +0.19 | -0.38 |

| metric | value | bar | verdict |
|---|---|---|---|
| Mean degradation | +0.551 | < 0.5 | **FAIL** |
| Median degradation | +0.630 | — | FAIL |
| Splits w/ deg < 0.5 | 2/5 | ≥ 3 | **FAIL** |
| Splits w/ OOS Sh > 0 | 2/5 | ≥ 3 | **FAIL** |
| **Walk-forward OVERALL** | — | — | **FAIL** |

Walk-forward FAILS three independent criteria. The IS Sharpe rises through S1-S3 because
each split incorporates more of the W2 (2020-2021) effect; OOS then collapses because the
W2-only mechanism doesn't transfer to W3-W4 testing windows.

### Verdict (2026-05-13): **REJECT** — pre-institutionalization-only edge

| phase | verdict |
|---|---|
| Phase 2 (kill criteria) | **FAIL** (MDD, W4 floor) |
| Phase 4 (regime stability) | **FAIL** (1/4 windows clean positive) |
| Phase 5 (parameter sensitivity) | FAIL (no plateau, peak-picking) |
| Phase 6 (walk-forward) | **FAIL** (mean deg +0.55, 2/5 OOS positive) |
| Null check | PASS (fade-gap +1.17) |

**Pattern: one-window wonder.** Vol-expansion directional continuation on BTC D1 worked
strongly in 2020-2021 (parabola + COVID-liquidity high-vol-of-vol regime) and essentially
nowhere else. The mechanism description is mechanically reasonable, but the empirical
edge lived in a single anomalous regime. By the BTC institutionalization rule (see
[RESEARCH_NOTES.md #30](../../docs/RESEARCH_NOTES.md) and lesson #31 added 2026-05-13),
strategies whose edge is concentrated in a pre-institutionalization window are not
deployable regardless of full-sample Sharpe.

**Per lumber_oats lesson — not a refinement candidate.** A "post-2022 only" or
"regime-conditional" variant would be a separate Phase 1 thesis with its own pre-committed
criteria. Don't move goalposts on this one.

**Cross-thread observation.** With btc_volbreak now REJECT, three independent BTC daily
theses have closed:
- `btc_trend` (slow autocorrelation): edge decays as BTC institutionalizes.
- `btc_weekend` (microstructure): edge activates post-institutionalization but full-sample
  MDD fails because of the pre-activation drawdown years.
- `btc_volbreak` (short-term vol-event continuation): edge lived entirely in one
  pre-institutionalization window.

Together they map the institutionalization phase transition from three different
mechanism families. The BTC daily-frequency research thread is effectively bounded:
**any new BTC daily thesis must pre-commit to a W4 (post-2022) absolute floor as
binding**, not full-sample Sharpe.
