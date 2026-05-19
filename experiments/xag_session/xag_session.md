# XAGUSD intraday session structure — Phase 0 exploration

**Status (2026-05-16):** Phase 0 starting. Test whether the Asian-session
structural drift mechanism that PASSED on XAUUSD (xau_session, deployed
2026-05-16) also works on silver. Honest prediction: silver should activate
the mechanism similarly to gold (both physical-sovereign-driven metals), but
with lower amplification confidence than gold's W4 +1.23 Sharpe.

## Origin

xau_session deploy is live as of 2026-05-16. The deploy variant (Variant C
23-08 UTC + DOWN-med prior-NY filter) captures structural Asian-session
drift driven by Asian OTC physical / sovereign reserve / Indian / Chinese
flow rotation. Silver (XAGUSD) shares the physical-metals demand structure
with gold but has materially different flow characteristics:

- **More industrial demand share**: ~60% industrial vs ~10% for gold
  (per World Silver Survey 2024). Industrial demand correlates with
  growth/equity cycles, not USD-weakness regimes.
- **Less central-bank reserve demand**: silver is not held as sovereign
  reserve at material scale. Indian household demand exists but is
  smaller in absolute USD terms than gold.
- **Retail/ETF concentration**: silver ETFs (SLV) have proportionally
  higher retail share; physical bar demand is lower per dollar.
- **Higher vol**: silver typically has 2-3x gold's per-bar vol
  (XAUUSD H1 std ~0.15-0.2%, XAGUSD H1 std ~0.4-0.6% historically).

Predictions for the Asian-session-handoff thesis on silver:

1. **Hour-00 UTC drift exists** — yes (same Tokyo-open structural flow
   touches both metals)
2. **Direction is positive (LONG)** — yes (same USD-weakness mechanism)
3. **W4 amplification matches gold's 3.5x** — uncertain. Silver's lesser
   sovereign-reserve role means the 2024-2026 sovereign-reserve-rotation
   thesis may apply more weakly. Could be 1.5-2x rather than 3.5x.
4. **Cost economics**: silver Eightcap spread is typically 1.5-3 pips on
   raw account = 7-15 bps RT (vs XAU 0.35bp). MUCH wider cost barrier
   per percent of price. Mitigation: higher vol means bigger gross per
   hold to overcome the wider cost.

This is a different reckoning than retail-FX (which failed) — silver per-hour
moves are large enough that even at 10 bp RT cost the absolute gross can
clear it. The question is whether the Asian-session-specific drift
concentrates enough to amplify a multi-hour hold above 10 bp gross.

## Key reference

- World Silver Survey 2024 (Silver Institute) for demand breakdown
- xau_session.md — companion strategy, deployed 2026-05-16, full pipeline
- [[project_asian_session_family_divergence]] — XAU +1.23 / BTC +0.64 /
  WTI -0.58 W4 split across the same Asian-session hour-window. Silver
  becomes the 4th data point in this family.

## Signal math (preliminary, finalized after Phase 0)

Phase 0 hour-of-day profile:
- pct_change of H1 close-to-close across all hours UTC
- Per-hour mean + std + t-stat
- Regime breakdown (W1=2019, W2=2020-2021, W3=2022-2023, W4=2024-2026)
- Cross-comparison vs xau_session profile to assess mechanism overlap

If Phase 0 shows hour-00 t > +3 in W4 specifically (the deploy-binding
regime per [[feedback_btc_w4_floor_binding]]), proceed to Phase 0b filter
exploration.

If hour-00 W4 is weaker than +1.5 OR there's a regime decay pattern
(W4 << W3 or W4 negative): tombstone — silver doesn't carry the gold-
physical-flow story strongly enough.

## Pre-committed exploration plan

### Phase 0a — hour-of-day profile (running now)
- Same template as xau_session/_profile_xau_hod.py
- Cross-reference vs xau profile to identify silver-specific vs
  gold-shared patterns

### Phase 0b — multi-hour holds + filter sweep (conditional on Phase 0a)
- Same template as xau_session/_profile_xau_holds.py + _profile_xau_filters.py
- Variant C (23->08 UTC, 9-hour overnight) as the primary candidate
- DOWN-med filter (prior-NY direction × magnitude) overlay
- Cost sweep at 5/10/15 bp RT (silver-realistic Eightcap)

### Phase 0c — Eightcap XAGUSD spread verification (conditional)
- Pull M1 spread distribution via MT5 (same template as
  xau_session/_check_xau_spread.py)
- Need: median + p90 + max during 23-08 UTC deploy window
- Bar: median ≤ 10 bp RT for deploy viability

### Phase 2 — simulator + kill criteria (conditional)
- Same template as xau_session_demo.py with silver-adjusted cost model

## Pre-committed kill criteria (FX-style sketch, will finalize after Phase 0)

These will be tightened/loosened in Phase 1:

- **W4 Sharpe > +0.50** at honest XAGUSD cost (binding per W4-floor lesson)
- **FULL Sharpe > +0.30** at honest cost
- **MDD < 20%** (slightly looser than gold's 15% — silver vol is higher)
- **Trade count ≥ 100** cumulative (matches silver's expected ~40/yr × 6yr)
- **Fade-gap > +0.40** vs symmetric short variant
- **Cost-stress at 1.5× realistic** Sharpe must remain positive
- **Correlation with xau_session < +0.70** trade-by-trade — silver must
  not just be a more-volatile gold clone. If correlation > 0.70,
  diversification benefit is marginal.

## Files

- `xag_session.md` — this doc
- `_profile_xag_hod.py` — Phase 0a hour-of-day profile (running now)
- Future: `_profile_xag_filters.py`, `_profile_xag_holds.py`,
  `_check_xag_spread.py`, `xag_session_demo.py`
- Data: `ohlc_data/XAGUSD_H1.csv` (42,706 H1 bars, 2019-2026)
