# USDJPY Tokyo morning fix flow

**Status (2026-05-26 EOD)**: REJECT at Phase 0b magnitude gate.

**Verdict**: REJECT. The pre-committed day-of-week direction map (Mon/Tue=SHORT,
Wed=LONG) yields gross **-1.337 bps per-trade** on 560 trades — below the +1.5
bps Phase 0b floor and on the WRONG SIGN. The underlying data shows a strongly
significant Asian-session USDJPY-LONG signature on every weekday (aggregate
t = +8.03, n=936) — opposite the exporter-flow / WMR-anomaly academic prior.
Per Lesson #45 the cost-ceiling is not the binding failure here; the binding
failure is **directional-prior inversion in the 2022-10 → 2026-05 sample**.
Per thesis open-question #1, the prior is tombstoned in this experiment; a
separate v2 pre-commit (Asian-session-LONG drift, DOW-amplified, with Mon as
the strongest arm) is justified and should be filed as `usdjpy_tokyo_drift_v2`,
NOT bolted on here.

## Phase 0b results (2026-05-26)

USDJPY M5 2022-10-07 → 2026-05-26 (~3.6y, W3+W4 era only — the
broker-side data cap means W1/W2 regime checks per the original thesis are
infeasible; full sample sits inside the BoJ-intervention era).

### Per-arm gross zero-cost, with thesis-pre-committed direction

| DOW arm   | n   | gross w/ direction | t-stat | thesis prior |
|-----------|-----|--------------------|--------|--------------|
| Mon SHORT | 185 | **-4.155 bps**     | -5.98  | exporter JPY-buying → USDJPY down |
| Tue SHORT | 189 | **-1.315 bps**     | -4.66  | exporter JPY-buying → USDJPY down |
| Wed LONG  | 186 | **+1.444 bps**     | +3.42  | importer JPY-selling → USDJPY up  |
| **Combined Mon+Tue+Wed (thesis mapping)** | **560** | **-1.337 bps** | **(REJECT, < +1.5 bps floor)** | — |

Only Wed agrees with the prior. Mon and Tue point hard the other way.

### Raw per-DOW gross (no direction applied), USDJPY up at the fix

| DOW | n   | mean    | median  | std   | pos%  | year-by-year stability |
|-----|-----|---------|---------|-------|-------|-------------------------|
| Mon | 185 | +4.155  | +3.995  |  9.42 | 75.1% | 2022 +6.24 / 2023 +3.74 / 2024 +3.51 / 2025 +3.97 / 2026 +6.09 — **no year inverts** |
| Tue | 189 | +1.315  | +1.413  |  3.87 | 65.6% | (stable) |
| Wed | 186 | +1.444  | +1.166  |  5.73 | 66.1% | (stable) |
| Thu | 187 | +0.345  | +0.738  |  6.09 | 57.2% | (weakest) |
| Fri | 189 | +1.138  | +1.375  |  4.70 | 65.1% | (stable) |
| **All wkdy** | **936** | **+1.672** | **+1.539** | 6.37 | **65.8%** | aggregate t = **+8.03** vs zero |

The Monday signal is **NOT outlier-driven**: trimmed (2.5% tails) mean
unchanged at +4.165 bps; median +3.995 bps ≈ mean; 75% of Mondays positive;
**every year 2022-2026 is positive with mean in [+3.5, +6.2] bps**.

### Interpretation

1. **The Mon/Tue=SHORT exporter-flow prior is wrong-signed in the post-2022
   regime.** Plausible candidates for *why* the prior inverted (not validated,
   just hypothesised for a v2 thesis):
   - **Importer JPY-selling now dominates the fix.** Japan's energy import
     deficit ballooned post-2022 (LNG ramp on Russia/Ukraine substitution);
     mechanical USD-buying / JPY-selling at the fix can plausibly outweigh
     month-start exporter hedges Mon/Tue.
   - **Life-insurer hedge-rebalance is JPY-selling on a multi-year USDJPY
     uptrend.** With USDJPY 100 → 160 (2021-2024), foreign-bond books
     systematically needed to LIGHTEN JPY-hedges (= sell JPY at the fix).
   - **Asian-session carry-trade resumption.** Post-YCC-exit (2024-03) the
     yen-funded carry trade re-emerged in size; the 00:45-01:05 UTC window
     overlaps Tokyo-AM positioning into the Asian risk-on, mechanically a
     USDJPY-LONG flow.
   - **Monday's amplification** likely reflects weekend-gap mean-reversion
     + Asia-fresh-week positioning concentrated into the Tokyo open.

