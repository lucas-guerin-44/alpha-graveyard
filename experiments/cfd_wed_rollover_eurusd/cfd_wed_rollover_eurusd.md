# CFD Wednesday triple-rollover unwind flow on EURUSD

**Status (2026-05-26)**: Phase 2 complete — **REJECT, tombstoned**.

**Verdict**: REJECT (3/10 pre-committed kill criteria passed). Wednesday
SHORT-EURUSD in the 10-20 UTC window does NOT produce a tradable edge on
EURUSD M5, 2019-01-02 → 2026-05-22. Headline: full-sample mean **-0.28 bps
net** (Sh -0.04) over 253 carry-filtered trades; the 2023-2026 holdout
(W3, 164 trades) is **-1.16 bps mean, Sh -0.23**. Walk-forward OOS Sharpe
mean -0.28, min -0.46 — IS positive in every split, OOS negative in every
split. Rate-diff tercile is u-shaped, not monotone — directly contradicts
the "mechanism scales with |rate-diff|" prediction.

## Phase 2 result table

| metric                          | result                  | pre-commit         | pass? |
| ------------------------------- | ----------------------- | ------------------ | ----- |
| full-sample mean (SHORT, 0.86bp)| **-0.28 bps**           | > +2 bps           | FAIL  |
| W3 mean (2023-2026, n=164)      | **-1.16 bps, Sh -0.23** | > +0 bps           | FAIL  |
| null-gap (SHORT − LONG)         | **+1.16 bps**           | ≥ +3 bps           | FAIL  |
| placebo pool (Mon/Tue/Thu/Fri)  | -0.33 bps (n=1037)      | < +1 bp            | PASS  |
| trade count                     | 253                     | ≥ 100              | PASS  |
| Sharpe                          | **-0.04**               | > +0.30            | FAIL  |
| MDD                             | -5.87%                  | < 15%              | PASS  |
| WF OOS mean Sh                  | **-0.28**               | ≥ +0.20            | FAIL  |
| WF OOS min Sh                   | **-0.46**               | ≥ -0.10            | FAIL  |
| cost-stress @ 2bp mean          | **-1.42 bps**           | > 0                | FAIL  |

Regime breakdown:
- W1 (2019-2020, n=58): +1.56 bps, Sh +0.45 — weakly positive
- W2 (2021-2022, n=31): +0.94 bps, Sh +0.11 — flat
- W3 (2023-2026, n=164): **-1.16 bps, Sh -0.23** — *negative*

Rate-diff tercile (q33=158bp, q66=209bp):
- LOW (≤158bp, n=92): -0.85 bps
- MID (158-209bp, n=80): **+6.93 bps, Sh +0.67**
- HIGH (>209bp, n=81): **-6.76 bps, Sh -0.59**

The thesis predicted monotone scaling with |rate-diff|; the data is
u-shaped, which is what you would expect under no underlying signal +
small-sample variance across three bins of ~80 trades.

Window-timing sweep best variant (entry 12 UTC / exit 22 UTC) was only
+0.40 bps gross net of cost — still trivial. Goodhart diagnostic (Tue
18-22 UTC) was -0.71 bps — edge has not migrated, it simply does not exist.

## Mechanistic interpretation (why it failed)

1. **The W1 → W3 sign-flip is the load-bearing pattern.** W1 was mildly
   positive (+1.56 bps), W3 went negative (-1.16 bps). This matches red
   flag #3 ("retail may have correctly shorted EUR during the 2022-2023
   hiking divergence — meaning the unwind would be LONG-EUR flow, opposite
   the thesis direction"). The post-2022 rate-divergence environment
   appears to have inverted the *direction* of retail positioning bias
   on EURUSD, which inverts the sign of any unwind-flow signature. The
   triple-swap mechanism may still exist mechanically, but the cohort
   producing it is no longer net-long-EUR.

2. **Rate-diff tercile is u-shaped, not monotone.** If the mechanism
   were truly carry-driven, HIGH would be the strongest, not the worst.
   The MID tercile result (+6.93 bps on 80 trades) is most likely small-
   sample noise dressed up as a mid-band sweet spot. The HIGH tercile
   straddles the 2024-2025 post-hike period, which sits in W3 — same
   sign-flip story.

