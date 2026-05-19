# FX intraday session structure — INSTITUTIONAL-ONLY (retail-undeployable)

**Status (2026-05-16 EOD):** TOMBSTONED for retail deploy. Pan-FX hour-23 UTC
SHORT signal is statistically real (t -3 to -12 across 5 USD-majors) but
per-trade gross 1-3 bp is too thin for retail RT cost (~3 bp Eightcap).
At fund-pod prime-brokerage cost (0.5-1 bp RT), the same signal produces
estimated Sharpe +1.2 to +2.8 with multi-pair capacity. The signal is a
known institutional edge (Evans/Lyons intraday flow lit; WMR fix Melvin/Prins);
we don't claim discovery, we confirmed the cost barrier empirically.

Filed as INSTITUTIONAL-ONLY in STATE.md rather than REJECT — preserved in
case a future broker-tier change makes it retail-deployable.

**Original (pre-tombstone) status:** Phase 0a in-progress. Hour-of-day profile across FX
majors to identify whether any structural intraday window exists that's
deployable as a strategy. Specifically targeting time-of-day-structural
mechanisms — same family as deployed `lunch_fade` (NDX) and `xau_session`
(XAU). Generic FX factor strategies have been REJECTED 3x in this repo
(`fx_carry`, `fx_carry_trend`, `fx_mean_reversion`); the session-handoff
microstructure family has not been tested on FX.

## Origin

The xau_session cross-product check (2026-05-16) found that EURUSD has a
structural hour-00 UTC long drift (t=+4.54 FULL, Sharpe +1.63) — same signal
as XAUUSD but on a different asset with different regime amplification
(EURUSD W3 strongest at t=+4.88, vs XAU W4 strongest at +2.46). That finding
was noted but not turned into a strategy.

This experiment formalizes the FX-intraday hypothesis space and tests whether
any FX pair shows a deployable structural signal that diversifies the
existing 3-strategy book (`orb_dax`, `lunch_fade`, `xau_session`).

## Why this might (or might not) work

### Encouraging priors

- The session-handoff microstructure family WORKS for two of the three
  deployed strategies (`lunch_fade` NDX, `xau_session` XAU). Same family
  has not been tried on FX intraday — that's a logical extension.
- EURUSD hour-00 UTC t=+4.54 from the xau_session cross-product check is
  the strongest existing FX intraday signal in the repo.
- FX market is fragmented across global sessions (Tokyo → London → NY).
  Session-handoff microstructure (institutional order flow concentrating
  at session open/close) is a well-documented FX phenomenon, not just
  equity-specific. Refs: Evans & Lyons (2008) on intraday FX flow; Melvin
  & Prins (2015) on London 4pm fix; Ranaldo (2009) intraday seasonality.
- Eightcap FX spreads are ultra-tight on majors (typically 0.1-0.5 pips RT
  = 1-5 bps RT) — much less cost-binding than CFDs or BTCUSD intraday.

### Discouraging priors

- All three prior FX theses in this repo REJECTED (carry / carry+trend /
  M5 mean-reversion). Per RESEARCH_NOTES lesson #1: "FX 2015-2026 is a
  graveyard for non-momentum factors." Caveat: those were factor strategies,
  not time-of-day-structural — different mechanism family.
- `fx_mean_reversion` REJECTED specifically because 12bps RT cost ate
  ~25% equity across 2093 trades. Lesson: high-cadence intraday FX is
  cost-binding even at tight spreads. Any thesis must have low cadence
  (≤ 100 trades/yr) or unusually high per-trade gross.
- Broker history depth on Eightcap: USDJPY caps at ~2.2 years (only W4),
  AUDUSD/USDCAD/NZDUSD cap at ~6 months. Only EURUSD has multi-regime
  H1 history (8 years via datalake). Most FX pairs cannot be regime-tested
  per the standard W1-W4 framework — they can only be W4-validated.

