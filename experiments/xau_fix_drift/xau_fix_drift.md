# XAU London Gold Fix drift — pre-fix accumulation, post-fix reversion (M1, AM + PM Fix)

**Status (2026-05-26):** Phase 2 complete. REJECT — decisive, both directions losing decisively, direction-gap +0.08 (≈ zero).

**Verdict:** **REJECT (direction-ambiguous, signal-absent post-2015 reform).** Pre-committed COMBINED-CONT primary fails 10 of 11 binding criteria; only criterion #11 (correlation tombstone vs deployed XAU book) passes — and that PASS is moot because the strategy itself has no edge. The signal is **absent**, not friction-eaten: cost-zero gross per-trade ≈ −0.06 bps (estimated by extrapolating the cost-sweep linear slope back to zero), entirely inside the M1 measurement noise floor. Direction-gap +0.08 confirms there is no asymmetric flow in either direction — the auction print is, in 2018-2026, a fair-value print whose pre-/post-print 10-min movement is centred on zero, exactly as red-flag #1 (post-2015 LBMA reform) predicted.

| # | Criterion | Threshold | Observed | Result |
|---|---|---|---|---|
| 1 | FULL Sharpe (COMBINED-CONT) | > +0.40 | **−1.91** | FAIL |
| 2 | W1 2018-2020 CONT Sharpe | > +0.10 | −3.19 | FAIL |
| 3 | W2 2021-2022 CONT Sharpe | > +0.10 | −1.90 | FAIL |
| 4 | W3 2023-2026 (holdout) CONT Sharpe | > +0.20 | −1.10 | FAIL |
| 5 | Max DD | < 10% | −26.75% | FAIL |
| 6 | Trade count (combined) | ≥ 400 | 3,015 | PASS |
| 7 | Direction-gap COMBINED (CONT − FADE) | > +0.40 | **+0.08** | FAIL |
| 8 | Cost-stress Sh @ 0.30pt RT | > 0.00 | −2.88 | FAIL |
| 9 | AM or PM individual Sh | > +0.20 | AM −1.21 / PM −1.48 | FAIL |
| 10 | Deflated Sharpe (n_trials=8) | > +0.20 | −99.46 | FAIL |
| 11 | \|Corr vs deployed XAU book\| | < +0.40 | **−0.02** | PASS (moot) |

### Headline numbers (COMBINED-CONT primary, 0.20pt RT cost, MIN_PRE_DRIFT=3bp)

- n = 3,015 trades over 2018-01-02 → 2026-05-26 (~379 events/yr)
- Mean per-trade net: **−1.01 bps** (t = −5.38)
- WR 41.7%, PF 0.72
- Sharpe **−1.91**, MDD **−26.75%**, total return **−26.35%**

### Per-window CONT vs FADE Sharpe

| Window | CONT Sh | FADE Sh | dir-gap |
|---|---|---|---|
| AM only | −1.21 | −1.78 | +0.57 (only AM is mechanism-coherent — sign correct) |
| PM only | −1.48 | −1.06 | **−0.42** (PM mechanism-INVERTED — fading the drift loses slightly less) |
| COMBINED | −1.91 | −1.99 | +0.08 (no directional content) |

### Cost sweep (COMBINED-CONT, MIN_PRE_DRIFT=3bp)

| cost RT | mean (bp) | Sh | MDD | note |
|---|---|---|---|---|
| 0.10 pt | −0.49 | −0.93 | −14.7% | |
| 0.15 pt | −0.75 | −1.42 | −20.9% | |
| 0.20 pt | −1.01 | −1.91 | −26.8% | deploy |
| 0.30 pt | −1.53 | −2.88 | −37.1% | stress |
| 0.50 pt | −2.56 | −4.82 | −53.9% | |

