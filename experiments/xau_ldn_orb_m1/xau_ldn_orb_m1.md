# XAU London-open ORB (M1) — Asian-range breakout into LDN cash hours

**Status (2026-05-26):** Phase 2 COMPLETE — REJECT.

**Verdict:** **REJECT** — 2/8 pre-committed binding kill criteria PASS. The single-venue-concentrated-auction mechanism that powers `orb_dax` does NOT port to XAU's 24/7 OTC structure even with the LBMA-desk-staffing analog. Off-session C1 control fails decisively (lesson #-14 binding rule). Cost-zero gross +0.69 bp/trade → signal-absent per lesson #26 diagnostic (NOT friction-eaten).

## Verdict summary (2026-05-26)

Baseline LONG_cont (07:00 UTC LDN-open Asian-range break, T+90 exit, 0.20pt RT, n=775 / 8.4y):

| # | Criterion | Threshold | Observed | Result |
|---|---|---|---|---|
| 1 | FULL Sharpe | > +0.30 | **-0.17** | **FAIL** |
| 2 | W1 2018-2020 Sh | > +0.00 | -0.16 | **FAIL** |
| 3 | W2 2021-2022 Sh | > +0.00 | -0.04 | **FAIL** |
| 4 | W3 2023-2026 (holdout) Sh | > +0.20 | **-0.24** | **FAIL** |
| 5 | Max DD | < 12% | -5.92% | PASS |
| 6 | Trade count | ≥ 300 | 775 | PASS |
| 7 | Direction-gap (CONT − FADE) | > +0.40 | **+0.24** | **FAIL** (mechanism direction-weak, not direction-absent) |
| 8 | Cost-stress @ 0.30pt | > 0.00 | **-0.42** | **FAIL** |
| 9 | Deflated Sh | > +0.10 | — | not run (#1 fails decisively) |
| 10 | Corr vs deployed XAU book | < +0.50 | +0.47 | PASS-but-irrelevant |
| 11 | Off-session C1 delta | > +0.40 | **-0.06** | **FAIL — binding** |

Six of eight required PASS, plus the binding lesson #-14 off-session control. Three deploy-blockers: (a) W3 holdout negative, (b) zero-cost gross only +0.69 bp/trade vs ~5 bp default cost = signal-absent, (c) LDN-open NOT specially better than shift+12h off-session window.

## Phase 2 full results

### Baseline LONG_cont (deploy candidate)

```
period      : 2018-01-02 -> 2026-05-14 (8.4y)
trades      : 775  (93/yr)
win rate    : 49.2%   profit fac. : 0.95
mean/trade  : -0.0036%  (net of 0.20pt RT cost)
Sharpe      : -0.17
Max DD      : -5.92%
```

### Regime breakdown

| Regime | n | Sharpe | MDD | mean/trade |
|---|---|---|---|---|
| W1 2018-2020 | 245 | -0.16 | -3.67% | -0.0035% |
| W2 2021-2022 | 184 | -0.04 | -1.85% | -0.0007% |
| W3 2023-2026 (holdout) | 346 | **-0.24** | -5.13% | -0.0053% |

Holdout is the worst regime — the inverse of the deploy-grade pattern. The mechanism is **decaying**, not building. orb_dax (deployed) has holdout Sharpe +0.93 as its single strongest regime — this XAU port has the opposite shape.

### 4-variant grid + direction-gap (lesson #13)

| Variant | n | Sharpe | mean/trade |
|---|---|---|---|
| LONG_cont   | 775 | -0.17 | -0.0036% |
| SHORT_cont  | 710 | -0.55 | -0.0160% |
| LONG_fade   | 710 | -0.36 | -0.0110% |
| SHORT_fade  | 775 | -0.83 | -0.0178% |
| **CONT avg** | — | **-0.36** | — |
| **FADE avg** | — | **-0.60** | — |
| **dir-gap** | — | **+0.24** | — |

dir-gap +0.24 is positive — the mechanism direction is *weakly* in the predicted (continuation) direction — but it's below the +0.40 bar. Per lesson #-19, the goalpost-moving option (REJECT CONT, adopt FADE) is also unavailable because the FADE direction is decisively negative. Both directions lose; CONT loses less. This is essentially a no-signal-with-noisy-asymmetry pattern, consistent with the SPX500 ORB REJECT from orb.md (both directions lose, no directional content).

### Cost sweep — LONG_cont

| Cost RT | Sharpe | MDD | n |
|---|---|---|---|
| 0.10pt | **+0.08** | -4.70% | 775 |
| 0.15pt | -0.05 | -5.31% | 775 |
| **0.20pt (deploy)** | **-0.17** | -5.92% | 775 |
| 0.30pt (stress) | -0.42 | -9.29% | 775 |
| 0.50pt | -0.91 | -16.10% | 775 |

At 0.10pt RT (below the realistic Eightcap floor of ~0.15-0.20pt), Sharpe barely clears zero (+0.08). This is the lesson #26 signal-absence diagnostic in action: cost-zero gross is +0.69 bp/trade (per off-session control), which annualizes at the LONG_cont sample variance to Sharpe ~+0.32. After realistic 5 bp cost (0.20pt at $4500 avg price), per-trade net is -3.6 bp — Sharpe goes negative. **There is no edge to extract**, even at zero friction the signal is sample-noise-grade, not "real edge eaten by friction".

### Off-session C1 control (binding, lesson #-14)

Identical signal logic on three windows. Zero-cost (so the comparison is pure signal):

| Window | n | mean/trade | Sharpe (zero-cost) |
|---|---|---|---|
| **LDN-open (baseline, 22-07 Asian → 07-10 trade)** | 775 | +0.0069% | **+0.32** |
| shift+7h (Asian=05-14, trade=14-17 = NY-AM analog) | 1001 | +0.0035% | +0.11 |
| shift+12h (Asian=10-19, trade=19-22 = late-NY) | 463 | +0.0132% | **+0.39** |
| **in-session − best-off-session delta** | — | — | **-0.06** |

LDN-open is **not** specially better than the shift+12h window (Asian-range = 10-19 UTC, trade = 19-22 UTC). Both clear cost-zero Sharpe ~+0.35. The lesson #-14 binding bar requires the LDN window to dominate off-sessions by ≥+0.40 Sharpe; it dominates by *-0.06*. **The mechanism is not LDN-open-specific — it's a generic 24/7 instrument range-break drift that surfaces in any 9h-Asian-range × 3h-break-window combination.** This directly falsifies the thesis's core mechanistic claim (LBMA-bullion-desk-staffing concentrates flow at LDN cash open).

Per the lesson #-14 binding rule, this is by itself a Phase 0 REJECT (criterion #11). Had Phase 0b been run before Phase 2 (as the thesis Phase 1→2 plan specified), Phase 2 could have been skipped entirely. **Methodological win**: the pre-committed C1 control is the sharpest single diagnostic in this experiment — it would have killed the thesis in 10 lines of code without needing the simulator at all.

### Correlation vs deployed XAU book

| Metric | Value | Threshold |
|---|---|---|
| n shared days | 662 | — |
| corr (Pearson) per-day-PnL vs xau_session proxy | **+0.47** | < +0.50 |

PASSES the diversification bar by a thin margin (+0.03 below threshold), but moot — the strategy itself loses money, so diversification value is zero. The +0.47 correlation does confirm the deployed `xau_session` is capturing roughly half of the same flow that this thesis attempted to extract; the *remaining* uncorrelated half is the signal-absent residual.

## Mechanistic interpretation (why the transplant failed)

1. **orb_dax mechanism requires LITERAL single-venue concentrated auction.** orb.md is explicit that the deploy-grade ORB result on GER40 is driven by Xetra's 09:00 cash auction — all 40 DAX constituents resolve their overnight information simultaneously at one venue, producing a clean information-release impulse the strategy can ride. The LBMA-bullion-desk analog is **structurally different**: there is no single moment when all of XAU's 24/7 OTC dealer book turns over. Bullion desks staff up at LDN open, but the cash market has been continuously price-discovering since the prior NY close — there is no information-release event analogous to Xetra opening. UK100 REJECT (orb.md, Sh -0.54) was the closest prior point — LSE has the single venue but ADR pre-trade smears the auction. XAU is one step further away from the orb_dax mechanism: no venue, no auction at all.

2. **xau_session has already extracted the Asian-handoff drift.** Confirmed by the +0.47 correlation vs the deployed daily-Variant-C book. The directional Asian → European handoff flow is real (Variant C captures it at H1 with DOWN-med filter), but the M1 ORB trigger on top of an Asian range adds zero information — it just resamples the same flow that the calendar-trigger Variant C already takes. With the deployed book in place, the LDN-open ORB has *no novel signal source*.

3. **W3 holdout being the WORST regime mirrors lesson #-14's W2-decisive-fail shape.** xau_ldn_am_fade REJECT had W2 Sh -0.63 as the load-bearing fail; this REJECT has W3 Sh -0.24 as the deploy-killing fail. Both are LDN-AM-window strategies on XAU at M1/M15. Together they tombstone the 07-10 UTC LDN-AM window for XAU intraday in BOTH directions (FADE rejected 2026-05-26 morning; CONT rejected 2026-05-26 afternoon). XAU intraday infrastructure is now bounded by: **NY-AM (deployed FADE) + Asian-handoff (deployed continuation) only.**

4. **The +0.69 bp/trade zero-cost gross is sample-variance-grade.** At n=775 trades with per-trade std ~50 bp, the standard error on the mean is 50/sqrt(775) ≈ 1.8 bp. The observed +0.69 bp is *less* than 1× standard error — entirely consistent with no signal at all. This is the cleanest lesson #26 diagnostic in the repo: cost-zero ≈ 0 → no edge, not "friction-eaten edge". Distinct from `xau_ldn_am_fade` (also REJECT but where cost-zero was small-positive and the question was friction-eaten-vs-signal-absent).

5. **Methodological win — the pre-committed C1 control is the load-bearing kill.** Lesson #-14 introduced the rule "before transplanting an intraday-microstructure strategy to a second session window on the same instrument, explicitly run the in-session-vs-off-session C1 control on the candidate window FIRST." This experiment is the **second application** of that rule (after `xau_ldn_am_fade`), and it identifies the kill cleanly: shift+12h beats LDN-open zero-cost, so the mechanism is not LDN-specific. Had we run the C1 check as Phase 0b before writing the simulator, the experiment would have closed in 30 minutes instead of needing the full 4-variant + cost-sweep + regime battery. **Next intraday-microstructure thesis on any instrument: run the C1 control as the first diagnostic, before ANY simulator work.**

## Lesson candidates for RESEARCH_NOTES.md

- **Lesson #-20 candidate (XAU intraday window exhaustion)**: with `xau_break_retest_m15/h1` deployed on NY-AM, `xau_session` deployed on Asian-handoff, `xau_ldn_am_fade` REJECTED (LDN-AM FADE), `xau_ldn_orb_m1` REJECTED (LDN-AM CONT) — XAU intraday at retail has now been comprehensively mapped. The two deployed windows (NY-AM + Asian) are the only positive-signal windows; the LDN-AM window is dead in both directions; mid-NY and late-NY have not been tested but are LIKELY redundant with deployed NY-AM strategies. **Future XAU intraday theses must either (a) propose a window NOT in {Asian, LDN-AM, NY-AM}, or (b) propose a fundamentally different trigger type (event-driven, regime-conditional) on an already-tested window.** Generic time-of-day or range-break theses on remaining intraday windows are pre-tombstoned.

- **Lesson #-21 candidate (orb_dax mechanism is venue-specific, NOT timeframe-specific)**: orb_dax PASSES at M5 on Xetra single-venue cash auction; this XAU port FAILS at M1 even though XAU has 2.5× tighter cost-to-bar-range ratio. Going to a finer timeframe on a more-cost-favorable instrument does not rescue a mechanism that requires a literal single-venue concentrated auction. The cost-floor analysis at the start of this thesis (M1 floor on XAU because spread is 0.64bp) was *necessary but not sufficient* — the mechanism still needs the venue-concentration prerequisite, which XAU's 24/7 OTC structure lacks. **Rule for future ORB transplants**: the deploy-grade prerequisite is single-venue-concentrated-auction (DAX/Xetra). Cost-favorable instruments without venue concentration (XAU, BTC, FX, commodities) are pre-tombstoned for ORB-family theses regardless of timeframe.

## Files

- `xau_ldn_orb_m1.md` — this doc (verdict updated 2026-05-26)
- `xau_ldn_orb_m1_demo.py` — Phase 2 simulator (numpy inner loop, 4-variant grid + off-session C1)
- `_fetch_xau_m1.py` — datalake puller (kept; M1 data shared with `xau_fix_drift`)
- Data: `ohlc_data/XAUUSD_M1.csv` (2.82M bars 2018-01-02 → 2026-05-26)

## Original pre-committed thesis follows below (preserved unchanged)

---

## Origin

User question (2026-05-26): given Eightcap's ~0.15pt XAUUSD spread (~0.64 bps RT), how fast can we go on XAU? Cost math says **M1 is the practical floor** — M1 bar range on XAU is 3-8 bps, comfortably above the cost floor, whereas M1 on indices (SPX500 etc.) sits below the cost floor and dies. This thesis tests whether the ORB mechanism — deployed at M5 on GER40 (Sh +0.76, deployed 2026-04-22) — ports to XAUUSD at M1 using the Asian session as the range-defining window and the London cash-hours as the break-watch window.

Direct sibling of deployed `orb_dax` (M5, Xetra cash open). Distinct from `xau_session` (deployed H1 Asian-handoff continuous drift) by trigger: ORB requires an explicit *range break*, `xau_session` fires every day on calendar trigger. The intent is for the two to be *low correlation despite same flow universe* — different triggers select different days.

## Thesis (mechanism)

The Asian session (22:00 prior → 07:00 UTC, 9 hours) establishes an overnight range for XAUUSD reflecting Tokyo/HK/SGP institutional flow + light Sydney/Wellington liquidity. The London cash open (07:00-08:00 UTC, anchored to LBMA bullion desk staffing) is the first window in which European real-money desks add directional flow. A *break of the Asian range* during the London-open window is an information-resolution event:

1. **Asian range = institutional benchmark**: gold desks reference the overnight Asian range as the prior-period reference for risk; LDN cash-open positioning is set relative to it.
2. **London-open liquidity wave**: 07:00-08:00 UTC sees the largest intraday liquidity step-up — bid/offer depth at Eightcap (and the underlying OTC market) jumps 3-5× vs pre-07:00 levels. Breakouts in this window meet sufficient continuation liquidity to push trend, vs the Asian session where breakouts often retrace on thin book.
3. **Trend-day bias on event-rich days**: macro-event days (NFP, CPI, FOMC, ECB) frequently break the Asian range early and trend. orb_dax's structural finding (3h opening-impulse persistence) is hypothesized to port — gold is not Xetra-auction-concentrated like DAX, but the LBMA-desk flow concentration at LDN open is the analog.

The mechanism specifically requires *single-venue concentrated flow at the break window* — orb.md Cross-instrument finding #1. XAU's analog: even though XAU trades 24/5 globally with no single exchange, the OTC LBMA-member-bank dealer flow is concentrated at LDN cash-hours (Goldman, JPM, HSBC, UBS — five of the LBMA market-maker banks have their primary bullion desks in London). This is the structural mirror of DAX/Xetra: not a *literal* single auction, but a concentrated *dealer-bank desk-staffing* moment that funnels flow.

**Why this is not auto-pre-rejected by lesson #-14 (`xau_ldn_am_fade` REJECT)**: that lesson tombstones a *fade* strategy in the same 07-10 UTC window. The mechanism cited (LME AM auction one-way real-money flow pre-positions in the entry window) is the *exact* mechanism this thesis is trying to ride in the *continuation* direction. Lesson #-14 essentially says "there is one-way directional flow in this window; do not fade it". This thesis says "ride it via range-break trigger". The two are mechanistically aligned, not contradictory.

## Key references

- **`orb.md`** (deployed `orb_dax`) — primary template. M5 ORB on GER40 PASS Sh +0.76, mechanism = single-venue concentrated opening auction. This thesis is the XAU-M1 analog with LDN bullion desk wave as the venue-concentration mechanism.
- **Crabel (1990)** — Opening Range Breakout original framework. M5/M15 OR on equity futures.
- **Zarattini & Aziz (2023)** — Modern QQQ ORB. Demonstrates 5-min OR with strict cost+volume filters survives at retail M5 timescales. We're going one TF finer (M1) on the lowest-cost retail-tradeable instrument.
- **Repo lesson #-14** — `xau_ldn_am_fade` REJECT — pre-tombstones the FADE direction in this same window. Tied directly to this thesis's CONTINUATION direction; if FADE fails AND CONT also fails, the 07-10 UTC LDN window is dead in both directions and XAU intraday infrastructure is bounded by NY-AM (deployed) + Asian (deployed) only.
- **Repo lesson #-15** — TF×window 2-D search. M1 is at the fast end of the search ladder; OR width and break window must be picked together. M5-OR (5 min) + 60-min break-watch is the pre-committed baseline.

## Signal math — pre-committed config (LONG-only baseline, BOTH-direction null check)

```
Parameters:
  ASIAN_RANGE_START_UTC     = 22                    # prior calendar day
  ASIAN_RANGE_END_UTC       = 7                     # current day
  LDN_OR_MINUTES            = 5                     # 1-bar M1 OR within LDN-open window
  LDN_OR_ANCHOR_UTC         = (7, 0)                # 07:00:00 UTC, define a 5-min "LDN-OR"
                                                    # which must break the *Asian range*
  ENTRY_CUTOFF_UTC          = (10, 0)               # no new entries after 10:00 UTC
  T_EXIT_MIN                = 90                    # 90-min time-of-day exit
  EXIT_HARD_UTC             = (12, 0)               # hard flat by 12:00 UTC (before NY-AM)
  COST_POINTS_ROUND_TRIP    = 0.20                  # Eightcap conservative; sweep 0.10/0.15/0.20/0.30
  STOP                      = opposite Asian-range bound
  DIRECTION                 = LONG-only primary; BOTH-direction null check pre-committed
  MIN_ASIAN_RANGE_BPS       = 15                    # below this, range too tight — skip day

Per trading day (UTC-anchored, Mon-Fri only):

  Asian_high = max(high) over M1 bars in [prior-day 22:00 UTC, today 07:00 UTC)
  Asian_low  = min(low)  over M1 bars in [prior-day 22:00 UTC, today 07:00 UTC)
  Asian_range_bps = (Asian_high - Asian_low) / mid(today 07:00) * 1e4

  if Asian_range_bps < MIN_ASIAN_RANGE_BPS:
    skip day                                        # range too tight; break-direction noise-dominated

  For each M1 bar b in [07:00, 10:00 UTC):
    if flat and b.close > Asian_high and first long-break of day:
      LONG variant:    enter LONG at next bar open
                       stop at Asian_low
                       T+90min time exit, or 12:00 UTC hard flat
      SHORT-null:      enter SHORT at next bar open (same bar)
                       same stop/exit structure (mirrored)

    if flat and b.close < Asian_low and first short-break of day:
      LONG variant:    skip (LONG-only baseline)
      BOTH-direction:  enter SHORT at next bar open
                       stop at Asian_high
                       T+90min time exit, or 12:00 UTC hard flat

  Max 1 round-trip per day per direction.

  Variants to score:
    LONG-only      (baseline; orb_dax pattern post-asymmetry-split)
    BOTH-symmetric (LONG + SHORT, lesson #54 pre-commit)
    LONG-FADE      (LONG when Asian range broken DOWN — null check, lesson #13)
    SHORT-FADE     (SHORT when broken UP — null check, lesson #13)
```

The four-variant grid (LONG-cont / SHORT-cont / LONG-fade / SHORT-fade) is the standard fade-test diagnostic; a positive `dir-gap = mean(CONT) - mean(FADE)` is required per lesson #13 + #-19.

## Why retail-accessible at M1

- Eightcap XAUUSD spread is **0.34 bp RT median** with no widening at 07-08 UTC (per `xau_session` Phase 0). All-in cost ~1.9 bp RT (~0.20pt). M1 bar range at LDN open is typically 4-9 bp, so per-trade gross-to-cost ratio is favorable.
- M1 entry + 90-min time-exit means 90 M1 bars per trade. Slippage on stop hit at Asian-range opposite bound is 1-2 ticks on average — modest within the cost budget.
- Single MT5 EA, UTC-anchored scheduler, ~250 fix-days/year × ~60-80% range-break-rate × Asian-range-filter pass rate ≈ ~100-150 trades/year (LONG-only).
- No special infrastructure — the LDN-OR + Asian-range computation is identical in pattern to orb_dax.

## Universe

XAUUSD only. ORB-on-XAU is the deploy candidate. Two natural extensions deliberately deferred to follow-on experiments:
- **EURUSD M1 LDN ORB** — cost on Eightcap is 0.4-0.8 bp RT (per `fx_session` cost notes); marginally above XAU but possibly viable. Defer.
- **XAU M5 LDN ORB** — coarser TF on same window. Per lesson #-15 (TF×window is a 2-D peak search), the M-shape may peak at M5 not M1. Run if M1 PASSES, to find the local maximum.

## Expected performance (pre-committed point estimates)

orb_dax (deployed): research Sh +0.76 / holdout +0.93 / MDD -7.8% / 197 trades/yr at M5 GER40.

XAU LDN ORB at M1 is a faster-bar variant with higher fill noise but tighter cost-per-bp ratio. Expectations:

- **Research Sharpe** +0.30 to +0.70 (point +0.45 — explicitly below `orb_dax`'s +0.76 because M1 fill noise on a CFD is higher than M5 fill noise, and the LDN bullion-desk concentration is weaker than Xetra single-venue auction).
- **Holdout (W3 2023-2026) Sharpe** ≥ +0.20 (BTC W4-floor-binding analog per lesson #31, here weakened to +0.20 because we have a deployed sibling, `xau_session`, capturing W3 strongly).
- **MDD** < 12%.
- **Trade cadence** 100-200/year.
- **WR** 38-48%, **PF** 1.10-1.30.
- **Direction-gap** > +0.40 (lesson #13 + #-19).

## Fail conditions (PRE-COMMITTED — written before backtest runs)

| # | Criterion | Threshold | Direction |
|---|---|---|---|
| 1 | LONG-only net Sharpe (full sample, 0.20pt RT) | > +0.30 | binding |
| 2 | W1 2018-2020 LONG Sharpe | > +0.00 | binding |
| 3 | W2 2021-2022 LONG Sharpe | > +0.00 | binding |
| 4 | W3 2023-2026 (holdout) LONG Sharpe | > +0.20 | binding (holdout floor) |
| 5 | Max DD | < 12% | binding |
| 6 | Trade count | ≥ 300 over 7-8 years | binding (else INSUFFICIENT_N) |
| 7 | Direction-gap (LONG-cont Sh − LONG-fade Sh) | > +0.40 | binding (lesson #13) |
| 8 | Cost-stress @ 0.30pt RT: LONG Sharpe | > 0.00 | binding |
| 9 | Deflated Sharpe (n_trials=8: LONG/SHORT × cont/fade × 2 cost levels) | > +0.10 | binding |
| 10 | **Trade-by-trade correlation vs deployed XAU book** (xau_session + xau_br_m15 + xau_br_h1, per-day-aggregated PnL) | **< +0.50** | **binding — tombstone if violated** |
| 11 | **Off-session C1 control** (per lesson #-14): run identical signal logic on a non-LDN-open window (e.g. break of prior-day NY-PM range at 14:00 UTC entry); LDN-open Sh − off-session Sh delta | > +0.40 | binding |

If LONG-only fails BUT BOTH-symmetric or LONG-fade or SHORT-cont passes by hand-tuning the variant — that is goalpost-moving (per lesson #-19 + lesson #20). REJECT, no salvage. The pre-committed direction is LONG-only (orb_dax pattern + xau_session LONG-bias prior).

If criterion #10 fails (correlation > +0.50 with deployed book): REJECT-by-redundancy. The mechanism is real but adds no portfolio diversification value beyond deployed `xau_session`.

If criterion #11 fails (no in-session-vs-off-session edge differential): the mechanism is generic time-of-day drift on XAU, not LDN-open-specific. REJECT — this directly applies the new methodological rule from lesson #-14.

## Why this might fail (red flags)

1. **High correlation with deployed `xau_session`** — same flow universe (Asian → LDN handoff), partially overlapping time window. `xau_session` exits at 08:00 UTC LONG; this thesis enters at 07:00 UTC on LDN-OR break-UP and may sit in the position `xau_session` is exiting from. Criterion #10 is the binding tombstone.

2. **No single-venue concentrated auction**. orb.md is explicit that ORB works specifically when constituents resolve overnight information at one venue's opening auction. XAU has no such auction — LBMA Gold Fix is at 09:30 / 14:00 UTC, *not* at LDN cash open (07:00 UTC). The bullion-dealer-desk-staffing concentration is a weaker mechanism than Xetra's literal single auction. **This is the main mechanistic risk.** orb.md UK100 REJECT (Sh -0.54) found that single-venue (LSE) was *not enough* — overnight info arrives via ADR pre-LSE-open, smearing the auction; XAU could fail for the same reason (Asian session has already digested overnight events).

3. **Lesson #-14 already says LDN-AM 07-10 UTC is hostile.** That lesson rejected a *fade*, but explicitly notes "LDN-AM is a directional window, not a fade window" (point 1) and "LME AM auction (10:30 UTC) leaks into the entry window" (point 2). If the directionality is real, CONT-on-Asian-range-break should PASS. If LDN-AM is hostile in BOTH directions, the window has no extractable edge.

4. **M1 fill noise**. Eightcap M1 OHLC is broker-reconstructed from tick stream; M1 bar opens can be 0.5-2 pts off from tick fills on volatile bars (typical at LDN-open). Phase 2 must include a slippage stress test: add +1 pt cost on entries during the 5 min following LDN-OR window and re-check Sharpe.

5. **Asian-range filter calibration**. MIN_ASIAN_RANGE_BPS=15 is pre-committed but un-tested. Too tight = excludes deployable days; too loose = noise trades. A sweep is part of Phase 2 but the deploy variant is the pre-committed value (per orb.md "do not aggregate best variant").

6. **Holiday and DST regime contamination**. UK bank holidays (May Day, Jubilee) leave the 07-10 UTC window pseudo-Asian; Christmas/New Year week is illiquid. Phase 2 must explicitly handle these.

7. **Deployed `event_calendar` overlaps macro-event days.** On NFP/CPI/FOMC days, `event_calendar` is positioning on NDX. XAU correlates with USD/yields on macro releases. Although criterion #10 covers XAU book correlation, the macro-cross-asset interaction is a separate concern — flag for post-Phase-2 audit if Phase 2 passes.

## Phase 1 → 2 plan

- [ ] **Phase 0a — data**: fetch XAUUSD_M1 from datalake (or `scripts/mt5_fetch.py --symbols XAUUSD --timeframes M1 --datalake`). Need ≥ 5 years back to 2020. Estimated ~1.3M M1 bars. Shares M1 data with `xau_fix_drift` (write once, both thesis use).
- [ ] **Phase 0b — off-session C1 pre-check (cheap)**: per lesson #-14 binding rule, run the in-session-vs-off-session control BEFORE Phase 2. Compute zero-cost daily-mean of (Asian-range-break LONG-continuation entry) for LDN window (07-10 UTC) vs control window (e.g. 14-17 UTC NY-PM break of prior-LDN range, or 02-05 UTC mid-Asia break of prior-NY range). If `Δ mean < +0.20%/trade` zero-cost, the LDN-open is not a special window → REJECT before Phase 2.
- [ ] **Phase 0c — `xau_session` correlation pre-check**: aggregate trigger days (Asian range broken UP in LDN window) and compute daily-PnL correlation against deployed `xau_session`. If corr > +0.6 at the raw trigger level, criterion #10 is at risk → flag for early consideration of REJECT-by-redundancy framing.
- [ ] **Phase 1**: write `xau_ldn_orb_m1_demo.py` per signal-math block above. Pre-commit LONG-only as primary; BOTH-direction null in same simulator pass.
- [ ] **Phase 2 baseline**: run 4-variant grid (LONG-cont / SHORT-cont / LONG-fade / SHORT-fade), score against 11 binding criteria.
- [ ] **Phase 2 regime breakdown**: W1 2018-2020 / W2 2021-2022 / W3 2023-2026.
- [ ] **Phase 2 cost sweep**: 0.10 / 0.15 / 0.20 / 0.30 / 0.50pt RT.
- [ ] **Phase 2 sensitivities** (informational only — do not goalpost-move on these):
  - MIN_ASIAN_RANGE_BPS ∈ {5, 10, 15, 25, 40}
  - LDN_OR_MINUTES ∈ {1, 3, 5, 10, 15}
  - T_EXIT_MIN ∈ {30, 60, 90, 120, 180}
- [ ] **Phase 2 correlation tombstone**: trade-by-trade per-day-aggregate PnL correlation vs deployed XAU book.
- [ ] **Phase 2 off-session control (full)**: per lesson #-14 binding rule, re-run identical simulator on a control window for the C1 differential test.
- [ ] **Update this doc** with results + verdict + RESEARCH_NOTES + STATE.md YAML.

## Files

- `xau_ldn_orb_m1.md` — this doc
- `xau_ldn_orb_m1_demo.py` — Phase 2 simulator (to be written)
- `_fetch_xau_m1.py` — shared with `xau_fix_drift` (write once)
- `_off_session_control.py` — lesson #-14 C1 pre-check (to be written)
- `_corr_precheck.py` — Phase 0c deployed-book correlation pre-check (to be written)
- Data: `ohlc_data/XAUUSD_M1.csv` (to be populated)