2. **This is exactly the inversion the thesis open-question #1 anticipated**:
   > Don't post-hoc adjust this based on what works in-sample. If the actual
   > data shows different day-of-week skew, document the deviation, tombstone
   > the prior, and write a fresh pre-commit experiment with the new mapping.

   Phase 2 (and the kill-criteria battery) was NOT run, per pre-committed
   Phase 0 binding floor. Documenting the inverted signal here is informational
   only and does NOT constitute a PASS for the current thesis.

3. **The next experiment is `usdjpy_tokyo_drift_v2`** (separate dir, fresh
   pre-commit doc): hypothesis = unconditional or Mon-amplified LONG USDJPY at
   the 00:45→01:05 UTC window, mechanism explicitly RE-anchored to importer-
   flow / yen-funded-carry / Mon-Asia-positioning (not the WMR exporter
   anomaly). Cost-headroom at 1 pip RT looks plausible at +1.67 bps gross
   on aggregated all-weekday LONG; per-arm Mon LONG at +4.16 bps gross has
   meaningful headroom even at 2-3 bps cost. But: that is for a fresh
   experiment, not this one.

4. **Lesson #45 is NOT the binding failure here.** Cost-ceiling would be the
   binding failure if the prior-correct direction showed +0.5 bps gross
   (eaten by cost); instead the prior-correct direction shows -1.34 bps
   gross (signal-absent in the pre-committed direction). The lesson hook is
   #43 family ("pre-commit BOTH directions on any mechanism with a non-trivial
   sign-uncertainty channel") — extended to academic / institutional-flow
   priors on FX, which can invert across regimes.

### Phase 2 kill criteria — NOT RUN

Per pre-committed Phase 0 binding floor (gross < +1.5 bps → REJECT before
Phase 2). The kill-criteria pre-commits remain in the thesis above as a
record of what was promised.

### Data caveat

USDJPY M5 on Eightcap (and in the datalake) only covers **2022-10-07 onward**
(~3.6y, ~270K bars). The thesis assumed 2019-2026 (~7.4y) and pre-committed
a W1/W2/W3 regime split — this is infeasible at retail data depth. Full
sample sits inside the W3+W4 BoJ-intervention era. A wider window via a
non-Eightcap source (DTCC ticks, prime-broker tape, academic FX-fix dataset)
would extend the test but is outside retail-research scope.

**Project context**: this is the first Asian-session FX hypothesis in the
repo. The existing Asian-leaning strategy is `xau_session` (Asian XAU
handoff); the FX-Asian-session universe is otherwise untested. Adding a
diversifying Asian-session FX leg is a deliberate cross-asset gap fill.

## Why this — institutional flow at a known structural anchor

The Tokyo morning **WMR fix at 09:55 JST (= 00:55 UTC summer / 01:55 UTC
winter)** is a published institutional-FX execution benchmark. Japanese
real-money players (corporates, life insurers, asset managers, pension
funds) execute USD↔JPY conversions against this fix as their standard
hedging benchmark. The flow is **mechanical, time-anchored, and
asymmetric** by day-of-week and month-end status:

- Exporters (Toyota, Sony, etc.) systematically SELL USD (= buy JPY)
  to convert foreign earnings — heavier flow on Mon/Tue.
- Importers (Japanese energy/raw-materials) systematically BUY USD
  (= sell JPY) — heavier flow on Wed.
- Life insurers rebalance JGB-vs-foreign-bond portfolios at month-end fix
  (last business day of month) — typically JPY-buying flow if foreign
  bonds rallied during the month, JPY-selling if they sold off.

This is *exactly* the kind of "specific institutional flow source at a
known structural timing" that the refined post-Lesson-A framing requires
(per the latest re-anchoring: it's not "institutions can't go here", it's
"institutions DO go here at a known time, and the flow is mechanical").

## Capacity moat — different from the recent rejects

Unlike `cfd_wed_rollover_eurusd` (which had a strong capacity moat but
no detectable magnitude), Tokyo fix flow is **documented in BIS Triennial
FX surveys** as comprising 5-10% of daily USDJPY volume concentrated in
the ~30-min fix window. That's a meaningful magnitude.

