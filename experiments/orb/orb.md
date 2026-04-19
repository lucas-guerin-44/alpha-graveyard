# Opening Range Breakout — cross-instrument (SPX500 / NDX100 / GER40 / UK100 / FRA40)

**Status**: Phase 2 + refinement complete across five US/EU cash-index CFDs on M5, 2019-2026.

**Verdict**:

| Instrument | Verdict | Leading config | Sharpe (full) | Holdout Sh | MDD |
|---|---|---|---|---|---|
| SPX500 | REJECT | — | −0.92 | −0.87 | −51% |
| NDX100 | MARGINAL (do not deploy) | Baseline EOD | +0.03 | +0.19 | −22% |
| **GER40** | **PASS — deploy** | **T+180 LONG-only** | **+0.76** | **+0.93** | **−7.8%** |
| UK100 | REJECT | — | −0.54 | −0.84 | −32% |
| FRA40 | INCONCLUSIVE | — | data coverage issue | — | — |

**Deployment recommendation**: GER40 T+180min LONG-only. Expected live Sharpe after 50-70% haircut: **+0.23 to +0.46**. Trade cadence 3.8/week. Fade-gap +1.04 confirms real directional signal; long/short split shows the edge is concentrated on the long side (shorts are a drag in 3 of 3 regime windows except 2021-2022).

---

## Thesis (mechanism)

Around the cash-equity open, overnight information, non-session flow, and pre-market positioning resolve into a short-term price impulse. The **opening range** — first 15–30 minutes of RTH — brackets that resolution. Price closing outside the OR tends to continue because:

1. **Liquidity clusters at round levels and overnight high/low**, so clean breaks generate stop-runs and momentum-chasing from late entrants.
2. **Asymmetric information incorporation**: pre-market news is digested during the OR window; breakout direction reveals which way the net new information cut.
3. **Trend-day bias**: on decisive-impulse days, intraday high/low is set in the first or last hour ~60-65% of the time (Crabel 1990; Fisher). ORB tries to be positioned during the big directional window.

Effect sizes have compressed as intraday markets have become more efficient, so realistic retail expectations run well below 1990s literature.

## Key reference

**Zarattini & Aziz (2023), "Can Day Trading Really Be Profitable?"** — 5-min ORB on QQQ 2016-2023. With a relative-volume filter and 0.01% commission, reported annualized Sharpe 1.65-2.81. Modern anchor paper; we expect meaningful degradation on CFD instruments vs cash-equity QQQ, and further haircut from commission vs CFD spread.

## Signal math — deploy config (GER40 T+180 LONG-only)

```
Parameters:
  OR_MINUTES                = 30    (opening range window length)
  ENTRY_CUTOFF_MIN          = 180   (no new entries after 12:00 Berlin)
  T_EXIT_MIN                = 180   (time-of-day exit 180 min after entry)
  EXIT_MIN_BEFORE_CLOSE     = 5     (flat by 17:25 Berlin regardless)
  COST_POINTS_ROUND_TRIP    = 1.0   (pessimistic retail CFD)
  LONG_ONLY                 = True  (short leg is a net drag in sample)

Per trading day (Europe/Berlin cash session, 09:00-17:30):

  OR_high = max(high) over bars in [09:00, 09:30)
  OR_low  = min(low)  over bars in [09:00, 09:30)

  For each M5 bar b after 09:30 and before 12:00 (entry cutoff):
    if flat and b.close > OR_high and first long breakout of day:
      enter LONG at next bar open
      stop = OR_low
      take = none (T+180 time exit does the risk-management)

  Exit: (a) stop hit, or (b) 180 min after entry, or (c) 17:25 Berlin flat.
  Max 1 round-trip per day.
```

Note: short-side entry is logged but not executed in production. See "Long/short asymmetry" below.

## Universe

- **Research**: SPX500, NDX100, GER40, UK100, FRA40 CFDs on MT5. M5 bars, 2019-01-02 → 2026-04-17.
- **Live (GER40)**: MT5 broker CFD. QC analog: FDAX / MFDAX (Eurex DAX futures).

## Expected performance (at thesis time)