3. **Gross signal is +0.58 bps at zero cost.** The thesis prior was +3
   to +12 bps gross. Off by an order of magnitude. The Wed-CFD-unwind
   flow either (a) is dwarfed by other Wednesday flows (CPI prints,
   PMI prints, EU economic calendar concentration on mid-week), or (b)
   does not exist at the magnitude assumed. The flow may be too small a
   fraction of EURUSD CFD volume to be detectable in 5-min closes even
   when the cohort is positioned correctly.

4. **Walk-forward is unambiguous.** All three IS windows are mildly
   positive; all three OOS windows are negative. This is the canonical
   signature of a non-existent edge that overfits weakly in-sample
   simply because there are degrees of freedom in the window
   specification. The IS/OOS gap is not a regime story — it's a
   sampling story.

5. **Placebo and Goodhart diagnostics both clean.** The non-Wed pool
   is -0.33 bps and Tuesday-evening is -0.71 bps. The mechanism has not
   migrated to a different day; it is simply absent. This makes the
   REJECT clean — no ambiguity about whether the edge exists somewhere
   else in time.

## Lessons for the project

- **"Retail is structurally long X" is not a stable assumption across
  rate-cycle regimes.** This thesis joins `pre_fomc_drift` (REJECT on
  EURUSD via cost-asymmetry) as a second EURUSD-thesis-killed-by-the-
  post-2022-rate-regime. Any future FX thesis that depends on retail
  positioning direction needs to gate on rate-regime or, better, on
  *measured* positioning (CoT-adjacent retail-broker data if obtainable).
  → RESEARCH_NOTES lesson candidate.

- **"Institutionally invisible" framing is necessary but not sufficient.**
  The capacity-moat argument for this thesis was strong: retail CFD
  microstructure genuinely is invisible to spot/futures/PB FX. But a
  mechanism being structurally inaccessible to institutional arb does
  not imply that the mechanism *exists* at detectable magnitude. The
  retail cohort generating the flow may be too small a share of EURUSD
  volume regardless of who else is in the venue. **Capacity moat ≠ edge.**

- **U-shaped factor-binding is a tell.** When a thesis predicts monotone
  scaling and the data delivers u-shaped, the burden of proof is on the
  experimenter to explain the inversion, not to claim a mid-band sweet
  spot. The MID-tercile +6.93bp here is the kind of in-sample artifact
  that would be a strategy if you didn't pre-commit. We pre-committed
  the monotone prediction; the u-shape fails it.

## What survives

Nothing for deployment. The strategy file `cfd_wed_rollover_eurusd_demo.py`
stays as the reference Phase 2 simulator for any future "Wednesday
flow" mechanism (e.g., USDJPY positive-carry version, or AUDUSD regime-
dependent version). The cross-pair Phase 3 plan (GBPUSD/USDJPY/AUDUSD)
is **deferred indefinitely** — given that the EURUSD test (largest carry
in the FX universe, cleanest setup) fails this thoroughly, the cross-pair
priors are now substantially worse, and we should require a positive
EURUSD result before paying the data-and-time cost of three more sims.

## Why this — the "institutionally invisible" framing

This thesis is the second deliberate test of the project's reframing:
**chase mechanisms that institutional capital structurally cannot access**.
Where `retail_overshoot_fade` exploits a *capacity-walled* universe, this
thesis exploits a **CFD-microstructure-walled** mechanism — a flow signal
that only exists in retail-CFD broker accounting and is completely invisible
to spot FX, FX futures, NDF markets, and institutional prime-brokerage FX.

The mechanism cannot be arbed at institutional scale because the
infrastructure that produces it (broker weekly swap-accrual triple) does
not exist in any institutional FX execution venue.

## Thesis (mechanism)

1. **Most retail FX/index CFD brokers (Eightcap, IC Markets, Pepperstone,
   FP Markets, others) apply triple-swap on Wednesday night to cover the
   financing accrual through the weekend.** The convention is industry-
   wide retail-CFD-specific. Spot FX accrues financing daily, no weekend
   triple. FX futures roll quarterly. Institutional accounts via prime
   brokerage use spot or futures, not retail CFDs. **The Wednesday triple
   exists only in retail CFD accounting.**

2. **On EURUSD specifically, LONG-EUR positions accrue negative carry**
   (Fed > ECB rate, currently ~150-200 bps differential). The Wednesday
   triple makes the long-EUR position pay **3× the normal -0.8 pip swap
   = -2.4 pips per night**, or roughly -2.1 bps RT-equivalent for a one-
   night hold. That cost is non-trivial relative to a typical retail FX
   trader's weekly P&L target.