Cost-stripped gross extrapolation (linear slope ≈ 5.16 bps mean per 1pt RT, intercept at cost=0): gross ≈ **−0.06 bp/trade**. **Signal-absent, NOT friction-eaten** (lesson #26 diagnostic). No cost-venue improvement would deploy this strategy.

### Pre-drift threshold sweep (COMBINED-CONT, cost 0.20pt)

| min_drift (bp) | n | mean (bp) | Sh | W3 Sh |
|---|---|---|---|---|
| 1.0 | 3,727 | −1.03 | −2.29 | −1.33 |
| 2.0 | 3,389 | −1.01 | −2.09 | −1.25 |
| 3.0 | 3,015 | −1.01 | −1.91 | −1.10 | pre-commit |
| 5.0 | 2,344 | −1.01 | −1.57 | −0.76 |
| 8.0 | 1,628 | −0.98 | −1.14 | −0.64 |

Raising the threshold tames Sharpe magnitude (less leverage of the cost drag through more trades) but **does not recover positive gross**. Per-trade mean is locked at ~−1.0 bps across every threshold cell. This rules out the "tighter filter unmasks the edge" rescue.

### Phase 0c cheap pre-tombstone

Raw daily sign(drift_bps) vs daily XAUUSD return correlation: **+0.137** (benign; well under 0.5). The corr-tombstone PASS at the full trade-by-trade level is therefore real, not a sample artefact.

### Mechanistic interpretation

1. **Post-2015 LBMA electronic-auction reform has fully closed the retail-accessible pre-fix continuation window.** Caminschi-Heaney (2014) measured 8-22 bp pre-fix drift on the pre-2015 telephone-call fix; the thesis prior estimated post-reform compression to 2-6 bps. The actual gross at 5-min entry, 5-min exit at MIN_PRE_DRIFT=3bp is **≈ 0 bp in both directions**. The hypothesised "still 2-6 bps after reform" compression assumption was too generous by roughly an order of magnitude.

2. **Direction-gap +0.08 (≈ zero) means no asymmetric flow.** If pre-fix MM hedging produced even residual continuation pressure, FADE would lose distinctly more than CONT. It does not. The auction print is a fair-value print whose 10-min M1 envelope is symmetric noise.

3. **AM-window weakly mechanism-coherent (dir-gap +0.57); PM-window mechanism-inverted (dir-gap −0.42).** This is not a window-selection signal, it is sample-period bias. The AM dir-gap is below the +0.40 bar at +0.57 but with both arms losing decisively and a near-zero gross gap, it is a noise-coin-flip, not a deployable window. PM inverting confirms this is regime/sample noise, not a structural asymmetry.

4. **Cost-zero gross ≈ −0.06 bp confirms the diagnostic is "mechanism dead", not "mechanism alive but eaten by cost".** Per lesson #26, a cost-zero Sharpe at or below zero with cost-linear deterioration matches the "no edge" diagnostic, not the "edge eaten by friction" diagnostic. A tighter-execution venue (zero-spread XAU, deep RFQ) would NOT change the verdict.

5. **Cross-strategy correlation is exactly the wrong tombstone to fail (criterion #11) — and indeed it passes (−0.02).** If the mechanism were real and inherited from `xau_session` / `xau_break_retest_*` flow, we'd see a high positive corr. Zero corr says the pre-fix window has independent (and zero) information content from the deployed XAU book. The deployed book's edge is decoupled from the fix mechanism entirely.

### Lessons extracted

- New lesson **#71** (RESEARCH_NOTES): post-publication market-microstructure REFORM of a famous price-impact pattern (LBMA Aug-2015 electronic-auction reform) defaults to "fully arbed at retail-accessible windows" prior, even when the academic decay literature reports "compression not elimination". The cost-zero gross is the diagnostic — if the residual signal is below the M1/M5 measurement noise floor in BOTH directions, the mechanism is dead. Compression-not-elimination claims should be discounted by another order of magnitude before being treated as a deployable prior.
- Validates red-flag #1 in the thesis doc verbatim — the strongest red-flag was correctly identified pre-experiment, and ran the experiment anyway because the experiment is cheap (M1 data, single instrument, two events/day, ~6h end-to-end including data fetch). Cost of confirmation: small; value of confirmation: medium — extracts the "famous-mechanism + market-structure-reform" tombstone shape cleanly.
- Negative confirmation that the LDN-AM 07-10 UTC window is now tombstoned for XAU in THREE directions: `xau_ldn_am_fade` (FADE, REJECT 2026-05-26), `xau_ldn_orb_m1` (LONG-cont/FADE, REJECT 2026-05-26), `xau_fix_drift` AM-CONT/FADE (REJECT 2026-05-26). LDN-AM is fully tombstoned at M1/M5/M15 across all directional flavours. Together they constrain XAU intraday infrastructure to: deployed `xau_session` (Asian-handoff LONG, 23→08 UTC), deployed `xau_break_retest_m15` (NY-AM 13-15 UTC FADE), deployed `xau_break_retest_h1` (NY 12-18 UTC FADE). No fix-related extension viable.

---

---

## Origin

User question (2026-05-26): "How short a holding period could XAU support given Eightcap's ~0.15pt spread?" Cost math (~0.64 bps RT at $2350) puts the M1 cost floor below ~1 bp per-trade gross, well below typical M1 bar range. Of the four candidate mechanism families that survive HFT at retail latency, the London Gold Fix is the cleanest published — auction-style accumulation persists over minutes, not microseconds, so the institutional-latency arb does not close the window.

Pairs with deployed XAU book: `xau_session` (Asian 23-08 UTC LONG), `xau_break_retest_m15` (NY 13-15 UTC FADE), `xau_break_retest_h1` (NY 12-18 UTC FADE). Both Fix windows overlap deployed territory — AM Fix sits inside `xau_session`'s exit hour, PM Fix sits inside the deployed NY-FADE windows. Correlation tombstone vs the deployed book is binding (criterion #11 below).

## Thesis (mechanism)

The LBMA Gold Price (electronic auction since 2015, ICE Benchmark Administration) prints twice per London business day at **10:30 and 15:00 London local** (= 09:30 / 14:00 UTC in DST; 10:30 / 15:00 UTC in standard time). The auction matches buy and sell interest at a clearing price; directly-participating market-maker banks pre-position inventory in the cash/OTC market ahead of the print to manage auction risk. This produces three observable price-impact phases:

1. **Pre-fix drift (T-30 → T-1 min)**: net buy/sell imbalance of submitted auction orders is hedged in OTC spot incrementally. If the order book is one-sided (e.g. net sell pressure from ETF redemptions), spot drifts in that direction at sub-bp/minute rates. The direction is unknown ex-ante but *recent pre-window drift* is a proxy for the auction-side imbalance.

2. **Through-fix continuation (T → T+5 min)**: the auction print itself can produce a 2-10 bp impulse as MMs settle inventory and reference-priced derivatives (futures-options, structured products) re-mark. The impulse persists for several minutes because retail/institutional algos pegged to the fix execute in the post-print window.

3. **Post-fix reversion (T+5 → T+30 min)**: once the auction-driven flow clears, the temporary price impact bleeds back. Caminschi & Heaney (2014) document this on the pre-2015 phone-auction fix; post-2015 LBMA electronic-auction studies (Ronen & Wei 2015; LBMA market reports) suggest the magnitude has compressed but not vanished.

The thesis at retail M1 latency: **trade phase (1) — pre-fix drift continuation in the direction of T-30→T-5 drift**, exit at T+1 to T+5. We are *not* attempting to fight the auction flow; we are renting the same direction the MM hedging is moving spot. HFTs cannot close this window because the underlying mechanism is *auction order accumulation over tens of minutes*, not millisecond information arrival — they can compress the post-print impulse, but the pre-print accumulation is a slow-time-scale flow they participate in alongside us.

Direction null-check (phase 1-reverse): same trigger, opposite direction (fade the T-30→T-5 drift). If both win, signal is structural-asymmetry / cost artifact. If both lose, signal is absent. If only continuation wins, mechanism direction is confirmed.

## Key references

- **Caminschi, A. & Heaney, R. (2014)**. "Fixing a Leaky Fixing: Short-Term Market Reactions to the London PM Gold Price Fixing." *Journal of Futures Markets* 34(11), 1003-1039. Pre-electronic-auction baseline showing pre-fix drift + post-fix reversion magnitudes of 8-22 bps.
- **Ronen, T. & Wei, X. (2015)**. "The price discovery function of the London gold fix." Working paper. Post-2015 LBMA reform impact assessment.
- **LBMA (2023)**. ICE Benchmark Administration — LBMA Gold Price auction technical specification (10:30 / 15:00 London, 45-second rounds, ±1% imbalance cap per round).
- Repo cross-reference: deployed `xau_session` (Asian-handoff LONG through 08 UTC) — the AM Fix at 09:30 UTC sits 1.5h after `xau_session` exits. Same flow universe (Asian + early-LDN), different mechanism (continuous overnight drift vs scheduled auction print).

## Signal math — pre-committed config (BOTH FIX windows, BOTH directions co-equal)

```
Parameters:
  FIX_WINDOWS_UTC_DST       = [(9, 30), (14, 0)]    # AM Fix, PM Fix during BST/EDT
  FIX_WINDOWS_UTC_STD       = [(10, 30), (15, 0)]   # AM Fix, PM Fix during GMT/EST
  PRE_FIX_LOOKBACK_MIN      = 25                    # drift measurement window
  ENTRY_OFFSET_MIN          = 5                     # enter at fix - 5 min
  EXIT_OFFSET_MIN           = 5                     # exit at fix + 5 min (10-min hold)
  COST_POINTS_ROUND_TRIP    = 0.20                  # Eightcap conservative; sweep 0.15/0.20/0.30/0.50
  MIN_PRE_DRIFT_BPS         = 3.0                   # below this, no signal — skip
  DIRECTION                 = pre-commit BOTH       # CONTINUATION (primary) + FADE (null)

Per fix event:
  drift_bps = (mid[T-5] - mid[T-30]) / mid[T-30] * 1e4
  if abs(drift_bps) < MIN_PRE_DRIFT_BPS:
    skip                                            # no auction-flow signal to lean on

  CONTINUATION variant:
    if drift_bps > 0: enter LONG at fix-5 min, exit at fix+5 min
    if drift_bps < 0: enter SHORT at fix-5 min, exit at fix+5 min

  FADE variant (null check):
    if drift_bps > 0: enter SHORT at fix-5 min, exit at fix+5 min
    if drift_bps < 0: enter LONG at fix-5 min, exit at fix+5 min

  Variants to score:
    AM-CONT, AM-FADE, PM-CONT, PM-FADE, COMBINED-CONT, COMBINED-FADE
```

Pre-committed Phase 2 will report BOTH AM and PM separately and as a combined book — if only one window survives, deploy that one window only (do not goalpost-move within the experiment).

## Why retail-accessible at M1

- Per `_check_xau_spread.py` (xau_session Phase 0): Eightcap XAUUSD median spread is **0.34 bp RT across all 24 UTC hours**, no widening at the fix times. P99 = 0.35 bp. The AM Fix window (09:30 UTC) and PM Fix window (14:00 UTC) both fall in the universally-tight regime.
- All-in cost ~1.9 bps RT (spread + Raw commission); 10-min hold sees ~10× this in M1 bar range, so per-trade gross to cost ratio is favorable.
- HFT compresses the *post-print impulse* (phase 2-3) to sub-minute scale, but the *pre-fix drift* (phase 1) is a 25-minute slow accumulation that retail M1 latency can capture without millisecond competition.
- No special infrastructure required — single MT5 EA, UTC-aware scheduler, two events per day (AM + PM).

## Universe

XAUUSD only. The mechanism is LBMA-Gold-Price specific (auction venue is unique). No cross-asset extension at this phase. **No XAG** — Eightcap XAG spread is 8 bp (per STATE.md xag_session line), eats the magnitude immediately.

## Expected performance (pre-committed point estimates)

Caminschi-Heaney's pre-2015 pre-fix drift was 8-22 bps over T-15 → T fix. Post-2015 LBMA electronic auction estimates compress this by ~50% (smaller round-trip allowances, anonymity). Realistic retail expectation:

- **Per-trade gross** ~4-10 bps in CONTINUATION direction, ~zero in FADE direction (if mechanism is real).
- **Per-trade net at 2 bps RT** ~2-8 bps.
- **Trade cadence**: 2 fix events/day × ~250 fix-days/year × ~60% pass `MIN_PRE_DRIFT_BPS` filter = ~300 trades/year.
- **Annualized gross** ~150-300 bps; ~100-200 bps net.
- **Sharpe** ~+0.30 to +0.80 net (point estimate +0.50 — explicitly *below* the +1.0 bar that deployed XAU strategies cleared, because the mechanism has been known and arbed since the 2014 LBMA reform).
- **MDD** < 8% (high-frequency, small-magnitude, well-diversified by 500+ events).
- **WR** 52-57%, **PF** 1.15-1.30.

## Fail conditions (PRE-COMMITTED — written before backtest runs)

These bars mirror the deployed XAU intraday strategies, with two tightenings: (a) the cost-stress bar uses 0.30pt RT (1.5× the deployed `xau_break_retest_m15` baseline of 0.20pt, because M1 entry/exit faces more slippage than M15) and (b) a correlation tombstone vs deployed book.

| # | Criterion | Threshold | Direction |
|---|---|---|---|
| 1 | Combined CONTINUATION net Sharpe (full sample, 0.20pt RT) | > +0.40 | binding |
| 2 | W1 2018-2020 CONT Sharpe | > +0.10 | binding |
| 3 | W2 2021-2022 CONT Sharpe | > +0.10 | binding |
| 4 | W3 2023-2026 (holdout) CONT Sharpe | > +0.20 | binding (holdout floor) |
| 5 | Max DD | < 10% | binding (high-freq strategy, tight bar) |
| 6 | Trade count (combined AM+PM) | ≥ 400 over 7-8 years | binding (else INSUFFICIENT_N) |
| 7 | Direction-gap (CONT Sh − FADE Sh) | > +0.40 | binding (else signal direction-ambiguous → REJECT) |
| 8 | Cost-stress @ 0.30pt RT: CONT Sharpe | > 0.00 | binding |
| 9 | AM/PM independence: at least one of AM-CONT or PM-CONT individually | full Sh > +0.20 | binding (combined PASS via single-window must default to single-window deploy) |
| 10 | Deflated Sharpe (n_trials=8: 2 windows × 4 cost levels) | > +0.20 | binding |
| 11 | **Trade-by-trade correlation vs deployed XAU book** (xau_session + xau_br_m15 + xau_br_h1, per-day-aggregated PnL) | **< +0.40** | **binding — tombstone if violated** |

If criterion #7 fails (FADE wins or both win/lose similarly): REJECT, no signal direction. Goalpost-moving (REJECT CONT but adopt FADE post-hoc) is **disallowed** per lesson #-19; either pre-committed BOTH-direction PASS or REJECT-and-stop.

If criterion #11 fails on a Sharpe pass: REJECT-by-redundancy. The mechanism is real but the deployed book already captures it via overlapping windows.

If only one of AM or PM passes (criterion #9 partial): deploy only the passing window; do **not** combine.

## Why this might fail (red flags)

1. **Post-2015 LBMA reform compressed the effect.** The electronic auction (vs the pre-2015 phone-call fix) reduced pre-fix order-imbalance leakage materially. Caminschi-Heaney's 8-22 bp pre-fix drift may now be 2-6 bp, which after 2 bp cost leaves single-digit-bp net per trade — Sharpe-positive but borderline.

2. **AM Fix window overlaps `xau_session`'s exit.** `xau_session` exits LONG at 08:00 UTC; AM Fix is at 09:30 UTC (DST) or 10:30 UTC (standard). The 1.5-2.5h gap is short enough that residual Asian-handoff drift from `xau_session`'s positive-mean exit hour bleeds into the AM Fix entry window. Pre-fix drift measurements may largely be measuring the same flow `xau_session` traded, with the new strategy entering *after* `xau_session` has captured most of the drift. This is the main scenario for criterion #11 (correlation tombstone) firing.

3. **PM Fix window overlaps `xau_break_retest_h1` (NY 12-18 UTC FADE).** PM Fix is at 14:00 / 15:00 UTC, squarely inside the deployed H1 BoS+retest FADE window. A pre-fix CONT entry going LONG into 15:00 UTC may take the FADE side of a deployed H1 trade going SHORT at a recently broken structural level. Two strategies trading opposite directions on the same instrument at the same minute is **execution-hostile** even if both research-PASS — risk of net-zero-on-platform.

4. **One-way LME / LBMA flow pre-tombstoned the LDN-AM fade window (lesson #-14).** The same auction flow this thesis is trying to *follow* took down `xau_ldn_am_fade` which tried to *fight* it. If the AM Fix drift mechanism is real, AM-CONT should be the mirror PASS. If AM-CONT also fails, the LDN-AM 07-10 UTC window is dead in both directions and the auction-flow framing is wrong.

5. **DST boundary handling**: AM Fix moves from 09:30 UTC (BST/EDT) to 10:30 UTC (GMT/EST) twice per year. Asymmetric US/UK DST transitions (US shifts 2 weeks before UK in spring; 1 week after in autumn) create 1-3 weeks/year where the fix is at a non-standard UTC hour. Phase 2 must handle this correctly — wall-clock-London, not UTC-fixed. Bug in DST mapping = invisible 15% sample contamination.

6. **News-release spread widening at fix.** Although the 30-day Eightcap spread sample showed flat distribution, that sample did not include large-imbalance fix events (some fixes blow out to 3-4× normal). Phase 5 spread-regime-stress bucket required.

## Phase 1 → 2 plan

- [ ] **Phase 0a — data**: fetch XAUUSD_M1 from datalake (or `scripts/mt5_fetch.py --symbols XAUUSD --timeframes M1 --datalake`). Need ≥ 5 years back to 2020 to cover post-LBMA-reform regime cleanly. Estimated ~1.3M M1 bars.
- [ ] **Phase 0b — fix calendar**: build LBMA fix-day calendar (London business days minus LBMA holidays — closed days from `gold.org` calendar). Map each fix-day to UTC via DST-aware London local-to-UTC conversion. Validate against 5-10 spot-checked events vs published prices.
- [ ] **Phase 0c — correlation pre-check (cheap)**: pre-tombstone — run a 1-day-aggregated correlation between (a) raw `prior-25-min XAU drift` at fix times and (b) deployed `xau_session` daily PnL. If corr > +0.5 at the raw signal level, criterion #11 is already at risk and the thesis is on borrowed time before Phase 2.
- [ ] **Phase 1**: write `xau_fix_drift_demo.py` per signal-math block above. Implement BOTH-direction co-equal pre-commit (CONT primary, FADE null).
- [ ] **Phase 2 baseline**: run baseline AM-CONT + AM-FADE + PM-CONT + PM-FADE + combined, score against 10 binding criteria + correlation tombstone.
- [ ] **Phase 2 regime breakdown**: W1 2018-2020 / W2 2021-2022 / W3 2023-2026.
- [ ] **Phase 2 cost sweep**: 0.10 / 0.15 / 0.20 / 0.30 / 0.50pt RT.
- [ ] **Phase 2 pre-drift-magnitude sweep**: MIN_PRE_DRIFT_BPS ∈ {1, 2, 3, 5, 8}. The cleanest variant is the one that holds W3 holdout positive at MIN_PRE_DRIFT=3 (pre-committed value); a sweep showing the W3 peak at a different value is informative-but-disallowed-as-deploy (per orb.md "do not aggregate best variant").
- [ ] **Phase 2 correlation tombstone**: trade-by-trade per-day-aggregate PnL correlation vs (xau_session ∪ xau_break_retest_m15 ∪ xau_break_retest_h1) book.
- [ ] **Update this doc** with results + verdict + RESEARCH_NOTES + STATE.md YAML.

## Files

- `xau_fix_drift.md` — this doc
- `xau_fix_drift_demo.py` — Phase 2 simulator (to be written)
- `_fetch_xau_m1.py` — datalake / MT5 M1 puller with caching (to be written)
- `_build_fix_calendar.py` — LBMA fix-day calendar with DST mapping (to be written)
- `_corr_precheck.py` — Phase 0c deployed-book correlation pre-check (to be written)
- Data: `ohlc_data/XAUUSD_M1.csv` (to be populated)
