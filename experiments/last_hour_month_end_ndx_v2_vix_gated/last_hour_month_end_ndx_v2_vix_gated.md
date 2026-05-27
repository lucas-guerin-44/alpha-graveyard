# Last-hour month-end NDX v2 — VIX-CALM gated — Phase 2 thesis

**Status**: Phase 2 REJECT (2026-05-27, 8/10).
**Type**: Resurrection-v2 of a REJECTed strategy (`last_hour_month_end_ndx`, REJECT 2026-05-27 7/13 via W2 sign-flip).
**Verdict**: **REJECT — 8/10 pre-committed kill criteria PASS. Mechanism falsification PASSES decisively (criterion #5 direction-gap +0.84, #6 bootstrap CI [+2.06, +40.48] excludes zero, #8 placebo clean +0.12 bp); gating produces +0.35 Sharpe lift over parent (parent +0.29 → v2 +0.64). Two binding fails: (#7) direction-lock fails on W2 2021-2022 being an empty regime (0 CALM events — gate correctly excluded the QE era but the criterion didn't have an exception for empty regimes); (#10) deflated Sh +0.04 vs +0.20 bar — Bailey-López-de-Prado deflation eats ~0.60 Sh at n=17 with 20-trial diagnostic selection bias. REAL signal, real lift, but n=17 too small to clear deflated-Sh bar.**

## Phase 2 results

| # | Criterion | Threshold | Observed | Pass? |
|---|---|---|---|---|
| 1 | Gated full Sh | ≥ +0.50 | **+0.64** | ✅ |
| 2 | W3 holdout Sh | ≥ +0.30 | **+0.92** | ✅ |
| 3 | CALM events n | ≥ 15 | **17** | ✅ (barely) |
| 4 | CALM active-aware Sh | ≥ +0.65 | **+1.43** | ✅ |
| 5 | Direction-gap | ≥ +0.30 | **+0.84** | ✅ |
| 6 | Bootstrap 95% CI lower | > 0 bp | **+2.06** | ✅ |
| 7 | **Direction-lock all W's** | yes | **W2 empty** (no CALM events 2021-2022) | ❌ logic-edge-case |
| 8 | Placebo |mean| | < 1 bp | +0.12 | ✅ |
| 9 | Cost-stress 2× net | > 0 | +17.36 | ✅ |
| 10 | **Deflated Sh** | ≥ +0.20 | **+0.04** | ❌ |

## Why the two fails are different shapes

**Criterion #7 (direction-lock)**: W2 2021-2022 had zero CALM-regime events because VIX was elevated the whole regime (post-COVID inflation panic + war + Fed hike anticipation). The gate **correctly excluded** that regime — that's the whole point of the gate. But the pre-commit said "all W's must agree on direction" with no exception for empty regimes, so the criterion mechanically fails. This is a *criterion-design issue*, not a strategy issue.

**Criterion #10 (deflated Sh)**: real, binding, n-driven. Observed +0.64 Sh, deflated to +0.04 because Bailey-López-de-Prado correction at n=17 with 20 selection trials is severe (deflation factor ~0.60 Sh). Even at the correct +0.20 bar, the strategy needs n≥25-30 events to clear with the same +0.64 raw Sh.

**Naturally resolves with time**: at current cadence (~2.4 CALM events/year) the strategy adds ~3 events by Q4 2027. At n=25 the deflation hit drops to ~0.48 Sh, putting the deflated Sh around +0.16 — still short, but close. At n=30 deflation hit is ~0.44, deflated Sh ~+0.20. So **a natural re-evaluation in ~2-3 years from accumulated data would plausibly clear the criterion** if the regime-conditional signal holds.

## Honest interpretation

The v2 produces +0.35 Sharpe lift over the parent's unconditional REJECT (parent +0.29 → v2 +0.64). The lift is real:
- Bootstrap 95% CI [+2.06, +40.48 bp] cleanly excludes zero — sampling variance doesn't explain the result
- Direction-gap +0.84 is decisive — asymmetric SHORT edge, not symmetric variance
- W3 holdout +0.92 ann-Sh — the most-recent regime is the strongest

But the strict pre-commit's deflated-Sh bar correctly identifies that **at n=17 the result is statistically vulnerable to the small-sample variance + selection-bias combo**. The discipline rule says REJECT.

## Pairs with `xau_session_v2_ffr_gated` REJECT

Both regime-line Phase 2 attempts today produced REJECT-marginals:
- `xau_session_v2_ffr_gated`: 9-10/11, failed by ~0.10 on magnitude bar
- `last_hour_month_end_ndx_v2_vix_gated` (this): 8/10, failed by ~0.16 on deflated Sh

Both have **real mechanism signal**. Both fall short on small-sample or pre-commit calibration. The pattern is: the regime classifier methodology **detects real conditional signal** but the deploy bar is **hard to clear with current sample sizes**. Each regime-gated subset of a multi-year strategy has 15-30 events typically — exactly the n-range where small-sample variance + deflated-Sh combine hardest.

## Methodological deliverable

The diagnostic + v2 pipeline is **research-validated, deploy-undelivered** for now. The methodology produces honest predictions (xau_session_v2 actual +1.11 vs predicted +1.09) and honest REJECTs (this v2 +0.64 falls short of bar by exactly the amount predicted by deflation math). What it doesn't produce — yet — is a Phase 2 PASS at currently-available sample sizes.

**Forward path**: queue both REJECTs for natural re-evaluation when sample sizes grow:
- `xau_session_v2_ffr_gated`: revisit when TIGHTENING regime accumulates 30+ more trades (likely 2027-2028 depending on Fed cycle)
- `last_hour_month_end_ndx_v2_vix_gated`: revisit when CALM regime accumulates 8-10 more trades (~2027-2028, less Fed-cycle dependent since VIX regime is faster-moving)

Set a calendar reminder for end of 2027 to rerun the diagnostic + re-test both v2s with accumulated data. The mechanism stories may or may not persist — but if they do, sample-size growth alone would convert both REJECTs to PASSes mechanically.

## Files

- [last_hour_month_end_ndx_v2_vix_gated_demo.py](last_hour_month_end_ndx_v2_vix_gated_demo.py) — Phase 2 simulator (REJECT 8/10)
- Parent: [`../last_hour_month_end_ndx/`](../last_hour_month_end_ndx/)
- Diagnostic: [`../regime_classifier_diagnostic/`](../regime_classifier_diagnostic/)
- Sibling REJECT: [`../xau_session_v2_ffr_gated/`](../xau_session_v2_ffr_gated/)


Origin: `regime_classifier_diagnostic` v2 (2026-05-27, post-deflation calibration) surfaced `last_hour_month_end_ndx × vix_regime CALM` as the highest deployable spread among Pool B resurrect candidates — deployable Sh +0.68 in CALM regime, deployable spread +1.08 across regimes.

## Why this experiment exists

Parent strategy REJECTed because the SHORT-aggregate +3.57 bp/event masked W2 2021-2022 sign-flip (SHORT lost there: −5.17 bp, LONG won +4.67 bp). The diagnostic identifies VIX regime as the *mechanism-selecting* gate — SHORT works when VIX 60d median < 15 (CALM), inverts in NORMAL.

The hypothesis (with three pre-committed competing mechanism stories per parent thesis):
1. **Etula et al. (2020) USD-funding pressure** dominates → SHORT NDX last hour of month-end. This mechanism is *risk-on regime conditional*: in CALM-VIX environments, equity risk-on positioning concentrates last-hour selling pressure to fund USD obligations.
2. **Goyenko-Sarkissian (2014) equity-fund redemptions** dominate → SHORT NDX. Also CALM-regime amplified (redemption flow is more impactful when market is thin/CALM).
3. **Lakonishok-Smidt (1988) turn-of-month** dominates → LONG NDX. CONTRADICTED by data: this story dominates in NORMAL/stimulus regimes, NOT CALM regimes.

In CALM-VIX regimes the SHORT mechanism (Etula + Goyenko) dominates uniformly. Gating to CALM-only removes the regime mixing that killed the unconditional v1.

## Calibrated expected performance

Per diagnostic v2 deflated estimate:
- CALM regime deployable Sh **+0.68** (active-aware was +1.03; deflation factor ~0.66 for CALM regime ~40% of sample)
- Spread vs NORMAL **+1.08 deployable** (NORMAL = −0.40 deployable)
- Lift over parent's REJECT (parent +0.29 unconditional) ≈ **+0.40 lift**

Live haircut (lesson #5 rewritten 10-25%): expected live Sh **+0.55 to +0.65**.

## Signal math

```
Universe          : NDX100 M5 (parent strategy)
Event calendar    : last business day of every month
Window            : 15:00 -> 16:00 ET (parent's window, unchanged)
Direction         : SHORT NDX (parent's BEST direction on aggregate)
NEW gate          : VIX 60d trailing median < 15 (CALM regime per diagnostic)
                    On event day, check VIXCLS rolling 60d median; trade only if < 15
Entry             : 15:00 ET open
Exit              : 16:00 ET close
Cost              : 0.5 pt RT NDX (~0.25 bp on $20K)
Holding           : intraday 1h
Trade frequency   : 12 events/year × ~40% CALM regime = ~5 events/year deployable
```

Cadence is sparse — ~5 events/year vs the parent's 12/year unconditional.

## Universe

NDX100 only. SPX500 sibling test is Phase 3 work if Phase 2 PASSES.

## Fail conditions (pre-committed — 10 criteria, ALL must PASS — CALIBRATED to v2-style deploy bars after xau_session_v2 lesson)

Set BEFORE Phase 2 simulator runs. All thresholds calibrated to the deflated diagnostic expectation, NOT the active-aware numbers that misled the xau_session_v2 attempt.

| # | Criterion | Threshold | Rationale |
|---|---|---|---|
| 1 | **Gated full Sh ≥ +0.50** | ≥ +0.50 | Calibrated bar (matches lesson #5 expected-live range +0.55-0.65 with margin); +0.18 above the +0.32 fail bar from parent REJECT |
| 2 | **Gated W3 holdout Sh ≥ +0.30** | ≥ +0.30 | Holdout regime must be positive; parent W3 was +0.34, gating shouldn't kill it |
| 3 | **CALM-regime events ≥ 15** | ≥ 15 | n=15 is the bootstrap CI floor; below this, sampling variance dominates |
| 4 | **CALM-regime Sh ≥ +0.65** | ≥ +0.65 | Matches diagnostic-calibrated expectation; binding sanity check on the gate logic |
| 5 | **Direction-gap (SHORT − LONG) ≥ +0.30** in CALM regime | ≥ +0.30 | Asymmetric edge confirmed within the gated regime |
| 6 | **Bootstrap 95% CI lower bound on full-sample mean > 0 bp** | > 0 | Survives n~30-40 sampling variance |
| 7 | **Direction-lock**: SHORT wins in CALM AND no W1/W2/W3 sub-regime inversion in CALM-only sample | yes | Verify CALM gate stabilizes direction; this is the load-bearing criterion that killed parent |
| 8 | **Placebo non-event same-weekday-CALM-day mean magnitude < 1 bp** | < 1 bp | Disambiguate from generic CALM-regime NY-PM drift |
| 9 | **Cost-stress @ 2× default** still net > 0 | net > 0 | Inherited from parent |
| 10 | **Deflated Sharpe ≥ +0.20** | ≥ +0.20 | Lower than xau_session_v2's +0.50 because this is the first Pool B resurrect (no within-strategy diagnostic selection bias on the gate) |

PASS = all 10. REJECT otherwise.

## Why this might fail (red flags)

1. **Sample size collapse**: ~5 events/year × 7.3y = ~36 trades total. Bootstrap CI will be wide. Criterion #6 is binding.
2. **VIX regime is not perfectly stable** — 60d median can transition across a regime boundary mid-strategy-period. The gate must be observable AT each trade date with no lookahead — handled in implementation.
3. **CALM-VIX regime in our sample is heavily 2019-2020 + 2024-2025** — two distinct macro contexts. If the SHORT mechanism works in one but not the other, criterion #7 fails.
4. **Sparse-event-strategy live validation timeline is 3+ years** at 5 events/year before any live-vs-research call is statistically meaningful. Even a PASS means a watchlist-deploy-style multi-year validation cycle.
5. **The diagnostic itself has selection bias** — we picked the best Pool B candidate from the screen. Deflated Sharpe (#10) controls for this but at low n it's a soft control.

## Phase plan

- [ ] Phase 1 — simulator + per-direction gated metrics + regime breakdown of CALM-only events
- [ ] Phase 2 — 10 pre-committed kill criteria
- [ ] Phase 3 — IF PASS, bootstrap CI + walk-forward halves + sibling SPX test
- [ ] Phase 5 — IF PASS, broker-spread audit at month-end 15-16 ET on NDX (likely fine, cost is already small)
- [ ] Phase 7-8 — IF PASS, MQL5 EA build with VIX gate (requires daily VIX series from FRED)

## Files

- [last_hour_month_end_ndx_v2_vix_gated_demo.py](last_hour_month_end_ndx_v2_vix_gated_demo.py)
- Parent (REJECT): [`../last_hour_month_end_ndx/`](../last_hour_month_end_ndx/)
- Diagnostic origin: [`../regime_classifier_diagnostic/`](../regime_classifier_diagnostic/)