3. **Retail traders aware of the triple convention systematically unwind
   long-EURUSD positions during the day on Wednesday** to flatten before
   the 22:00 UTC broker rollover (when the triple is charged). The
   unwind creates **directional sell-EUR pressure** concentrated in the
   Wednesday daylight hours (roughly 10:00-20:00 UTC, covering European
   morning through US market close).

4. **The sell pressure is detectable in the EURUSD price-action signature
   on Wednesdays** vs other weekdays. Specifically, SHORT EURUSD trades
   entered during the Wednesday unwind window should outperform the same
   trades on non-Wednesday weekdays (placebo control) by a statistically
   significant margin.

5. **The mechanism does NOT exist in spot FX, FX futures, or institutional
   FX venues** because none of them have a weekly triple-rollover charge.
   This is the institutional-absence argument: there's literally no flow
   to arb because the cohort generating the flow (CFD-retail-traders-aware-
   of-triple-swap) is a subset of retail-FX traders, and the venue is a
   subset of FX execution venues. Institutional capital cannot enter this
   trade.

## Key references

- **No direct academic literature** — broker-CFD microstructure is a
  retail-trading-community knowledge domain, not published in academic FX
  microstructure journals. Closest adjacencies:
  - **Levich & Pojarliev (2014), "Currency Strategies: The Origin of Excess
    Returns", *Financial Analysts Journal*.** Documents that carry-related
    flow signatures in FX have persistence; complements the directional
    expectation here even though the mechanism is CFD-financing-specific
    rather than carry-fund-rebalance-specific.
  - **Evans & Lyons (2002), "Order Flow and Exchange Rate Dynamics",
    *Journal of Political Economy*.** Establishes that flow has price
    impact in FX over short windows; the Wednesday-CFD-unwind flow is a
    specific named flow source predictable from broker convention.
- **Internal**:
  - `experiments/_live/lunch_fade/lunch_fade.md` — institutional-absence
    framing applied to NDX cash/futures basis during institutional lunch.
    This thesis applies the same framing to FX-CFD weekly accrual.
  - `experiments/pre_fomc_drift/pre_fomc_drift.md` — REJECT 2026-05-26 on
    EURUSD; the swap-asymmetric-cost concern flagged there is directly
    relevant to this thesis (cost modeling must be direction-asymmetric).
  - `docs/RESEARCH_NOTES.md` lesson #45 (retail-vs-institutional cost
    regime gates FX) — this thesis flips the framing: a flow that ONLY
    exists at the retail cost regime, structurally.

## Signal math — pre-commit pseudo-code

```
Parameters (≤ 7 hard cap):
  WED_ENTRY_HOUR_UTC    = 10     (Wednesday entry, start of European morning)
  WED_EXIT_HOUR_UTC     = 20     (Wednesday exit, before 22 UTC triple-rollover)
  CARRY_FILTER_BPS      = 100    (only trade when EUR-USD rate-diff > 100bp;
                                   mechanism strength scales with carry)
  HOLIDAY_EXCLUSION     = US holiday weeks (Thanksgiving, Christmas, NY,
                                   July 4th — broker rollover schedule shifts)
  COST_BPS_DEFAULT      = 0.86   (Eightcap EURUSD median RT spread,
                                   confirmed by user screenshot 2026-05-26)
  COST_BPS_SWAP_SHORT   = -0.28  (short EURUSD swap CREDIT per overnight;
                                   half-overnight if crossing 22 UTC = -0.14
                                   for the 10-20 UTC window which does NOT
                                   cross daily rollover, so this is zero)

Per Wednesday W in sample, IF (rate_diff(W) > CARRY_FILTER_BPS AND W not in
                                HOLIDAY_EXCLUSION):

  entry_t = W at WED_ENTRY_HOUR_UTC
  exit_t  = W at WED_EXIT_HOUR_UTC
  entry_px = EURUSD M5 close at nearest bar to entry_t
  exit_px  = EURUSD M5 close at nearest bar to exit_t

  # Primary direction: SHORT EURUSD (capturing the unwind sell-flow)
  short_gross_bps = (entry_px - exit_px) / entry_px * 10000
  short_net_bps   = short_gross_bps - COST_BPS_DEFAULT
                    + 0    (no overnight swap on 10-20 UTC same-day window)

Position: SHORT EURUSD, full notional, one trade per qualifying Wednesday.
```

Direction null-check: run LONG EURUSD on the same triggers as null. If LONG
outperforms SHORT, the mechanism is sign-inverted (unlikely given the rate-
differential is clearly Fed > ECB and the unwind direction is well-defined).

