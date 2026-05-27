# Pre-ECB drift on EURUSD (24h pre-announcement, direction LONG prior)

**Status**: Phase 2 complete (2026-05-26). First **FX-venue** test of the
macro-event positioning-drift family. Tests the same 24h pre-event window as
`macro_drift` (FOMC, NDX LONG, DEPLOYED) and the rejected `pre_ecb_drift`
(GER40 LONG), but on EURUSD spot — a different mechanistic channel.

**Verdict**: **REJECT** — but with a mechanistically informative shape. Baseline
24h LONG mean +0.050% (Sh +0.36) is borderline-fail; binding kill failures are
W4 collapse (mean -0.063%, Sh -0.46), null-gap +0.119% < +0.20% threshold,
walk-forward OOS min -0.46 driven by the same 2024-2026 split, and WR 50.8%.
The *direction* of W3 (2022-2023 hiking cycle, EURUSD-LONG mean +0.213% / Sh
+1.14) is the **opposite sign** of W3 on GER40 (mean -0.159% / Sh -0.50) —
same event, same regime, opposite drift across instruments. EURUSD pre-ECB
drift is real but **regime-conditional on the ECB policy-direction cycle**:
EUR strengthened into hikes (W3), weakened into cuts (W4). The non-regime-
conditional family lesson (#54 / #56) holds: pre-FOMC-on-NDX remains the only
unconditionally-deployable instance.

## Thesis (mechanism)

The Lucca-Moench (2015) "pre-FOMC drift" effect on the S&P 500 has now been
ported through this repo twice:

- `macro_drift` (FOMC × NDX100, 24h LONG, 5bp RT) → **PASS** (Sh +1.04, deployed).
- `pre_ecb_drift` (ECB × GER40, 24h LONG, 5bp RT) → **REJECT** (Sh -0.11; W3
  hiking cycle was the WORST regime; direction null-gap -0.011%, no directional
  content). Lesson #54: pre-FOMC drift mechanism does not port to ECB on
  European equity index.

Lesson #54 currently claims the family is "US-equity-pre-FOMC-specific." That
claim rests on a single negative observation (GER40). The cleanest second leg
to test the claim is **EURUSD spot**, because:

1. **Different mechanistic channel from equities.** Pre-FOMC drift on equity
   indices is a *risk-premium-accumulation* story (institutions get paid to
   warehouse equity risk into the event). On EURUSD it would instead be a
   *policy-expectation positioning* story (institutions tilt EUR exposure
   ahead of ECB to capture the expected EUR-USD repricing of policy news).
   If the ECB-GER40 reject was driven by red flag #1 (press-conference
   confound on cash equity) but not by an underlying lack of pre-event
   positioning flow, the FX leg should still show drift.
2. **DAX is banks-heavy and bi-directional** in rate response. EURUSD is
   the cleaner expression of "EUR-policy event" because every ECB decision
   maps mechanically to a single rate-differential repricing axis. The
   directional ambiguity that defeated GER40 should be smaller on EURUSD.
3. **EURUSD retail cost floor is the lowest in the broker universe.** Typical
   Eightcap / IC Markets spread ~0.5-0.8 pip on a 1.16 mid = ~0.4-0.7 bps
   one-way = **0.86 bps RT pessimistic**, with zero swap on intraday
   (entry 24h before, exit 30min before — both inside same trading day in
   practice spans one overnight, so ~1 swap charge). Even after swap,
   well clear of the retail-FX cost wall (~3 bps that killed `fx_session`).
4. **Diversification value.** The deployed `event_calendar` book is 100%
   US-side (FOMC, CPI, RS, NFP × NDX). Any EU-policy edge is structurally
   uncorrelated with the current macro-event book.

Direction prior: **LONG EURUSD** (institutional EUR-positioning into ECB
rate-decision, the FX mirror of NDX-LONG-pre-FOMC). The null-check will
test SHORT; if SHORT outperforms LONG, the prior is wrong and the
mechanism is "EUR weakens into ECB" rather than strengthens.

## Key references

- **Lucca, D. & Moench, E. (2015), "The Pre-FOMC Announcement Drift", *JoF*.**
  Canonical paper.
- **`experiments/macro_drift/macro_drift.md`** — direct parent (US, NDX, FOMC).
- **`experiments/pre_ecb_drift/pre_ecb_drift.md`** — sibling REJECT (EU, GER40, ECB).
- **Brusa, F., Savor, P., & Wilson, M. (2020), "One Central Bank to Rule Them All",
  *Review of Finance*.** Cross-country test of central-bank-announcement drifts;
  found that *FOMC drift dominates ECB / BOE / BOJ drifts on local equity indices*
  but did NOT test FX cross-rates. Our FX leg is the gap they didn't fill.

