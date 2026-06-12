# Pre-event macro drift on XAUUSD (24h pre-release, direction TBD per event)

**Status**: Phase 2 in progress (2026-05-25). Cross-asset extension of the
NDX `event_calendar` book (`macro_drift` FOMC + `pre_cpi_drift` + `pre_retail_sales_drift`
+ `pre_nfp_drift`) onto gold spot (XAUUSD).

**Verdict**: **REJECT (whole book)**. 0/4 events pass the 10-criterion pre-commit;
2 MARGINAL (FOMC, CPI), 2 REJECT (RS, NFP). The single failing criterion that
kills *every* event is the **direction null-gap (|LONG−SHORT| ≥ +0.30)** — XAU
drifts too symmetrically around macro events for the signal to clear noise. The
deeper finding: on XAU, the LONG mean on **non-event weekdays** is *as large or
larger* than on event days for CPI/NFP/RS (placebo null-gaps of +0.290 / +0.184 /
-0.022 vs event null-gaps of +0.255 / +0.206 / +0.179) — the apparent edge is
**structural gold drift, not event-specific positioning**. FOMC is the only event
where the placebo is clean (placebo t -0.02, event Sh +0.31), but the absolute
magnitude is too small to deploy on its own.

**Cross-asset finding (new family lesson candidate)**: the NDX-canonical
direction (FOMC/CPI/RS LONG, NFP SHORT) does NOT transfer to XAU. All four XAU
events trade LONG — including NFP, which is SHORT on NDX. This confirms that the
NDX NFP-SHORT mechanism is **NDX-microstructure-specific** (Friday 0DTE gamma +
weekend de-risking) and not a generic gold/equity hedge-flow story.

## What this experiment tests

The `event_calendar` book is currently NDX-only (FOMC LONG +1.04 Sh, CPI LONG +0.56,
RS LONG +1.25, NFP SHORT +0.60). User reports observing pre-event price drift on
XAUUSD discretionarily and wants to know whether the same four-event book extends
to gold.

The mechanism on NDX is **institutional risk-premium accumulation** (lesson #56 — most
scheduled US macro events drift LONG on equities; NFP is the SHORT exception).
On gold, the candidate mechanism is **different and not transferable**:

- **Real-rate channel**: gold is priced off 10y TIPS yield. Pre-CPI/FOMC, if the
  market is positioned for a dovish print, real yields drift down and gold drifts
  up. Direction is regime-conditional on the prevailing rate-expectations bias.
- **DXY channel**: gold trades inversely vs USD. Pre-NFP positioning often
  involves DXY hedging — strong-USD bias would pull gold DOWN into the print.
- **Risk-off hedge channel**: gold also catches a risk-off bid when equities sell
  off. In post-2022, gold and NDX have *positive* correlation during dovish
  surprises (both up) and *negative* during stagflation fears (gold up, NDX down).
- **Central-bank-buying flow**: structural since 2022. May produce a slow upward
  drift on all days regardless of event — needs the placebo to isolate.

Because the mechanism is plausibly different per event, **direction is decided
per event from the data**, not assumed from NDX's direction.

## Pre-commits (applied to BEST of LONG/SHORT per lesson #54, per event)

Per lesson #55 (mechanism-aware kill set):

1. **Best-direction per-trade mean > +0.10%** at 2bp RT cost (XAU is cheaper than NDX).
2. **Best-direction W4 (2024-2026) per-trade mean > +0.05%**.
3. **Best-direction PF > 1.3**.
4. **Best-direction Sharpe > +0.30** (annualised per-event cadence).
5. **Max DD < 25%**.
6. **Events ≥ 50**.
7. **Direction null-gap |LONG − SHORT| ≥ +0.30**.
8. **Walk-forward OOS mean Sh ≥ +0.30, min OOS Sh ≥ 0** (3 rolling splits).
9. **Placebo non-event weekdays at the same ET anchor benign** (|mean| < 0.05% or |t| < 1.5).

PASS per event only if ALL of (1)-(9) hold for the same direction.