Placebo control: run the same WED_ENTRY_HOUR → WED_EXIT_HOUR window on
**non-Wednesday weekdays** (Mon/Tue/Thu/Fri) with same carry filter. If the
placebo also shows a SHORT-EURUSD edge of similar magnitude, the result is
a general-EUR-weakness-during-Eu-morning artifact, not Wednesday-specific.

## Why retail-accessible

- **EURUSD CFD spread on Eightcap is 0.86 bps RT** (confirmed by user
  screenshot 2026-05-26 at quote 1.1630, ~10 broker points = 1 pip = 0.86
  bps). Sub-1bp execution cost; this thesis is operationally retail-native.
- **No overnight hold required**: the 10:00 - 20:00 UTC window is entirely
  within the same broker server-day (Eightcap server ≈ EET, daily
  rollover at 22:00 UTC winter / 21:00 UTC summer). **Zero swap cost.**
  This avoids the swap-asymmetry concern that contaminated `pre_fomc_drift`.
- **Calendar-driven entry/exit**: same EA scaffolding pattern as
  `event_calendar.mq5` (date-conditional + time-of-day entry). One trade
  per week, ~52 trades/yr × carry-filter ≈ 30-45 active trades/yr.
- **Capacity moat is the binding feature**: the trade only exists because
  the venue is retail-CFD. Institutional capital cannot access the trade
  at the venue where the flow lives. Capacity at $5k-$500k notional is
  unconstrained relative to EURUSD spot-CFD liquidity.

## Universe

- **Primary instrument**: EURUSD M5 CFD, Eightcap MT5 / datalake /
  `ohlc_data/EURUSD_M5.csv`.
- **Research timeframe**: 2019-01-02 → 2026-05-22 (~7.4y, ~52 Wednesdays/yr
  × 7.4y = ~385 Wednesdays). Carry-filter and holiday-exclusion reduce
  active sample to estimated 230-280 events.
- **Not in scope for Phase 2** (deferred to Phase 3 if PASS):
  - GBPUSD (BoE > BoJ but smaller differential; check applicability)
  - USDJPY (positive-carry-LONG; thesis predicts neutral or weak positive
    edge in the opposite direction — long-USDJPY holders keep position
    through Wed to collect 3× positive swap)
  - AUDUSD, NZDUSD (carry direction depends on RBA/RBNZ vs Fed regime)
- **Deployment target**: Eightcap MT5 EURUSD spot CFD via single-pair
  scheduled EA, magic-number-distinct from `event_calendar`.

## Expected performance (point estimates, pre-run)

Honest priors:
- **Cost-zero gross per-trade signal**: +3 to +12 bps on SHORT-EURUSD
  Wednesday-window. Lower bound = mechanism barely visible above noise;
  upper bound = retail-cohort concentrated enough that flow is detectable.
- **Net per-trade**: +2 to +11 bps (after 0.86 bp spread, zero swap).
- **Trade cadence**: 30-45 trades/yr (52 Wed/yr × ~70% qualifying after
  carry-filter and holiday-exclusion).
- **Annualized gross**: 30 × 6 bps = ~1.8% / yr at the median expectation;
  45 × 10 bps = ~4.5% at the upper end. Modest absolute return; the value
  is **low correlation** with everything else in the book (no FX in the
  book; the mechanism is structurally distinct from event-drift /
  break-retest / session-handoff / ORB families).
- **Sharpe**: depending on intra-window volatility, +0.4 to +1.2 annualized.
- **WR**: 52-60% (small-edge directional bet on a noisy 10-hour window).
- **MDD**: -5% to -12%. Wednesday SHORT-EUR sometimes hits a EUR-spike
  (ECB news, ECB-member-speeches, EU surprise data) that overwhelms the
  unwind flow.

## Fail conditions (pre-committed, BEFORE running Phase 2)

Phase 2 KILL if ANY at 0.86 bps RT cost:

1. **Full-sample mean per-trade ≤ +2 bps** (SHORT direction). Mechanism
   needs to clear noise.
2. **W3 (2023-2026 holdout) mean per-trade ≤ +0 bps**. Modern regime
   must be positive.
3. **Direction null-gap (SHORT − LONG mean) < +3 bps**. Load-bearing
   pre-commit; if LONG also has positive mean of similar magnitude, the
   "Wednesday CFD-unwind" mechanism is contaminated by something else.