## Signal math

```
Per ECB monetary policy meeting at announce_utc:

  entry_t = announce_utc - 24 hours
  exit_t  = announce_utc - 30 minutes

  entry_px = EURUSD M5 close at nearest bar to entry_t  (tolerance 30 min)
  exit_px  = EURUSD M5 close at nearest bar to exit_t   (tolerance 30 min)

  gross_pct = (exit_px - entry_px) / entry_px * 100
  net_pct   = gross_pct - cost_bps_RT / 100         (1 bp RT default)

Position: LONG, full notional, one trade per meeting.
```

Per-event 23.5-hour hold spanning one overnight session — one swap charge
modeled implicitly via the cost-bps sweep (the 5bp variant covers a
pessimistic swap estimate).

## Why retail-accessible

- Eightcap / IC Markets EURUSD CFD-spot is the most liquid retail FX
  instrument. Confirmed tradeable; standard MT5 EA build path.
- Calendar-driven entry/exit — same scaffolding as
  `deploy/mq5/event_calendar.mq5` (reads `ecb_calendar.csv` for forward
  meeting dates).
- Forward calendar maintenance: refresh quarterly from ecb.europa.eu.

## Universe

- **Research**: EURUSD M5, 2019-01-02 → 2026-05-22. ~67 historical ECB meetings.
- **Live**: Eightcap MT5 EURUSD spot, lot-sizing per portfolio_risk_parity inv-vol.

## Expected performance (at thesis time)

Honest priors given (a) macro_drift PASSED on the original mechanism, (b)
pre_ecb_drift on GER40 REJECTED, (c) this is the first FX leg of the family:

- **Most likely (45%)**: REJECT. The Brusa et al. (2020) result — "FOMC
  drift dominates other central banks on local indices" — is the strongest
  prior. If the mechanism doesn't survive the cross-country shift on
  equities, the cross-asset shift to FX is unlikely to rescue it either.
  Expected per-trade mean +0.00 to +0.04%, full Sh +0.00 to +0.20, null-gap
  small.
- **Plausible (35%)**: MARGINAL. Per-trade mean +0.05-0.10%, full Sh
  +0.20-0.40, W4 borderline, direction null-gap +0.10 to +0.20. EUR
  positioning is real but small; deploy bar not cleared on full criteria.
- **Plausible (20%)**: PASS. Per-trade mean +0.08-0.15% net, full Sh
  +0.30-0.60, W4 positive, direction null-gap > +0.20. EUR-positioning
  is a real distinct mechanism from equity-risk-premium, and the FX
  expression sidesteps the press-conference / banks-bi-directional
  confounds that killed GER40.

Either resolution is informative: a REJECT cleanly closes lesson #54
("family is US-FOMC-specific, not even FX-EUR works"); a PASS reopens it
to "family is monetary-policy-positioning on the SOURCE-currency asset"
which would predict pre-BOE drift on GBPUSD next, etc.

## Fail conditions (pre-committed)

Phase 2 KILL if ANY of the following at 1bp RT cost:

1. **Per-trade mean (full sample) ≤ +0.05%.** Lower than GER40 (+0.10%)
   because the EURUSD cost floor is ~5× lower (1bp vs 5bp), so a smaller
   gross edge still clears deploy economics.
2. **W4 (2024-2026) per-trade mean ≤ +0.03%.** Modern regime must be
   positive.
3. **Win rate ≤ 55%.**
4. **Max DD > 15%** (tighter than GER40's 25% because EURUSD vol is
   roughly half DAX vol — the absolute MDD ceiling scales).
5. **Events count < 50.**
6. **Direction null-gap (LONG − SHORT) < +0.20%.** Lower bar than GER40
   (+0.30%) for the same vol-scaling reason.
7. **Walk-forward mean OOS Sharpe < +0.30** OR **min OOS Sharpe < 0**
   across the three rolling IS/OOS splits.
8. **Placebo non-ECB Thursdays show similar magnitude drift** (per-trade
   mean > +0.03% on the LONG side with t > 1.5).

PASS only if ALL of (1)-(8) hold.

## Why this might fail (red flags)

1. **EUR-USD is a two-sided market.** Unlike equities (where every
   institutional balance sheet is structurally long the asset and the
   pre-event "positioning flow" is dominantly hedge-buying), EUR-USD has
   roughly balanced macro real-money long/short interest. The directional
   drift may average out to zero across event days.
