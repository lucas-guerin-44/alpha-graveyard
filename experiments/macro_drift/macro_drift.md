# Macro event drift — MARGINAL / WATCH-LIST

**Status (2026-05-17 EOD):** Phase 0a+0b complete. Pre-FOMC drift on
SPX500/NDX100/GER40 is statistically real but **regime-concentrated in
W3 (2022-2023 rate-hike era) with marginal W4 (2024-2026) evidence**.
Filed as MARGINAL / watch-list. **Revisit 2026-11 / 2027-05** when 4-8
additional FOMC events provide more W4 evidence.

## Phase 0 verdict summary (2026-05-17)

**SPX500 pre-FOMC 24h drift (n=56 events, 2018-2026, 2bp cost):**
- Net mean per trade: +0.276%, t=+2.44, WR 60.7%, est. Sh +0.92 annualized
- W1 2018-2019: -0.04% (n=8, negative)
- W2 2020-2021: +0.17% (n=14, modest)
- W3 2022-2023: **+0.70% (n=16, t=+3.36)** — carries the full-sample signal
- W4 2024-2026: +0.12% (n=18, WR 44%) — MARGINAL, sub-coin win rate

**Cross-product**: NDX100 Sh +1.04 (W3 +0.88% / W4 +0.23%), GER40 Sh +0.86
(W3 +0.73% / W4 +0.10%). GER40 positive on FOMC dates is surprising —
the effect is **global risk-on event-anticipation**, not US-Fed-specific.

**Placebo (non-FOMC Wednesdays)**: mean -0.03%, t -0.26 → clean. Effect IS
event-specific (not generic mid-week drift).

**Variant sweeps**: 18h window peaks at Sh +0.96; 48h reaches Sh +1.11
(but with 2x exposure). Exit buffer 60min slightly better than 30min.

## Why this is filed MARGINAL not REJECT

The mechanism is genuine (Lucca-Moench 2015 documented; placebo clean;
3 indices corroborate; W3 t=+3.36 is decisive). The decay pattern matches
what 0DTE-options-flow papers predict (compressed pre-event vol-risk premium
post-2022). But n=18 W4 with mean +0.12%, std 0.85% gives 95% CI roughly
[-0.28%, +0.52%] — **we cannot distinguish noise from decay** with this n.

Same class as btc_intraday MARGINAL: real historical signal, post-2022
decay, low statistical power to confirm in deploy-relevant regime.

## Watch-list trigger (when to revisit)

Re-run `_profile_fomc_drift.py` after 4-8 additional FOMC events accumulate:

- 6 months out (2026-11-17): adds ~4 FOMC events (Jun/Jul/Sep/Oct/Dec 2026
  scheduled — 5 events if all run) → W4 n grows to ~23
- 12 months out (2027-05-17): adds ~12 more events → W4 n ~30

**Re-decide rule**: if updated W4 mean > +0.15% AND W4 WR > 55%, proceed
to Phase 1 with W4-binding kill criteria. Otherwise tombstone.

If 0DTE regime continues compressing the effect and W4 stays near zero,
this is structural decay and the strategy is dead — accept verdict.

## Files

- `macro_drift.md` — this doc
- `fomc_calendar.csv` — 66 historical scheduled FOMC events 2018-2026 +
  5 forward-2026 dates (includes statement time ET, projections flag,
  emergency-meeting exclusion notes)
- `_profile_fomc_drift.py` — Phase 0b event-window profile + cross-product
  + placebo + window/buffer sweeps. RERUN this in 6-12 months.

## Original (pre-tombstone) plan

(Preserved below for future re-evaluation. Most of the thesis framing,
mechanism candidates, and Phase 0 plan remain valid for the watch-list
recheck.)

---

# Macro event drift — Phase 0 scoping (ORIGINAL)

**Status (2026-05-17):** Phase 0 scoping. Test whether US macro announcements
(FOMC, NFP, CPI) produce systematic event-window drift on equity indices
that's deployable as a retail strategy at Eightcap M5 spreads. Primary
candidate: **Pre-FOMC drift on SPX500 / NDX100** (24h before announcement).

## Origin & motivation

Following xau_session deploy and the FX/silver/platinum tombstones, the
diversification gap in the book is in **time-of-trade and mechanism-family**.
Current 3 strategies are all session-microstructure intraday:

- `orb_dax`: GER40 opening-range breakout, 08:00-12:00 Berlin
- `lunch_fade`: NDX100 lunch-hour mean reversion, 11:30-13:30 ET
- `xau_session`: XAUUSD Asian-session drift, 23:00-08:00 UTC