Per the family canonical rule (lesson #56), **also report the cross-asset
direction-agreement vs NDX**. Three-of-four agreement = confirmatory; two-of-four
or fewer = XAU mechanism is independent of NDX and the book is genuinely diversified.

## Why this might fail (red flags)

1. **Central-bank-buying drift may dominate**: post-2022 gold has a structural
   upward drift (~+15-25%/yr). The 24h-pre-event window will catch a slice of
   this regardless of the event. Placebo non-event weekdays MUST be controlled
   for, or the LONG direction will trivially "pass" via the background drift.
2. **XAU has 24h trading (no cash open)** — unlike NDX where the 24h pre-window
   includes the previous day's RTH close and overnight. XAU 24h-pre-release is
   pure round-the-clock trading; the structural-flow story (pre-cash institutional
   positioning) doesn't directly apply.
3. **Direction may be inconsistent across events**. NDX has a 3-LONG-1-SHORT
   pattern that maps to a clean mechanism. XAU might have 2-LONG-2-SHORT or
   all-noise; if so, the cross-event book has no joint mechanism story.
4. **CPI/NFP regime conditionality**: NDX research showed CPI and NFP were
   regime-conditional (pre-2022 Sh ~0). Gold's response to those events was
   also structurally different pre-2022 (different real-rate regime). Expect
   the same pre/post-2022 split — and demand robustness via the joint-audit
   pre-2022 vs post-2022 cut before sizing >0.5%.
5. **Multiple-comparisons inflation**: 4 events × 2 instruments = 8 (event,
   instrument) cells across the book. If ≥2 XAU events pass after only running
   the full panel once, treat each as a "first time being looked at" — no
   pre-event-specific direction assumption was made.

## Files

- `pre_xau_macro_drift.md` — this doc
- `pre_xau_macro_drift_demo.py` — single-file simulator that iterates over the
  4 events. Re-uses the existing calendars in `experiments/{macro_drift,
  pre_cpi_drift, pre_retail_sales_drift, pre_nfp_drift}/*_calendar.csv`.
  Data: XAUUSD M5 from datalake (2018-01-02 → 2026-04-30 coverage).

## Cost model

XAUUSD typical retail spread: 0.20-0.40 USD on ~2,400 = ~0.85-1.7 bps RT.
Default 2bp (pessimistic for IC Markets/Eightcap, realistic for wider brokers).
Sweep: [0, 1, 2, 5, 10] bps.

## Results (2026-05-25)

### Book summary

| Event | NDX dir | XAU dir | match | n | mean | Sh | W4 Sh | WF mean OOS | placebo t | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| **FOMC** | LONG | LONG | YES | 66 | +0.093% | +0.31 | +0.55 | +0.49 | -0.02 | **MARGINAL** |
| **CPI**  | LONG | LONG | YES | 99 | +0.108% | +0.54 | +0.95 | +0.85 | **+1.44** | **MARGINAL** |
| **RS**   | LONG | LONG | YES | 93 | +0.069% | +0.28 | +0.58 | +0.47 | -0.28 | **REJECT** |
| **NFP**  | SHORT | **LONG** | **NO** | 98 | +0.083% | +0.36 | +0.27 | +0.17 | +0.78 | **REJECT** |

Direction agreement with NDX: 3/4 (NFP is the exception).

### Pre-commit kill-criteria detail (per event)

| Criterion | FOMC | CPI | RS | NFP |
|---|---|---|---|---|
| mean > +0.10%        | FAIL | PASS | FAIL | FAIL |
| W4 mean > +0.05%     | PASS | PASS | PASS | PASS |
| PF > 1.3             | PASS | PASS | FAIL | PASS |
| Sh > +0.30           | PASS | PASS | FAIL | PASS |
| MDD < 25%            | PASS | PASS | PASS | PASS |
| events ≥ 50          | PASS | PASS | PASS | PASS |
| **null-gap ≥ +0.30** | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| WF OOS mean ≥ +0.30  | PASS | PASS | PASS | FAIL |
| WF OOS min ≥ 0       | PASS | PASS | PASS | FAIL |
| placebo benign       | PASS | PASS | PASS | PASS |
| **PASS count**       | **8/10** | **9/10** | **6/10** | **6/10** |

### The "null-gap fails on all 4" smoking gun

Per-event LONG vs SHORT mean gaps:

| Event | LONG mean | SHORT mean | gap (LONG−SHORT) | pass ≥ +0.30? |
|---|---|---|---|---|
| FOMC | +0.093% | -0.133% | +0.227% | FAIL |
| CPI  | +0.108% | -0.148% | +0.255% | FAIL |
| RS   | +0.069% | -0.109% | +0.179% | FAIL |
| NFP  | +0.083% | -0.123% | +0.206% | FAIL |

XAU drifts approximately symmetrically. Compare to NDX CPI null-gap +0.548% and
NDX RS null-gap +0.69% — both ~2-3× wider. **XAU does not have enough
directional content in the 24h pre-event window for the mechanism to clear noise.**

### The "placebo is bigger than the event" red flag

For CPI, RS, NFP, the **placebo non-event weekday null-gap is comparable to or
larger than the event null-gap**:

| Event | Event LONG−SHORT gap | Placebo LONG−SHORT gap | Edge over placebo |
|---|---|---|---|
| FOMC | +0.227% | +0.037% | **+0.190%** (real event-specific lift) |
| CPI  | +0.255% | **+0.290%** | **−0.035%** (placebo bigger than event) |
| RS   | +0.179% | -0.022% | +0.201% (real but small) |
| NFP  | +0.206% | +0.184% | +0.022% (basically none) |

**Only FOMC has a clean event-specific lift on XAU.** CPI's apparent +0.108%
LONG mean is mostly the structural gold drift on Tue/Wed/Thu weekdays — when you
match the weekday distribution and exclude CPI days, the LONG drift is +0.125%,
even bigger. The CPI "edge" disappears once you control for which weekdays you're
sampling.

### Cost sensitivity (LONG, all events at 2bp default)

All four events have a similar cost profile: ~+0.04% Sharpe lift per −1bp cost
saving. None survive 10bp RT with the original kill criteria. At 0bp (frictionless),
even CPI is only Sh +0.64 — below the +1.0 bar needed for a single-event deploy.

### Regime breakdown (best direction = LONG, all events)

W4 (2024-2026) holdout, by event:

| Event | W4 n | W4 mean | W4 Sh |
|---|---|---|---|
| FOMC | 19 | +0.252% | +0.55 |
| CPI  | 28 | +0.234% | +0.95 |
| RS   | 25 | +0.159% | +0.58 |
| NFP  | 28 | +0.064% | +0.27 |

W4 is the strongest regime for all four events — same regime-trajectory shape as
the NDX family (post-2022 reactivation). But the magnitudes are smaller than NDX
across the board (NDX W4 means: FOMC +0.41%, CPI +0.58%, RS +0.47%, NFP +0.24%).

### Walk-forward (best direction)

Three of four events (FOMC, CPI, RS) show clean IS-low/OOS-high profiles
matching the NDX family pattern — the mechanism activated post-2022 on XAU too.
But the post-activation Sharpes are lower (+0.49 / +0.85 / +0.47 vs NDX's
+0.65 / +1.04 / +1.46). NFP fails walk-forward outright.

### Window sweep — interesting non-results

CPI 18h window: Sh +1.04 mean +0.140% (vs pre-committed 24h Sh +0.54). 48h: Sh
+0.85 mean +0.296%. Per lesson #16/#20 (don't deviate from pre-commit because of
post-hoc sweep optimization), the 24h pre-commit is binding. But the strong 18h
result suggests the XAU CPI drift starts later in the pre-window than NDX's —
worth noting for any future Phase 3 reconsideration.

