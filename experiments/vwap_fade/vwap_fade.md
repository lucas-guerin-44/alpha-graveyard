# Late-Session VWAP Fade — SPX500 / NDX100 (US session)

**Status**: Phase 2 complete 2026-05-13.

**Verdict**: **REJECT — thesis sign inverted on NDX, signal absent on SPX**.

| Symbol | Baseline Sh (fade) | Null Sh (cont) | Dir-gap | Holdout Sh | MDD | Trades |
|---|---|---|---|---|---|---|
| SPX500 | −0.77 | −0.62 | −0.15 | −1.41 | −26.0% | 940 |
| NDX100 | −0.51 | **+0.13** | **−0.64** | −1.27 | −25.6% | 1,004 |

Three lines of evidence against the thesis:

1. **Sign inversion on NDX**: continuation (the null direction) wins by +0.64 Sharpe vs fade. The TWAP-deviation signal carries directional content, but in the *opposite* direction — late-session deviations from session-mean tend to **extend**, not revert.
2. **Holdout is the WORST regime** on both instruments (SPX -1.41, NDX -1.27 in 2023-2026 vs 0.06/0.06 in 2019-2020). Mechanism has decayed monotonically through the sample — consistent with 0DTE-options-era trend-amplification displacing the older "VWAP magnet" microstructure.
3. **SPX is pure noise** (dir-gap -0.15) — same shape as SPX pre-close drift; both directions lose without informational content. SPX's multi-venue diffuse session-end execution doesn't produce a clean directional signal at M5.

**Mechanistic interpretation**: the thesis assumed institutional VWAP-benchmarked execution + MOC pre-positioning drags price back to session-average in the last 60-90 min. Empirically the opposite holds at retail M5 granularity on US indices:

- Late-session trend-day continuation dominates the mean-reversion effect.
- 0DTE-options gamma flow has rewired late-session microstructure post-2022 toward trend-amplification rather than mean-reversion.
- The lunch-fade window (11:30-13:30 ET) is genuinely structurally different — fresh institutional flow has *paused*, leaving HFT inventory rebalancing dominant (mean-reverting). By 14:30, institutional flow returns and re-establishes directional pressure into the close.

The 0DTE-amplification hypothesis is the strongest single explanation: holdout Sharpe collapse from +0.06 (pre-COVID) to -1.41/-1.27 (post-2022) tracks the 0DTE volume explosion almost monotonically.

---

---

## Thesis (mechanism)

In the last 60-90 minutes of US RTH (14:30-16:00 ET), institutional execution algorithms with VWAP benchmarks dominate the tape:

1. **VWAP-benchmarked execution algos**. Pension funds, mutual fund cash-flow trades, and ETF creation/redemption baskets are routed through broker execution desks against a VWAP benchmark — i.e., the desk is rewarded if it transacts at or better than session VWAP. When price runs significantly *above* VWAP, the desk has a fill-the-rest-cheaper bias (sells into the bid); when price is significantly *below* VWAP, desks targeting buy-side baskets bid more aggressively. Net: cross-flow biases price back toward VWAP.
2. **MOC / LOC pre-positioning**. Closing-cross orders that will print at 16:00 ET typically have associated pre-hedging in the 15:30-15:55 window. Imbalance-chasers and dealers route this flow against the prevailing intraday move — also VWAP-relative.
3. **0DTE-options pin/de-pin dynamics**. Late-session 0DTE positions resolve into the close; large gamma exposure at near-the-money strikes tends to magnetize price toward those strikes, which themselves cluster around session VWAP / session mid.
4. **Net prediction**: a price that is significantly above or below session VWAP at 14:30-15:00 ET will mean-revert toward VWAP into the 15:55 close.

Distinct from the lunch-fade thesis (`experiments/lunch_fade/`):
- **Lunch fade** times: 11:30 → 13:30 ET, fades morning-overshoot during structural lull. Mechanism: NY/Chicago lunch + EU close = liquidity vacuum.
- **VWAP fade** times: 14:30/15:00 → 15:55 ET, fades session-overshoot during MOC-algo dominance. Mechanism: VWAP-benchmarked execution + closing-cross pre-hedging.

Same family (time-of-day structural mean-reversion on US indices) but different sub-mechanism, different time window, different filter. Combined book runs lunch-fade through midday and VWAP-fade into close — non-overlapping sessions, plausibly low correlation.

## Key references

- **Berkowitz, Logue, Noser (1988)**, "The total cost of transactions on the NYSE." *Journal of Finance* 43(1). Establishes the VWAP benchmark as the standard execution-quality metric for institutional desks.
- **Bessembinder, Panayides, Venkataraman (2009)**, "Hidden liquidity: An analysis of order exposure strategies in electronic stock markets." *Journal of Financial Economics* 94(3). Late-session order-routing and hidden-liquidity behavior.
- **Bogousslavsky & Muravyev (2023)**, "Who Trades at the Close?" Closing auction volume has tripled since 2010; institutional VWAP/MOC dominance has correspondingly grown.
- **Hu, Pan, Wang (2017)**, "Early Peek Advantage." Documents end-of-session price reversal patterns on macro-news days.