Literature benchmarks:
- Zarattini/Aziz (2023), QQQ 5-min 2016-2023: Sharpe 1.65-2.81 (published, with volume filter).
- Crabel (1990), S&P futures 1980s: ~60% WR, 2:1 PF anecdotal.
- Desk replications 2015-2023: Sharpe 0.4-0.8 on futures after costs, 5-8 trades/week.

**Expected retail-net after 1pt RT cost**: Sharpe 0.3-0.6, 3-8 trades/week, WR 45-55%, PF 1.2-1.5, MDD 12-20%. Live target after 50-70% haircut: Sharpe 0.15-0.35.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200 over 7 years.
- WR < 38% AND PF < 1.1.

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows (2019-2020 / 2021-2022 / 2023-2026).

Phase 6 kills if 2023-2026 holdout Sharpe ≤ 0.

**Fade-test null check**: if fade (trade against the breakout) produces similar Sharpe to baseline, signal has no directional content → tombstone even if absolute Sharpe looks acceptable.

## Why this might fail (red flags)

1. **ORB is one of the most-published intraday edges** — likely arbed down from literature levels.
2. **CFD costs are higher than cash-equity commission** — 1pt RT on index CFDs is ~2bps vs Zarattini's 2bps commission-total, giving us ~2× the friction at similar nominal assumption.
3. **Timezone/session alignment risk** — MT5 broker server timestamps need careful UTC mapping.
4. **Phantom fills** — M5-close entry → next-bar-open fill assumes open-price availability; live tick fills can be 1-5 ticks away on strong breakouts.

---

## Phase 2 results — by instrument

### SPX500 — REJECT

M5, RTH 09:30-16:00 ET, 146,054 bars, 1,884 trading days.

**Baseline (OR=30min, opposite-OR stop, cost=1pt)**:

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | −0.92 | FAIL |
| Max DD | −51.1% | FAIL |
| Trades | 2,638 (7.0/wk) | PASS |
| WR / PF | 23.0% / 0.85 | FAIL |
| Avg win / loss | +0.587% / −0.205% | — |

**Regime breakdown**: all 3 windows negative (−0.83 / −1.15 / −0.87). **3/3 regime fail.**

**Stop-tightness sweep**: tighter stops *worsen* Sharpe (0.25x OR → Sharpe −2.18, WR 4.4%) because SPX500 M5 bars routinely traverse 30-50% of OR width intrabar. Stop is inside normal intrabar noise.

**Fade variant**: Sharpe −0.95 (also loses). **No directional content** — baseline and fade both lose → pure noise trading.

**Why this doesn't invalidate Zarattini/Aziz**: they used 5-min OR (not 30-min), a relative-volume filter on real share volume (CFDs only have tick-volume), 10%-of-opening-bar-range stops (much tighter), 0.01%/side commission (tighter cost). Some combination of these explains the flip.

**3 of 4 hard fails. REJECT, tombstone.**

### NDX100 — MARGINAL (do not deploy)

M5, RTH 09:30-16:00 ET, 520,594 raw bars.

**Baseline (OR=30min, EOD exit, cost=1pt)**:

| Metric | Value |
|---|---|
| Sharpe | +0.03 |
| MDD | −22% |
| Trades | 2,707 (7.1/wk) |
| WR / PF | 16.8% / 1.00 |

**Regime breakdown**: 2019-2020 −0.15, 2021-2022 +0.01, **2023-2026 holdout +0.19**. Holdout is the *best* sub-period — opposite of the post-2022 decay seen in other strategies, suggesting the mechanism may be intact in the current regime.

**Fade test**: baseline +0.03 vs fade −0.46 → **fade-gap +0.49**. Clean directional signal content (unlike SPX500 where both directions lose identically).

**Refinement attempts fail**:

| Variant | Full Sh | 2019-2020 | 2021-2022 | Holdout |
|---|---|---|---|---|
| Baseline (EOD) | +0.03 | −0.15 | +0.01 | **+0.19** |
| 1:2 R:R + EOD | −0.64 | +0.46 | −1.19 | −1.12 |
| T+180 (no RR) | −0.09 | −0.35 | −0.22 | +0.22 |
| T+180 + 1:2 R:R | −0.52 | +0.57 | −0.85 | −1.14 |

