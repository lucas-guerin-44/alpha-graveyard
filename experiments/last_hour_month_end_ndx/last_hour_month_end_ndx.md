# Last-hour-of-month-end on NDX100 — Phase 2 thesis

**Status**: Phase 2 REJECT (2026-05-27). Direction-lock criterion #13 caught a W2 regime sign-flip — clean methodology kill.
**Verdict**: **REJECT — 7/13 pre-committed kill criteria PASS. Best-direction (SHORT) wins on aggregate (+3.57 bp net, ann-Sh +0.29) but the mechanism flips sign in W2 2021-2022 (QE/pandemic era): SHORT −5.17 vs LONG +4.67. Funding-pressure mechanism dominates in tight-money regimes (W1 + W3), turn-of-month LONG dominates in stimulus regimes (W2). Regime-conditional mechanism instability — deploy-blocked by criterion #13 direction-lock, which is exactly the discipline check this thesis pre-committed for this risk.**

## Phase 2 results

| # | Criterion | Threshold | Observed | Pass? |
|---|---|---|---|---|
| 1 | Best-dir full mean net | ≥ +1.5 bp | **+3.57** (SHORT) | ✅ |
| 2 | Best-dir W3 mean net | ≥ +1.0 bp | +3.52 | ✅ |
| 3 | All 3 regimes net positive | W1, W2, W3 > 0 | **W1 +12.40 / W2 −5.17 / W3 +3.52** | ❌ |
| 4 | Annualized Sharpe | ≥ +0.30 | **+0.29** (one bp short) | ❌ |
| 5 | WR | ≥ 50% | 52.3% | ✅ |
| 6 | MDD | ≤ −3% | −2.40% | ✅ |
| 7 | Bootstrap 95% CI lower | > 0 bp | **[−5.50, +12.54]** | ❌ |
| 8 | Direction-gap ≥ +0.30 Sh | ≥ +0.30 | **+0.18** | ❌ |
| 9 | Placebo |mean| < 1 bp | < 1 bp | +0.12 bp | ✅ |
| 10 | Cost-stress 2× | net > 0 | +3.32 bp | ✅ |
| 11 | Deflated Sharpe | ≥ +0.20 | **+0.03** | ❌ |
| 12 | WF halves both net > 0 | both > 0 | H1 +6.02 / H2 +1.12 | ✅ |
| 13 | **Direction-lock across regimes** | same dir all 3 | **W2 sign-flips: LONG wins** | ❌ (load-bearing) |

## Direction breakdown (the headline)

| Regime | SHORT mean (best aggregate) | LONG mean | Regime winner |
|---|---|---|---|
| **W1 2019-2020** (normal) | **+12.40 bp** | −12.90 bp | SHORT |
| **W2 2021-2022** (QE/pandemic) | **−5.17 bp** | +4.67 bp | **LONG ← sign-flip** |
| **W3 2023-2026** (rate cycle) | **+3.52 bp** | −4.02 bp | SHORT |

The QE/pandemic regime *inverts* the dominant flow direction. Two real mechanisms compete:

- **Tight-money regimes (W1, W3)**: Etula et al. (2020) USD-funding-pressure mechanism dominates — last-hour-of-month sees selling pressure on equities as institutions source USD liquidity. SHORT direction wins.
- **Easy-money regime (W2)**: Lakonishok-Smidt (1988) turn-of-month effect dominates — pension/passive contribution inflows + stimulus-era window-dressing produce positive last-hour drift. LONG direction wins.

Both stories were pre-committed in the thesis. The data direction-selected which was active in each window — and the mechanism flipped at the QE-on / QE-off transitions (2020-Q2 onset and 2022-Q4 end).

## Why this is a clean REJECT, not a noisy one