A macro-event-drift strategy would add:

- **Event-driven mechanism** (vs session-handoff microstructure) — completely
  different family
- **Multi-day hold horizon** (24-48h vs same-day) — different vol exposure
- **Scheduled-event cadence** (lumpy 8-30/yr vs continuous daily) — uncorrelated
  with the other strategies' day-to-day trade flow
- **Macro-policy-regime sensitivity** — gives the book some exposure to
  rate-cycle dynamics that the current book lacks

## Thesis (mechanism)

### Primary: Pre-FOMC drift (Lucca & Moench 2015)

**Documented effect**: In the 24 hours BEFORE scheduled FOMC announcements,
SPX 500 historically drifts up ~0.49% on average (Lucca & Moench 2015,
*Journal of Finance*). That single 24h window 1994-2011 explained roughly
80% of SPX's total excess return over the sample period.

**Mechanism candidates** (multiple proposed, not fully resolved):

1. **Risk-premium compensation**: investors demand higher returns to hold
   risky assets through a macro-uncertain event. The pre-announcement run-up
   pays this premium ex-ante.
2. **Information leakage**: institutional positioning shifts ahead of
   announcements (informed flow, not necessarily leak of the decision).
3. **Reduced macro uncertainty**: as the announcement approaches, ambiguity
   resolves — discount rates compress, valuations rise.
4. **Lower vol pre-announcement** drives risk-on positioning by vol-targeting
   funds (Cieslak/Morse/Vissing-Jorgensen 2019).

**Post-2015 status**: the effect has attenuated but not disappeared.
Papers post-2018 (e.g., Cocoma et al. 2017, Boguth et al. 2019) find the
drift persists but with reduced magnitude (~0.2-0.3% vs original ~0.49%).
Need to verify on current SPX500 CFD data.

### Secondary candidates (Phase 0 expansion)

- **Pre-NFP drift**: less documented, monthly cadence (~12/yr)
- **Post-NFP fade or momentum**: spike on announcement, then reversion or
  continuation in next 24-48h
- **CPI surprise asymmetry**: directional reaction based on surprise vs
  consensus (requires real-time consensus data — skip for retail Phase 0)
- **Pre-ECB drift on DAX / EUSTX50**: 8 events/yr, ECB equivalent of FOMC

## Universe & instruments

- **Primary**: SPX500 (CFD, datalake M5+H1 available), NDX100 (CFD)
- **Secondary expansion**: GER40 for ECB tests
- **NOT in scope**: bond / rates / VIX products (Eightcap doesn't carry bonds;
  VRP already REJECTED in vix_term_structure)

## Signal math (preliminary)

### Pre-FOMC drift, baseline

```
For each scheduled FOMC announcement date D, at time T_announce:
    # Pre-announcement entry: 24h before announcement
    entry_time = T_announce - 24h
    entry_price = close of SPX500 M5 bar at entry_time
    
    # Exit: 30 minutes before announcement (avoid event spike)
    exit_time = T_announce - 30min
    exit_price = close of SPX500 M5 bar at exit_time
    
    long_pnl = (exit_price - entry_price) / entry_price - cost_pct
```

### Variants to sweep (Phase 0b)

- **Window length**: 6h / 12h / 18h / 24h / 48h pre-announcement
- **Exit buffer**: 60min / 30min / 15min / 5min before announcement
- **Instrument**: SPX500 vs NDX100 vs GER40 (ECB)
- **Direction null**: same window on a randomly-chosen non-FOMC Wednesday
  (placebo test — must show NO drift; if drift exists on non-event days,
  the FOMC effect is just generic mid-week drift, not event-specific)

## Data needs

| dataset | source | notes |
|---|---|---|
| SPX500 M5 / H1 | datalake (already have) | ✅ ready |
| NDX100 M5 / H1 | datalake (already have) | ✅ ready |
| GER40 M5 / H1 | datalake (already have) | ✅ ready |
| **FOMC calendar (historical, 2018-2026)** | Fed website / federalreserve.gov | scrape or manually compile ~64 dates |
| **NFP calendar (historical, 2018-2026)** | BLS website | scrape or compile ~96 dates |
| **CPI calendar (historical, 2018-2026)** | BLS website | ~96 dates |
| **ECB calendar (historical, 2018-2026)** | ECB website | ~64 dates |

Forward calendars (next 6-12 months) are publicly available from same sources.

**Calendar compilation approach**: 
- FOMC: 8 meetings/yr × 8 years = ~64 entries. Manually compile a CSV with
  (date, announcement_time_ET) tuples. Or scrape the Fed website's calendar
  page. ~30 min of work.
