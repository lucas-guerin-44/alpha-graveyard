# XAUUSD DXY-stall contra-signal — REJECT (Phase 0, no edge over baseline)

**Status (2026-05-27):** **REJECT at Phase 0.** No Phase 1 built.

**Headline failures:**

1. **Real-vs-baseline delta ≈ 0** across all (N, kind, horizon) cells. The
   +0.5 bp HWM-stall LONG signal at N=5 60m (Section 2 t=+2.62) is fully
   explained by W4 XAU baseline drift (+0.4 bp/60min on hour-matched random
   non-stall bars). When compared against time-of-day-matched controls, the
   "edge" disappears.
2. **Combined HWM+LWM signed mean ≈ 0**. HWM-stall (XAU drifts up: +0.5 bp)
   and LWM-stall (XAU also drifts up: +0.4 bp raw, sign-mapped to -0.4 in
   short-XAU framing) cancel out. The signal is *one-directional bullrun
   drift*, not a structural DXY-XAU exhaustion mechanism.
3. **Sign-inversion in mechanism-strongest cells**: large prior DXY moves
   (>±0.10% in the 30 min before stall) produce XAU forward returns
   **opposite** to the thesis (HWM-after-up: -6.3 bp, LWM-after-down: +6.2 bp,
   n=34/27 — small but consistent sign). DXY-XAU is a **continuation**
   correlation at M5 horizons, not a momentum-exhaustion-reversal one.
4. **Magnitude below cost**: all cells with significant t have means ≤ 1.2 bps,
   below the 2 bp Eightcap RT cost and far below the +3 bp Phase 1 floor.

**Data caveat**: USDJPY M5 only available from 2022-11-18 at Eightcap →
synthetic-DXY series covers W3-end + W4 only (~3.5 years). Same broker-side
constraint that hit `usdjpy_tokyo_fix`. The DXY-XAU daily correlation on
this proxy = **-0.41** vs expected -0.5 to -0.85 (weaker than ideal but
inversion is intact).

**Methodological win**: the hour-of-day-matched random-bar baseline control
was pre-committed in this thesis doc as load-bearing for Phase 0 PASS, and
it cleanly killed the surface signal that the inflated-n t-stats had made
look real. Continues the **bullrun-isolation discipline** from
`xau_asia_range` (same-day reject) — without the baseline control,
this strategy would have looked like a Phase 1 candidate.

**No mechanism extension viable at retail M5**: the DXY-XAU correlation is
real but it's already extracted at the daily horizon by xau_session's
Asian-handoff drift, and the intraday "stall → reversal" framing is refuted.
A DXY-positioning-based XAU strategy would need either (a) CFTC TFF weekly
positioning data (sub-daily flow signal), or (b) a different cross-asset
trigger (e.g., 10Y real rates, gold-ETF flows) — out of scope for retail
intraday CFD.

Tombstoned to STATE_GRAVEYARD.

## Origin

Idea-bench output from the xau_asia_range REJECT discussion. With Asia-range
level-touch on XAU now tombstoned and the EOM-rebal family arbed flat, the
remaining shelf of mechanism-clean intraday XAU theses points to *cross-asset
flow signals*. The deployed `xau_session` extracts an Asian-handoff LONG
drift; `xau_break_retest_m15/h1` extracts NY-AM/NY level-retest FADE. Nothing
in the deployed book uses **DXY positioning exhaustion** as the trigger.

## Thesis (mechanism)

1. **DXY and XAU are structurally inversely correlated.** Daily correlation
   typically -0.6 to -0.8. The inverse runs through TIPS / real-rate channels
   and central-bank-FX-reserve rebalance flows.
2. **DXY intraday momentum exhausts before XAU does.** During trending DXY
   moves, dollar-positioning saturates (CTAs full, macro real-money full) and
   the marginal flow flips at the top/bottom of the move. XAU's reaction is
   slower because gold flow involves physical/sovereign/ETF channels with
   longer decision cycles than spot-FX.
3. **A "stall event" (DXY 30-min high water mark holds for 4-6 M5 bars
   without a new high) signals positioning saturation.** At that point,
   DXY's near-term EV is flat-or-mean-revert and XAU's compensating move is
   the higher-probability path.
4. **Mirror for DXY LWM stall → expected XAU SHORT.**

Critical: this is a *contra-DXY-momentum* trade, not a continuation. It only
works if DXY momentum-stall predicts mean-reversion better than continuation.
That's the first thing Phase 0 checks (symmetry + null comparison).

## Key reference

- Borys et al. 2024 — "Dollar funding pressures and gold demand: a positioning
  channel" (concept-level reference; mechanism uses CFTC TFF positioning data
  as DXY-saturation proxy — we're substituting intraday momentum exhaustion).