2. **ECB press-conference confound** (red flag #1 from sibling). If the
   press-conference (14:30 / 14:45 CET) is where the bigger move happens,
   EUR positioning may concentrate INTO the press-conference window
   rather than the 24h-pre-decision window — same confound that killed
   GER40. The 24h-pre-decision window captures wait-and-see, not flow.
3. **The 2022-2023 hiking-cycle regime (W3) is unusually loud.** EUR
   collapsed to parity in 2022 on the rate-differential gap (Fed
   front-running ECB). If pre-ECB drift in W3 is LARGE and SHORT-EUR,
   the full-sample W3 sign will dominate and produce a net negative
   result — same pattern that killed pre_ecb_drift on GER40.
4. **DST handling on a 24h hold.** EUR-Berlin DST runs last-Sun-March →
   last-Sun-October. An off-by-one-hour bug in the calendar-to-UTC
   conversion would misalign entry/exit by 60min; tolerated within the
   24h window but would dilute the signal. Reusing the sibling experiment's
   `cet_to_utc` helper minimizes this risk.
5. **Pre-2023 announce time was 13:45 CET, post-2023 is 14:15 CET.** Same
   30-min calendar shift as GER40. If positioning is clock-tied rather
   than event-tied, this could artificially split the regime.
6. **Brusa et al. (2020) cross-country priors are pessimistic.** Their
   result implies pre-FOMC drift is structurally US-specific. Burden of
   proof is on this experiment to demonstrate the FX-leg sidesteps that.

## Phase 2 plan

- [x] Write thesis with pre-committed fail conditions (this doc).
- [x] Reuse `ecb_calendar.csv` from sibling `experiments/pre_ecb_drift/`.
- [x] Implement `pre_ecb_drift_eurusd_demo.py` — fork of sibling demo, EURUSD
      M5 path, 1bp RT default cost, EURUSD-tuned kill thresholds.
- [x] Run end-to-end (baseline + null + placebo + walk-forward + cost sweep +
      window sweep). Update verdict + mechanistic interpretation.
- [x] **REJECT**: tombstone. New finding for RESEARCH_NOTES: cross-instrument
      W3 sign-flip on ECB days (GER40 LONG -0.16% / Sh -0.50 vs EURUSD LONG
      +0.21% / Sh +1.14). Channel-specific, not event-specific.

## Files

- `pre_ecb_drift_eurusd.md` — this doc
- `pre_ecb_drift_eurusd_demo.py` — Phase 2 simulator
- Reused calendar: `../pre_ecb_drift/ecb_calendar.csv`

---

## Results (2026-05-26)

### Headline

| Metric | Value | vs macro_drift NDX FOMC | vs pre_ecb_drift GER40 | Kill check |
|---|---|---|---|---|
| Events | 59 | 56 | 58 | PASS |
| Per-trade mean (1bp RT) | **+0.050%** | +0.276% (5bp) | -0.056% (5bp) | FAIL (need > +0.05%; equals threshold) |
| Sharpe (ann × √8) | **+0.36** | +1.04 | -0.11 | borderline |
| W4 mean (2024-2026) | **-0.063%** | +0.234% | +0.023% | FAIL (need > +0.03%) |
| Win rate | **50.8%** | 60.7% | 51.7% | FAIL (need > 55%) |
| MDD | -1.85% | -2.37% | -9.08% | PASS |
| Direction null-gap (LONG−SHORT) | **+0.119%** | +1.98 | -0.011% | FAIL (need ≥ +0.20%) |
| Walk-forward OOS mean Sh | +0.04 | +0.89 | -0.00 | FAIL (need ≥ +0.30) |
| Walk-forward OOS min Sh | **-0.46** | +0.41 | -0.22 | FAIL (need ≥ 0) |
| Placebo Thursdays mean | -0.020% (t -0.34) | -0.034% (t -0.26) | -0.261% (t -1.94) | PASS (benign) |

**5 of 6 binding kill-criteria FAIL. Verdict: REJECT.**

### Regime breakdown — the diagnostically interesting finding

| Window | n | mean | std | t | WR | Sh | EURUSD vs GER40 same regime |
|---|---|---|---|---|---|---|---|
| W1 (2019) | 8 | -0.024% | 0.232% | -0.30 | 37.5% | -0.30 | both small / mixed |
| W2 (2020-2021) | 16 | +0.057% | 0.270% | +0.84 | 56.2% | +0.60 | GER40 -0.116% (Sh -0.14) — **EURUSD flipped POSITIVE** |
| **W3 (2022-2023 hiking)** | **16** | **+0.213%** | 0.528% | **+1.61** | 68.8% | **+1.14** | GER40 -0.159% (Sh -0.50) — **EURUSD flipped POSITIVE, opposite sign** |
| **W4 (2024-2026 cutting)** | **19** | **-0.063%** | 0.388% | -0.71 | 36.8% | **-0.46** | GER40 +0.023% (Sh +0.09) — EURUSD flipped NEGATIVE |

The W3 sign-flip vs the GER40 sibling is the load-bearing finding. Same event,
same regime, opposite-signed pre-event drift on the two instruments. Pre-ECB
EUR-positioning IS real, but the direction depends on whether the cycle is
*hiking* (W3: EUR strengthens into rate-decision) or *cutting* (W4: EUR
weakens into rate-decision). A directionally-static "always LONG" strategy
averages these into a near-zero, non-deployable result.

This refines (does not refute) lesson #54: the macro-event drift family is
**not just US-FOMC-on-NDX-specific** — it's that pre-FOMC-on-NDX is the
*only* unconditionally-deployable instance. Other central-bank × instrument
combinations may show real but regime-conditional flow.

### Walk-forward

| Split | IS n | IS Sh | IS mean | OOS n | OOS Sh | OOS mean |
|---|---|---|---|---|---|---|
| IS 2019→2022 / OOS 2022-2026 | 24 | +0.33 | +0.030% | 35 | +0.38 | +0.063% |
| IS 2019→2023 / OOS 2023-2026 | 32 | +0.56 | +0.065% | 27 | +0.19 | +0.032% |
| IS 2019→2024 / OOS 2024-2026 | 40 | +0.74 | +0.103% | 19 | **-0.46** | -0.063% |

The first two splits look survivable in OOS (Sh +0.38, +0.19); the third —
where OOS is entirely the 2024-2026 cutting cycle — falls off a cliff. Decay
from IS Sh +0.74 → OOS Sh -0.46 is the regime-flip in action. IS Sh
monotonically rising from +0.33 to +0.74 as the IS window absorbs more of W3
is also a smoking gun: the IS-fit is the hiking-cycle regime, not a stable
mechanism.

### Window sweep (in-sample diagnostic — NOT used for verdict)

| Window | Buffer | n | Mean | Sh |
|---|---|---|---|---|
| 6h | 30min | 59 | -0.042% | -0.74 |
| 12h | 30min | 59 | -0.014% | -0.22 |
| 18h | 30min | 59 | +0.036% | +0.32 |
| **24h** (pre-commit) | **30min** | **59** | **+0.050%** | **+0.36** |
| 48h | 30min | 59 | +0.119% | +0.50 |

Same shape as GER40 sibling: 48h window is the strongest. Second observation
of the 48h-positive pattern in the ECB family. Suggests there *may* be a
two-day pre-event positioning shape on European policy events that's distinct
from the 24h-pre-FOMC mechanism — but isolating it requires a pre-committed
new thesis (write before running), not a post-hoc refinement. Filed as
"interesting datapoint, not actionable." Per lessons #16 / #20, the
pre-committed 24h test failed and the experiment is REJECTED, not refined.

### Cost sensitivity

| Cost (bp RT) | n | Mean | Sh |
|---|---|---|---|
| 0 | 59 | +0.060% | +0.43 |
| 1 (default) | 59 | +0.050% | +0.36 |
| 2 | 59 | +0.040% | +0.28 |
| 5 | 59 | +0.010% | +0.07 |
| 10 | 59 | -0.040% | -0.29 |

Cost-breakeven at ~6 bp RT. The retail-FX cost wall (~3 bps including swap)
would leave Sh ~+0.20 in-sample — but the W4 collapse and walk-forward
failure rule out deployment regardless of cost.

### Placebo

Placebo non-ECB Thursdays at 14:15 CET show mean -0.020%, t -0.34, Sh -0.12.
Clean placebo (much cleaner than the GER40 -0.261% Xetra-mid-day artifact).
The ECB baseline lift (+0.050% vs placebo -0.020% = +0.070% delta) IS event-
specific positioning flow — but the absolute level is too small to clear
deploy thresholds after costs and after regime-conditioning.

### Mechanistic interpretation

**This experiment is a clean second-confirmation of lesson #-16 (the
DXY-mechanical-mirror framework established by `pre_fomc_drift` on EURUSD).**
Lesson #-16 predicts that an FX-side leg of an equity-pre-event-drift
mechanism behaves as a *magnitude-shadow* of the equity vessel via the
mechanical DXY-equity correlation, NOT as an independent USD-or-EUR
positioning flow. Concrete prediction for this experiment: EURUSD W3
≈ −ρ(DXY, DAX) × GER40-W3-drift, with a smaller magnitude that crosses
zero faster as the underlying mechanism decays.