- NFP / CPI: same approach; BLS publishes annual schedules in advance.
- ECB: similar from ECB website.

### Eightcap CFD spread reality-check needed

- SPX500 typical Eightcap spread: ~0.5-1 pt RT on ~6000 level = ~1-2 bp RT.
  Should be deployable.
- NDX100 typical Eightcap spread: ~1-2 pt RT on ~20000 level = ~0.5-1 bp RT.
  Should be deployable.
- GER40 typical Eightcap spread: similar to SPX500.

All comfortably within "deployable at retail" zone (much tighter than XAG/XPT).

## Why retail-accessible

- Eightcap SPX500/NDX100 CFD spreads ~1-2 bp RT — competitive with the
  deployed strategies.
- Entry/exit is scheduled, no real-time data feed required (calendar is
  known in advance).
- 24h hold = minimal slippage exposure.
- 8 FOMC trades/yr × 8 years = 64 obs for Phase 1 simulator. Small but
  sufficient given the effect's documented magnitude (0.2-0.5% per trade).

## Expected performance (point estimates)

Based on Lucca-Moench (~0.49% per trade pre-2011, modern estimates ~0.2-0.3%):

| metric | optimistic (full L-M) | realistic (post-2015) |
|---|---|---|
| Per-trade mean | +0.49% | +0.25% |
| Trades/yr | 8 (FOMC only) | 8 |
| Annual gross | +3.9% | +2.0% |
| Std per trade | ~0.6% | ~0.6% |
| Annualized vol | ~1.7% | ~1.7% |
| Sharpe (est) | ~2.3 | ~1.2 |

Even at the conservative end (Sh +1.2 research → live ~+0.6), this would
be the **highest-Sharpe** strategy in the book if it survives Phase 2-5.

Important nuance: 8 trades/yr means low absolute return contribution to the
book. At 1% risk per trade, ~+2% gross annual is reasonable but small.
Worth pursuing for diversification (zero correlation with other strategies)
not standalone return.

## Pre-committed kill criteria (sketch — finalized after Phase 0a)

These get tightened after Phase 0a hour-of-day / day-of-cycle profile lands:

- **Per-trade mean > +0.10%** at 2bp RT cost (need to clear realistic spread)
- **W4 (2024-2026) per-trade mean > +0.05%** (post-2015 attenuation must
  still leave positive deploy-relevant signal)
- **Win rate > 55%** (per-event nature means high WR is the expected
  shape — gains accrue smoothly during the window)
- **Direction null-check fade-gap > +0.30**: random non-FOMC mid-week
  Wednesday windows must show < +0.05% per-window mean
- **Cross-product corroboration**: NDX100 must also show positive (if
  SPX500 alone, signal is index-specific, less robust)
- **Trade count ≥ 50** cumulative (8 events/yr × 8 years = 64 — passes
  if all events tradable)

## Why this might fail (red flags)

1. **Mechanism decay (most likely failure mode)**: post-2015 papers show
   attenuation. If 2024-2026 specifically shows ~zero or negative drift,
   tombstone — this is the most likely outcome given how widely-known
   the effect is.

2. **0DTE options regime change**: post-2022 SPX 0DTE option volume has
   massively expanded. Could compress pre-FOMC vol risk premium and
   eliminate the drift. Same mechanism that killed vix_term_structure.

3. **2026 specifically might be regime-anomalous**: high macro uncertainty
   in 2026 (election cycle, tariff dynamics, AI capex cycle) might amplify
   OR distort the historical pattern. n=8 trades for 2026 alone is too
   small to distinguish.

4. **Statement-time-of-day variability**: FOMC statements were 14:15 ET
   historically, moved to 14:00 ET around 2010-2011, sometimes 14:00 ET
   with presser 14:30 ET. Need to verify entry/exit time alignment per
   event.

5. **Non-cumulative**: unlike xau_session (39 trades/yr) the 8/yr cadence
   means a single bad year (1-2 negative events) can dominate the sample.
   Phase 4 regime stability check will be brutal.

## Phase 0 plan (checkbox list)

- [ ] **Phase 0a — calendar compilation**: build `fomc_calendar.csv`
  with 64 historical FOMC dates 2018-2026 + announcement_time_ET column.
  Source: federalreserve.gov/monetarypolicy/fomccalendars.htm
- [ ] **Phase 0b — pre-FOMC window profile**: load SPX500 M5, intersect
  with FOMC calendar, compute per-event return over [T-24h, T-30min]
  window. Report: mean, median, std, t-stat, per-event sequence
  (visualize regime stability).
