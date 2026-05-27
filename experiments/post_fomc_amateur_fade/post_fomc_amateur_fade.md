# Post-FOMC amateur-hour fade (T+15min → T+60min)

**Status (2026-05-26)**: Phase 0 ABORT → REJECT. Phase 2 not built.

**Verdict**: **REJECT (decisive, Phase 0 magnitude gate).** FADE-direction
mean at SPIKE_FLOOR=10 bps on NDX100 M5 over 57 historical FOMC events
(2019-2026) is **+3.84 bps gross**, below the pre-committed **+5 bps Phase 0
floor**. W3 (2023-2026 holdout, n=9) FADE mean is **-0.36 bps** — modern-regime
zero. Mechanism is dead in the deploy-relevant window. Pre-committed Phase 0
gate fired exactly as intended; Phase 2 build avoided.

**Prior expectation honesty check**: pre-run prior was ~30-40% PASS-shape with
the user-pre-flagged red flag #1 (HFT absorbs in <60s) as the most likely
failure mode. Red flag #1 is the empirically correct failure mode.

## Phase 0 results (NDX100 M5, 57 FOMC events 2019-01-30 → 2026-04-17, _phase0_magnitude_check.py)

**Headline @ SPIKE_FLOOR=10 bps** (binding +5 bps floor):

| direction | n | mean gross | std | t | wr |
|---|---:|---:|---:|---:|---:|
| **FADE** | 22 | **+3.84 bps** | 20.6 | +0.88 | 63.6% |
| CONT (null) | 22 | -3.84 bps | 20.6 | -0.88 | 36.4% |

Mechanically symmetric (CONT = -FADE at fixed floor) — the load-bearing
null check is the **per-regime sign**, not the full-sample mirror.

**SPIKE_FLOOR sweep — FADE direction**:

| floor (bps) | n | mean (bps) | t |
|---:|---:|---:|---:|
| 5 | 34 | +4.32 | +1.23 |
| 10 | 22 | +3.84 | +0.88 |
| 15 | 12 | +8.68 | +1.21 |
| 20 | 10 | +11.72 | +1.72 |
| 30 | 2 | -9.71 | -0.69 |

Sweep is *near-monotone* through floor=20, supporting "bigger first-15min
spikes do mean-revert more" weakly — but n collapses to 2 at floor=30,
and floor=20 still only yields 10 events over 7 years (~1.4/yr cadence,
far below the 30-trade floor). Not a workable variant.

**Per-regime breakdown @ SPIKE_FLOOR=10 (FADE direction)** — *decisive*:

| regime | window | n | mean (bps) | Sh per-trade-style |
|---|---|---:|---:|---:|
| W1 | 2019-2020 | 5 | **+10.13** | +0.70 |
| W2 | 2021-2022 | 8 | +4.64 | +0.17 |
| W3 | 2023-2026 holdout | 9 | **-0.36** | -0.02 |

The amateur-fade signature existed in W1 (pre-COVID, n=5, mean +10 bps —
matches the literature prior) and decayed monotonically: W2 +4.64 bps,
W3 essentially zero. The 2023-2026 holdout is the deploy-relevant window
and shows zero directional content in either FADE or CONT direction.

**Spike-distribution context** (sanity that the trigger isn't trivially
rare or trivially common):

- |spike| median: 7.6 bps, mean: 10.7 bps, p25/p75: 2.9 / 12.5 bps
- 22 of 57 events have |spike| ≥ 10 bps (38% — adequate trigger density)

The trigger fires at expected rate; the *reaction* is the part that's dead.

## Pre-committed kill criteria — result

| # | criterion | result | pass? |
|---|---|---|---|
| Phase 0 | FADE mean @ floor=10 ≥ +5 bps | +3.84 bps | **FAIL** |

Phase 0 binding → REJECT before Phase 2. Criteria (1)-(9) not evaluated.
The W3 -0.36 bps would have failed criterion (2) in any case, and the
near-zero full-sample mean at floor=10 fails criterion (1).

## Mechanistic interpretation

1. **The pre-flagged HFT-absorption red flag is empirically correct.** By
   T+15 min, post-FOMC information absorption is essentially complete on
   NDX100 M5. The retail amateur spike — if it exists at all in modern
   regime — concentrates in the T+0 → T+5 minute window and is fully
   metabolized by T+15 by 0DTE-gamma desks and equity-index ETF arb.
   There is no T+15 → T+60 minute imbalance to fade.

