# Pre-FOMC drift on EURUSD (24h pre-announce, direction TBD per lesson #54 / #57)

**Status (2026-05-26):** Phase 2 COMPLETE. The FX-side falsification test of the
deployed NDX-LONG-pre-FOMC mechanism. Same calendar (`fomc_calendar.csv`, 58
events matched 2019-2026 — EURUSD M5 coverage cuts the 8 W1-2018 events), same
24h window, same 30-min exit buffer; vessel = EURUSD M5.

**Verdict: REJECT — but a *third-outcome* reject that refines the framework
more sharply than either of the user's pre-posed outcomes.** The directional
content IS there full-sample (null-gap +0.75 Sharpe — comfortably above +0.30
threshold), and the placebo is clean (non-FOMC Wednesdays mean -0.025%, t -0.55
— rules out generic mid-week drift). But the signal points **LONG EURUSD** (=
USD weakens pre-FOMC, OPPOSITE the user's stated SHORT prior), AND the W4
(2024-2026) deploy-relevant regime is dead (mean -0.0093%, Sh -0.07), AND the
walk-forward third split (deploy-binding per lesson #29) is also negative
(OOS Sh -0.07 on n=19).

**Mechanism interpretation (the value-add).** The DXY-equity mechanical
negative-correlation regime that's dominated since post-2022 dovish-pivot
explains the LONG-EURUSD signal: pre-FOMC equity risk-on (the NDX-LONG-
drift mechanism that's deployed) co-occurs with USD weakening. EUR is the
opposite-side of a DXY trade; if NDX rises pre-FOMC and USD weakens pre-FOMC,
then EURUSD rises pre-FOMC — which is what the data show in W1/W2/W3. This
is NOT a separate flow mechanism (USD-risk-premium accumulation, as the user
hypothesised). It's the *same* equity-risk-on flow showing up as the FX-mirror
via the DXY-equity correlation. The user's two outcomes (PASS-USD-leg vs
FAIL-equity-vessel-only) were both incomplete — what we got is "the FX vessel
DOES move pre-FOMC, but via mechanical DXY-equity correlation, not via a
parallel USD-risk-premium leg."

The W4 collapse (Sh -0.07 on n=19) parallels the W4 decay in macro_drift
itself (W4 Sh +0.41 vs W3 +2.38, a ~6x reduction). Both legs of the same
flow have decayed in the deploy-relevant window, but the equity leg's decay
left it positive-floor (+0.41) while the FX leg's decay crossed zero. This
makes mechanistic sense: the FX leg was always the smaller-magnitude
shadow-of-the-equity-flow; same fractional decay leaves equity barely
viable and FX entirely dead.

**Implications for the deployed book.**

1. **NO new deploy.** Walk-forward + W4 fail; the deploy-relevant window
   doesn't carry the signal. Tombstone.
2. **Sharpens lesson #62 in a NEW direction.** The original #62 framing
   ("NDX event_calendar book is NDX-cash-equity-microstructure-specific")
   was about *whether* the mechanism extends to other vessels. The cleaner
   refined statement is: "The flow extends to other vessels via known cross-
   asset correlations (here, DXY-equity negative correlation post-2022),
   but the magnitude on those secondary vessels is the cross-correlation
   coefficient × the primary-vessel magnitude — which is necessarily
   smaller and decays first as the primary mechanism decays. Don't deploy
   on the secondary vessel — deploy on the primary."
3. **Does NOT corroborate the user's risk-premium-flow story.** The fact
   that EURUSD goes UP (not down) pre-FOMC refutes the "investors rotate
   into USD safe-haven cash ahead of Fed events" narrative. The mechanism
   is risk-on-into-the-print, not de-risking-into-the-print.

## Results (Phase 2, 2026-05-26)

### Baseline 24h, 1bp RT, n=58 events 2019-2026

| direction | events | mean | Sh (×√8) | WR | PF | MDD |
|---|---|---|---|---|---|---|
| LONG EURUSD  | 58 | +0.0335% | +0.29 | 55.2% | 1.34 | -1.81% |
| SHORT EURUSD (user prior) | 58 | -0.0535% | -0.46 | 44.8% | 0.63 | -4.61% |
| **null-gap LONG-SHORT** | — | **+0.0869%** | **+0.75** | — | — | — |

User's SHORT prior is wrong-signed. The signal lives in LONG EURUSD = USD weakens pre-FOMC.

### Regime breakdown (LONG, best direction)

| window | n | mean | Sh | WR | t |
|---|---|---|---|---|---|
| W1 2019 (partial) | 8 | +0.0912% | +2.00 | 75.0% | +2.00 |
| W2 2020-2021 | 15 | +0.0219% | +0.21 | 60.0% | +0.29 |
| W3 2022-2023 | 16 | +0.0662% | +0.48 | 62.5% | +0.67 |
| **W4 2024-2026** | 19 | **-0.0093%** | **-0.07** | 36.8% | -0.11 |

W4 is the deploy-binding regime per lesson #29 / lesson #31. It's negative. Same shape as macro_drift's W4-decay-but-positive vs this experiment's W4-decay-through-zero — the secondary-vessel decay outpaces the primary.

### Pre-commit kill checks

| criterion | threshold | observed | verdict |
|---|---|---|---|
| Per-trade mean | > +0.05% | +0.0335% | FAIL |
| W4 per-trade mean | > +0.03% | -0.0093% | FAIL |
| PF | > 1.3 | 1.34 | PASS |
| Sharpe (×√8) | > +0.30 | +0.29 | FAIL (by 0.01) |
| MDD | < 25% | -1.81% | PASS |
| Events | ≥ 40 | 58 | PASS |
| Direction null-gap (Sh) | ≥ +0.30 | +0.75 | PASS |
| Placebo benign | abs(mean)<0.04% OR abs(t)<1.5 | mean -0.025%, t -0.55 | PASS |
| Walk-forward OOS mean Sh | ≥ +0.30 | +0.19 | FAIL |
| Walk-forward min OOS Sh | ≥ 0 | -0.07 | FAIL |

5 of 10 binding kill criteria FAIL. The PASSES are on direction-content (null-gap, placebo) which together establish the mechanism is real and non-spurious, but every magnitude / regime / OOS criterion fails.

### Walk-forward (LONG)

| split | IS n | IS Sh | IS mean | OOS n | OOS Sh | OOS mean |
|---|---|---|---|---|---|---|
| IS 2019-2022 / OOS 2022-2026 | 23 | +0.53 | +0.0460% | 35 | +0.19 | +0.0252% |
| IS 2019-2023 / OOS 2023-2026 | 31 | +0.10 | +0.0108% | 27 | +0.46 | +0.0595% |
| IS 2019-2024 / **OOS 2024-2026** | 39 | +0.50 | +0.0543% | **19** | **-0.07** | **-0.0093%** |

The deploy-relevant third split is negative. Same exact lesson #29 / #31 / #36 walk-forward shape — full-sample looks promising, but the binding holdout window is dead.

### Cost sensitivity (LONG)

| cost (bp RT) | mean | Sh |
|---|---|---|
| 0.0 | +0.0435% | +0.37 |
| 0.5 | +0.0385% | +0.33 |
| 1.0 (default) | +0.0335% | +0.29 |
| 2.0 | +0.0235% | +0.20 |
| 5.0 | -0.0065% | -0.06 |

Cost-breakeven ~3-4 bp RT. EURUSD CFD is well inside this so the failure is signal-side, not friction-side.

### Window × buffer sweep

The 18h × 15min buffer cell peaks at Sh +0.40 (mean +0.0464%) versus baseline 24h × 30min Sh +0.29. Marginal cell-shopping lift; the post-hoc nature of picking that cell + the W4-still-dead reality means this doesn't rescue anything. Reported here as honest disclosure, not as a deployable refinement.

### Placebo (non-FOMC Wednesdays at 14:00 ET, n=66)

| direction | n | mean | t | Sh |
|---|---|---|---|---|
| LONG (best dir) | 66 | -0.0247% | -0.55 | -0.19 |
| SHORT | 66 | +0.0047% | +0.10 | +0.04 |

Clean placebo. The FOMC effect is event-specific, not a generic Wednesday-14ET microstructure pattern. This was the cleanest single result — without the regime decay and walk-forward failure, the +0.75 null-gap and clean placebo would be Phase-2-passing signals. They're not enough on their own.

## Why run this — the falsification value is the prize, not the deploy

`macro_drift` (LIVE on NDX100 since 2026-05-22) and the broader event_calendar
book (CPI/NFP/RetailSales/FOMC) sit on a single asserted mechanism: **scheduled
US-macro events cause institutional positioning into the print, which manifests
as pre-event drift on the asset that vessel-carries the positioning**. The
deployed shape says that vessel is *US cash equity index* — which is the same
NDX-cash-equity-microstructure framing that lesson #62 codified after the XAU
cross-asset extension was REJECTED.

The user's posed test: does the *FX side of the same dollar* show the
mirror-image pre-FOMC accumulation? Two outcomes, both informative:

- **PASS (SHORT EURUSD shows a positive net pre-FOMC mean with null-gap ≥ +0.30
  and walk-forward OOS mean Sh ≥ +0.30):**  
  The mechanism extends to USD-risk-premium accumulation flows. Pre-FOMC drift
  is not equity-vessel-specific; the flow has a parallel FX leg. Adds a
  potentially-deployable SHORT EURUSD strategy to the book AND refines
  lesson #-13 / lesson #56 from "first-read-mid-month/mid-cycle US-macro events
  drift LONG on NDX" to "...drift LONG on NDX AND drive a parallel SHORT-EURUSD
  USD-bid leg, with the FX leg the cleaner mechanism-vessel because (a) FX has
  no cash-open boundary, (b) 24h trading removes the pre-RTH-open accumulation
  artefact, and (c) FX directly prices USD-risk-premium without an equity-risk-
  premium confound." That would tighten the NDX framing — it wouldn't break it,
  but it would say the equity-cash-microstructure framing of lesson #62 was
  incomplete.
- **FAIL (null-gap below +0.30, OR W4 not positive in SHORT, OR walk-forward
  OOS Sh below floor):**  
  Lesson #62 tightens. The mechanism is genuinely NDX-cash-equity-microstructure-
  specific — pre-cash-open institutional positioning into a fixed RTH boundary
  is the load-bearing leg, NOT generic USD-risk-premium accumulation. FX (and
  by extension other 24h-traded venues) is mechanism-empty for pre-FOMC drift.
  Same kind of framework-sharpener that lesson #62 produced via XAU cross-
  asset rejection; this would corroborate it on a second cross-asset, with FX
  being a stronger test because the USD-leg-of-the-same-trade story is more
  superficially plausible than the gold-leg-of-the-same-trade story was.

Direction prior per user: **SHORT EURUSD** (= LONG USD). That's the
"risk-premium flow into the Fed decision" hypothesis. But **per lesson #54
discipline (validated in pre_nfp_drift), both LONG and SHORT are run as
co-equal candidates and the direction is selected ex-post from the null-gap**;
the SHORT prior is used only for interpretation, not for kill-criteria
selection.

## Thesis (mechanism)

1. **Risk-premium accumulation has a USD leg.** Lucca-Moench (2015) framed
   pre-FOMC drift on SPX as compensation for holding risky assets through
   the announcement. If institutional investors are de-risking equities into
   FOMC (which would drive EQUITIES DOWN, not up — so the LM mechanism is the
   opposite: they're accepting equity risk in return for an ex-ante premium),
   they may simultaneously rotate into safe-haven USD cash. That second leg
   would show as SHORT EURUSD pre-FOMC.
2. **Carry-unwind asymmetry.** EUR-funded carry positions (long EM, long
   equities, etc.) get unwound into uncertain Fed events to reduce leverage.
   Unwinding a EUR-funded carry trade buys EUR back — that's LONG EURUSD,
   *opposite* the user's prior. The fact that the user's prior and this
   mechanism point opposite ways is itself informative: if EURUSD ends up
   netting flat (zero null-gap), the two mechanisms cancel and the FX-side
   is mechanism-empty by superposition.
3. **DXY-equity correlation regime.** Post-2022 dovish-pivot regime saw a
   persistent negative DXY-SPX correlation (USD weakens on risk-on). Pre-FOMC
   risk-on positioning by definition *weakens USD* under this regime
   correlation — which would predict LONG EURUSD, again opposite the user's
   SHORT prior. W4 (2024-2026) is the deploy-relevant regime, so this is the
   binding question: does pre-FOMC USD strengthen (SHORT EURUSD) or weaken
   (LONG EURUSD) in the current 24h pre-announce window?
4. **Information-leakage / Fed-funds-futures alignment.** If FFR futures
   already prices the decision before the announcement, there's no
   "uncertainty-resolution" premium to capture on either side. The FX market
   is sophisticated and Fed-aware; any persistent pre-FOMC FX drift suggests
   the equity-side is the leading vessel, not a parallel-and-equal leg.

Net: the FX-side prior is not cleanly directional under any single mechanism.
SHORT under user-stated risk-premium-flow story; LONG under carry-unwind or
risk-on-USD-weakening. The null-gap diagnostic is the load-bearing test here.

## Key references

- **Lucca, D. & Moench, E. (2015)**. *Journal of Finance*, 70(1). Original
  pre-FOMC SPX +0.49%/event 1994-2011. Equity-side framing.
- **Mueller, P., Tahbaz-Salehi, A., Vedolin, A. (2017)**. "Exchange Rates
  and Monetary Policy Uncertainty", *Journal of Finance*, 72(3). Documents
  that USD appreciates pre-FOMC announcements 1980-2010 in monthly data; the
  precise intraday-pre-announcement structure is less-studied. This is the
  paper-grade prior for the SHORT-EURUSD direction.
- **Karnaukh, N. (2018)**. "Currency Returns and FOMC Announcements", *J.
  Financial and Quantitative Analysis*. FX returns around FOMC; finds USD
  appreciation around announcements in EM currencies but mixed in DM.
- **Cieslak, A., Morse, A., Vissing-Jorgensen, A. (2019)**. *Journal of
  Finance*, 74(5). 5-day cyclic pattern around FOMC. Cross-asset implications.
- Internal: `experiments/_live/macro_drift/macro_drift.md` (the deployed
  NDX-LONG version of this experiment); `experiments/pre_ecb_drift/pre_ecb_drift.md`
  (lesson #54 — venue/event-pair non-portability); `experiments/pre_pce_drift/pre_pce_drift.md`
  (lesson #-13 / #62 — refined framework).

## Signal math (preliminary)

```
For each scheduled FOMC announce date D, at time T_announce (14:00 ET):
    entry_t = T_announce - 24h
    exit_t  = T_announce - 30min
    entry_px = close of EURUSD M5 bar at entry_t
    exit_px  = close of EURUSD M5 bar at exit_t
    
    # Direction TBD per null-gap; baseline runs BOTH:
    long_gross  = (exit_px - entry_px) / entry_px * 100   # LONG EURUSD
    short_gross = -long_gross                              # SHORT EURUSD = LONG USD
```

### Variants to sweep

- **Window**: 6h / 12h / 18h / 24h / 48h pre-announce
- **Exit buffer**: 5min / 15min / 30min / 60min pre-announce
- **Cost**: 0 / 0.5 / 1 / 2 / 5 bp RT (EURUSD CFD spread is tight; default 1bp)
- **Regime**: W1 (2019, partial) / W2 (2020-2021) / W3 (2022-2023) / W4 (2024-2026)

## Why retail-accessible

- EURUSD CFD spread at Eightcap is consistently sub-pip (~0.5 pip / ~5e-5 on
  ~1.10 quote = ~0.5 bp RT, sometimes 1 bp). The deploy-cost reality-check
  prerequisite of lesson #45 is satisfied: per-trade gross would need to
  exceed ~3-5 bp RT to be retail-deployable. Pre-FOMC FX drift studies
  (Mueller-Tahbaz-Vedolin) find ~20-40 bp pre-announce USD moves in monthly
  data; if any fraction of that lands in the 24h window, retail-deployability
  is comfortably clear.
- EURUSD is the most-liquid FX pair on the planet — no liquidity-microstructure
  surprises.
- Entry/exit times are predetermined and the broker is open continuously, so
  no GAP-fill execution risk like in equity-CFD-on-Sunday-open style theses.

## Universe

- **Primary instrument**: EURUSD M5 CFD, datalake / `ohlc_data/EURUSD_M5.csv`,
  2019-01-02 → 2026-05-22 (~7.4y, 551k bars).
- **NOT in scope**: extension to GBPUSD, USDJPY, AUDUSD (each could carry its
  own micro-mechanism with different sign-direction; if EURUSD shows clean
  signal, those become natural Phase 3 cross-product checks but are not
  pre-committed here).
- **Event calendar**: re-uses `experiments/_live/macro_drift/fomc_calendar.csv`
  (8 events/yr × ~8 years = ~64 events; minus the ~8 W1-2018 events that fall
  before EURUSD M5 coverage begins = ~56 expected matched events).

## Expected performance (point estimates)

This is mostly an uncertainty-resolution test, not a clear-prior deploy. Two
imaginable shapes:

| shape | per-trade mean | Sh (×√8) | Trades/yr | annual gross |
|---|---|---|---|---|
| **PASS shape (USD-leg lives)** | SHORT +0.08% to +0.20% | +0.50 to +1.20 | 8 | +0.6% to +1.6% |
| **FAIL shape (mechanism empty)** | abs < 0.04% either side | abs Sh < 0.30 | 8 | ~0% net |

Even at the PASS end, an FX-leg event-drift strategy is a low-absolute-return
add to the book (8 trades/yr × ~0.1% gross = sub-1% annual). Its primary
value would be (a) low correlation with the existing NDX-LONG-pre-FOMC
deploy (both ride the same event but the vessels are different), enabling
some implicit position-sizing diversification, and (b) framework refinement.
Don't deploy a marginal pass.

## Pre-committed kill criteria (binding; applied to BEST of LONG/SHORT)

Per lesson #55 (mechanism-aware kill criteria — FX-event-drift is
asymmetric-payoff territory, not LONG-bias-WR territory):

1. **Best-direction per-trade mean > +0.05%** at 1bp RT cost. Lower bar than
   macro_drift's +0.10% — FX moves smaller than equity, so a 5bp gross signal
   is genuinely meaningful here.
2. **Best-direction W4 (2024-2026) per-trade mean > +0.03%**. Even tighter on
   the deploy-relevant window.
3. **Best-direction PF > 1.3**.
4. **Best-direction Sharpe (×√8) > +0.30** (annualised, ~8 FOMC/yr).
5. **Max DD < 25%** (in event-equity-curve terms).
6. **Events ≥ 40** (FOMC-only universe; EURUSD coverage 2019+ means ~56
   expected, comfortably above floor).
7. **Direction null-gap |LONG − SHORT| ≥ +0.30** (Sharpe space). The
   load-bearing pre-commit. Without this, mechanism has no directional
   content.
8. **Walk-forward OOS mean Sh ≥ +0.30, min OOS Sh ≥ 0** (3 rolling splits).
9. **Placebo non-FOMC Wednesdays at the same UTC anchor benign** (mean abs
   < 0.04% or |t| < 1.5). Confirms the result is FOMC-specific and not a
   weekday-microstructure artefact.

PASS only if ALL of (1)-(9) hold for the same direction.

## Why this might fail (red flags)

1. **Mechanism cancellation / superposition.** As enumerated in the thesis,
   three plausible flow mechanisms point in opposite FX-side directions. The
   most likely outcome is a wash — null-gap below +0.30, near-zero means
   either side, the FAIL shape. That would still be informative (extends
   lesson #62 to FX cross-asset).
2. **Carry-regime confound.** 2019-2021 EURUSD carry was massively short
   (USD>>EUR rates → long-EUR-funded-carry got built). 2022-2023 the carry
   inverted (EUR rates caught up). 2024-2026 carry re-normalised at narrower
   spread. Pre-FOMC behaviour could be regime-driven by which side is the
   funder, not by the Fed decision per se. The 4-regime split is the
   diagnostic.
3. **Asymmetric FX response on hawkish-vs-dovish surprises.** Pre-event drift
   could be driven by *expected* policy direction, not the announcement
   itself. The script doesn't condition on FFR-futures-implied direction
   (out of scope for retail Phase 2). If the W3 rate-hike-cycle period
   delivers a strong SHORT-EURUSD signal but W2 / W4 do not, it would
   suggest hawkish-expectation-conditional and not deployable as a calendar-
   only strategy.
4. **DXY-DXY mechanical correlation.** EURUSD has ~57% weight in the DXY
   index. Any pre-FOMC DXY drift (a published intraday DXY drift exists in
   the literature) will mechanically pull EURUSD with it. So the SHORT
   prior, if it shows up, partly tautologically restates a known DXY
   intraday effect rather than a new flow story. Cross-product test on
   GBPUSD / USDJPY (out of scope here) would discriminate.
5. **Friday/weekend boundary.** ~12% of FOMC dates have the 24h pre-window
   crossing into Tuesday or another non-Wednesday day — no boundary issue
   in FX (24h-traded). Not actually a red flag for this thesis vessel; flagged
   here only to note that the FX vessel side-steps a complication that
   equity-vessel pre-event drift has.

## Phase 0 / 1 / 2 plan (single-pass; per CLAUDE.md run A-to-Z convention)

This is a Phase 2 spinup that goes straight to the simulator-with-kill-criteria
because the macro_drift FOMC infrastructure (calendar, et_to_utc helper,
window/buffer sweep code) all exists and is reused. No separate Phase 0 needed.

Single pass executes:
- [ ] Baseline 24h LONG + SHORT EURUSD on full sample
- [ ] Regime breakdown W1/W2/W3/W4 on best direction
- [ ] Walk-forward 3 rolling splits on best direction
- [ ] Cost sensitivity 0/0.5/1/2/5 bp on best direction
- [ ] Window/buffer 2-D sweep on best direction
- [ ] Placebo non-FOMC Wednesdays at 14:00-ET anchor (both directions)
- [ ] Day-of-week subset diagnostic (Wed-anchored events should be uniform; this
       diagnostic exists mostly for parallel-to-pre_pce_drift discipline)
- [ ] Kill-criteria summary + verdict

## Files

- `pre_fomc_drift.md` — this doc
- `pre_fomc_drift_demo.py` — Phase 2 simulator (reuses
  `experiments/_live/macro_drift/_profile_fomc_drift.py` calendar / ET helpers
  + `experiments/_live/macro_drift/fomc_calendar.csv`)
- No new calendar file — re-uses the deployed FOMC calendar.

## Related strategies & lessons

- `experiments/_live/macro_drift/macro_drift.md` — deployed NDX-LONG-pre-FOMC;
  this experiment is its FX-side falsification test.
- `experiments/pre_ecb_drift/pre_ecb_drift.md` (lesson #54) — established
  venue/event-pair non-portability; "ECB-on-GER40" failed where "FOMC-on-NDX"
  passed. The FX-on-FOMC analog is a different test (same event, different
  vessel) but inherits the same direction-discipline ("pre-commit BOTH
  directions, select ex-post").
- `experiments/pre_pce_drift/pre_pce_drift.md` (lesson #-13 / #62) — refined
  the framework to first-read-mid-month-mid-cycle US-macro events on NDX.
  This experiment tests whether the *vessel-of-asset* axis is also load-bearing.
- `experiments/_live/macro_drift/joint_book_audit.py` — if this PASSES, the
  joint book audit will need a new sizing row.

## Open questions

1. **If PASS, can it deploy alongside macro_drift on the same FOMC event?**
   The two would be perfectly time-overlapping (entries 24h before announce,
   exits 30min before). Correlation could be moderate (both ride the same
   event flow). Pre-position-sizing rule: at PASS, deploy with risk halved
   versus a standalone deploy and re-check book correlation in
   joint_book_audit. **N/A — REJECT.**
2. **Should we also pre-commit a "joint signal" form?** E.g. "long NDX +
   short EURUSD when both fire" with a single risk envelope. Out of scope
   here — establish each leg standalone first. **N/A — REJECT.**
3. **Pre-CPI / pre-NFP / pre-RetailSales FX-side extensions are obvious
   follow-ups if this PASSES.** Each becomes its own thesis doc, not auto-
   extended from this one. **Pre-tombstoned by this experiment's REJECT.**
   The DXY-equity mechanical-correlation mechanism would apply equally to
   pre-CPI / pre-RetailSales (LONG-NDX events → LONG-EURUSD via DXY mirror)
   and OPPOSITELY to pre-NFP (SHORT-NDX → SHORT-EURUSD); in all cases the
   FX leg is the magnitude-shadow of the equity leg and decays first. Don't
   spin those up — they're predictably the same reject shape.