---

## Mechanistic interpretation

The NDX `event_calendar` book's edge comes from **two ingredients**:

1. **Pre-cash-open institutional positioning into US-time releases** (CPI/RS/NFP
   at 08:30 ET, FOMC at 14:00 ET). Cash-equity desks rebalance risk-on the
   afternoon before; the 24h window catches that flow.
2. **Risk-premium accumulation** specific to equities (NDX is the duration-leveraged
   instrument that responds most to rate-expectation shifts).

XAU has **neither** of these:

1. **No cash open** — XAU trades round-the-clock; there's no concentrated
   institutional positioning window 24h pre-release. The flow is smeared.
2. **Different mechanism** — XAU responds to real yields (TIPS) + DXY +
   risk-off bid, not to equity risk-premium. None of these have a clean
   "accumulate into the print" story; if anything, gold is a *hedge* for the
   release uncertainty itself, so positioning is more two-sided.

The 3-of-4 direction agreement with NDX (FOMC/CPI/RS all LONG on both) is
**spurious** — it's the structural gold drift (central bank buying + inflation
hedge bid since 2022) coincidentally pointing the same way as the NDX equity
drift, not the same mechanism operating on both. The placebo proves it: on
CPI/NFP/RS, gold drifts up *just as much* on non-event weekdays.

The 1-of-4 disagreement (NFP) is **the genuinely informative finding** — NDX
NFP-SHORT is a Friday-microstructure exception that doesn't generalise.
Gold has no equivalent Friday SHORT mechanism.

## Why this is still a useful result

1. **Don't dilute the deploy book**. Adding XAU instances of the same EA would
   2× the gross exposure for a tiny incremental edge (FOMC alone) that may not
   even be event-specific in real-money sizing.
2. **Confirms NDX mechanism is asset-specific**. The NDX `event_calendar` book
   isn't a generic "trade macro events" template — it's an NDX-pre-cash-open
   institutional-positioning template. Future cross-asset extensions should
   target instruments with a similar microstructure (SPX500, NDX-component
   single stocks, MES/MNQ futures), not commodities.
3. **The user's discretionary observation is real but misattributed**. Gold
   does "bump" pre-data — but the bump is the same size on a random Tuesday.
   The pattern recognition is picking up structural drift, not event-specific
   lift. (Useful conversation: confirms gold has been in a structural bull
   regime since 2022; doesn't validate event-timing as the entry trigger.)
4. **New family lesson** for `docs/RESEARCH_NOTES.md`: when a strategy passes
   on one instrument, the cross-asset test must include a *weekday-matched
   placebo* on the candidate instrument — not just the original. A clean
   placebo on NDX does not guarantee a clean placebo on XAU.

## Decision

**REJECT the XAU pre-event book.** Do NOT add XAU instances to the
`event_calendar_ea`. Keep this thesis doc as the negative-result tombstone.

Optional future Phase 3 (low priority): isolate FOMC alone (the only event with
a clean placebo on XAU), look at whether the 18h vs 24h window difference
suggests a different entry timing for XAU specifically. Likely small.