- [ ] **Phase 0c — regime breakdown**: same metrics for W1/W2/W3/W4
  windows. **Binding question: is W4 (2024-2026) still positive?**
- [ ] **Phase 0d — direction null-check**: same 24h window on randomly
  selected non-FOMC mid-week Wednesdays (placebo dates). Must show
  ~zero drift if FOMC effect is real and not generic.
- [ ] **Phase 0e — cross-product check**: same analysis on NDX100 and
  GER40. NDX should mirror SPX (US tech-heavy). GER40 should NOT mirror
  (different central bank).
- [ ] **Phase 0f — window-length sweep**: 6h / 12h / 18h / 24h / 48h
  entry windows. Find the sweet spot.
- [ ] **Phase 0g — exit-buffer sweep**: 5min / 15min / 30min / 60min
  before announcement. Avoid the volatility spike.

If Phase 0a-g produce: W4 per-trade > +0.05% AND cross-product positive
AND null-check shows < +0.05% on placebo → proceed to Phase 1 (pre-commit
kill criteria + walk-forward) → Phase 2 (simulator).

If W4 negative or null-check shows drift on placebo → tombstone.

## Phase 0 → 1 → 2 → ... plan

Same standard pipeline as xau_session:
- Phase 0: discovery + filter exploration (this doc)
- Phase 1: pre-committed kill criteria
- Phase 2: simulator with kill-criteria battery
- Phase 3: statistical validation (Deflated Sharpe, bootstrap CI, permutation)
- Phase 4: regime stability (block bootstrap per regime) — likely brutal at
  n=8/yr cadence
- Phase 5: real-cost stress
- Phase 6: reserve-and-retest (truncate to pre-2024, see if mechanism
  still emerges)
- Phase 7: MT5 EA (event-calendar-aware — needs to read calendar file
  on each tick)
- Phase 8: VPS deploy

## Key references

- **Lucca, D. & Moench, E. (2015)**. "The Pre-FOMC Announcement Drift",
  *Journal of Finance*, 70(1). Canonical paper. SPX +0.49%/event 1994-2011.
- **Cieslak, A., Morse, A., Vissing-Jorgensen, A. (2019)**. "Stock Returns
  over the FOMC Cycle", *Journal of Finance*, 74(5). 5-day cyclic pattern.
- **Boguth, O., Grégoire, V., Martineau, C. (2019)**. "Shaping
  Expectations and Coordinating Attention: The Unintended Consequences
  of FOMC Press Conferences", *Journal of Financial and Quantitative
  Analysis*. Documents press-conference-day vol effects.
- **Savor, P., Wilson, M. (2013)**. "How Much Do Investors Care About
  Macroeconomic Risk?", *Journal of Financial and Quantitative Analysis*.
  Macro announcement-day risk premia.

## Files (to be created)

- `macro_drift.md` — this doc
- `fomc_calendar.csv` — Phase 0a compiled calendar (date, time_et columns)
- `_profile_fomc_drift.py` — Phase 0b/c/d profile script
- `_compile_fomc_calendar.py` — calendar scraper/compiler (or manual CSV)
- Future: `nfp_calendar.csv`, `cpi_calendar.csv`, `ecb_calendar.csv`
- Future: `macro_drift_demo.py` (Phase 2), `macro_drift_validation.py`
  (Phase 3)

## Related strategies & precedents

- [[project_lunch_fade_ndx100_deploy]] — same NDX100 instrument, different
  mechanism family. Time-of-day microstructure vs event-driven; should be
  uncorrelated trade-by-trade.
- [[project_xau_session_phase0]] — analog pipeline structure (8-phase
  research-to-deploy template).
- `vix_term_structure` REJECT — VRP-based macro strategy, killed by 0DTE
  regime change. The pre-FOMC drift has a different mechanism (risk
  premium for event uncertainty) but could be vulnerable to the same
  post-2022 regime shift. **Compare W4 carefully**.

## Open questions for Phase 0

1. **Statement-vs-presser timing**: should "T_announce" mean statement
   release (14:00 ET) or press conference (14:30 ET)? Pre-statement
   drift is the documented effect; presser-window is different.
2. **Inter-meeting cycle effects**: Cieslak et al. found 5-day cyclic
   patterns AROUND FOMC. Worth probing separately (different thesis).
3. **Asymmetric drift**: does the pre-FOMC drift differ on dovish-expected
   vs hawkish-expected meetings? Requires implied-policy-direction data
   (Fed funds futures). Probably out of scope.
4. **Single-stock spillovers**: documented that pre-FOMC drift is
   stronger on high-beta names. Skip — single-stock is its own can of
   worms.