4. **Placebo (non-Wednesday weekdays, same window, same carry filter):
   SHORT-EUR mean > +1 bps OR placebo and Wed have overlapping CIs.** If
   the same SHORT-EUR edge shows on Mon/Tue/Thu/Fri, the result is not
   Wednesday-specific (probably general-EUR-weakness-during-Eu-morning),
   REJECT.
5. **Trade count after filters < 100** over full sample. Need enough
   events for statistical power.
6. **Annualised Sharpe (with carry filter on) ≤ +0.30** net of cost.
7. **MDD > 15%** on the full sample. Stop-loss discipline.
8. **Walk-forward 3-fold OOS Sharpe**: mean ≥ +0.20 AND min OOS ≥ -0.10.
9. **Cost-stress at 2 bps RT** (3× the live spread; covers broker spread
   widening or fill-time slippage): SHORT-EUR mean still > +0 bps.

PASS only if ALL of (1)-(9) hold for the SHORT direction.

## Why this might fail (red flags)

1. **The "everyone knows the triple" Goodhart problem.** If the
   Wednesday-triple-unwind pattern is widely known among retail FX traders,
   systematic players will pre-position SHORT-EUR on Tuesday late-day to
   capture the Wednesday flow, which would compress the Wed signal and
   inflate a "Tuesday-evening" signal instead. **Diagnostic**: scan
   Tuesday 18:00 UTC → Wednesday 02:00 UTC as a separate window; if that
   has stronger signal than Wed 10-20 UTC, the trade has migrated.

2. **Broker-specific rollover convention may not be Wednesday everywhere.**
   Some brokers (rarely) charge triple on Friday instead of Wednesday.
   Eightcap is confirmed Wednesday per public documentation, but if the
   broker silently changed mid-sample (which has happened in retail-broker
   industry), the historical signal would have shifted by 2 days mid-sample
   and the full-sample result would be diluted. **Diagnostic**: split the
   sample by year and check if any year is anomalously weak.

3. **The thesis assumes retail is structurally LONG EURUSD.** That
   assumption is likely true on aggregate over 2019-2026 (per public CoT-
   adjacent retail-positioning data), but **may flip in specific regimes**
   (especially W3 hiking cycle 2022-2023, where retail may have correctly
   shorted EUR-vs-USD on the rate-divergence theme — meaning the unwind
   would be LONG-EUR flow, opposite the thesis direction). If W3 mean
   per-trade is negative while W1/W2/W4 are positive, this is the
   regime-specific-positioning explanation.

4. **Rate-differential regime sensitivity.** The carry filter
   (CARRY_FILTER_BPS = 100) is designed to catch this: when EUR-USD rates
   converge to <100 bps (e.g., 2020-2021 zero-rate or 2024-2025 post-hike
   normalization), the unwind incentive is weaker because the triple-swap
   penalty is smaller in absolute pips. **Mechanism strength expected to
   correlate with |rate-diff|.**

5. **DST transitions could mis-align the window.** EU-Berlin DST shifts
   the broker-server-time relative to UTC by 1 hour twice a year. The
   10:00 UTC entry corresponds to different broker-local times across
   DST. **Phase 0 must verify the broker-rollover-time-in-UTC stays at
   22:00 UTC year-round** (most brokers anchor to UTC, but some to local).
   If broker rollover is anchored to local, the entry/exit window needs
   DST-aware calculation.

6. **The cost model has zero overnight swap, which is correct for the
   10-20 UTC same-day window.** But if Phase 2 sweeps include
   alternative windows that cross 22:00 UTC, the cost model must add
   swap (direction-asymmetric per `pre_fomc_drift` lesson — for SHORT
   EURUSD over one overnight, swap is +0.28 bps credit; for LONG it's
   -0.69 bps penalty).

7. **Carry-filter binding range is uncertain.** The 100 bps threshold is
   a guess. Mechanism strength may scale with |rate-diff|² or some other
   non-linear function. **Sweep 0 / 50 / 100 / 200 / 300 bps as the
   filter threshold to find the operating range.**

8. **Holiday-week effects are not just exclusion.** Around US holiday
   weeks (Thanksgiving, Christmas, NY, July 4th), broker rollover days
   sometimes shift Tuesday or Friday. The 4-5 holiday weeks/yr are too
   few to meaningfully diagnose but the exclusion may itself bias the
   sample (excludes the periods of thinnest liquidity = often biggest
   moves). **Sensitivity check: run with vs without the exclusion.**

## Phase 1 → Phase 2 plan (checkbox)

