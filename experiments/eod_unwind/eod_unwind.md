# End-of-Day Leverage Unwind — cross-instrument (SPX500 / NDX100 / GER40 / UK100)

**Status**: Phase 2 complete across four US/EU cash-index CFDs on M5, 2019-2026 (run 2026-04-20).

**Verdict**:

| Instrument | Verdict | Baseline Sh | Holdout Sh | Fade-gap | EOD vs Overnight |
|---|---|---|---|---|---|
| SPX500 | **REJECT** | −0.85 | −1.90 | +0.46 | EOD wins (intraday-specific) |
| NDX100 | REJECT | +0.00 | −0.80 | +0.58 | EOD wins |
| GER40 | **REJECT (post-refine)** | +0.14 | +0.86 | +0.98 | EOD wins |
| UK100 | REJECT (confound) | −0.44 | −0.88 | +0.85 | **Overnight wins — signal is overnight drift, not unwind** |

**Headline finding**: The leverage-unwind thesis is **directionally correct on all four instruments** — fade systematically beats continuation by +0.46 to +0.98 Sharpe — but the absolute magnitude is too small to clear costs anywhere. The effect is a **real-but-too-small mechanism**: present on every instrument tested, tradeable on none. Final verdict post Phase 2b: tombstone across the full universe.

---

## Thesis (mechanism)

Retail and mid-size discretionary traders on leveraged products (CFDs, day-margin futures) avoid holding positions over the cash-session close because (a) overnight gap risk is asymmetric vs intraday noise, (b) day-margin on futures reverts to overnight initial-margin at settlement, tripling capital requirement, (c) CFD financing charges accrue on the daily snapshot. The aggregated effect on the last 30–60 minutes of the cash session:

1. **Forced-exit flow is directional with the day's move.** If the session ran up, day-traders' net book is long → they sell to close → supply into the last hour. Symmetric on down days.
2. **The flow is concentrated, not uniform.** Unlike MOC rebalance flow (which clusters at the 15:50-16:00 ET imbalance print and is information-free), the unwind is spread across ~T-60 to T-5 as participants manage exit slippage, and is *mechanical*, not belief-driven.
3. **Net prediction**: the last N minutes of the session should **fade** (mean-revert) the day's prior move, with effect size proportional to |session_open → T-Nmin| scaled by volatility.
4. **Overnight drift is a confound**: S&P 500 has well-documented positive close-to-open drift (Kelly & Clark 2011, Lou/Polk/Skouras 2019). If the mechanism is real, an overnight-hold variant entered at T-Nmin should show *lower* Sharpe than a close-of-session exit — because you'd be absorbing the overnight drift, which pushes back against the fade.
5. **Instruments with weaker retail leverage presence should show weaker effect.** DAX (heavy institutional/algo concentration, Xetra auction close at 17:30) should show less. SPX (massive retail MES/SPX CFD presence) should show more.

Effect sizes in literature: intraday mean-reversion on equity indices is typically noted as <0.1% per day (Bogousslavsky 2016, Heston/Korajczyk/Sadka 2010) — small gross but potentially tradeable at low cost.

## Key references

- **Heston, Korajczyk & Sadka (2010)**, "Intraday Patterns in the Cross-section of Stock Returns." *Journal of Finance* 65(4). Documents half-hour return autocorrelation patterns; reversal dominates at end-of-day on single names.
- **Bogousslavsky (2016)**, "Infrequent Rebalancing, Return Autocorrelation, and Seasonality." *Journal of Finance* 71(6). Models why rebalancing creates EOD reversal patterns.
- **Lou, Polk & Skouras (2019)**, "A Tug of War: Overnight Versus Intraday Expected Returns." *Journal of Financial Economics* 134(1). Overnight drift is persistent and large on SPX; intraday is zero-to-negative.

## Signal math

```
Parameters:
  ENTRY_MIN_BEFORE_CLOSE    = 45     (enter 45 min before RTH close)
  SIGNAL_ANCHOR             = "open" (measure day move from session open to entry bar close)
  MIN_MOVE_ATR              = 0.5    (require |day_move| >= 0.5 * ATR20d to enter)
  EXIT_MIN_BEFORE_CLOSE     = 5      (flat by T-5)
  COST_POINTS_ROUND_TRIP    = 1.0    (pessimistic retail CFD)
  DIRECTION                 = "fade" (baseline; "cont" is the null-check)

Per trading day (cash session):

  day_open = open of first RTH bar of the day
  entry_bar = first bar where mod >= rth_minutes - ENTRY_MIN_BEFORE_CLOSE
  day_move_px = close[entry_bar] - day_open
  atr = rolling 20-day ATR of daily close-to-close abs move (in price units)

  if |day_move_px| < MIN_MOVE_ATR * atr:  skip day
  if DIRECTION == "fade":
    position_sign = -sign(day_move_px)
  else:  # "cont" null-check
    position_sign = +sign(day_move_px)

  enter at next bar open
  exit: close of last pre-cutoff bar (T - EXIT_MIN_BEFORE_CLOSE)
  no intraday stop (optional variant: stop at 1.5 * bar ATR)

  Max 1 trade per day.
```