2. **W1 → W3 monotonic decay matches the deployed macro_drift W3→W4
   shape**, but the *post-event* leg has decayed further and faster than
   the *pre-event* leg. `event_calendar` FOMC LONG (24h-pre) still posts
   Sh +0.41 in W4; this post-event fade has crossed zero in W3 already.
   Pre-event positioning flow (slow institutional accumulation over 24h)
   has more cross-regime persistence than post-event amateur-vs-algo
   opposition (which depends on a temporal *gap* that HFT density has
   closed).

3. **Temporal-axis non-portability of the FOMC event-flow mechanism.**
   The deployed pre-event leg captures a real *anticipation-window* flow
   (Lucca-Moench 2015 / Hu-Pan-Wang-Zhu 2022 risk-premium-accrual).
   The post-event 15-60 min window is structurally a different flow type
   (algorithmic rebalancing, not directional positioning). Mechanism-by-
   temporal-extension assumed the post-event window inherits exploitable
   directionality from the pre-event window — it does not. This is the
   *temporal axis* analog of lesson #56's "macro-event-family extension
   requires the flow mechanism to port" — same event, different intra-
   event horizon, different mechanism, no inheritance.

4. **W2 +4.64 bps weakly suggests the mechanism's persistence depended on
   pre-2023 retail-tooling speed.** Pre-Robinhood-options-flow + pre-
   ubiquitous-0DTE-on-FOMC, the amateur-vs-algo gap at T+15 had a few
   minutes of detectable signal. Post-2023 (CBOE 0DTE every weekday +
   options-app-tier UX + social-feed real-time alerting), retail reacts
   inside the same temporal bucket as the algos, eliminating the gap.