- [x] Read lesson #45, #59, `pre_fomc_drift` (swap-asymmetric-cost
      lesson), `lunch_fade` (institutional-absence framing), Evans-Lyons
      / Levich-Pojarliev references for flow-impact theory
- [x] Write this thesis with pre-committed kill criteria
- [ ] **Phase 0**: verify Eightcap MT5 EURUSD broker rollover happens
      Wednesday night (not Friday); verify rollover time-of-day in UTC
      across DST; pull a 1-month broker swap-rate sample to confirm the
      triple-Wed pattern is active currently (broker swap rates change
      with rates; the *triple* convention is structural)
- [ ] **Phase 0**: pull EUR-USD historical rate differential time series
      (FRED FEDFUNDS - ECB MRO or DFR) to build the CARRY_FILTER_BPS
      indicator
- [ ] **Phase 0**: list US holiday calendar 2019-2026 for HOLIDAY_EXCLUSION
- [ ] Build `cfd_wed_rollover_eurusd_demo.py`:
  - Wednesday-only event extraction
  - 10:00 UTC entry / 20:00 UTC exit (close-of-bar)
  - Carry-filter conditional
  - Holiday-week exclusion
  - SHORT primary + LONG null
  - Placebo on non-Wed weekdays
  - Regime breakdown (3-window default per CLAUDE.md)
  - Window-sweep diagnostic for Goodhart (Tuesday-evening edge migration)
- [ ] Run Phase 2 end-to-end; update this doc with verdict +
      mechanistic interpretation
- [ ] If PASS: Phase 3 — verify on GBPUSD (BoE-similar setup), USDJPY
      (positive-carry, expected null), AUDUSD (variable-carry)
- [ ] If REJECT: tombstone with which red flag fired (Goodhart / regime
      decay / sign-flip in W3 / placebo contamination)

## Files

- `cfd_wed_rollover_eurusd.md` — this doc
- `cfd_wed_rollover_eurusd_demo.py` — Phase 2 simulator (TBD)
- Data: `ohlc_data/EURUSD_M5.csv` (already on disk per session work
  2026-05-26); FRED rate-differential series (fetch via
  `scripts/fred_fetch.py FEDFUNDS,ECBDFR` if not on disk)

## Open methodology questions for the agent

1. **The carry filter's operating range is uncertain.** The 100 bp threshold
   is a guess based on the post-2022 Fed-ECB rate divergence. Sweep 0 / 50
   / 100 / 200 / 300 bp to identify the binding range. If the filter is
   non-binding (i.e., the mechanism works at all rate-diff levels), drop
   it from the deploy form — fewer free params is better.

2. **Window timing sensitivity.** Phase 2 should sweep entry/exit hours
   (08-18, 10-20, 12-22 UTC) to identify the optimal 10-hour window. If
   the optimal is much narrower (e.g., 14-18 UTC = US morning concentration),
   document and deploy on the narrower form. If the optimal is much wider
   (e.g., 06-22 UTC), the mechanism is broader than the thesis predicts —
   investigate whether non-CFD-rollover-related flow is contributing.

3. **The "everyone knows" Goodhart diagnostic** is the critical methodology
   check. Phase 2 must include the Tuesday-evening / Tuesday-night /
   Tuesday-overnight sub-window scan. If the edge has migrated upstream
   in time, the strategy is stale even if historically the Wed window
   shows signal.

4. **GBPUSD / USDJPY / AUDUSD Phase 3 cross-pair check** is high-value:
   - GBPUSD with BoE 4.5% vs Fed 5.5%: ~100bp carry, similar setup
     (long-GBP = negative carry). Expected SHORT-GBP edge similar shape.
   - USDJPY with BoJ 0.5% vs Fed 5.5%: ~500bp carry, OPPOSITE direction
     (long-USDJPY = positive carry, retail HOLDS through Wed to collect
     triple). Expected null or weak LONG-USDJPY edge (people holding
     through Wed = no flow signal).
   - The 3-pair cross-check is the cleanest test of whether the mechanism
     is the structural-CFD-rollover-unwind story or something pair-specific.

5. **3-window vs 4-window regime split.** CLAUDE.md default is 3-window;
   `pre_fomc_drift` used 4-window. For this thesis the relevant regime
   axis is **rate-differential regime** (high / low / inverted), which
   doesn't cleanly map to either convention's year boundaries. Recommend
   running 3-window per CLAUDE.md AND a separate rate-diff-tercile
   breakdown as a diagnostic.