Three of the failing criteria (#3, #7, #13) all derive from the same root cause: **regime-conditional sub-mechanisms with opposite signs**. Without criterion #13 (direction-lock), this would have looked like a borderline deploy on aggregate (+3.57 bp full mean, +3.52 W3 holdout). The W2 sign-flip is the disqualifier and **the live deployment risk is that any policy regime shift toward QE-style stimulus would immediately invert the live P&L sign**.

This is exactly the scenario criterion #13 was pre-committed to catch. The kill criterion did its job; the strategy correctly REJECTS.

## Mechanism interpretation — generalizable lesson

Going forward, **any month-end equity-flow thesis must pre-commit a monetary-regime gate** (e.g., QE-on vs QE-off via Fed balance sheet change, or real-rate sign, or Fed-funds-rate change in 6-month window). The strategy operates only in one regime at a time:

- In tight-money / QT regime: funding-pressure SHORT mechanism dominates → deployable as SHORT
- In easy-money / QE regime: turn-of-month LONG mechanism dominates → deployable as LONG-direction (different strategy then)

A regime-conditional gated version of this strategy might be deployable (e.g., "SHORT only when Fed funds rate is rising and balance sheet is shrinking, else flat"). That's a v2 thesis, not a refinement of this one — would need fresh pre-commits.

**Pairs with lesson #-7** (Mag7 earnings sign-flip at 2022/2023 boundary) and **lesson #2** (holdout regime as 0DTE-amplification proxy): regime-conditional direction inversion is now a documented family failure mode across (a) Mag7 single-stock earnings, (b) US-index intraday MR, (c) month-end equity rebal. The common pattern is *monetary regime change* (QE-on/off + 0DTE structural-short-gamma) flipping the institutional-flow direction.

## Why this experiment is methodologically valuable

The structural-flow audit pipeline now has **three Phase 2 data points** (2026-05-27):

| Experiment | Magnitude/cost | Result | Lesson |
|---|---|---|---|
| `quarter_end_xau_short` | 19× (decisive) | **PASS 12/12 → deployed** | Mechanism strong, structurally consistent |
| `month_end_usd_short` (EUR+GBP basket) | 1.5× | REJECT 7/13 | Cost-blocked at retail tier, mechanism real |
| `last_hour_month_end_ndx` | 11× gross / regime-fragile | **REJECT 7/13** | Aggregate-positive but regime-conditional mechanism — direction-lock criterion catches the W2 sign-flip |

The pipeline isn't just for finding new deploys — it's also for **structured failure-mode discovery**. Each REJECT informs the next thesis pre-commit. This experiment's failure mode (regime-conditional sub-mechanism inversion) is now a documented pattern that any future month-end equity-flow thesis must address.

## Files

- [last_hour_month_end_ndx_demo.py](last_hour_month_end_ndx_demo.py) — Phase 2 simulator with both directions, 13 kill criteria

---

## Original thesis content preserved below for context


Origin: candidate #4 from the post-`month_end_usd_short` brainstorm (2026-05-27). The structural_flow_audit pipeline produced a deploy (`quarter_end_xau_short` PASS) and an at-cost REJECT (`month_end_usd_short` cost-blocked despite mechanism validation). This thesis tests a *different mechanism* (equity rebalancing at month-end last hour) on a *friendlier-cost venue* (NDX100 M5, ~0.7 bp RT vs FX ~1.5-2 bp RT) — same calendar trigger family as the prior two structural-flow experiments.

## Thesis (mechanism)

The 15:00-16:00 ET window on the last business day of each month is the densest window for monthly rebalance flow on US equities. Three mechanism stories compete and the data must direction-select:

1. **Goyenko-Sarkissian (2014) — equity fund net redemptions at month-end.** Open-end mutual funds and pension fund withdrawals concentrate at month-end settlement; the resulting sell flow hits in the last cash-equity hour. **Predicts SHORT NDX**.
2. **Etula, Rinne, Suominen & Vaittinen (2020) — USD-funding pressure spills cross-asset.** Same paper that drives `month_end_usd_short`. Month-end USD demand forces de-risking of equity holdings to source USD; **predicts SHORT NDX**.
3. **Hartzmark-Solomon (2013) + Lakonishok-Smidt (1988) — turn-of-month LONG drift.** Pension and 401(k) contribution inflows on the monthly cycle, plus window-dressing buying of winners. **Predicts LONG NDX** (but operates at day-level granularity, weaker at hourly).

Stories 1 and 2 are intra-day mechanisms localized to the last hour; story 3 is day-level. The simulator runs BOTH directions per lesson #54 and the data decides which (if any) dominates. The candidate is plausibly SHORT-only (matching user direction preference) per stories 1+2, but the simulator pre-commits both directions to prevent post-hoc rationalization.

This is a fundamentally different mechanism from `quarter_end_xau_short` (institutional rebalance of safe-haven gold) and `month_end_usd_short` (USD funding squeeze on FX) — same calendar family, different flow.

## Key references

- Goyenko, R. & Sarkissian, S. (2014). "Treasury Bond Illiquidity and Global Equity Returns." *Journal of Financial and Quantitative Analysis* 49(5). — documents month-end equity-fund net redemptions.
- Etula, E., Rinne, K., Suominen, M., & Vaittinen, L. (2020). "Dash for cash: Monthly market impact of institutional liquidity needs." *Review of Financial Studies* 33(1). — Same paper backing `month_end_usd_short`. Cross-asset USD-funding pressure spillover to equities.
- Hartzmark, S. & Solomon, D. (2013). "The Dividend Month Premium." — Window-dressing literature.
- Lakonishok, J. & Smidt, S. (1988). "Are seasonal anomalies real? A ninety-year perspective." *Review of Financial Studies* 1(4). — Foundational turn-of-month effect (day-level LONG bias).

## Signal math

```
Universe          : NDX100 M5 (Eightcap CFD, deployed instrument)
Event calendar    : last business day of every month
                    pure rule (no external CSV needed)
Window            : 15:00 -> 16:00 ET local (last cash-equity hour, DST-aware)
Direction         : BOTH (pre-commit) — data direction-selects per lesson #54
Entry             : at 15:00 ET open (first M5 bar in window)
Exit              : at 16:00 ET close (last M5 bar in window)
Cost              : 0.5 pt RT (~0.25 bp on $20K NDX); sweep 0.25 / 0.5 / 1.0 / 2.0 pt
Holding           : intraday 1h, no overnight risk
Trade frequency   : 12 events / year; ~88-92 events available 2019-01 → 2026-04
```

## Why retail-accessible

- Pure calendar-rule trigger (10 lines of MQL5).
- Single intraday 1h window, no multi-day hold, no overnight gap risk.
- NDX100 is a primary CFD product at Eightcap; spread floor at NY-PM is the tightest tier.
- 12 trades/yr cadence.
- Cost tier (~0.25-0.5 bp gross) is meaningfully better than retail FX (~1.5-2 bp) — magnitude bar to clear deploy is lower.

## Universe

NDX100 only for this thesis lock. SPX500 is the natural sibling test (same flow, different vessel) — if NDX PASSES, sibling SPX test becomes Phase 3 cross-asset shadow rather than a separate Phase 2 thesis. If both PASS independently, they're co-deployable (corr-tombstone check required).

## Expected performance (priors)

**Cannot be confidently signed.** Three mechanism stories disagree on direction. Honest range:

| Outcome | Direction | Per-event mean | Implication |
|---|---|---|---|
| Stories 1+2 dominate | SHORT NDX | −2 to −5 bp gross | Deploy candidate (SHORT-only matches user constraint) |
| Story 3 dominates | LONG NDX | +1 to +3 bp gross | Deploy candidate but adds LONG-direction (book already net-long) |
| Mechanisms cancel | Either direction near zero | 0 to ±1 bp | REJECT — direction-gap fails, no asymmetric edge |
| Direction inverts post-2022 | W3 opposite of W1+W2 | Regime-conditional | Reject on regime-instability criterion |

Cost is friendly enough that the magnitude bar is lower than the FX basket (~1.5 bp full-mean net should be plausibly clearable for a real ~3 bp gross signal).

## Fail conditions (pre-committed — 13 criteria, ALL must PASS on the BEST direction)

Set BEFORE Phase 2 simulator runs. Any single fail → REJECT. Best-of-direction logic per lesson #54 (orb_dax template).

| # | Criterion | Threshold | Rationale |
|---|---|---|---|
| 1 | **Best-direction full mean net ≥ +1.5 bp/event** | ≥ +1.5 | Below this is hard to justify against retail cost stack |
| 2 | **Best-direction W3 mean net ≥ +1.0 bp/event** | ≥ +1.0 | Holdout regime is binding deploy criterion |
| 3 | **All 3 regimes net-positive** (best direction) | W1, W2, W3 > 0 | Standard regime gate |
| 4 | **Annualized Sharpe ≥ +0.30** (best direction) | ≥ +0.30 | Phase 2 deploy bar |
| 5 | **WR ≥ 50%** | ≥ 50% | Coin-flip baseline at 12/yr cadence |
| 6 | **MDD ≤ −3%** (event-equity curve, fixed notional) | ≤ −3% | Low-cadence strategy MDD should be small |
| 7 | **Bootstrap 95% CI lower bound on full mean > 0 bp** | > 0 | Survives n~90 sampling variance |
| 8 | **Direction-gap ≥ +0.30** Sh (best − worst) | ≥ +0.30 | Asymmetric edge, not symmetric variance |
| 9 | **Placebo non-event same-weekday |mean| < 1 bp** | < 1 | Disambiguate from generic NY-PM-hour drift |
| 10 | **Cost-stress @ 1.0pt RT (2× default) — best-dir net > 0** | net > 0 | Live spread could widen at month-end close |
| 11 | **Deflated Sharpe ≥ +0.20** | ≥ +0.20 | 17 screen cells + 2-direction test = 19 effective trials selection-bias adjustment |
| 12 | **Walk-forward halves**: split chronologically; both halves best-dir net > 0 | both > 0 | Detect monotonic decay |
| 13 | **Direction lock**: same direction wins in ALL of W1, W2, W3 holdout-binding | yes | Mechanism must be consistent across regimes; sign-flip across regime = REJECT regardless of full-sample magnitude (lesson #-7 / earnings_continuation_mag7 family) |

PASS = all 13. REJECT otherwise.

## Why this might fail (red flags)

1. **Three competing mechanism stories with conflicting direction predictions.** If story 3 (turn-of-month LONG, day-level) dominates over stories 1+2 (last-hour-of-month-end-day SHORT), the win-direction inverts vs user preference. Honest call: deploy what the data shows, not what the constraint wants.
2. **Possible W1→W3 regime shift** at the 2022/2023 boundary (0DTE-amplification era per repo lesson #43 family). Cross-asset funding squeeze magnitude may have changed shape with 0DTE structural-short-gamma dealer hedging now dominant in the NDX last-hour. Criterion #13 (direction-lock across regimes) catches this.
3. **n~90 small-sample variance** — bootstrap CI will be wide; magnitude needs to be cleanly above noise floor not just statistically positive.
4. **Cell-shopping risk**: I picked 15-16 ET (last hour) without evidence the mechanism concentrates there vs 14-16 ET (last 2h). This is a pre-commit; no post-hoc widening allowed.
5. **Overlap with deployed `lunch_fade`** (NDX100 M5 LONG, 11:30-13:30 ET) is window-disjoint (we're at 15-16 ET), so co-deploy correlation should be low. But pre-Phase-3 corr-tombstone needed if it PASSES.
6. **Overlap with deployed `event_calendar`** (NDX100 H1 FOMC/CPI/RS/NFP) is event-disjoint by design — month-end days rarely coincide with macro-event days. Skip events that fall within ±1 day of any deployed event to avoid double-trading.

## Phase plan

- [ ] Phase 1 — basket simulator on NDX M5, BOTH directions, baseline + variant sweeps + regime + cost
- [ ] Phase 2 — full 13-criterion kill-criteria evaluation, regime breakdown, bootstrap, cost-stress, walk-forward halves
- [ ] Phase 3 — IF PASS, cross-asset shadow (does same direction appear on SPX500 same window?) + corr-tombstone vs deployed `lunch_fade`
- [ ] Phase 5 — IF PASS, broker-spread audit at month-end 15-16 ET
- [ ] Phase 7-8 — IF PASS, MQL5 EA build

## Files

- [last_hour_month_end_ndx_demo.py](last_hour_month_end_ndx_demo.py) — Phase 2 simulator + 13 kill criteria, both directions
- Origin context: [structural_flow_audit](../structural_flow_audit/), [month_end_usd_short](../month_end_usd_short/)
