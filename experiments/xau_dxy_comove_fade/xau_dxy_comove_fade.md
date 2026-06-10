# XAU/DXY co-movement fade — correlation-breakdown reversion (real USDX)

**Status (2026-06-01):** **REJECT at Phase 0.** No Phase 1 built. Tombstoned to
STATE_GRAVEYARD.

**Verdict summary (2026-06-01):** REJECT. Fails criteria 1, 3, 5 outright;
2 and 4 marginal/inconsistent. With **real USDX** (daily corr −0.439, M5 −0.375 —
the inverse is real but moderate), the co-move-breakdown fade produces no
tradeable forward reversion in XAU.

**Headline failures:**

1. **Magnitude an order below the floor.** Best signed cell is **+1.3 bp**
   (W=6, θ=70, 90 min, t=+2.46); nothing clears the **+3 bp** Phase-0 floor and
   everything is **below the 2 bp Eightcap RT cost**. (Sec 3)
2. **Asymmetric — the "edge" is one-directional long-gold.** The both-DOWN leg
   (dollar down + gold down → fade = LONG XAU) carries it (90m +1.9/+2.24);
   the both-UP leg (→ SHORT XAU) is flat-to-negative (θ=85 both-up 120m =
   **−3.7/−2.25**). A long-gold bias, not a structural co-move reversion. (Sec 5)