The retail moat: at 00:55-01:55 UTC, retail FX activity is at its
daily nadir (Asian retail traders are at work; European retail traders
are asleep; US retail traders went to bed 3-5 hours ago). The
institutional fix flow IS the dominant order flow during the window —
retail flow can ride or fade it cleanly without retail counterflow
contamination.

Why not arbed at institutional scale already: it largely IS arbed by
prime-brokerage FX accounts at sub-1bp execution cost (`fx_session`
lesson #45). **But Eightcap CFD spread on USDJPY at ~1 pip RT = 0.62 bps
(at quote ~160.00) is in the "borderline retail-deployable" zone that
lesson #45 flagged.** This thesis tests whether the *specific* Tokyo-fix
sub-window has enough per-trade gross to clear retail cost — different
question from the generic intraday-FX-flow signal that `fx_session` was
killed on.

## Thesis (mechanism)

1. **Tokyo fix (09:55 JST) concentrates Japanese real-money FX flow into
   a ~30-min window.** Documented in BIS Triennial Survey 2022, Melvin &
   Prins (2015) "Fixing the Mistake", and broker-side trade reports. The
   flow is asymmetric by day-of-week and month-end status.

2. **Day-of-week skew** (best supported by historical academic studies
   on Tokyo-fix-window FX returns):
   - **Mon/Tue**: net JPY-buying (exporter month-start hedging) →
     USDJPY weakness in fix window.
   - **Wed**: net JPY-selling (importer mid-week hedging) → USDJPY
     strength in fix window.
   - **Thu/Fri**: weaker / no consistent skew.

3. **Month-end-fix amplification**: last business day of month sees
   ~3× normal Tokyo-fix flow magnitude (insurance rebalance + exporter
   month-end MTD-adjustment). The direction depends on the past-month
   USDJPY return (if USDJPY rallied during the month, foreign-bond
   relative value tells life insurers to lighten JPY-hedges on their
   foreign-bond books, which is mechanically JPY-buying at the fix).

4. **The trade**: enter SHORT USDJPY at T-10 min (00:45 UTC summer /
   01:45 UTC winter) on Mon/Tue fix days; exit at T+10 min (01:05 / 02:05
   UTC). Reverse direction (LONG) on Wed fix days. Skip Thu/Fri (no
   consistent flow). Amplify position on month-end-fix days.

5. **Why retail-tradeable**: the 20-min window with predetermined
   direction-by-day-of-week is mechanically simple. MT5 EA implementation
   is trivial. The cost question (1 pip RT) is the binding test.

## Key references

- **Melvin, M. & Prins, J. (2015), "Fixing the Mistake: A Discussion
  Paper on the FX Fixing Anomalies", *Journal of Banking & Finance*.**
  Documents WMR fix-window anomalies post-2008 institutional reforms.
- **Evans, M. & Lyons, R. (2005), "Are Different-Currency Assets
  Imperfect Substitutes?", *American Economic Review*.** Order-flow
  models that predict fix-window concentration of real-money flow.
- **BIS Triennial Central Bank Survey 2022**, Section on FX Fix-Window
  Trading. Confirms Tokyo fix is ~5-10% of daily USDJPY volume in the
  09:50-10:00 JST window.
- **Internal**:
  - `experiments/_live/xau_session/xau_session.md` — the project's only
    other Asian-session strategy; institutional-flow-at-structural-timing
    framing.
  - `docs/RESEARCH_NOTES.md` lesson #45 — retail-vs-institutional cost
    regime gates intraday FX. Binding consideration here.
  - `experiments/pre_fomc_drift/pre_fomc_drift.md`, `pre_ecb_drift_eurusd`,
    `cfd_wed_rollover_eurusd` — three recent EURUSD FX rejects.
    USDJPY is a structurally different pair (positive-carry, BoJ
    intervention regime, Asian-session-dominated) so the "post-2022
    EUR-positioning collapse" lesson doesn't directly apply.

## Signal math — pre-commit pseudo-code

```
Parameters (≤ 5):
  FIX_WINDOW_MIN_BEFORE = 10     (entry 10 min before fix)
  FIX_WINDOW_MIN_AFTER  = 10     (exit 10 min after fix)
  MEF_AMPLIFY           = 2.0    (2x notional on month-end-fix days;
                                   optional, kill if data-mining-prone)
  COST_BPS_DEFAULT      = 1.0    (Eightcap USDJPY M5 ~1 pip RT,
                                   confirmed via the broker swap/spread
                                   data; calibrate in Phase 0)

Tokyo fix anchor:
  09:55 JST = 00:55 UTC (summer / JDT)
              01:55 UTC (winter / JST)
  → use 00:55 UTC year-round for simplicity (causes ~1h DST drift twice
    a year; flagged as red flag #4)

Per fix-day d in sample:
  if d is Monday or Tuesday:    direction = -1  (SHORT USDJPY)
  elif d is Wednesday:           direction = +1  (LONG USDJPY)
  elif d is Thursday or Friday: SKIP (no consistent skew)
  else: SKIP (weekend / holiday)

  Optional MEF amplification:
    if d is last business day of month: notional = MEF_AMPLIFY * baseline
    else: notional = baseline

  entry_t = d at 00:45 UTC
  exit_t  = d at 01:05 UTC
  entry_px, exit_px = USDJPY M5 closes at nearest bars

  gross_bps = direction * (exit_px - entry_px) / entry_px * 10000
  net_bps   = gross_bps - COST_BPS_DEFAULT
```

Free param count: 3 (FIX_WINDOW_MIN_BEFORE/AFTER, MEF_AMPLIFY, COST). Direction
prior is captured in the day-of-week mapping, not a free param. **Under 7-cap.**

Direction null-check options:
1. **Flat-direction null**: same trade entry/exit times, randomized
   direction. Tests if the day-of-week mapping carries information.
2. **Day-of-week shuffle null**: keep entry/exit times, shuffle the
   day-of-week → direction mapping. Tests if the *specific* Mon/Tue=SHORT,
   Wed=LONG mapping is necessary (vs any consistent direction-by-day-of-
   week mapping working).

Use both in Phase 2.

## Why retail-accessible

- **USDJPY CFD on Eightcap**: confirmed tradeable. Spread at quote ~160.00
  is ~1 pip RT = 0.62 bps RT — at the edge of the lesson #45 retail-vs-
  institutional cost wall.
- **Same-day intraday execution**: 20-min hold, no overnight, no swap
  (Eightcap rollover at 22:00 UTC; the 00:45-01:05 UTC window is well
  after rollover so no swap charge).
- **EA implementation**: trivial — fixed time + day-of-week filter + 20-min
  hold. ~120-150 trades/yr (3 valid days/week × 50 weeks × ~80% qualifying
  after holiday filter).
- **Capacity moat**: at $5k-$500k notional, retail FX execution at fix is
  trivially absorbed. Institutional fix-window arb (which exists at sub-
  1bp cost) doesn't degrade the signature at retail-deployable scale —
  the institutional arb is the *fix-resetting* flow itself, not a counter
  to it.

## Universe

- **Primary instrument**: USDJPY M5 CFD on Eightcap. Datalake / `ohlc_data/
  USDJPY_M5.csv` if available; otherwise fetch via `scripts/mt5_fetch.py`.
- **Research timeframe**: 2019-01-02 → 2026-05-22 (~7.4y, ~5 fix days/week
  × 50 weeks × 7.4y = ~1850 candidate days, ~1100 after day-of-week filter
  and holiday exclusion).
- **Not in scope for Phase 2** (Phase 3 robustness if PASS):
  - EURJPY (other JPY cross, similar fix structure)
  - GBPJPY (same)
  - AUDJPY, NZDJPY (carry-pair JPY crosses)
- **Deployment target**: Eightcap MT5 USDJPY CFD.

## Expected performance (pre-run, with explicit Phase 0 magnitude floor)

**Phase 0 magnitude check (binding before Phase 2)** per Lesson A:

Compute the **gross zero-cost mean** of the strategy on the full sample:
- Mean across all (Mon+Tue SHORT) and (Wed LONG) day-of-week trades.
- **Phase 0 floor: +1.5 bps gross**. The cost is ~1 bp RT; need at least
  +50% headroom over cost for the mechanism to be deploy-grade.
- If gross < +1.5 bps, REJECT before Phase 2 expansion. Document the
  "Tokyo-fix-flow-arbed-to-zero-at-Eightcap-cost-level" methodology lesson.

If Phase 0 passes:
- **Gross per-day**: +2 to +5 bps in the 20-min fix window.
- **Net per-day** (1 bp cost): +1 to +4 bps.
- **Annualized return** at 120-150 trades/yr × 2 bps net = ~25-50 bps/yr
  (modest absolute; the deploy value is **diversification** — adding
  an Asian-session FX leg uncorrelated with the rest of the book).
- **Sharpe**: +0.3 to +1.0 depending on intra-window vol.
- **WR**: 53-58%.
- **MDD**: -3% to -8%. The 20-min window has bounded per-trade risk.
- **Month-end amplification**: if MEF=2x is binding, monthly cadence-
  weighted Sharpe should improve materially (the Phase 0 diagnostic
  is whether MEF days show meaningfully larger per-trade gross than
  non-MEF days).

## Fail conditions (pre-committed, BEFORE running Phase 2)

Phase 0 ABORT:
- **Gross mean per-day < +1.5 bps** on full sample → REJECT (mechanism
  below realistic cost headroom, lesson #45 corroborated for USDJPY).

Phase 2 KILL (if Phase 0 passes) at 1 bp RT cost:
1. **Full-sample net mean per-day ≤ +1 bp**.
2. **W3 (2023-2026 holdout) mean per-day ≤ +0 bps** — modern regime
   must clear zero net (Lesson A binding). 2022-2024 BoJ-intervention
   era may have shifted USDJPY fix-window microstructure; W3 test is
   the regime-stability check.
3. **Direction null-gap (day-of-week-specific vs flat-direction null)
   < +1 bp**. The day-of-week mapping must carry information.
4. **Day-of-week-shuffle null**: the actual Mon/Tue=SHORT, Wed=LONG
   mapping must beat ≥75% of randomly-shuffled-mapping permutations.
5. **Trade count < 200** over full sample (after day-of-week filter
   and holiday exclusion). Likely passes easily given ~1100 candidate days.
6. **WR < 52%** OR **PF < 1.10** (joint).
7. **MDD > 10%** in per-day-equity-curve.
8. **Walk-forward 3-fold OOS Sharpe**: mean ≥ +0.15 AND min ≥ -0.10.
9. **MEF-amplification sweep sanity**: month-end-fix days should show
   *higher* per-trade gross than non-MEF days (1.5× to 2× expected
   per the thesis). If MEF days are flat or worse vs non-MEF, the
   month-end amplification mechanism is unsupported — drop the MEF
   parameter, deploy without amplification.
10. **Cost-stress at 2 bps RT** (2× live spread; covers Asian-session
    spread widening): net mean still > 0.

PASS only if Phase 0 floor PLUS all of (1)-(10) hold.

## Why this might fail (red flags)

1. **Lesson #45 applies directly**. The intraday-FX-flow signature at
   Tokyo fix is the **exact category** of signal that `fx_session`
   tombstoned at retail Eightcap cost (was institutional-deployable at
   sub-1bp). The 1 pip USDJPY spread is *better* than the cost level
   `fx_session` was killed on (~3 bps), but only marginally — the Phase
   0 magnitude floor is the binding test.

2. **BoJ intervention regime distorts the W3 (2023-2026) sample.**
   BoJ intervened multiple times 2022-2024 (Sep-Oct 2022, Apr-May 2024,
   Jul 2024); each intervention created multi-day directional USDJPY
   moves that swamp the fix-window microstructure. The W3 regime
   check is the diagnostic — if W3 dies because of intervention noise,
   the strategy may still be valid in calm regimes but needs an
   intervention-state gate (which is goalpost-moving territory; pre-
   commit *not* to add such a gate post-hoc).

3. **Post-2020 algorithmic-fix-trading has compressed the anomaly.**
   Melvin & Prins (2015) documented WMR-fix anomalies pre-2008 reforms;
   post-2015 reforms (5-min fix window, transparent algo trading)
   may have eliminated the institutional-flow predictability. The
   academic literature on post-reform fix-window returns is mixed.

4. **DST mis-anchor.** The 00:55 UTC year-round anchor is a simplification;
   actual Tokyo fix is 09:55 JST which is 00:55 UTC in summer (JDT, but
   Japan doesn't observe DST so this is JST always) and 00:55 UTC
   year-round. Wait — Japan does NOT observe DST. The 00:55 UTC anchor
   is correct year-round. **CORRECTION: Tokyo fix is constant in JST and
   therefore constant in UTC offset (+9). The "winter" / "summer" split
   I noted above is wrong; remove from the simulator.** Flag for Phase 0
   correction.

5. **Day-of-week skew may not hold in 2024+ post-YCC-exit regime.**
   BoJ ended yield-curve-control 2024-03; the structural Japanese-real-
   money-flow direction may have inverted. Exporter hedging behavior is
   regime-conditional on JGB yield direction. The W3 regime check should
   surface this.

6. **Holiday filter is critical.** Japanese holidays (12-15 per year) +
   US holidays (~10) + EU holidays (~8) = ~20-30 effective non-trading
   days where the fix doesn't behave normally. Must include explicit
   holiday exclusion in the simulator.

7. **Eightcap CFD price-discovery at 00:55 UTC.** Asian session is the
   thinnest-liquidity period for USDJPY at retail CFD venues. Spread
   may widen 2-3× the daytime quote during the window. Phase 0 spread
   audit (pull broker M1 spread data 00:45-01:05 UTC for a representative
   month) is the cost-realism check.

## Phase 1 → Phase 0 → Phase 2 plan (checkbox)

- [x] Read lesson #45 (retail-vs-institutional FX cost), `xau_session`
      thesis (Asian-session-flow template), Melvin & Prins (2015) prior
- [x] Write this thesis with pre-committed kill criteria + Phase 0 floor
- [ ] **Phase 0a (spread audit)**: pull Eightcap USDJPY M1 spread data
      00:45-01:05 UTC for a representative 1-month sample. Confirm spread
      at fix-window is ≤ 2 bps p95. If p95 > 2 bps, the COST_BPS_DEFAULT
      assumption is wrong; raise to actual p75 and re-evaluate Phase 0
      floor.
- [ ] **Phase 0b (magnitude check)**: compute gross zero-cost mean on
      full sample with day-of-week direction mapping. Compare to Phase 0
      floor (+1.5 bps gross). REJECT if below.
- [ ] If Phase 0 passes, build `usdjpy_tokyo_fix_demo.py`:
      - USDJPY M5 entry/exit at 00:45 / 01:05 UTC (verify constant
        across DST — Japan doesn't observe DST, see red flag #4)
      - Day-of-week direction mapping
      - Holiday exclusion (US + JP + EU calendars)
      - MEF (month-end-fix) amplification optional + diagnostic
      - 3-window regime breakdown (W1/W2/W3 per CLAUDE.md)
      - Day-of-week-shuffle null
      - Walk-forward 3-fold
      - Cost-stress 1/1.5/2/3 bps
- [ ] Update this doc with results + verdict + mechanistic interpretation
- [ ] If PASS: Phase 3 cross-pair check on EURJPY / GBPJPY (other JPY
      crosses with documented fix-window flow)
- [ ] If REJECT: tombstone with mechanism interpretation — likely lesson
      #45 corroboration (retail-cost ceiling eats the edge) or post-reform
      fix-window-flattening evidence

## Files

- `usdjpy_tokyo_fix.md` — this doc
- `usdjpy_tokyo_fix_demo.py` — Phase 2 simulator (TBD; only built if
  Phase 0 passes)
- Data: `ohlc_data/USDJPY_M5.csv` (verify on disk; pull via
  `scripts/mt5_fetch.py --symbols USDJPY --timeframes M5 --from 2019-01-01
  --datalake` if not)

## Open methodology questions for the agent

1. **Day-of-week direction mapping is pre-committed**. The Mon/Tue=SHORT,
   Wed=LONG mapping comes from prior academic studies on Tokyo-fix
   exporter-vs-importer flow. **Don't post-hoc adjust this** based on
   what works in-sample. If the actual data shows different day-of-week
   skew, document the deviation, tombstone the prior, and write a fresh
   pre-commit experiment with the new mapping (separate `usdjpy_tokyo_fix_v2`).

2. **MEF amplification is a discretionary add**. The 2× notional on
   month-end days is *not* required for the core thesis. If the MEF
   diagnostic shows no amplification, drop MEF entirely and deploy
   constant-notional. Don't add MEF post-hoc as a "rescue" if the
   constant-notional version is borderline.

3. **Lesson #45 corroboration vs refutation**. If Phase 0 magnitude
   passes (>1.5 bps gross) but Phase 2 net Sharpe doesn't clear +0.3,
   the binding issue is the W3 BoJ-intervention regime, not the cost
   regime. Document which lesson it corroborates — #45 (cost-ceiling)
   vs a new lesson on intervention-era FX-anomaly compression.
