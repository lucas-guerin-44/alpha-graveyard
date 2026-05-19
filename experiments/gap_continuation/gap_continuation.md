# Overnight Gap Continuation — SPX500 / NDX100 (US session)

**Status**: Phase 2 complete 2026-05-13.

**Verdict**: **REJECT — thesis sign inverted on both instruments; fade direction shows positive Sharpe on NDX (+0.29) but at the kill-criteria floor.**

| Symbol | Cont Sh (baseline) | Fade Sh (null) | Dir-gap | Holdout (cont) | MDD | Trades |
|---|---|---|---|---|---|---|
| SPX500 | −0.88 | −0.40 | **−0.48** | −0.76 | −28.8% | 871 |
| NDX100 | −0.63 | **+0.29** | **−0.92** | −0.24 | −26.4% | 838 |

**Headline**: The hypothesis was that US-index overnight gaps continue (Asia/EU + earnings info loading). Empirically the opposite holds on both SPX and NDX — the continuation direction loses, and on NDX the FADE direction is mildly profitable (Sh +0.29, WR 52.6%, PF 1.09, MDD -9.8% at 838 trades — right at the +0.30 floor).

This **contradicts the DAX-gap-fade result** (`experiments/dax/gap_fade.md`: continuation gross +0.12, fade -1.04). Same mechanism description, opposite empirical conclusion on different venues:
- DAX gaps: continue (auction under-prices overnight info)
- NDX gaps: fade (auction overshoots overnight info)
- SPX gaps: no clean signal in either direction

**Mechanistic read**: NYSE/Nasdaq pre-market is a 5.5-hour window of continuous price discovery on liquid futures (ES/NQ trade 18 hours/day). By 09:30 ET RTH open, the gap on cash CFDs reflects ES/NQ overnight price action plus 6:00-09:30 ET pre-market single-stock action. Both windows have ample time for over-extension. Xetra by contrast opens at 09:00 Berlin with a discrete auction; gap reflects just the actual overnight EU futures action plus a thin set of EU pre-open quotes. The "thin pre-market = auction under-prices info" mechanism that makes DAX gaps continue is absent on US indices because their pre-market is anything but thin.

NDX fade Sh +0.29 sits right at the kill-criteria floor. Worth flagging as a candidate for a follow-up *gap-fade-on-US-indices* thesis with proper sweeps + holdout regime check — but not as a primary deploy candidate from this experiment.

## Threshold sweep (Sharpe at 1pt cost)

| thr | SPX cont | NDX cont | SPX trades | NDX trades |
|---|---|---|---|---|
| 0.00 | −1.55 | −0.93 | 1,878 | 1,881 |
| 0.25 | −1.26 | −0.86 | 1,305 | 1,259 |
| 0.50 | −0.88 | −0.63 | 871 | 838 |
| 0.75 | −0.48 | −0.58 | 548 | 514 |
| 1.00 | −0.31 | −0.17 | 356 | 317 |
| 1.50 | −0.09 | +0.04 | 141 | 118 |

Monotonic improvement with higher threshold but never positive enough at trade-floor-passing levels.

## Hold-window sweep (NDX cont)

| Hold | Sharpe | MDD |
|---|---|---|
| 30min (10:00 ET) | −0.92 | −13.6% |
| 60min (10:30 ET) | −0.64 | −15.5% |
| 90min (11:00 ET) | **−0.35** | **−13.5%** |
| 120min (11:30 ET) | −0.63 | −26.4% |
| 180min (12:30 ET) | −0.81 | −42.3% |
| 240min (13:30 ET) | −0.81 | −52.5% |
| 300min (14:30 ET) | −0.68 | −52.5% |

Best hold is 90min (-0.35 Sh) — never crosses zero. Longer holds get progressively worse, hitting -52% drawdown at 240min+. The losing trades compound through the day; gap-direction trades lose more the longer you hold.

## Long/short asymmetry (baseline cont)

NDX: LONG (long gap-up) Sh −0.70, SHORT (short gap-down) Sh −0.26. Both lose, neither side rescues.

## Lessons captured

