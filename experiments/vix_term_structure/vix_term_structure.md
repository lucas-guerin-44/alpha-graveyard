# VIX Term-Structure Roll (short-vol VRP)

**Status**: REJECTED at Phase 2
**Verdict**: REJECT — full-sample Sharpe 0.31, 2024-2026 sub-window Sharpe -0.19. Neither the baseline nor the fix cleared the pre-committed bars. Post-2022 vol compression appears to be a structural regime shift, not a blip.

## Thesis (mechanism)

The VIX futures curve is in contango ~75-80% of the time: VX futures trade above spot VIX because option sellers demand a premium for bearing gap-risk. A short position in front-month VX futures (or the VXX ETN that tracks a constant-maturity 1M VX blend) captures this **variance risk premium (VRP)** as the future rolls toward spot. In backwardation, the roll flips against the short, so the strategy must flatten or flip based on curve state.

Signal: `ts_ratio = VIX / VIX3M` (or `VX1 / VX2` once we wire futures).
- `ts_ratio < 1` → contango → short vol (long SVXY or short VXX proxy)
- `ts_ratio > 1` → backwardation → flat (or long VXX, but asymmetry of upside tails argues for flat)

## Why retail-accessible

VRP is the canonical "insurance premium" trade. It's *not* inefficient — it's compensation for tail risk. Retail can access it because:
1. ETP wrappers (VXX, SVXY, UVXY) are liquid and regulation-friendly.
2. The tail risk that institutional vol sellers hedge with OTC variance swaps doesn't have a clean retail analog, so most retail short-vol is naked — which keeps the premium wide.
3. Post-Feb-2018 "Volmageddon" (XIV blowup, SVXY re-leveraged 1x → 0.5x), capacity at retail scale rebuilt but hasn't fully competed the premium away.

## Universe & timeframe

- Instrument set: `^VIX` (spot), `^VIX3M` (3-month constant maturity), `VXX` (1M VX ETN, short proxy), `SVXY` (inverse 0.5x VXX, long proxy for short vol).
- All daily bars via `scripts/yahoo_fetch.py`.
- Period: 2015-01 to 2026-04 (full period matches other strategies; note SVXY re-leveraged Feb-2018 so pre-/post-split behavior differs).

## Signal math

```
ts_ratio[t] = VIX[t] / VIX3M[t]

if ts_ratio[t] < threshold_contango (e.g. 0.95):
    target = long SVXY  (short-vol exposure)
elif ts_ratio[t] > threshold_backwardation (e.g. 1.00):
    target = flat
else:
    target = prior position  (hysteresis band)

position sizing: vol-target 15% annualized on the SVXY leg, capped at 1.0x gross
rebalance: daily check, only act when regime changes
```

Params to explore later (Phase 5):
- `threshold_contango` ∈ [0.90, 1.00]
- `threshold_backwardation` ∈ [1.00, 1.10]
- smoothing: raw ratio vs 3-day / 5-day average
- vol-target lookback: 20 vs 60 days

## Expected Sharpe range

Literature on VRP strategies:
- Naked short-vol (no regime filter) 2004-2017: Sharpe 1.2-1.5, annihilated Feb-2018.
- Regime-filtered (flat in backwardation): Sharpe 0.7-1.0 post-2012 (various vendors — Simplify, ProShares whitepapers).
- Realistic retail expectation 2015-2026 with 15% vol target and ETP slippage: **Sharpe 0.4-0.7**, max DD 25-35% assuming the filter fires in time. Without the filter, Feb-2018 is a full wipeout.