3. **W4-only — a 2024+ gold-bull-run rider.** W3 (2022-2023, dollar-strength
   hiking regime) shows **zero/negative** reversion (30m −0.9/**−2.07**); all the
   positive signal is in W4 (90m +2.0/+2.67). If the mechanism were structural it
   would appear in the dollar-strength regime too. Same **bullrun-isolation**
   failure that killed `xau_asia_range` and `xau_dxy_stall`. (Sec 8)
4. **Anchor assumption refuted.** Leg attribution shows the *USDX* leg reverts
   marginally more reliably by t-stat (60m −0.3/**−2.05**) than gold (60m
   +0.5/+1.06) — but both at trivial (<0.5 bp) magnitude. Gold is not the
   cleanly-reverting leg the thesis assumed. (Sec 7)
5. **Direction gap inconsistent.** FADE beats CONTINUE at θ=50/70 (gap +0.5/+0.9,
   sub-bp) but **CONTINUE wins at θ=85** (gap −1.7) — no stable directional
   content. (Sec 6)

**Methodological win:** real USDX (2021-06+) removed the synthetic-DXY data
caveat that limited `xau_dxy_stall`, and the result is the same family verdict —
confirming it was the *mechanism*, not the proxy, that was absent. The hour-
matched same-rule control (Sec 4) again did its job: it showed the surface
+1.3 bp at 90 min barely clears noise vs an always-fade-the-dollar baseline
(delta +1.3/t+2.05, under the +1.5 bp gate).

**Mechanistic interpretation — why there's no edge:**

- DXY–XAU is a strong *contemporaneous* inverse (M5 corr −0.375) but carries
  **no exploitable forward reversion** after the inverse breaks intraday. By the
  time an M5 co-move is observable, the relationship has already re-equilibrated
  — consistent with `cross_asset_lead_lag` (M5 cross-asset lead-lag corr ≈ 0.05,
  HFT-closed) and `xau_intraday_mr` (XAU M5 efficient to ~0.2-0.3 bps).
- The real-rate anchor that drives the inverse is a daily/weekly force; its
  reassertion does not resolve on a 30-120 min M5 horizon.
- What looks like a co-move-reversion edge is the 2024+ gold bull leaking through
  the both-down/long-XAU leg — a regime bet, not a structural pairs signal.

**Family conclusion:** the DXY–XAU intraday-pairs family is now rejected from two
independent angles — momentum-stall reversal (`xau_dxy_stall`) and co-move-
breakdown reversion (this) — with real USDX closing the data-quality escape
hatch. Any future DXY-positioning XAU signal needs a lower-frequency / non-price
trigger (CFTC TFF positioning, 10Y real rates, ETF flows), not intraday CFD price.

## Origin

Follow-up to `xau_dxy_stall` (REJECT, Phase 0) and `cross_asset_lead_lag`
(REJECT, Phase 0). The stall experiment established that **DXY–XAU is a
*continuation* relationship at M5, not a momentum-exhaustion-reversal one**, and
was crippled by a synthetic-DXY proxy that (a) only went back to 2022-11 and
(b) showed a weak −0.41 daily correlation vs the textbook −0.6/−0.8.

This experiment changes two things:

1. **Real USDX M5** (MT5, fetched 2026-06-01, injected to the lake), 2021-06-10 →
   2026-06-01 — a true dollar-index series, not a 3-currency synthetic.
2. **A different mechanism**: not "DXY momentum stalls → XAU reverts" but
   "**XAU and DXY break their structural inverse (co-move same-direction) →
   the inverse reasserts → fade the anomalous leg**." This is a relative-value
   /pairs framing, distinct from the directional-momentum framing that
   `xau_dxy_stall` refuted.

## Thesis (mechanism)

1. **XAU and DXY are structurally inversely correlated.** The inverse runs
   through the real-rate (TIPS) channel and dollar-funding/FX-reserve flows.
   At the daily horizon the correlation is typically −0.5 to −0.8.
2. **The inverse occasionally breaks intraday: both rise together, or both fall
   together.** A positive co-movement violates the structural relationship. It
   happens when one leg is driven by an idiosyncratic, non-dollar flow — e.g. a
   gold-specific safe-haven bid, an ETF/physical block, or a dollar move driven
   by a cross (EUR/JPY event) that gold hasn't yet absorbed.
3. **Idiosyncratic co-moves are transient; the dollar anchor reasserts.** The
   real-rate channel is the slower, structural force. When the breakdown clears,
   the leg that moved *against* the structural inverse retraces toward the
   dollar-implied path.
4. **The dollar is the macro anchor; gold is the faster, noisier leg.** So the
   higher-probability reversion is in **XAU**: if USDX and XAU both rose
   (dollar strong, gold "should" be weak) → **SHORT XAU**; if both fell →
   **LONG XAU**. Phase 0 also measures the USDX leg's forward return to test the
   anchor assumption (which leg actually reverts).

Critical framing: this is a *fade of the co-move*, anchored on the dollar's
direction. It is NOT continuation of the dollar move (that's the direction
null-check), and NOT the stall-reversal mechanism (already tombstoned).

## Key reference

- Erb & Harvey (2006), "The Strategic and Tactical Value of Commodity Futures" —
  gold's dollar-beta and real-rate sensitivity.
- Internal: `xau_dxy_stall.md` (continuation > reversal at M5; data caveat),
  `cross_asset_lead_lag.md` (M5 lead-lag corr ≈ 0.05 — so any edge here must be
  a *state-conditioned reversion*, not a lead-lag prediction).

## Signal math

For each M5 bar `t`, over a co-move window `W` bars:
```
r_xau   = 1e4 * (log XAU[t]   - log XAU[t-W])      # bps
r_usdx  = 1e4 * (log USDX[t]  - log USDX[t-W])     # bps

comove_event(t) =  sign(r_xau) == sign(r_usdx)             # broke the inverse
               AND |r_xau|  >= THETA_XAU(pctile)           # both legs moved
               AND |r_usdx| >= THETA_USDX(pctile)

# Fade-XAU signal, dollar-anchored:
signal(t) = -sign(r_usdx)        # both up -> short XAU; both down -> long XAU

fwd_xau_signed[h] = signal(t) * 1e4 * (XAU[t+h]/XAU[t] - 1)   # bps, h in FWD_BARS
```
Sweeps: `W ∈ {3, 6, 12}` (15/30/60 min), `THETA` = {50th, 70th, 85th} pctile of
each leg's |W-bar return|, `FWD_BARS = {6, 12, 18, 24}` (30/60/90/120 min).

## Why retail-accessible

XAU is the showcase tradeable (Eightcap XAUUSD, 2 bps RT research cost). USDX is
read-only signal input (no trade required on the dollar leg). A Phase-1 strategy
trades XAU only, conditioned on the USDX co-move state — fully retail.

## Universe

- **Trade leg:** XAUUSD (CFD; deploy analog = spot gold on Eightcap MT5).
- **Signal leg:** USDX (real dollar index, M5).
- **Window:** 2021-06-10 → 2026-06-01 (USDX M5 coverage), ~5 years.

## Expected performance

Point estimate (pre-Phase-0, weak prior given two sibling rejects): if the
mechanism is real, expect signed forward XAU mean +3 to +8 bps at 30-60 min on
the large-co-move cells, decaying past 90 min. Cadence depends on θ: 70th-pctile
both-legs co-move is rare (sign-agreement is already the minority state given a
strong inverse), so expect ~150-500 events/yr — borderline on the 200-trade
floor at the strict thresholds.

## Fail conditions (pre-committed)

Phase 0 PASS (→ build Phase 1 sim) requires **all** of:

- **≥1 (W, θ, horizon) cell** with signed mean **≥ +3 bps** AND **t ≥ +2.0**.
- **Real-minus-control delta ≥ +1.5 bps, t ≥ +1.8** vs the hour-of-day-matched
  control (control applies the *same* `-sign(r_usdx)` fade rule on random
  non-event bars — isolates the co-move-breakdown contribution from any
  always-fade-the-dollar drift).
- **Symmetry**: both-up SHORT-XAU mean and both-down LONG-XAU mean both positive,
  within ±50% magnitude of each other.
- **Persists across W3 AND W4** (not a single-window artifact; W4 = 2024+ binding).
- **Direction null-check (gap > 0)**: the fade rule (`-sign(r_usdx)`) must beat
  the continuation rule (`+sign(r_usdx)`) — if both win, structural confound;
  if continuation wins, mechanism is sign-inverted (→ becomes a different,
  continuation thesis, re-route not extend).
- **Cell n ≥ 200** (cadence floor).

If only some clear → document as MARGINAL, do not build Phase 1.
If none clear → REJECT at Phase 0, tombstone to graveyard.

Downstream Phase 1 kill criteria (only if Phase 0 passes), per repo bar:
Sh FULL > +0.30 @ 2 bps RT; Sh W4 > +0.50; MDD < 25%; trades ≥ 200; cost-stress
passes at 4 bps RT; placebo-bar control gap ≥ +0.30; |corr| < 0.50 vs deployed
XAU book (`xau_session`, `xau_br_m15/h1`).

## Why this might fail (red flags)

- **Sign-agreement is the minority state under a strong inverse → thin cells.**
  Adding a magnitude filter on both legs thins it further. The 200-trade floor
  may not be reachable at the thresholds where the effect (if any) is strongest.
- **Continuation, not reversion.** `xau_dxy_stall` found DXY–XAU *continues* at
  M5 in the mechanism-strong cells. A co-move may simply continue (both keep
  going) rather than revert — the direction null-check is the load-bearing test.
- **The co-move may be information, not noise.** Both-down (dollar weak + gold
  weak) can signal a broad risk-on liquidation where gold is sold for liquidity;
  that regime can persist, not revert.
- **Real-rate anchor is a daily/weekly force, not M5.** Intraday co-moves may
  clear over hours-to-days, past any tradeable M5 horizon — same frequency
  mismatch that killed the stall variant.
- **USDX only from 2021-06** → no W1, partial W2; W3+W4 must both carry it.

## Phase 0 → Phase 1 plan

- [x] Phase 0 profile (`_profile_comove.py`) — ran 2026-06-01, **REJECT**
- [ ] ~~Phase 1 simulator~~ — not built (Phase 0 failed)
- [ ] ~~Phase 2-5 battery~~ — n/a

## Files

- `xau_dxy_comove_fade.md` — this doc
- `_profile_comove.py` — Phase 0 co-move forward-return profile