## Signal math

```
Parameters:
  ENTRY_MIN_OF_SESSION      = 300   (enter at first bar with mod >= 300, = 14:30 ET)
  EXIT_MIN_OF_SESSION       = 385   (exit at last bar; 09:30 + 385 min = 15:55 ET close-bar)
  MIN_DEV_ATR               = 0.5   (threshold = MIN_DEV_ATR * ATR_M5_proxy * sqrt(elapsed_bars))
  COST_POINTS_ROUND_TRIP    = 1.0
  ATR_LOOKBACK_DAYS         = 20

Per trading day (US/Eastern RTH 09:30-16:00):
  elapsed_bars  = entry_bar - session_open_bar   # bars from 09:30 to entry
  vwap_t        = sum_{i=0..entry_bar}(typical_price_i * volume_i) / sum(volume_i)
                  where typical_price = (H + L + C) / 3
                  and volume is bar tick-volume (CFD proxy — true volume not available)
  dev_pct       = (close[entry_bar] - vwap_t) / vwap_t

  atr_m5        = trailing-20-day mean of single-bar |return|
  threshold     = MIN_DEV_ATR * atr_m5 * sqrt(elapsed_bars)

  if |dev_pct| < threshold:  skip day
  pos           = -sign(dev_pct)                          (fade)
  enter at next-bar open (mod = ENTRY_MIN_OF_SESSION + 5)
  exit at last bar (mod = EXIT_MIN_OF_SESSION) close

  Max 1 trade per day. Flat overnight.
```

Note on the "VWAP" implementation: the local CSV cache holds OHLC only — no volume column. Phase 2 uses **TWAP** (time-weighted average price = equal-weighted bar mean of typical price) as the VWAP proxy. The institutional flow above benchmarks against true VWAP, but TWAP and VWAP are highly correlated on liquid index CFDs because each M5 bar represents the same elapsed time. Refining with real tick-volume is a Phase 2b step *if* TWAP passes Phase 2 — pulling fresh data with the volume column requires re-running `scripts/mt5_fetch.py --symbols SPX500,NDX100 --timeframes M5`.

Variants: ENTRY ∈ {240, 270, 300, 330, 360}, MIN_DEV ∈ {0.0, 0.25, 0.5, 0.75, 1.0, 1.5}, cost ∈ {0.5, 1, 2, 3}pt. Null-check: continuation (flip sign).

## Universe

- **SPX500** CFD on MT5, M5 bars, 2019-01-02 → 2026-04-17. Broad NYSE/Nasdaq blue-chip basket — VWAP-execution flow concentrates here because it's the institutional-benchmark index.
- **NDX100** CFD on MT5, same range. Tech-heavy. Strong 0DTE-on-QQQ tie-in supports the gamma-pin sub-mechanism.

## Expected performance

Literature on VWAP-deviation reversion (single-stock, intraday): 5-15 bps gross mean-reversion over a 60-90min hold on overdone days. Filtered to outlier-deviation days only, gross effect should be 10-30 bps per trade. With 1pt RT (~2.5 bps on SPX, ~2 bps on NDX) and ~80-150 trades/yr expected post-filter, net Sharpe target 0.30-0.70. MDD target 6-12%.

**Target trade cadence**: 80-150 trades/year (~1.5-3 per week). Higher cadence than lunch-fade but still selective.

## Fail conditions (pre-committed)

Phase 2 kills if ANY:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 200 over 7 years.
- WR < 50% OR PF < 1.05 (mean-reversion expects > 50% WR).
- **Null-check direction-gap < +0.30** (fade Sharpe − continuation Sharpe must exceed +0.30).

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows (2019-2020 / 2021-2022 / 2023-2026).
Phase 6 kills if 2023-2026 holdout Sharpe ≤ 0.

## Why this might fail (red flags)

1. **CFD tick-volume ≠ real volume**. VWAP-proxy from tick-volume may diverge from the actual VWAP that institutional desks benchmark against. If the proxy is too noisy, the deviation signal won't reflect the real over/undershoot.
2. **Trend-day persistence**. On strong macro-news afternoons (Powell speech, big earnings, geopolitical headline), price extends *away* from VWAP rather than reverting. Threshold filter must catch these — but if it doesn't, large losing trades dominate.
3. **0DTE has rewired late-session microstructure**. Post-2022 0DTE gamma flow can produce *trend-amplifying* moves into the close on some days (the "Volmageddon" pattern at 0DTE timescale). The mechanism may be regime-dependent on which way 0DTE positioning is leaning.
4. **Overlap with lunch fade**. If lunch-fade already captured the morning-overshoot reversion, by 14:30 ET the "easy" reversion is gone and what's left in the 14:30-15:55 window is genuine end-of-day trend.
5. **Friction-vs-magnitude binding**. If per-trade gross is < 15 bps and CFD cost is 2-3 bps, the friction:edge ratio is too high to survive — similar problem to the pre-close MOC drift we just tombstoned.

## Phase 1 → 2 plan