## Data inventory (as of 2026-05-16)

| pair | source | window | bars (H1) | regime coverage |
|---|---|---|---|---|
| EURUSD | datalake (xau_session cross_cache) | 2018-01 → 2025-05 | 46,725 | W1+W2+W3+W4(part) |
| USDJPY | MT5 fetch (Eightcap) | 2024-03 → 2026-05 | 19,392 | W4 only |
| AUDUSD | MT5 fetch (Eightcap) | 2025-11 → 2026-05 | 4,320 | W4(recent) only |
| USDCAD | MT5 fetch (Eightcap) | 2025-11 → 2026-05 | 4,320 | W4(recent) only |
| NZDUSD | MT5 fetch (Eightcap) | 2025-11 → 2026-05 | 4,320 | W4(recent) only |
| GBPUSD | datalake | (TBD) | 62,102 | (TBD) |

## Phase 0a plan (running now)

1. **Hour-of-day profile across all available FX pairs.** Same template as
   `xau_session/_profile_xau_hod.py`. Reports per-hour mean H1 return, t-stat,
   per-regime breakdown where possible.
2. **Identify the strongest signal** — pair × hour × regime combination.
3. **Diversification check** — is the surfaced signal different from
   xau_session's hour-00 UTC long-bias?
4. **Mechanism candidates** — for each surfaced signal, write a one-line
   mechanism hypothesis. If no plausible mechanism, drop it.

## Phase 0b → Phase 2 plan (conditional on Phase 0a finding)

If Phase 0a surfaces a deployable signal:
- **Phase 0b**: confirmation filters (analog of xau_session Filter A/B/C/combo)
- **Phase 0c**: Eightcap FX spread verification via MT5 M1 sample
- **Phase 1**: pre-committed kill criteria
- **Phase 2**: simulator + kill criteria check
- ... standard pipeline

If Phase 0a surfaces NO deployable signal (all hours t < +2 or signals
overlap entirely with xau_session/EURUSD long-bias): tombstone this
experiment, accept "FX intraday has no untapped session-microstructure edge."

## Pre-committed bars (FX-intraday-specific calibration)

These will be finalized in Phase 1 after Phase 0a finds the candidate, but
the sketch is:

- **Per-trade gross > +0.05%** at 2-3bp RT cost (FX is tight-spread but
  has lower vol per move than gold; ~+0.04% net is realistic deploy bar)
- **W4 Sharpe > +0.50** (where regime coverage allows; lower for W4-only
  pairs like USDJPY)
- **MDD < 15%**
- **Trade count ≥ 100 cumulative** (lower than xau_session's 200 bar
  because shorter usable history on most FX pairs)
- **Fade-gap > +0.40** vs symmetric short-direction
- **NO single-day-of-week concentration > 50%**
- **Diversification check**: must not be highly correlated with xau_session
  (since both could surface at hour-00 UTC long). Specifically: trade-by-trade
  correlation with xau_session deploy variant must be < +0.50.

## Files (placeholder — populated as Phase 0a runs)

- `fx_session.md` — this doc
- `_profile_fx_hod.py` — Phase 0a hour-of-day comparative profile across
  EURUSD / USDJPY / GBPUSD / AUDUSD / USDCAD / NZDUSD
- Future: `_profile_fx_filters.py`, `fx_session_demo.py` (Phase 2),
  `fx_session_validation.py` (Phase 3)
- Data: pulled into datalake by `mt5_fetch.py` invocation; cached locally
  at `ohlc_data/<SYM>_H1.csv`

## Related strategies

- [[project_xau_session_phase0]] — closest analog, same mechanism family
- [[project_lunch_fade_ndx100_deploy]] — also session-handoff, different
  asset/time
- [[project_us_index_intraday_fade_pattern]] — cautionary methodology:
  generic "fade overshoot" theses sign-invert; require explicit
  vacuum/microstructure mechanism, not just "price has deviated"