Expected correlation vs XS-mom: **mildly negative to mildly positive**. Short-vol pays during calm uptrends (when XS-mom also works) but crashes during vol spikes (when XS-mom often does fine because it's slow). Net corr estimate: -0.1 to +0.2. This is the diversification case.

## Fail conditions (pre-committed)

Phase 2 kills if:
- Full-sample Sharpe < 0.3 with the contango filter active.
- Max DD > 40% despite the filter (means filter is too slow).
- Single-day loss > 15% ever in the series (Feb-5-2018 alone was -96% for naked XIV holders; SVXY survived at ~-80%).

Phase 4 kills if:
- Regime-split shows one window dominates > 80% of return. The 2017 calm year is a real risk here.

Phase 6 kills if:
- OOS 2023+ Sharpe ≤ 0. Post-2022 vol regime has been structurally different (persistent ~15-20 VIX range), filter may be too restrictive.

## Reasons for prior skepticism (user-flagged)

User's gut: "don't believe much in VRP." Legitimate concerns:
1. **Negative skew that doesn't show up in Sharpe.** A 0.6 Sharpe with a single -30% day is not the same as a 0.6 Sharpe from equities — even if the math is identical. Calmar and worst-day matter more here than elsewhere.
2. **Feb-2018 is in-sample.** If the filter "catches" Volmageddon in backtest, it's probably because we designed the filter after knowing Feb-5 happened. Phase 6 holdout (2023+) is where we find out if the filter actually generalizes.
3. **Post-2022 vol compression.** With VIX stuck 13-18 for ~2 years, the roll premium has thinned. Could already be arb'd out for retail size.

These concerns go into the fail-condition list rather than stopping the experiment. The point of the pipeline is to let data kill the thesis cheaply.

## Phase 2 — initial run (baseline params)

Ran `experiments/vix_term_structure/vix_term_structure_demo.py` with the baseline setup described above:
contango entry 0.95, backwardation exit 1.00, daily vol-target rebalance, 15bps/side cost.

### Kill-criteria scorecard
All four Phase 2 kill criteria technically PASS — but only barely:

| Criterion | Actual | Status |
|---|---|---|
| Sharpe > 0.30 | +0.30 | PASS (at threshold) |
| Max DD < 40% | -32.93% | PASS |
| Worst single day > -15% | -7.48% | PASS |
| Trades >= 50 | 2,496 | PASS (too many — see below) |

### Regime-split (the real story)

| Window | Sharpe | Return | Max DD |
|---|---|---|---|
| 2015-2017 (calm) | +1.14 | +55.5% | -14.7% |
| 2018 (Volmageddon year) | -1.28 | -18.6% | -20.2% |
| 2019-2021 | +0.17 | +4.3% | -23.0% |
| 2022-2023 (bear) | +0.95 | +27.9% | -11.1% |
| **2024-2026 (recent)** | **-0.45** | **-16.3%** | **-28.5%** |

The "post-2022 vol compression" fail-condition from the thesis is **biting in the forward-looking window**. A Phase 6 holdout split at 2023 would likely come out near zero or negative.

### Good news — the filter caught Volmageddon

Feb-2-2018: `ts_ratio` crossed above 1.00 for the first time in the period. Target flipped from long to flat. We ate a -5.56% day on Feb 2, then sat flat through the Feb 5-6 SVXY cliff (SVXY closed -83% on Feb 5 alone). The backwardation exit is doing its job — the filter isn't the problem.

### Problems identified

1. **Recent-regime edge is gone.** 2024-2026 Sharpe -0.45 is not a blip — it's 2+ years of persistent sub-20 VIX and flat VX curve. The roll premium has thinned post-2022.
2. **Cost drag from daily sizing churn.** 2,496 trades over 11 years, 7.6% total cost drag. Vol-target sizing wobbles the book daily even when the signal state is static. A single-state period (e.g. 6 months long) generates ~120 redundant micro-rebalances.

## Phase 2 — fix attempt (in progress)

Two targeted changes, no other params touched:

1. **Weekly rebalance cadence.** Refresh vol-target scaling only every 5 bars (or immediately on a regime-state change). Signal-triggered flips (contango ↔ flat) remain instant — the filter reaction time that saved us in Feb-2018 is preserved.
2. **Tighter backwardation exit threshold: 1.00 → 0.98.** Shrinks the hysteresis hold-band to [0.95, 0.98]. We exit earlier at the first whiff of curve flattening, and sit flat more often during marginal regimes. Cost: we re-enter slightly later too, since the gap between entry (0.95) and exit (0.98) is now tighter.

### Rationale

- #1 should cut turnover ~5× → cost drag ~1.5% instead of 7.6%, which alone lifts Sharpe modestly.
- #2 is the bigger bet: if the post-2022 regime is a slow grind where the curve frequently visits 0.98-1.00 (marginal contango) without delivering reliable roll premium, exiting early avoids the small-but-accumulating bleeds in that zone.

### Pass bar for the fix

To survive Phase 2 and proceed to Phase 3, the fix must deliver:
- Full-period Sharpe **> 0.40** (meaningful improvement, not noise).
- 2024-2026 sub-window Sharpe **> 0** (the critical forward-looking regime).
- All other kill criteria still PASS.

If either of the first two fails, tombstone the strategy and move on. No further tuning — that's overfitting.

### Fix attempt result (REJECT)

| Criterion | Baseline | Fix (weekly rebal, exit 0.98) | Pass bar | Status |
|---|---|---|---|---|
| Full-period Sharpe | +0.30 | **+0.31** | > 0.40 | FAIL |
| 2024-2026 Sharpe | -0.45 | **-0.19** | > 0 | FAIL |
| Max DD | -32.9% | -34.2% | < 40% | pass |
| Worst single day | -7.48% | -7.14% | > -15% | pass |
| # Trades | 2,496 | 492 | ≥ 50 | pass |
| Cost drag | 7.60% | 8.88% | — | (note) |

Full regime breakdown after fix:

| Window | Baseline Sharpe | Fix Sharpe |
|---|---|---|
| 2015-2017 (calm) | +1.14 | +1.11 |
| 2018 (Volmageddon year) | -1.28 | -1.46 |
| 2019-2021 | +0.17 | +0.13 |
| 2022-2023 (bear) | +0.95 | +0.85 |
| 2024-2026 (recent) | -0.45 | -0.19 |

### Observations from the fix

- **The fix did what it was designed to do**: trades fell 5× (2,496 → 492) and the 2024-2026 Sharpe halved its drawdown (-0.45 → -0.19). So the cost-churn diagnosis was partially right.
- **But total cost drag slightly *increased*** (7.60% → 8.88%). Weekly rebalances have larger |Δw| than five daily micro-adjustments would sum to, because the weekly snap jumps over drift. The "lumping helps costs" intuition failed here.
- **The fix slightly worsened 2018** (-1.28 → -1.46). On 2018-02-02, weekly cadence meant we held a staler, larger weight (0.489 vs 0.421 baseline), so Feb-2 bled harder. The filter still caught Feb 5 — same safety — but we paid more to get there.
- **Neither variant clears the 0.40 Sharpe bar, and both have negative 2024-2026.** That's the pre-committed tombstone condition.

### Why the post-2022 regime may be structurally different

- VIX has spent most of 2023-2025 in a 13-18 range, historically low.
- 0-DTE option volume exploded post-2022, and 0-DTE sellers' hedging activity eats into the realized-vol / implied-vol spread that VRP harvests.
- VX futures curve has been flatter — the visible `p95` of `ts_ratio` in our data is 1.021 (baseline measurement), meaning even the worst 5% of days barely touch mild backwardation. The curve mostly sits in 0.87-0.94 (p25-p75), which is the "mid" zone where signal is weakest and churn is highest.

This isn't a tuning problem — it's a regime problem. No threshold choice on the same signal fixes a thinner underlying premium.

## Files

- Thesis: `experiments/vix_term_structure/vix_term_structure.md` (this file)
- Demo: `experiments/vix_term_structure/vix_term_structure_demo.py`
- Data: `ohlc_data/{VIX,VIX3M,SVXY,VXX}_D1.csv`

## Files (old draft — superseded above)

- Thesis: `experiments/vix_term_structure/vix_term_structure.md` (this file)
- Data: pull via `scripts/yahoo_fetch.py --symbols VIX:^VIX,VIX3M:^VIX3M,VXX,SVXY --timeframes D1 --from 2015-01-01`

## References

- Simon & Campasano (2014) "The VIX Futures Basis: Evidence and Trading Strategies" — documents contango edge.
- Bondarenko (2014) "Why Are Put Options So Expensive?" — VRP mechanism.
- Härdle & Silyakova (2012) "Volatility Investing with Variance Swaps" — institutional analog.
- Post-mortems on XIV/Feb-2018 (Bloomberg, CBOE whitepapers) — tail-risk calibration.