- **Gap-direction effect is venue-specific.** DAX (continuation) and NDX (fade) move in opposite directions — same mechanism description, different empirical conclusions. The Xetra-vs-NYSE/Nasdaq microstructure asymmetry (discrete vs continuous pre-market) is the most likely driver. **Never port a gap-direction thesis across venues without re-testing**.
- **The DAX-gap-fade-null was venue-specific evidence, not universal.** The +0.12 continuation Sharpe on DAX was the seed for this thesis; it doesn't generalize to US indices and shouldn't have been assumed to.
- **Fade-on-NDX-gap (+0.29) sits at the kill floor — worth one targeted follow-up.** Not a deploy candidate from this experiment, but a focused gap-fade thesis on NDX with cost-aware threshold sweep + regime check could potentially pull this above +0.30 if the post-2022 era continues. Caveat: the fade direction is mostly null-check fallout from the primary continuation REJECT, so a clean re-run with fade as primary hypothesis is required before any deploy consideration.

---

## Original thesis (Phase 1 — preserved for reference)



---

## Thesis (mechanism)

The overnight gap (prior 15:55 ET close → current 09:30 ET open) on US index CFDs reflects accumulated information from three sources:

1. **Asia + EU session price discovery** during 16:00-09:30 ET overnight window. By 09:30 ET, EU markets are at their 14:30 mark (mid-session) and Asia is closed; their net move during the US-overnight is priced into the index futures.
2. **Overnight earnings, macro releases, and central-bank communication** (e.g., FOMC minutes 14:00 ET prior day, ECB 08:15 ET same day, Asia central banks during their session, China data 21:00 ET prior day).
3. **Pre-market US-listed news** between 04:00-09:30 ET — biggest single-stock movers (especially mega-caps) move pre-market and the index gap reflects the aggregate impact.

The DAX-gap-fade experiment (`experiments/dax/gap_fade.md`) tested the *fade* direction and rejected with strong sign-inversion (continuation null +0.12, fade -1.04). That null result is the seed for this thesis: **the overnight gap is information-loaded and continues into the first session segment**, not a noise overshoot to fade.

Why this might work on US indices specifically (where ORB-on-SPX/NDX failed):

- ORB requires a **breakout signal** from the opening range — discards days where price oscillates within the OR without a clean break. Many US index sessions show oscillation in the 09:30-10:00 window even on information-rich days because of intraday auction stages and slow price discovery across NYSE/Nasdaq. Gap continuation uses the **already-set-at-09:30** signal, no breakout filter required.
- ORB's directional signal is shaped by OR-width and timing; gap continuation's directional signal is shaped by overnight information flow (Asia/EU + earnings + macro), which is more uniformly directional per unit of news.
- The mechanism is well-documented in single-stock literature (e.g., Heston-Korajczyk-Sadka 2010 intraday patterns) but rarely tested as a standalone index strategy because most retail gap research is paired with fade-thesis tests.

## Key references

- **Lou, Polk, Skouras (2019)**, "A tug of war: Overnight versus intraday expected returns." *Journal of Financial Economics* 134(1). Documents overnight-vs-intraday return asymmetry; overnight is information-dense, intraday is mean-reverting on average. Supports gap-continuation as a "ride the overnight info" thesis.
- **Berkman, Koch, Tuttle, Zhang (2012)**, "Paying attention: Overnight returns and the hidden cost of buying at the open." *Journal of Financial and Quantitative Analysis* 47(4). Retail-attention spike at 09:30 amplifies overnight-direction moves in the first 30 min.
- **Heston, Korajczyk, Sadka (2010)**, "Intraday patterns in the cross-section of stock returns." *Journal of Finance* 65(4). Half-hour autocorrelation patterns; the 09:30-10:30 ET continuation effect is documented.
- **Bollerslev, Li, Patton, Quaedvlieg (2020)**, "Realized semicovariances." Overnight return component is the dominant source of next-day directional information for equity-index futures.

## Signal math