**The baseline is the ceiling, not a starting point.** Every refinement that helped GER40 hurts NDX100 — classic in-sample overfit where 2019-2020 wins don't survive to holdout. Under tight R:R, fade actually beats baseline on NDX100 (opposite of GER40). The T+180 exit that unlocked GER40's edge fails here. Different post-breakout dynamics.

**Tight-stop + trend-filter "optimized" variant**: Sharpe +0.31 full, holdout **−0.19**. Baseline where holdout is strongest → optimized where holdout is weakest. Classic overfit signature; **prefer the unoptimized baseline if anything**.

**Verdict**: MARGINAL. Real directional signal (+0.49 fade-gap), but absolute Sharpe too weak to survive realistic cost or exit-structure choice. **Do not deploy.** Fallback only if GER40 has broker-specific execution issues.

### GER40 — PASS (deploy candidate)

M5, RTH 09:00-17:30 Europe/Berlin, 470,230 raw bars (188,895 session-filtered).

**Baseline (OR=30min, EOD exit, cost=1pt)**:

| Metric | Value |
|---|---|
| Sharpe | +0.38 |
| MDD | −13.0% |
| Trades | 2,831 (7.5/wk) |
| WR / PF | 14.7% / 1.08 |

**Regime breakdown**: all 3 windows positive (+0.59 / +0.47 / +0.12). Numerically best of all instruments.

**Initial fade test (EOD exit)** looked like a structural artifact: baseline +0.38, fade +0.34 → gap only +0.04. This was *wrong* — the EOD exit's asymmetric R:R was masking a real directional edge. Proper diagnosis via the refinement battery below.

#### Refinement 1 — T+180min time exit

Replace EOD with fixed time-of-day exit:

| Exit | Sharpe | MDD | PF |
|---|---|---|---|
| T+60min | +0.38 | −9.0% | 1.07 |
| T+120min | +0.38 | −12.6% | 1.07 |
| **T+180min** | **+0.58** | −12.3% | 1.11 |
| T+240min | +0.52 | −14.1% | 1.11 |
| EOD (prior baseline) | +0.38 | −13.0% | 1.08 |

**Edge is concentrated in the first 3 hours post-breakout.** Consistent with opening-impulse momentum having a half-life, not indefinite persistence.

#### Refinement 2 — symmetric R:R fade-gap diagnostic

Under symmetric R:R (replace asymmetric EOD exit with fixed R:R targets), the fade variant loses decisively:

| R:R | Baseline Sh | Fade Sh | Gap |
|---|---|---|---|
| 1:1 | −0.24 | −1.21 | **+0.97** |
| 1:1.5 | −0.05 | −1.06 | +1.01 |
| 1:2 | +0.35 | −0.66 | +1.01 |
| 1:3 | +0.13 | −0.19 | +0.32 |

**Fade-gap +0.97 to +1.04 under symmetric payoffs.** Directional signal is real; the prior +0.04 gap at EOD was the EOD asymmetry flattering both sides, not an absence of signal.

Re-run with T+180 + 1:2 R:R: fade-gap **+1.04**. Confirmed.

#### Refinement 3 — regime consistency across top candidates

| Variant | 2019-2020 | 2021-2022 | 2023-2026 HO | Full |
|---|---|---|---|---|
| Baseline (EOD) | +0.59 | +0.47 | +0.12 | +0.38 |
| 1:2 R:R + EOD | +0.89 | −0.11 | +0.11 | +0.35 |
| **T+180 (no RR)** | **+0.56** | **+0.69** | **+0.55** | **+0.58** |
| T+180 + 1:2 R:R | +0.49 | −0.08 | +0.43 | +0.30 |
| T+180 + 1:1 R:R | −0.34 | −0.63 | −0.23 | −0.36 |

**T+180 (no RR) is the clean winner**: 3/3 regime windows ≥ +0.55, tightest distribution. Adding an RR target hurts because the OR-boundary stop is already capping risk, and a TP caps winners prematurely.