- [x] Thesis written
- [x] SPX500 baseline + sweeps + regime breakdown + cost + null-check
- [x] NDX100 same battery
- [x] Cross-instrument verdict (REJECT both; NDX sign-inverted)
- [x] Long/short asymmetry split (no asymmetry rescues either side)
- [x] Mechanistic interpretation (0DTE-amplification + post-lunch institutional return)
- [N/A] Correlation check vs deployed book (skip — strategy not deployable)

## Threshold-sweep detail

| thr | SPX Sh | NDX Sh | SPX trades | NDX trades |
|---|---|---|---|---|
| 0.00 | −1.50 | −0.56 | 1,878 | 1,880 |
| 0.25 | −1.23 | −0.37 | 1,373 | 1,417 |
| 0.50 | −0.77 | −0.51 | 940 | 1,004 |
| 0.75 | −0.44 | −0.38 | 631 | 687 |
| 1.00 | −0.27 | −0.14 | 411 | 447 |
| **1.50** | **+0.13** | **+0.23** | **191** | **185** |

The thr=1.50 cells flip positive but sit just *below* the 200-trade Phase 2 floor on both instruments, with sample size insufficient for a meaningful Sharpe estimate (n≈185 → SE ≈ 0.45). Selection on "only the highest-conviction days" is the same overfit signature that killed the pre-close MOC drift at high thresholds — discount.

## Cost sensitivity (baseline thr=0.5)

| Cost RT | SPX Sh | NDX Sh |
|---|---|---|
| 0.5pt | −0.42 | −0.41 |
| 1.0pt | −0.77 | −0.51 |
| 2.0pt | −1.45 | −0.70 |
| 3.0pt | −2.12 | −0.89 |

Cost-zero extrapolation: SPX ≈ -0.07 (≈ flat), NDX ≈ -0.31 (negative gross). Even at zero friction the strategy doesn't make money — this is not a "good signal eaten by cost" pattern, it's "signal in the wrong direction" on NDX and "no signal at all" on SPX.

## Lessons captured

- **Sign-inversion as a structural finding, not a bug.** Three independent fade-thesis attempts on retail-M5 indices have now sign-inverted: DAX gap fade (continuation +0.12 / fade -1.04), DAX US-lead (continuation -0.07 / fade -0.48), VWAP fade NDX (continuation +0.13 / fade -0.51). The mean-reversion-to-some-reference thesis is consistently wrong on US/EU index M5 CFDs.
- **Lunch fade is a structural exception, not a generic rule.** The 11:30-13:30 ET window's working mean-reversion (Sh +1.02 LONG-only) cannot be generalised to "late session" or "session deviation" frameworks. Specifically the *liquidity-vacuum* mechanism (NY/Chicago lunch + EU close simultaneously) is what creates the reversion-favouring regime; other time-of-day slots that lack this confluence trend instead of revert.
- **Holdout decay is the smoking gun of regime-driven mean-reversion theses.** When 2023-2026 is the WORST regime (this thesis: SPX -1.41 vs +0.06; NDX -1.27 vs +0.06), the post-2022 microstructure has actively destroyed the edge. 0DTE-options gamma flow is the leading explanation given its tripling of volume in the same window.
- **TWAP/VWAP proxy was not the binding issue.** The sign inversion is large enough (-0.64 dir-gap on NDX) that no plausible volume-weighted refinement would flip the verdict back to "fade works." Refining the VWAP computation with real tick-volume is now moot.

## Why this differs from the lunch-fade PASS

Same author wrote both theses on the same week. Same instrument family (SPX500/NDX100). Same general "fade overshoot" intuition. Lunch-fade works (Sh +0.89 / dir-gap +1.87 / holdout-best); VWAP-fade fails inverted. The difference is specifically:

| Feature | Lunch fade (PASS) | VWAP fade (REJECT) |
|---|---|---|
| Time window | 11:30 → 13:30 ET | 14:30 → 15:55 ET |
| Liquidity context | NY+Chicago lunch + EU close = vacuum | MOC algos + 0DTE gamma + institutional return |
| Signal | Morning move magnitude | Deviation from session TWAP |
| Mechanism predicted | HFT inventory rebalance → mean revert | VWAP-target algo flow → mean revert |
| Mechanism observed | ✓ mean revert | ✗ trend continuation |

**The lunch window is uniquely depleted of fresh directional flow.** By 14:30, US institutional desks are back from lunch and 0DTE positioning is resolving into the close — both forces extend price in the prevailing direction. The "VWAP magnet" intuition borrowed from intraday equity execution literature doesn't survive contact with the 0DTE-amplified post-2022 microstructure at retail-M5 granularity.

---

## Files

- Thesis: this file.
- Demo: `experiments/vwap_fade/vwap_fade_demo.py` — env-var `VWAP_SYMBOL` (default SPX500). Baseline + entry / threshold / cost sweeps + regime breakdown + null-check + long/short split.
- Data: `ohlc_data/SPX500_M5.csv`, `ohlc_data/NDX100_M5.csv` (already on disk).
- Run commands:
  - `venv/Scripts/python.exe experiments/vwap_fade/vwap_fade_demo.py`
  - `VWAP_SYMBOL=NDX100 venv/Scripts/python.exe experiments/vwap_fade/vwap_fade_demo.py`