Variant families tested:

- **Entry timing**: 30 / 45 / 60 / 90 min before close.
- **Threshold**: MIN_MOVE_ATR ∈ {0.0, 0.25, 0.5, 1.0, 1.5}.
- **Exit**: EOD (session close) / T+15min after entry / T+30min / overnight-to-next-open.
- **Direction (null-check)**: fade (baseline) vs continuation (null).
- **Cost**: 0.5 / 1.0 / 2.0 / 3.0 pt RT.

## Why retail-accessible

- M5 CFD data, session-anchored times — fits the existing MT5/QC deployment pipeline.
- Trade cadence: 1 per day maximum → ~200 per year on a daily-frequency instrument, ~5/week. Slow enough to be robust to execution slippage.
- Entry 30-90 min before close means no MOC-auction execution risk; fills on regular continuous-session quotes.

## Universe

- **Phase 2 (primary)**: SPX500 M5, 2019-01-02 → 2026-04-18, RTH 09:30-16:00 ET.
- **Phase 3 (cross-instrument)**: NDX100, GER40, UK100, FRA40 — apply the same session-agnostic framework. FRA40 data-coverage issue noted in orb.md (may repeat here).

## Expected performance (at thesis time)

Literature & prior-work benchmarks:
- Heston et al. (2010) reported EOD reversal t-stats ~3-5 on single names, economic magnitude ~5-10bps per trade gross.
- Intraday index-futures EOD studies (unpublished): typical Sharpe +0.2-0.5 gross on S&P futures 2000-2015, degrading to near-zero 2015-2020.
- CFD cost drag: 1pt RT on SPX500 ≈ 2.5bps at 4000 level; 5bps at 2000 level; 1.8bps at 5500 level. Roughly equal to or larger than expected per-trade edge → cost-marginal strategy.

**Expected retail-net after 1pt RT cost**: Sharpe +0.10 to +0.40 on SPX500. 3-5 trades/week (depending on threshold). MDD 10-20%. WR 50-55% with slight positive skew (mean-reversion payoff shape). Borderline-deployable even in success case — the interesting finding will be the *null-check result* and the *overnight-hold comparison*.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200 over 7 years.
- WR < 48% AND PF < 1.05 (mean-reversion strategies should have WR > PF symmetric).
- **Null-check fade-gap < +0.30** (i.e., fade Sharpe minus continuation Sharpe must exceed +0.30 — if both win similarly, signal has no directional content; if continuation wins, thesis is inverted).

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows (2019-2020 / 2021-2022 / 2023-2026).

Phase 6 kills if 2023-2026 holdout Sharpe ≤ 0.

**Overnight-confound check**: if overnight-hold-from-T-Nmin has *higher* Sharpe than close-of-session exit, we're mostly capturing overnight drift, not the unwind mechanism — downgrade confidence even if the absolute numbers are acceptable.

## Why this might fail (red flags)

1. **Mechanism may have decayed post-2020**. Retail leverage is now dominated by 0DTE options, not day-margined futures/CFDs, which changes the unwind dynamic (0DTE flow hedges *into* the close by dealers, not out of it).
2. **Lou/Polk/Skouras overnight-drift effect** directly opposes the fade thesis. Late-session weakness on up-days is offset (or reversed) by overnight strength.
3. **Cost sensitivity is severe** for a small-effect intraday mean-reversion trade. 1pt RT is likely to eat most of the edge.
4. **MOC imbalance regime** post-2015: close-auction liquidity is now so large that residual continuous-session flow pre-close has less impact than it did in the 1990s-2000s literature.
5. **Threshold overfitting** — picking MIN_MOVE_ATR on the basis of best-Sharpe across a grid is precisely the kind of curve-fit that fails out-of-sample. Default threshold 0.5σ was picked before running.

## Phase 1 → Phase 2 plan