5. **The direction null check is trivially the negative at fixed floor**
   (FADE and CONT use the same trigger; they are mechanically -FADE).
   The non-trivial null is the **per-regime sign stability** check — W1
   FADE +10.13, W3 FADE -0.36. The mechanism didn't invert sign (no
   "CONT wins in W3"); it *evaporated*. This is a different failure
   shape than `retail_overshoot_fade` (W2-pass-W3-fail-sign-inversion
   per lesson #68) — here W3 is direction-neutral noise, not flipped.

## Phase 1 → Phase 0 plan — final status

- [x] Read lesson #43, #45, Lessons A/B/C from cfd_wed_rollover REJECT,
      `event_calendar` thesis (24h-pre leg), `lunch_fade` (amateur-flow
      framing), `pre_fomc_drift` REJECT (FX-side falsification context)
- [x] Write this thesis with pre-committed kill criteria + Phase 0 floor
- [x] **Phase 0 magnitude check** — FAIL (+3.84 bps < +5 bps floor)
- [ ] ~~Build Phase 2 simulator~~ — N/A, Phase 0 ABORT
- [x] Update this doc with results + REJECT + mechanistic interpretation
- [x] Update STATE_GRAVEYARD.md + RESEARCH_NOTES.md lesson #69

## Files

- `post_fomc_amateur_fade.md` — this doc
- `_phase0_magnitude_check.py` — Phase 0 binding diagnostic (kept for
  reproducibility)
- Data: `ohlc_data/NDX100_M5.csv`; FOMC calendar from
  `experiments/_live/macro_drift/fomc_calendar.csv`

---

## Pre-run scaffold (kept below for context — superseded by Phase 0 result above)

**Prior expectation (honest)**: ~30-40% PASS-shape. The user-pre-flagged
concern is that 0DTE/HFT-era post-event flow may already be absorbed in
<5 seconds, leaving no T+15 → T+60 retail-vs-institutional opposition to
trade. This thesis is run *because* the falsification value is high — if
it fails, the methodology-finding ("post-event amateur fade is dead at
modern HFT density") is the deliverable; if it passes, it adds a second
leg to the existing event_calendar book on the same FOMC events.

## Why this — the institutional-flow-and-absence framing

The deployed `event_calendar` book captures the **24h-pre-event** leg: slow
institutional positioning into FOMC drives the LONG NDX drift documented
by Lucca-Moench. **What about the 15-60 minute window AFTER the
announcement?**

The proposed mechanism is the *amateur-flow* signature: in the first 15 min
post-announce, retail traders watching the headline pile in on the surface
direction of the FOMC print. In T+15 to T+60 min, the institutional algos
re-assert (positioning was already done pre-event; their post-event flow
is rebalancing, not directional reaction), absorbing the retail spike and
reverting it.

The coverage gap argument: T+0 to T+5 seconds is HFT territory (instantly
arbed); T+24h post is fundamental-desk territory (digest the dot-plot);
**T+15 to T+60 minutes is amateur-hour** — the window where retail is the
dominant order flow because everyone else has already finished trading or
hasn't started yet.

## Thesis (mechanism)

1. **At FOMC announce (14:00 ET / 19:00 UTC summer / 18:00 UTC winter),
   institutional positioning is already DONE.** Slow institutional flow
   spans the 24h-pre window (captured by deployed `event_calendar`); the
   announcement itself crystallizes the position. Post-event institutional
   flow is small-magnitude rebalancing, not directional.

2. **In T+0 to T+15 min, retail piles in on the surface direction.**
   "Surface direction" = first-glance read of the rate decision + statement
   wording. Retail flow is small-ticket, momentum-following, headline-driven.
   It compresses into the first 5-15 min because retail traders who weren't
   pre-positioned react when the headline hits their feeds.

3. **In T+15 to T+60 min, institutional algos re-assert.** Specifically:
   delta-one rebalancing flow (ETF arb, index arb between cash and futures),
   options-market-maker hedging (gamma rebalancing as IV collapses post-
   event), and pre-positioned institutional shorts/longs taking profits.
   This re-asserts the institutional view, which by assumption is *opposite*
   the surface read (otherwise they wouldn't have positioned 24h-pre against
   the headline they expected).

4. **The trade**: fade the sign of the T+0 → T+15 min move. If NDX spiked
   +0.5% in the first 15 min post-announce, SHORT NDX from T+15 to T+60.
   If NDX dropped -0.5% in the first 15 min, LONG NDX from T+15 to T+60.
   The bigger the first-15-min move, the bigger the expected reversion.

5. **Why retail-tradeable**: the window is too slow for HFT (60 min hold
   period; HFT operates in seconds). It's too fast for fundamental shorts
   (no 60-min hold strategy makes economic sense at >$5M notional given
   exit slippage). It falls in the coverage gap.

## Key references

- **Lucca & Moench (2015)**, *Journal of Finance*. Canonical pre-FOMC drift
  on SPX — establishes the 24h-pre regularity that motivates the *post*
  leg's complement framing.
- **Hu, Pan, Wang, Zhu (2022), "Premium for Heightened Uncertainty:
  Explaining Pre-Announcement Market Returns", *Journal of Financial
  Economics*.** Documents that pre-FOMC drift is a risk-premium accrued
  through the *anticipation* window; post-event the premium has been
  delivered. Implies post-event mean-reversion is the natural counterpart.
- **Internal**:
  - `experiments/_live/macro_drift/macro_drift.md` — deployed 24h-pre-FOMC
    LONG NDX. This thesis is the post-event complement.
  - `experiments/_live/lunch_fade/lunch_fade.md` — same "amateur flow in
    the gap between institutional shifts" framing, applied to lunch-hour
    rather than post-event window.
  - `experiments/pre_fomc_drift/pre_fomc_drift.md` — recent REJECT on the
    FX-side of FOMC; corroborates that FOMC drift is equity-vessel-specific.
    Post-FOMC fade should also be tested primarily on NDX, secondarily on
    EURUSD (as a robustness check).

## Signal math — pre-commit pseudo-code

```
Parameters (≤ 5):
  FIRST_REACTION_MIN    = 15     (T+0 → T+15 min defines "spike direction")
  HOLD_MIN              = 45     (T+15 → T+60 min is the fade-hold window)
  SPIKE_FLOOR_BPS       = 10     (minimum |first-15min move| to trigger;
                                   skip flat events where no spike to fade)
  COST_BPS_DEFAULT      = 5      (NDX H1 CFD spread ~3-5 bps on Eightcap;
                                   intraday so no swap)

Per FOMC event E at announce_utc:
  t0    = announce_utc
  t15   = t0 + 15 min
  t60   = t0 + 60 min

  px_0  = NDX M5 close at t0
  px_15 = NDX M5 close at t15
  px_60 = NDX M5 close at t60

  spike_bps  = (px_15 - px_0) / px_0 * 10000

  if |spike_bps| < SPIKE_FLOOR_BPS: skip event (no spike to fade)

  # FADE: enter at t15, opposite sign to spike, exit at t60
  fade_direction = -sign(spike_bps)
  gross_bps      = fade_direction * (px_60 - px_15) / px_15 * 10000
  net_bps        = gross_bps - COST_BPS_DEFAULT
```

Free param count: 4 (FIRST_REACTION_MIN, HOLD_MIN, SPIKE_FLOOR, COST). Well
under the 7-cap.

Direction null-check: run CONTINUATION (LONG the spike direction in T+15
→ T+60 window) as null. If continuation outperforms fade by the threshold,
0DTE-era retail-spike-continuation is the actual mechanism — different
thesis, but same data informs.

## Why retail-accessible

- **NDX100 H1 / M5 CFD on Eightcap**: same instrument as deployed
  `event_calendar`. Spread ~3-5 bps RT on NDX H1.
- **Intraday entry/exit**: zero swap. Entire 60-min hold is well within
  the broker session-day.
- **Same EA scaffolding as `event_calendar.mq5`**: calendar-driven
  trigger, time-delay execution (T+15 entry, T+60 exit). New magic
  number, ~8 trades/yr (FOMC frequency).
- **Capacity moat**: not a strong moat by itself (this isn't an
  institutional-absence thesis at the same level as `lunch_fade`), but
  the 60-min hold on a calendar event is a smaller-EV opportunity than
  institutional desks staff for. Most quantitative funds either don't
  trade FOMC at this granularity or only via systematic vol-arb on
  options (different mechanism).

## Universe

- **Primary instrument**: NDX100 H1 CFD (Eightcap, datalake / `ohlc_data/
  NDX100_M5.csv` for fine-resolution measurement, aggregated to per-event
  T+0 / T+15 / T+60 timestamps).
- **Secondary instrument** (Phase 3, robustness only): EURUSD M5. If the
  mechanism works on NDX, test if it also shows up on the dollar-side
  (would be the post-event analog of the rejected `pre_fomc_drift` —
  same instrument, different timeframe).
- **Calendar**: re-uses `experiments/_live/macro_drift/fomc_calendar.csv`
  (~56 historical events 2019-2026 with NDX M5 coverage).

## Expected performance (pre-run, with explicit Phase 0 magnitude floor)

**Phase 0 magnitude check (binding before Phase 2 expansion)**:

Compute the simple mean of `gross_bps` (post-event fade direction net of
zero cost) on the full ~56-event sample with SPIKE_FLOOR_BPS = 10. The
**Phase 0 floor is +5 bps gross mean** — if the average post-event reversion
is less than +5 bps, the mechanism doesn't clear realistic cost (~5 bps RT
+ slippage) regardless of regime breakdown. **Abort to REJECT before
running the full Phase 2 sweep**, per Lesson A.

If Phase 0 passes, point-estimate priors:
- **Gross per-event reversion**: +8 to +20 bps after the SPIKE_FLOOR
  filter (events with no first-15-min spike are excluded).
- **Net per-event (5 bps cost)**: +3 to +15 bps.
- **Trade cadence**: ~6-8 trades/yr (FOMC events that have a >10 bps
  first-15-min spike — most do).
- **Sharpe (annualized × sqrt(8))**: +0.30 to +0.80.
- **WR**: 55-65%.
- **MDD**: -5% to -12% per-event-equity-curve.

## Fail conditions (pre-committed, BEFORE running Phase 2)

Phase 0 ABORT:
- **Gross mean per-event < +5 bps** on full sample (mechanism magnitude
  below realistic cost) → REJECT without running Phase 2, document the
  "0DTE-era post-event flow is faster than 60min" methodology lesson.

Phase 2 KILL (if Phase 0 passes) at 5 bps RT cost:
1. **Full-sample net mean per-event ≤ +3 bps** (FADE direction).
2. **W3 (2023-2026 holdout) mean per-event ≤ +0 bps** — modern regime
   must clear zero net. Lesson A binding.
3. **Direction null-gap (FADE − CONT) < +5 bps**. Load-bearing pre-commit.
   If CONT wins, 0DTE-era post-event spike continues, lesson #43 extends
   to post-event horizon — different mechanism, REJECT this thesis.
4. **Trade count after SPIKE_FLOOR < 30**. Need adequate sample given
   ~8/yr cadence.
5. **WR < 50% AND PF < 1.2** (joint).
6. **MDD > 15%** per-event-equity-curve.
7. **Walk-forward 3-fold OOS Sharpe**: mean ≥ +0.20 AND min ≥ -0.10.
8. **SPIKE_FLOOR sweep sanity** (5/10/15/20 bps): edge should be monotone
   increasing with SPIKE_FLOOR (bigger first-15-min spikes should produce
   bigger reversions). U-shaped or noisy = in-sample artifact per
   Lesson C from cfd_wed_rollover REJECT.
9. **Cost-stress at 10 bps RT** (worst-case slippage during NDX
   post-event vol): net mean still > 0.

PASS only if Phase 0 floor PLUS all of (1)-(9) hold for the FADE direction.

## Why this might fail (red flags)

1. **0DTE-era HFT absorbs the spike in <60 seconds.** This is the
   user-pre-flagged concern and the most likely failure mode. If
   institutional HFT plus options-market-makers are net long-gamma
   post-FOMC (rebalancing IV collapse), they may have already absorbed
   the retail spike by T+5 min, leaving no T+15 → T+60 reversion. Phase 0
   magnitude check is the diagnostic.

2. **The "amateur flow at T+0 → T+15" assumption is dated.** Post-2020
   retail tooling (Robinhood, Webull) is faster than the model assumes.
   The actual amateur-pile-in may concentrate T+0 → T+3 min and exhaust
   by T+5 min, meaning the T+15 → T+60 window is already post-flow, not
   mid-flow. The SPIKE_FLOOR_BPS = 10 threshold partly defends against
   this (only fade events where the first-15-min showed meaningful
   amateur flow), but if the threshold has to be raised to 30+ bps to
   find edge, trade cadence collapses below the n=30 floor.

3. **Direction can invert post-2022.** Lesson #43 (0DTE flipped intraday
   MR to continuation on US indices) has a natural extension to
   post-event 15-60 min flow. If the lesson generalizes, the FADE
   direction loses systematically while CONTINUATION wins — testable via
   the direction null-gap.