```
Parameters:
  HOLD_MINUTES              = 120   (exit at 11:30 ET = 120 min into session)
  MIN_GAP_ATR               = 0.5   (threshold on |gap| in ATR-proxy multiples)
  COST_POINTS_ROUND_TRIP    = 1.0
  ATR_LOOKBACK_DAYS         = 20

Per trading day:
  prev_close = close[last bar of previous session]      (15:55 ET prior day)
  today_open = open[first bar of current session]       (09:30 ET today)
  gap_pct    = today_open / prev_close - 1

  atr_m5     = trailing-20-day mean of single-bar |return|
  thr        = MIN_GAP_ATR * atr_m5 * sqrt(bars_per_overnight)
               (overnight gap variance scales like sqrt of bar count
                across the 16:00 → 09:30 = 17.5h overnight = 210 M5
                bars-equivalent)

  if |gap_pct| < thr:  skip day
  pos = sign(gap_pct)                                  (continuation)
  enter at session-open (today_open as fill price)
  exit at first bar with mod >= HOLD_MINUTES, last close

  Max 1 trade per day. Flat overnight.
```

Variants: HOLD ∈ {60, 120, 180, 240, 300}, MIN_GAP ∈ {0.0, 0.25, 0.5, 0.75, 1.0, 1.5}, cost ∈ {0.5, 1, 2, 3}pt. Null-check: fade direction (the DAX-gap-fade thesis, expected to lose).

## Universe

- **SPX500** CFD on MT5, M5 bars, 2019-01-02 → 2026-04-17.
- **NDX100** CFD on MT5, same range.

## Expected performance

If the DAX-gap-fade null result generalises: ~+0.12 Sharpe gross continuation observed on DAX. SPX/NDX should be modestly higher because (a) US-specific news (earnings, FOMC, macro) is fresh at 09:30 ET vs already-old by 09:00 Berlin for DAX, (b) mega-cap single-stock overnight moves (AAPL/MSFT/NVDA etc.) translate directly to NDX. Targets: Sharpe 0.30-0.60, 200-400 trades/yr after threshold filter, MDD 8-15%.

Trade cadence ~1-2 per week if filter clears ~30-50% of days.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200 over 7 years.
- WR < 48% OR PF < 1.05 (continuation-payoff is near-symmetric).
- **Null-check direction-gap < +0.30** (continuation Sharpe − fade Sharpe must exceed +0.30).

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows.
Phase 6 kills if 2023-2026 holdout Sharpe ≤ 0.

## Why this might fail (red flags)

1. **CFD overnight pricing is dealer-constructed.** The DAX overnight thesis was a CFD-data artifact — research +0.80 → FDAX futures −0.34. The gap at 09:30 ET on SPX/NDX CFD might include similar dealer-quote-construction effects that don't survive on real futures. Phase 8 must validate on MES/MNQ futures before deploy.
2. **Sign-inversion track record.** Four fade theses on indices have sign-inverted (DAX gap, DAX US-lead, DAX pre-auction, VWAP fade NDX). The continuation theses haven't been tested as primary — could still sign-invert the other way (i.e., fade actually wins) on SPX/NDX even though DAX's continuation was nominally positive.
3. **Overlap with ORB.** ORB on SPX/NDX failed. If the post-open price action is too noisy to support ORB's "breakout then continue" structure, gap continuation might face the same noise floor without the breakout filter buying any signal-quality.
4. **0DTE distortion.** On gap days, 0DTE option open-interest at strikes near the prior close creates immediate hedging pressure at the open — could either amplify continuation (dealer-short-gamma effect) or fade it (delta-rehedge into the gap). The net effect post-2022 is empirical, not predictable.
5. **First-30-min decay.** Single-stock literature shows the overnight-info edge dissipates within ~30-60 min. If our HOLD_MINUTES sweep finds the edge only survives at HOLD=30 with too few trades, that's a different problem.

## Phase 1 → 2 plan

- [x] Thesis written
- [ ] SPX500 baseline + sweeps + regime breakdown + cost + null-check
- [ ] NDX100 same battery
- [ ] Cross-instrument verdict + long/short asymmetry
- [ ] Correlation check vs ORB-GER40 + lunch-fade-NDX
- [ ] Mechanistic interpretation write-up

## Files

- Thesis: this file.
- Demo: `experiments/gap_continuation/gap_continuation_demo.py` — env-var `GAP_SYMBOL` (default SPX500).
- Data: `ohlc_data/SPX500_M5.csv`, `ohlc_data/NDX100_M5.csv`.
- Run commands:
  - `venv/Scripts/python.exe experiments/gap_continuation/gap_continuation_demo.py`
  - `GAP_SYMBOL=NDX100 venv/Scripts/python.exe experiments/gap_continuation/gap_continuation_demo.py`