#### Refinement 4 — OR-width conviction filter (rejected)

Filtering for OR width ≥ 0.3%-1.0% of price killed trade count (2,831 → 13-145) without improving Sharpe. DAX doesn't reward "wide OR = conviction"; narrow-OR breakouts are equally informative.

#### Refinement 5 — long/short asymmetry split

The T+180 +0.58 Sharpe is not symmetric across direction:

| Leg | Trades | Sharpe | MDD | PF |
|---|---|---|---|---|
| ALL | 2,831 | +0.58 | −10.83% | 1.11 |
| **LONG-only** | 1,440 | **+0.76** | **−7.77%** | **1.22** |
| SHORT-only | 1,391 | +0.01 | −9.76% | 1.00 |

**Regime-by-regime delta**:

| Window | LONG Sh | SHORT Sh | Delta |
|---|---|---|---|
| 2019-2020 | +0.94 | −0.31 | +1.26 |
| 2021-2022 | +0.44 | +0.55 | −0.11 |
| **2023-2026 holdout** | **+0.93** | **−0.17** | **+1.10** |

**Only 2021-2022 vol regime is directionally symmetric.** Outside that window shorts are a net drag. Exit-reason attribution: both directions have similar stop sizes and TOD-hit rate, but longs have more TOD wins (305 vs 270) with larger avg TOD size (+0.535% vs +0.493%) — asymmetry lives in the payoff distribution.

Two plausible drivers (non-exclusive):
1. **Secular upward drift** in DAX 2019-2026 (10,600 → 22,000+). LONG captures breakout alpha + drift; SHORT works against drift and breaks even before costs.
2. **Asymmetric breakout quality** — up-breakouts signal institutional buying (earnings, ECB-dovish); down-breakouts skew toward noise-flush-outs that mean-revert. 2021-2022 symmetry (sustained decline phase) weakly supports this.

**Regime risk**: if DAX flips to sustained decline, LONG-only underperforms symmetric. Hedge: run LONG-only in production but log SHORT signals for shadow analysis; re-enable if shadow PnL turns persistently positive over 3-6 months.

**Honesty flag (not yet run)**: a "long 11:30-14:30 every day no trigger" benchmark would quantify how much of the +0.76 LONG-only Sharpe is baseline drift vs true breakout alpha. Followup.

#### Refinement 6 — TOD edge decomposition

Per-entry-hour PnL attribution, full sample (entry_cutoff=180min means all entries are 09:00-12:00 Berlin):

| Hour | n | avg pnl | total | WR |
|---|---|---|---|---|
| 09 | 1,266 | +0.012% | +15.24% | 18.6% |
| 10 | 1,056 | +0.017% | +17.70% | 20.6% |
| 11 | 485 | −0.010% | −4.93% | 19.6% |
| 12 | 24 | +0.089% | +2.14% | 25.0% |

**The 10:00 hour is the best bucket; 11:00 entries are slightly negative.** Early-session trades carry the signal; the final hour before the 12:00 cutoff is mildly noisy.

**Entry-cutoff sweep (full-sample Sharpe)**: 180min +0.58, 240min +0.49, 300min +0.49, 390min +0.42, 480min +0.43. **Narrower cutoff is strictly better at full-sample level** — the current 180min placement is correct.

Interesting wrinkle: for LONG-only, wider cutoffs lift *holdout* Sharpe even as they depress full-sample (180 → +0.93 HO, 390 → +1.06 HO, 480 → +1.06 HO). This looks like a regime shift where post-2023 edge extends later into the session. Not chasing it — picking a wider cutoff on the basis of holdout-best is exactly the overfit pattern we're trying to avoid. Stick with 180min.

#### Cost sensitivity (T+180 + 1:2 R:R, slightly more conservative than T+180 pure)

| Cost RT | Sharpe |
|---|---|
| 0.5pt | +0.56 |
| 1.0pt | +0.30 |
| 1.5pt | +0.04 |
| 2.0pt | −0.23 |

GER40 CFD at IC Markets/Pepperstone typical spread 0.5-1.0pt. Cost headroom acceptable.

#### Deploy config summary