4. **The trigger ignores headline content.** Hawkish vs dovish surprises
   may have asymmetric post-event behavior (asymmetric retail reaction
   to "Fed hawkish" vs "Fed dovish" headlines, by way of asymmetric
   social-media virality). The mechanism is hypothesized as direction-
   agnostic (fade whichever sign showed up); if asymmetry is real, one
   side will dominate the kill criteria pass and the deploy form would
   need a headline-classifier (out of scope, would need NLP layer).

5. **NDX-vs-SPX confound**: NDX is more retail-popular than SPX (Mag7
   concentration). The mechanism may work on NDX but not SPX. Phase 3
   could add SPX as a robustness check — if it works on both, mechanism
   is index-generic; if NDX-only, mechanism is retail-concentration
   specific (which would corroborate the broader "where retail is
   dominant flow" thesis class).

6. **`event_calendar` is already in the book.** Adding post-FOMC fade
   creates two trades on the same calendar event. Per-event MDD risk
   stacks: a hawkish-shock event where pre-LONG loses AND the spike
   continues (post-FADE loses too) double-loses. Pre-commit position-
   sizing rule: half-risk if deploy alongside `event_calendar`, or
   single-EA-only-mode-toggle.

## Phase 1 → Phase 0 → Phase 2 plan (checkbox)

- [x] Read lesson #43, #45, Lessons A/B/C from cfd_wed_rollover REJECT,
      `event_calendar` thesis (24h-pre leg), `lunch_fade` (amateur-flow
      framing), `pre_fomc_drift` REJECT (FX-side falsification context)
- [x] Write this thesis with pre-committed kill criteria + Phase 0 floor
- [ ] **Phase 0 magnitude check** (binding, runs in ~30 min):
      - Compute per-event (T+0 → T+15) signed spike and (T+15 → T+60)
        opposite-direction realization on the full 56-event sample
      - Mean of FADE-direction-gross-bps across all events with |spike|
        > SPIKE_FLOOR
      - If mean < +5 bps → REJECT without Phase 2 (write the
        "post-event-fade-is-too-fast-in-modern-regime" tombstone, log
        as methodology lesson)
- [ ] If Phase 0 passes, build `post_fomc_amateur_fade_demo.py`:
      - NDX M5 entry/exit at T+15 / T+60 anchors
      - Per-event FADE primary + CONT null
      - SPIKE_FLOOR sweep diagnostic
      - Regime breakdown 3-window (W1/W2/W3)
      - Walk-forward 3-fold
      - Cost-stress 5/10/15 bps RT
      - Secondary EURUSD pass (robustness only — not a primary kill)
- [ ] Update this doc with results + verdict + mechanistic interpretation
- [ ] If PASS: Phase 3 (other event types — CPI/NFP/RS post-event,
      SPX/ES robustness, position-sizing with `event_calendar` joint
      MDD model)
- [ ] If REJECT: tombstone with mechanism specificity (HFT-absorption /
      0DTE-continuation generalization / asymmetric-headline / etc.)

## Files

- `post_fomc_amateur_fade.md` — this doc
- `post_fomc_amateur_fade_demo.py` — Phase 2 simulator (TBD; only built
  if Phase 0 passes)
- Data: `ohlc_data/NDX100_M5.csv` (already on disk); FOMC calendar reused
  from `experiments/_live/macro_drift/fomc_calendar.csv`