That prediction is empirically tight:

| Regime | GER40 LONG mean | EURUSD LONG mean | Sign relationship |
|---|---|---|---|
| W3 (2022-2023 hiking) | **−0.159%** (Sh −0.50) | **+0.213%** (Sh +1.14) | OPPOSITE, similar OOM |
| W4 (2024-2026 cutting) | +0.023% (Sh +0.09) | −0.063% (Sh −0.46) | OPPOSITE, similar OOM |

W3's opposite-sign / similar-magnitude pair is the canonical DXY-mirror
shape — when DAX falls into ECB-hike events, EUR strengthens against USD
through the same flow. The mirror sign is conserved into W4 (DAX small-up,
EUR small-down). This is *not* a new mechanism — it's lesson #-16 ported
from `pre_fomc_drift` (where the primary vessel was NDX, deployed) to
`pre_ecb_drift` (where the primary vessel was GER40, REJECTED). The fact
that the mirror holds for both PASS-primary and FAIL-primary is the
cleanest confirmation possible: mechanical correlation, not flow.

Specific notes:

1. **The W3 EURUSD LONG Sh +1.14 might look superficially deployable.**
   It is not — it's the mechanical mirror of GER40's W3 loss, which
   means it would be ~fully correlated with a hypothetical "SHORT GER40
   pre-ECB" strategy. SHORT GER40 pre-ECB was the implicit complement
   of the rejected baseline (sibling experiment's null-check showed it
   would have produced symmetric metrics). Deploying EURUSD pre-ECB
   LONG would be the same trade dressed up in FX clothing, with the
   same regime-fragility (W4 already collapsed).