- [x] Spec thesis doc with pre-committed fail conditions (this file).
- [x] Implement session-agnostic `simulate_eod_unwind()` with numpy inner loop.
- [x] Run baseline + entry-timing sweep on SPX500.
- [x] Run threshold sweep.
- [x] Run exit-variant sweep (EOD / T+15 / T+30 / overnight).
- [x] Run cost-sensitivity sweep.
- [x] Run regime breakdown.
- [x] Run null-check (continuation direction).
- [x] Port to NDX100 / GER40 / UK100 under same framework (ran despite SPX500 REJECT — negative result on one instrument doesn't falsify cross-instrument thesis).
- [x] Update this doc with tables + verdict.

## Phase 2 results — by instrument

### SPX500 — REJECT

M5, RTH 09:30-16:00 ET, 146,054 bars, 1,884 trading days.

**Baseline (fade, entry=T-45min, thr=0.5×ATR, EOD exit, cost=1pt)**:

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | −0.85 | FAIL |
| Max DD | −19.85% | PASS |
| Trades | 992 (2.62/wk) | PASS |
| WR / PF | 41.2% / 0.79 | FAIL |
| Avg win / loss | +0.173% / −0.154% | — |

**Regime breakdown**: +0.08 / −0.64 / **−1.90** (holdout is worst of all). **Monotonic decay 2019 → 2026.**

**Entry-timing sweep**: T-30 −1.44, T-45 −0.85, T-60 −0.73, T-90 −0.76. No window works.

**Threshold sweep**: thr=0.0 −1.39, thr=1.5 −0.51. Higher thresholds improve Sharpe but remain negative. Not a noise problem.

**Exit sweep**: EOD −0.85, T+15 −1.12, T+30 −1.07, Overnight −1.01. All losing. EOD is best, confirming (a) the mechanism sign is intraday-specific not overnight, (b) the fade just loses less when held shorter.

**Cost sweep**: even at 0.5pt, Sharpe is −0.31. Not a cost issue — **gross signal is negative**.

**Null-check**: continuation Sharpe −1.31, fade-gap **+0.46**. Directional content exists (fade loses less than continuation) but both directions lose decisively in absolute terms. The fade-gap + negative baseline is the signature of a **real but too-weak-to-trade** signal being drowned by costs and noise on SPX.

**Why the thesis fails on SPX specifically (mechanistic read)**:

1. **0DTE option flow dominates SPX since 2021-2022.** Post-2022 SPX has the largest 0DTE-options presence of any index. Dealer hedging into the close pushes the *opposite* direction of the unwind flow (delta-neutral dealer hedging a long-gamma book buys weakness and sells strength, but on 0DTEs dealer gamma is net short → amplifies trend into close). This opposes the retail unwind.
2. **Retail SPX leverage is now predominantly 0DTE options, not day-margined MES.** 0DTE expiry-at-4pm means the "unwind" is automatic and priced-in by the market-making desk via gamma pinning, not a supply/demand pulse.
3. **Holdout 2023-2026 is the worst regime** (Sharpe −1.90, vs +0.08 in 2019-2020). Consistent with the 0DTE hypothesis — the mechanism was weakly present pre-2022 and has inverted since.

**3 of 4 hard kills fail. REJECT, tombstone on SPX500.**

### NDX100 — REJECT (marginal, holdout negative)

Baseline Sharpe +0.00, holdout −0.80, fade-gap +0.58. Threshold sweep peaks at thr=0.0 (Sh +0.25, 1848 trades), inverting on higher thresholds — opposite of the expected shape (real signals strengthen with threshold, noise-trading flattens). The +0.25 at thr=0.0 is suspicious; it coincides with 2019-2022 edge that holdout (Sh −0.80) flatly contradicts. **REJECT.** Same 0DTE hypothesis applies — NDX100 0DTE activity rose alongside SPX.

### GER40 — REJECT post-refine (Phase 2b tombstone)

Baseline Sharpe +0.14, **holdout +0.86**, fade-gap **+0.98** (strongest of the four).

| Metric | Value |
|---|---|
| Full Sharpe | +0.14 |
| Holdout 2023-2026 Sharpe | **+0.86** |
| MDD | −5.19% |
| Trades | 990 (2.61/wk) |
| WR / PF | 50.6% / 1.04 |

**Regime breakdown**: −0.41 / −0.21 / **+0.86**. All the edge is post-2023 — opposite of the decay pattern on SPX/NDX. Mechanism appears to have *strengthened* on DAX.

**Threshold sweep**: thr=0.0 −0.07, thr=0.25 +0.10, thr=0.5 +0.14, thr=1.0 +0.22, thr=1.5 +0.06. Clean curve — rises with threshold to thr=1.0 then noise. Signature of a real effect concentrated in large-move days.

**Cost headroom**: 0.5pt +0.32, 1.0pt +0.14, 2.0pt −0.20. Marginal even at broker-typical 0.5pt.

**Phase 2 first look**: full-sample Sh +0.14, holdout +0.86, fade-gap +0.98 — looked like a Phase 2b refinement candidate (long/short asymmetry + regime × threshold grid).

**Phase 2b refinement results (ran 2026-04-20)**:

**(i) Long/short asymmetry — falsified.**

| thr | LONG Sh | SHORT Sh | note |
|---|---|---|---|
| 0.25 | +0.05 | +0.10 | SHORT slightly stronger |
| 0.5 | +0.02 | +0.20 | SHORT notably stronger |
| 1.0 | +0.19 | +0.11 | LONG stronger |
| 1.5 | +0.28 | −0.28 | LONG flip |

No stable asymmetry across thresholds — direction-dominance flips from SHORT (thr≤0.5) to LONG (thr≥1.0). That's the signature of noise, not a secular-drift-driven structural tilt.

**(ii) Regime split on all key candidates (T-45, EOD, cost=1pt)**:

| Config | 2019-2020 | 2021-2022 | 2023-2026 HO | 2/3 positive? |
|---|---|---|---|---|
| both, thr=0.5 (baseline) | −0.41 | −0.21 | **+0.86** | NO (1/3) |
| LONG, thr=0.5 | −0.97 | +0.68 | +0.25 | YES (2/3) |
| SHORT, thr=0.5 | +0.39 | −1.11 | +1.05 | YES (2/3) |
| both, thr=1.0 | +0.16 | −0.38 | +0.70 | YES (2/3) |
| LONG, thr=1.0 | −0.04 | +0.23 | +0.31 | YES (2/3) |
| SHORT, thr=1.0 | +0.26 | −0.84 | +0.77 | YES (2/3) |

Baseline config passes only 1 of 3 regimes (the holdout). The +0.86 holdout is a regime-specific artifact, not a stable property. The LONG-only + SHORT-only candidates each reach 2/3 regimes positive but with *different* weak windows — LONG flunks 2019-2020 (−0.97), SHORT flunks 2021-2022 (−1.11). That's not evidence of a robust directional edge; it's evidence of alternating sign-flip between regimes.

**(iii) Entry × threshold grid (LONG-only)** — best cell T-60 thr=1.5 Sh +0.43, but only ~110 trades over 7.3y (0.3/wk, fails trade-cadence). One positive cell out of 12 is within combinatorial-noise for a +0.14 baseline mechanism.

**(iv) Honesty benchmark — "long every day T-45 → close"**: Sharpe −0.61 full (regime −1.12 / +0.46 / −0.98). The final-45-min window on DAX has systematic *negative* drift — the fade-LONG strategy's alpha vs this passive benchmark is +0.6 Sharpe, but the benchmark is so negative that the fade-LONG still nets to only +0.02. The mechanism is adding value; the value is not enough to overcome the regime of the final 45-min slice.

**(v) Cost sensitivity — LONG, thr=1.0**: 0.5pt +0.26, 1.0pt +0.19, 2.0pt +0.05. Holdout-only: 0.5pt +0.37, 1.0pt +0.31, 2.0pt +0.20. If (a big if) the holdout-only result were the forward expectation, it would clear +0.30 at broker-realistic cost. But committing to that requires believing the regime shift is stable and not mean-reverting — and the 2019-2020 LONG Sharpe −0.04 argues it isn't.

**Final verdict: REJECT.** Under honest single-rule discipline (one pre-committed config with ≥2/3 regime support), the best candidate is LONG-only thr=1.0 with full-sample +0.19 and 2/3 regimes barely positive (2019-2020 at −0.04). Below the +0.30 bar. The pattern of alternating weak-regimes between LONG and SHORT variants is a cleaner tell than the top-line numbers: if the mechanism were structural, one direction would dominate consistently; instead each direction has a different dud regime, which is the signature of a mechanism with effect-size smaller than the regime-to-regime noise floor.

**Lesson captured**: "holdout is best" + "fade-gap > +0.9" + "EOD wins vs overnight" is *three* strong indicators that a real mechanism is present. All three can be true and the strategy can still fail the regime-robustness bar. Directional content ≠ tradeable edge; the orb.md version of this lesson is re-confirmed here.

### UK100 — REJECT (overnight confound)

Baseline Sharpe −0.44, holdout −0.88, fade-gap +0.85 — directional content present. **But overnight variant Sharpe +0.44 > EOD −0.44** (gap +0.88 favoring overnight). This means the fade signal, when carried overnight, captures the overnight-reversion on FTSE 100 (which is the mirror of the US overnight-drift effect — FTSE has historically had *negative* overnight drift due to commodity-sector adverse selection during Asian hours). The "unwind" interpretation is wrong; it's an overnight-drift capture in disguise. Not the mechanism we're after. **REJECT.**

---

## Cross-instrument mechanistic interpretation

| Instrument | Fade-gap | Holdout Sh | Overnight confound? | Dominant mechanism |
|---|---|---|---|---|
| SPX500 | +0.46 | −1.90 | No (EOD wins) | 0DTE gamma overrides retail unwind post-2022 |
| NDX100 | +0.58 | −0.80 | No (EOD wins) | Same — 0DTE-on-QQQ/NDX adoption |
| GER40 | +0.98 | +0.86 full / fails post-refine | No (EOD wins) | Retail unwind visible but effect-size < regime-noise floor |
| UK100 | +0.85 | −0.88 | **Yes (overnight wins)** | Overnight commodity reversion, not intraday unwind |

**Key insights**:

1. **The leverage-unwind thesis is mechanistically real but small** — fade-gap positive on 4/4 instruments with magnitudes +0.46 to +0.98. 
2. **Absolute tradability is dominated by two structural confounds** not in the original thesis:
   - **0DTE options ecosystem** (SPX/NDX): dealer hedging in the final hour has become the dominant intraday flow post-2022, and it opposes the retail-unwind sign.
   - **Overnight drift sign** (SPX/NDX positive, UK100 negative): determines whether the fade and overnight flow compound or conflict, and whether a UK-style "overnight win" is a mechanism confirmation or a confounder.
3. **GER40 is the cleanest test** of the raw unwind mechanism because it has (a) no 0DTE-DAX, (b) mild secular drift rather than a strong overnight effect, (c) a distinct Xetra cash-close auction at 17:30 that concentrates closing liquidity. The holdout-only +0.86 Sharpe and monotonic threshold response are consistent with the unwind mechanism being genuinely present on DAX and strengthening post-2023.
4. **SPX-specifically**: the original instrument is the *worst* case. Any revival of this thesis on SPX would need to explicitly model the 0DTE gamma regime and likely condition on it (e.g., only trade on low-0DTE-OI days) — outside this repo's scope without additional options data.

---

## Follow-up work (if revisited)

- ~~**GER40 Phase 2b refinement pass**~~ — COMPLETE 2026-04-20, results above. REJECT.
- **0DTE-conditional SPX variant**: gate entries on a 0DTE-OI proxy (e.g., recent VIX-term-structure shape, or days with small realised vs expected close-imbalance). Requires external data. Only worth doing if options data becomes available.
- **ES/NQ futures variant**: futures close at 17:00 ET (cash close) then reopen 17:00 continuation — the "unwind" mechanism in the cash-close-to-globex-open window might be cleaner than on CFDs because the futures close is itself an auction event. Would need CME futures data outside current repo.

## Files

- Thesis: this file (`experiments/eod_unwind/eod_unwind.md`).
- Demo: `experiments/eod_unwind/eod_unwind_demo.py` — env-var-driven cross-instrument Phase 2 runner.
- Refinement: `experiments/eod_unwind/eod_unwind_ger40_asymmetry.py` — GER40 long/short split + regime × threshold grid + entry × threshold grid + honesty benchmark.

## Files

- Thesis: this file (`experiments/eod_unwind/eod_unwind.md`).
- Demo: `experiments/eod_unwind/eod_unwind_demo.py` — supports `EOD_SYMBOL` + `EOD_SESSION` env vars; params `entry_min_before_close`, `min_move_atr`, `exit_mode`, `direction`.
- Data:
  - `ohlc_data/SPX500_M5.csv` (primary), `NDX100_M5.csv`, `GER40_M5.csv`, `UK100_M5.csv`, `FRA40_M5.csv`.
- Run commands:
  - `EOD_SYMBOL=SPX500 venv/Scripts/python.exe experiments/eod_unwind/eod_unwind_demo.py`
  - `EOD_SYMBOL=NDX100 venv/Scripts/python.exe experiments/eod_unwind/eod_unwind_demo.py`
  - `EOD_SYMBOL=GER40 EOD_SESSION=EU venv/Scripts/python.exe experiments/eod_unwind/eod_unwind_demo.py`
  - `EOD_SYMBOL=UK100 EOD_SESSION=UK venv/Scripts/python.exe experiments/eod_unwind/eod_unwind_demo.py`