- Internal: `xau_session.md` confirmed Asian-handoff specificity; this trade
  is a separate mechanism (cross-asset, not session-based).

## Phase 0 — DXY-stall → XAU forward-return profile

NO strategy commitment yet. Measure:

1. **DXY synthetic construction.** Weighted log-return composite:
   - EURUSD weight = -0.576 (inverted)
   - USDJPY weight = +0.136 (direct)
   - GBPUSD weight = -0.119 (inverted)
   - Other DXY components (CAD/SEK/CHF, 17%) skipped — proxy correlation
     with real DXY typically ≥ 0.95.
   - Reconstructed M5 log-DXY index.

2. **Stall event detection.** For each DXY M5 bar t:
   - HWM(t) = max(DXY_close[t-30bars .. t]) (i.e., 30m HWM)
   - Stall event after HWM = first bar where N consecutive bars (N ∈ {3,4,5,6,8})
     fail to make a new HWM AND the last HWM was within the past 60 minutes.
   - Mirror for LWM (low water mark).

3. **Forward XAU returns** at +6 / +12 / +18 / +24 M5 bars (30/60/90/120 min)
   from the stall event bar's close. Sign-mapped:
   - Post HWM-stall: XAU expected UP → record raw forward XAU return as +
   - Post LWM-stall: XAU expected DOWN → record -1 × forward XAU return
   - Combined: a positive mean across both directions = mechanism works.

4. **Baseline (null) comparison.** Same forward XAU returns sampled at
   random NON-stall M5 bars matched on hour-of-day distribution. If real
   stall events produce no edge over the time-of-day baseline, signal is null.

5. **Conditional splits**:
   - DXY momentum strength before stall (large move vs small move into the HWM/LWM)
   - Time-of-day (London / NY / overnight)
   - Regime window (W1-W4)
   - XAU prior 30-min direction (was XAU already trending opposite DXY?)

6. **Symmetry check.** HWM-stall LONG-XAU mean should mirror LWM-stall
   SHORT-XAU mean if mechanism is structural.

## Phase 1 pre-commit (conditional on Phase 0 PASS)

**Phase 1 fires only if Phase 0 produces** at least one cell with:
- Mean signed forward XAU return ≥ +3 bps (after time-of-day baseline)
- t-stat ≥ +2.0 vs both zero AND time-matched baseline
- Mirror direction (LWM-stall) confirms sign symmetry within ±50% magnitude
- Effect persists across W3+W4 (not 2018-2021-only)

Phase 1 kill criteria (apply at variant level):

- **Sh FULL > +0.30** at 2 bps RT cost
- **Sh W4 > +0.50** (W4 binding per BTC-floor lesson)
- **MDD < 15%**
- **Trade count ≥ 200** over backtest window
- **Direction-gap > +0.40**: HWM-stall LONG must beat HWM-stall SHORT
  (and mirror) by Sharpe gap ≥ +0.40
- **Walk-forward mean degradation < 0.50** across 5 rolling splits
- **Cost-stress passes at 4 bp RT**
- **Placebo-bar control**: same simulator with stall events replaced by
  random-bar entries (time-of-day matched). Real-stall Sharpe must exceed
  placebo Sharpe by ≥ +0.30.
- **Independence from deployed XAU book**: per-day net-return correlation
  vs `xau_session` and `xau_br_m15/h1` must be |corr| < 0.50, else the
  signal is redundancy (see lesson #-14 / xau_ldn_orb_m1 graveyard row).

## Why this might fail (red flags)

- **The inverse correlation runs both ways.** XAU often leads DXY into Asian
  hours (Asian physical demand pushes XAU first, DXY reacts). DXY-stall
  might be lagging-confirmation of an already-completed XAU move,
  producing no forward edge.
- **Momentum-stall at M5 is a noisy signal.** Real DXY positioning
  exhaustion is a daily/weekly phenomenon (CTFC TFF reports weekly).
  Intraday M5 stalls may capture noise, not real exhaustion.
- **Redundancy with xau_session.** xau_session's Asian-handoff LONG drift
  may already capture the DXY-Asia-stall mechanism implicitly. Independence
  check is critical.
- **Cost cliff.** XAU at 2 bp Eightcap is fine; mean per-trade gross needs
  ≥ 4-5 bps to clear cost-stress. Stall-event timing has to deliver this.

## Phase 0 → Phase 1 plan

- [ ] Phase 0 profile (`_profile_dxy_stall.py`) — NEXT
- [ ] If Phase 0 passes: Phase 1 simulator (`xau_dxy_stall_demo.py`) with
      placebo control built in from the start
- [ ] If Phase 1 passes: Phase 2-5 standard battery (statistical / regime /
      cost-stress)

## Files

- `xau_dxy_stall.md` — this doc
- `_profile_dxy_stall.py` — Phase 0 stall-event forward-return profile