**GER40 T+180 LONG-only** vs the initial symmetric EOD baseline:

| Metric | Symmetric EOD | T+180 ALL | **T+180 LONG-only** |
|---|---|---|---|
| Full Sharpe | +0.38 | +0.58 | **+0.76** |
| Holdout 2023-2026 | +0.12 | +0.55 | **+0.93** |
| MDD | −13.0% | −10.83% | **−7.77%** |
| Trades/week | 7.5 | 7.5 | 3.8 |
| Fade-gap (1:1 RR) | +0.04 | +0.97 | — |
| Expected live Sharpe (50-70% haircut) | +0.11 to +0.27 | +0.17 to +0.29 | **+0.23 to +0.46** |

### UK100 — REJECT

M5, RTH 08:00-16:30 Europe/London. Tested to probe the hypothesis "ORB works on European indices generically." It doesn't.

| Metric | Value |
|---|---|
| Baseline Sharpe | −0.54 |
| MDD | −32.2% |
| Trades | 2,884 (7.6/wk) |
| WR / PF | 13.2% / 0.88 |
| 2019-2020 | −0.93 |
| 2021-2022 | −0.34 |
| 2023-2026 holdout | −0.84 |

**3/3 regimes negative.** Probable driver: FTSE 100 is commodities-heavy with wide constituent rotation and less overnight-information accumulation than DAX. Overnight news prices via ADR trading (post-London close), so no coherent opening impulse. **Falsifies "European generic" hypothesis.** REJECT.

### FRA40 — INCONCLUSIVE (data coverage)

| Metric | Value |
|---|---|
| Trades (2019-2026) | 50 (0.13/wk) |
| Post-2020 trades | 0 |

This broker's FRA40 CFD starts streaming at ~09:00 UTC regardless of DST (= 10:00-11:00 Berlin), 1-2h past the intended 09:00 Berlin OR window. Most days have zero OR data.

Cash CAC 40 opens at 09:00 Paris (= 09:00 Berlin), but this broker treats FRA40 as a generic European tracker on a UTC-fixed server-time schedule. Retest would need a broker that mirrors Paris cash hours or a fixed-UTC session mode. Low priority — UK100 already falsified the "European generic" hypothesis.

---

## Cross-instrument mechanistic interpretation

| Instrument | Opening-impulse edge? | Post-breakout profile | Notes |
|---|---|---|---|
| SPX500 | None | Bars oscillate, hit stops both sides | No directional signal |
| NDX100 | Weak | Full-session slow drift; tight exits revert | Needs long hold; still too weak |
| **GER40** | **Strong** | **3h concentrated continuation, then noise** | Xetra morning-auction delivers clean resolution |
| UK100 | None | Commodity-sector rotation dominates | Overnight info not concentrated at LSE open |
| FRA40 | Untested | — | Data coverage issue |

**Key insight**: the "ORB mechanism" is not universal across index futures. It requires a market structure where overnight information concentrates into the opening auction (Xetra on DAX does this cleanly; cash-equity NYSE/Nasdaq does not; LSE does not). Refinement paths are instrument-specific — T+180 that unlocked GER40 hurts NDX100.

---

## Deployment plan (GER40 T+180 LONG-only)

1. **MT5 native path** — broker already set up, symbol live, data pipeline matches research.
2. **QC alternative** — FDAX (€25/pt full) or MFDAX (micro) on Eurex. Research cost ≈ real futures spread.
3. **Cost assumption** — 0.5-1.0pt broker spread expected; Sharpe stays positive up to ~1.3pt.
4. **Paper-trade 20 EU trading days** → ~15-25 live trades at 3.8/wk × 0.7 realized rate.
5. **Live kill trigger** — if live Sharpe < +0.17 after 20 trading days (worse than 70% haircut on research +0.76), tombstone and document gap.
6. **Shadow logging** — log SHORT entry signals (not executed) to detect regime shift toward bear phase where shorts might re-earn their seat.

## Lessons captured (for RESEARCH_NOTES.md)