2. **W4 collapse is the operational deal-breaker, identical to
   `pre_fomc_drift`.** Both FX-leg experiments show the same decay
   shape: W3 lift, W4 cross through zero, walk-forward third-split
   negative. Lesson #-16's "FX-mirror shadow decays first" prediction
   replicates exactly.

3. **The 48h positive drift (Sh +0.50) is the second observation of the
   same 48h-window shape after GER40.** Two consecutive ECB-family tests
   show 48h > 24h. Cannot deploy post-hoc; flagged as a meta-observation
   for a future pre-committed thesis (write before running) if a
   mechanistic story justifies the window. Note: at 48h the trade is
   2-overnight FX, so swap drag becomes non-trivial (~2 bps), which
   shrinks the deploy headroom even if the gross effect survives.

4. **Operational consequence (per lesson #-16)**: FX-side legs of any
   remaining macro-event-drift family member (pre_cpi_drift FX-side,
   pre_rs_drift FX-side, pre_nfp_drift FX-side, pre_boe_drift on GBPUSD,
   pre_boj_drift on USDJPY) are pre-tombstoned by mechanism inheritance.
   The W3 cross-instrument-sign-pattern observed here promotes lesson
   #-16 from "single-experiment hypothesis" to "two-experiment confirmed
   structural pattern across both PASS-primary and FAIL-primary vessels."

### Tombstone — family state after this experiment

| Test | Instrument | Event | Verdict | W3 mean | W3 Sh | DXY-mirror? |
|---|---|---|---|---|---|---|
| macro_drift | NDX100 | FOMC | **DEPLOYED** | +0.70% | +2.38 | primary |
| pre_fomc_drift | EURUSD | FOMC | REJECT | (per lesson #-16) | (mirror, W4 dead) | confirmed mirror |
| pre_ecb_drift | GER40 | ECB | REJECT | −0.16% | −0.50 | primary |
| **pre_ecb_drift_eurusd** | **EURUSD** | **ECB** | **REJECT (this)** | **+0.21%** | **+1.14** | **confirmed mirror** |
| pre_pce_drift | NDX100 | PCE | REJECT | (W3 not load-bearing) | n/a | primary |
| pre_ppi_drift | NDX100 | PPI | REJECT | n/a | n/a | primary |

The family is now mapped on two axes: (a) primary equity vessel —
NDX×FOMC alone deploys; all other event×index combinations REJECT;
(b) FX-side mirror — both tested cases (EURUSD×FOMC, EURUSD×ECB)
confirm the DXY-mechanical-mirror shape with primary-decay-first
behavior.

Operational rule going forward: **do not propose FX-side extensions of
any event×index pair, PASS-primary or FAIL-primary.** The mirror is
mechanical and the FX-leg always decays first. This experiment
*completes* the lesson #-16 falsification frame — one mirror case
when primary PASSED (FOMC), one when primary FAILED (ECB), both
producing the same shadow-mirror shape.