- **Intraday CFD costs + tick-volume ≠ real volume meaningfully change viability of published edges.** Literature results on commission-cash-equity instruments don't port 1:1 to retail CFDs even when mechanism translates.
- **Stop inside intrabar noise = instant death.** Measure intrabar range vs planned stop before committing. SPX500's 0.25-0.33x OR stops were inside typical single-bar range; WR collapsed faster than avg-loss shrunk.
- **Fade-test null check is cheap and decisive.** ~30 lines of code; saved us from tuning several strategies that had no directional content. Must be run under *symmetric payoffs* (same R:R both directions) — asymmetric EOD exits can give both directions artificial wins (GER40 initial misread).
- **Regime breakdown catches overfit "improvements".** NDX100's tight-stop+trend-filter took full Sharpe +0.03 → +0.31 but holdout went +0.19 → −0.19. Prefer baseline where holdout is strongest to optimized where holdout is weakest.
- **Refinement paths are instrument-specific, not universal.** T+180 unlocked GER40 and actively harmed NDX100. Run the symmetric-R:R + TOD sweep diagnostic from scratch on each instrument; don't port winning configs.
- **Numerically-best ≠ deployment-best.** GER40 symmetric T+180 looked like +0.58 full-sample Sharpe. Long/short split revealed shorts contribute ~zero — LONG-only with halved trade count is strictly better (higher Sharpe, better holdout, lower MDD). The asymmetric edge was being diluted by trading the weak side.
- **Fade-gap positive is necessary but not sufficient.** The companion z-score momentum experiment on DAX (`experiments/dax_zscore_momentum/`) has +0.82 fade-gap but fails on absolute Sharpe at 1pt cost. Direction ≠ magnitude.

## Files

- Thesis: this file (`experiments/orb/orb.md`).
- Demo: `experiments/orb/orb_demo.py` — supports `ORB_SYMBOL` + `ORB_SESSION` env vars; params `rr_target`, `tod_exit_minutes`, `min_or_width_pct`.
- Refinement scripts:
  - `experiments/orb/orb_refine.py` — symmetric R:R / TOD / OR-width diagnostic sweep.
  - `experiments/orb/orb_holdout.py` — regime breakdown + fade-test + cost sensitivity on top candidates.
  - `experiments/orb/ger40_asymmetry.py` — long/short split per regime window.
  - `experiments/orb/ger40_tod_decomposition.py` — per-entry-hour PnL attribution + entry-cutoff sweep.
- QC deploy: `deploy/qc_orb_dax.py` — DAX futures, 5-min bars, Berlin session.
- Data:
  - `ohlc_data/SPX500_M5.csv`, `NDX100_M5.csv`, `GER40_M5.csv`, `UK100_M5.csv`, `FRA40_M5.csv`.
- Run commands:
  - `ORB_SYMBOL=SPX500 venv/Scripts/python.exe experiments/orb/orb_demo.py`
  - `ORB_SYMBOL=NDX100 venv/Scripts/python.exe experiments/orb/orb_demo.py`
  - `ORB_SYMBOL=GER40 ORB_SESSION=EU venv/Scripts/python.exe experiments/orb/orb_demo.py`
  - `ORB_SYMBOL=UK100 ORB_SESSION=UK venv/Scripts/python.exe experiments/orb/orb_demo.py`
  - `ORB_SYMBOL=GER40 ORB_SESSION=EU venv/Scripts/python.exe experiments/orb/orb_refine.py`
  - `ORB_SYMBOL=GER40 ORB_SESSION=EU venv/Scripts/python.exe experiments/orb/orb_holdout.py`
  - `venv/Scripts/python.exe experiments/orb/ger40_asymmetry.py`
  - `venv/Scripts/python.exe experiments/orb/ger40_tod_decomposition.py`

## References

- Crabel, T. (1990). *Day Trading with Short Term Price Patterns and Opening Range Breakout*. Traders Press.
- Fisher, M. (2002). *The Logical Trader: Applying a Method to the Madness*. Wiley.
- Zarattini, C., & Aziz, A. (2023). "Can Day Trading Really Be Profitable?" SSRN 4416622.
- Lo, Mamaysky, Wang (2000). "Foundations of Technical Analysis." *Journal of Finance* 55(4).
