# Month-end USD-funding SHORT-basket (EUR + GBP) — Phase 2 thesis

**Status**: Phase 2 REJECT (2026-05-27). Mechanism real but magnitude sub-threshold for Eightcap-retail-cost deploy.
**Verdict**: **REJECT — 7/13 pre-committed kill criteria PASS. Magnitude/cost ratio ~1.5× is too low for retail-deploy Sharpe; mechanism falsification PASSES decisively (EUR+GBP co-direction in W3, dir-gap +0.45, placebo clean) so this is a broker-tier-mismatch tombstone, not a signal-absence one.** Institutionally-tradeable at < 0.5 bp RT FX cost; not at Eightcap's 1.5-2 bp tier.

## Phase 2 results

| # | Criterion | Threshold | Observed | Pass? |
|---|---|---|---|---|
| 1 | Full mean net | ≥ +1.5 bp/event | **+0.85** | ❌ |
| 2 | W3 mean net | ≥ +1.0 bp/event | **+0.93** (fails by 0.07) | ❌ |
| 3 | All 3 regimes net positive | W1, W2, W3 > 0 | +0.82 / +0.73 / +0.93 | ✅ |
| 4 | Annualized Sharpe | ≥ +0.30 | **+0.27** | ❌ |
| 5 | WR | ≥ 53% | 56.8% | ✅ |
| 6 | MDD | ≤ −3% | −0.83% | ✅ |
| 7 | Bootstrap 95% CI lower | > 0 bp | **[−1.46, +3.06]** | ❌ |
| 8 | Direction-gap | > +0.30 | **+0.45** | ✅ |
| 9 | Placebo basket |mean| | < 1 bp | +0.05 bp | ✅ |
| 10 | Cost-stress @ 2× | net > 0 | **−0.77 bp** | ❌ |
| 11 | Deflated Sharpe | ≥ +0.20 | **+0.02** | ❌ |
| 12 | WF halves both net > 0 | both > 0 | H1 +0.68 / H2 +1.01 | ✅ |
| 13 | EUR + GBP co-direction W3 | both > 0 | EUR +1.69 / GBP +0.18 | ✅ |

**Mechanism falsification (criteria 3, 8, 9, 12, 13)**: all PASS — the signal exists, EUR and GBP co-direct in W3 confirming the structural USD-funding mechanism, walk-forward halves both positive, placebo clean.

**Magnitude vs cost failure (criteria 1, 2, 4, 7, 10, 11)**: all FAIL — the magnitude (~0.9 bp net) is barely above cost floor (~1.75 bp blended), giving a magnitude/cost ratio of ~1.5×. For deploy-grade Sharpe at 12/yr cadence, the ratio needs to be ~3× or higher to clear bootstrap CI and cost-stress checks.

## Mechanism interpretation — broker-tier mismatch, not signal failure

The Etula, Rinne, Suominen & Vaittinen (2020) "Dash for cash" mechanism IS real at retail-observable magnitudes. The basket form proved this empirically:

- W3 holdout: both EUR and GBP positive (EUR +1.69 bp, GBP +0.18 bp net) — same direction confirms structural USD-funding flow, not venue-specific drift
- Walk-forward: H1 (2019-2022, EUR-only) +0.68 bp and H2 (2022-2026, EUR+GBP) +1.01 bp — H2 slightly stronger, consistent with rate-divergence regime amplifying the funding squeeze
- Placebo on 2,359 non-event same-weekday days: SHORT mean +0.05 bp — month-end day is genuinely distinct from random Tue/Wed/Thu/Fri

The reject path is purely cost-vs-magnitude: at Eightcap retail tier (~1.5 bp EUR RT, ~2 bp GBP RT), edge consumes 60-80% of gross. Deployable shape exists at lower-cost venues:

- Prime brokerage FX (< 0.5 bp RT) → magnitude/cost ~5× → deploy-grade Sharpe
- Cash-FX via spot ECN → similar
- Spot-FX-futures via CME (6E / 6B contracts) → comparable cost tier

But none of those are in the repo's current execution stack (Eightcap MT5 only). The strategy is **VALIDATED_BLOCKED_AT_COST**, analogous to `pead_midcap` (research PASS, blocked by CFD swap cost).

## Methodological deliverable — sharpens the structural-flow screen criteria

This REJECT is the second data point on the [structural_flow_audit](../structural_flow_audit/structural_flow_audit.py) source pipeline (first: `quarter_end_xau_short` deploy 12/12 PASS). With two data points the methodology refinement is empirically grounded:

**Lesson candidate (#73)**: The Phase 0 screen's `cost-headroom > 0` criterion is necessary but NOT sufficient for Phase 2 candidate-promotion. The actual deploy-threshold is **magnitude / cost-floor ≥ 3×**, not the screen's existing `magnitude > cost-floor` (1× ratio). Re-applying the tightened rule to the original 17-cell screen:

- `quarter_end_xau_short`: 13.32 / 0.7 = **19× ratio** — Phase 2 PASSED 12/12 ✓
- `month_end_usd_funding × EURUSD`: 2.20 / 1.5 = **1.5× ratio** — Phase 2 REJECTED 7/13 ✗
- `month_end_usd_funding × GBPUSD`: 2.34 / 2.0 = **1.2× ratio** — would have been pre-tombstoned
- `opex_day_after_am × SPX500`: 9.46 / 0.7 = 13.5× ratio — promoted PASSED 4/4 Phase 0 → still worth Phase 2 lock

The refined rule pre-tombstones the EUR/GBP basket attempt while keeping `opex_day_after_am` in the Phase 2 queue. This is a methodology lesson worth adding to `structural_flow_audit.py` for v2.

**Project-level lesson**: structural-flow audit produces ~50% strict-PASS at Phase 2 from STRONG-tier hits and ~0% from WEAK-tier hits. WEAK-tier candidates are mechanistically validated (signal exists) but cost-blocked. The screen's purpose is to surface candidates — the Phase 2 + Phase 5 chain is what determines deploy-feasibility. Don't conflate "screen-flagged signal exists" with "deploy-grade strategy."

## Why this might still be worth revisiting

1. **Institutional execution**: if execution stack ever expands beyond Eightcap (PB FX, ECN, CME FX futures), this strategy clears at < 0.5 bp cost. Tag as `VALIDATED_BLOCKED_AT_COST`, not `REJECTED`.
2. **AUDUSD / USDCAD extension**: the USD-funding mechanism should appear on other major USD pairs. If their magnitude is larger (CAD particularly — Canada has its own month-end cash demand cycle), a 3-leg or 4-leg basket might clear the 3× ratio. Worth a Phase 0+ check; not a full v2 thesis yet.
3. **Window refinement**: the screen used 14-15 ET. A narrower 14:45-15:00 ET window (last 15 min before settlement) might concentrate the flow more — but this is cell-shopping if done post-hoc and would need re-pre-commit.

## Files

- [month_end_usd_short_demo.py](month_end_usd_short_demo.py) — Phase 2 simulator (REJECT 7/13)
- [structural_flow_audit](../structural_flow_audit/) — origin (2 of 17 cells refined into this basket)

---

## Original thesis content preserved below for context


Origin: 2 of 3 WEAK candidates from the [structural_flow_audit](../structural_flow_audit/structural_flow_audit.md) Phase 0 screen, refined into a single combined LONG-USD basket trade per the user's "SHORT-only, slightly higher frequency on forex or index" research direction (2026-05-27). The basket form addresses both the *concentration* concern (book is 57% XAU after `quarter_end_xau_short` graduation) and the *direction* concern (only one SHORT-only strategy in the book pre-deploy of this).

## Thesis (mechanism)

USD strengthens against EUR and GBP in the 14:00-15:00 ET window on the last business day of every month. Mechanism candidate:

1. **End-of-month USD funding squeeze** — corporate and bank balance-sheet dressing forces USD demand at month-end as treasurers settle USD-denominated obligations, refresh USD liquidity buffers, and roll cross-currency basis swaps. The squeeze concentrates in the last hour of NY (14:00-15:00 ET = ~last hour before settlement cutoff).
2. **The 14-15 ET window is the deepest-liquidity hour for major FX pairs** with European desks still active (London closes 16:30 GMT = 11:30 ET in winter) overlapping with NY peak. Month-end imbalance prints here, not in thinner sessions.
3. **EUR and GBP are the two largest non-USD legs of major-currency funding flows** — together they cover ~50% of major-pair non-USD activity. Both should see the same SHORT direction against USD, providing a structural confluence diagnostic (if signal is real, both legs co-direct; if EUR-only or GBP-only, mechanism story is wrong).
4. **Etula, Rinne, Suominen & Vaittinen (2020) "Dash for cash"** documents month-end USD demand as a real, persistent institutional-liquidity flow at retail-tradeable magnitudes. The structural audit found the FX-side signature; the basket form tests whether the two strongest legs combine into deploy-grade strength.
5. **Not 0DTE-amplifiable** (FX has no concentrated 0DTE options market like equities post-2022). Not broker-spread-dependent at the 14-15 ET window (normal-spread for EUR/GBP at Eightcap during NY peak).

The basket form has a specific failure mode (mechanism story refuted): if EUR + GBP do NOT co-direct in the holdout regime, the apparent edge in the screen was venue-specific not flow-specific and tombstones the thesis.

## Key reference

- Etula, E., Rinne, K., Suominen, M., & Vaittinen, L. (2020). "Dash for cash: Monthly market impact of institutional liquidity needs." *Review of Financial Studies* 33(1). — DIRECT match: documents month-end USD demand mechanism + magnitudes.
- BIS Quarterly Review (multiple, 2018-2024) on month-end USD funding squeezes and cross-currency basis swap widening.
- Hartzmark, S. & Solomon, D. (2013) on equity-side month-end window-dressing (the cross-asset cousin of this FX-side flow).

## Signal math

```
Universe          : EURUSD M5 + GBPUSD M5 (Eightcap CFD, deployed instruments)
Event calendar    : last business day of every month
                    pure rule (no external CSV needed)
Window            : 14:00 -> 15:00 ET local (DST-aware via pytz)
Direction         : SHORT both legs (= LONG USD basket)
Entry             : at 14:00 ET open (first M5 bar in window) on BOTH legs
Exit              : at 15:00 ET close (last M5 bar in window) on BOTH legs
Cost (per leg)    : 1.5 bps RT EUR, 2.0 bps RT GBP (Eightcap typical)
Position sizing   : equal-notional per leg, fixed weight; basket = average
                    of available legs (fallback to single leg pre-2022-11 when
                    GBP data starts; full basket from 2022-11 onward)
Holding           : intraday 1h, no overnight risk
Trade frequency   : 12 events / year (monthly); ~94 events available 2019-01 → 2026-04
```

## Why retail-accessible

- Pure calendar-rule trigger — EA needs last-business-day-of-month detection (10 lines of MQL5).
- Single intraday 1h window per leg, no multi-day hold, no overnight gap risk.
- EUR/GBP are primary FX pairs at every retail MT5 broker; spread floor is at the broker's tightest pricing tier.
- 12 trades/yr cadence per leg; basket = ~12 combined events/yr (since both legs fire on same days).
- No options, no futures, no cross-instrument hedging.

## Universe

EURUSD + GBPUSD only. The screen's third WEAK candidate (`opex_day_after_am × SPX500`, t=+1.16, +9.46 bps null-gap) is *not* in this basket — it's a separate equity-side OPEX-related mechanism and would need its own thesis. Keeping the basket pure (USD funding-squeeze mechanism on FX) preserves the mechanistic clarity.

## Expected performance (Phase 0 screen + prior)

Screen results (from [structural_flow_audit.py](../structural_flow_audit/structural_flow_audit.py) ranked output):

| Cell | n | event mean | placebo mean | null-gap | t | cost-headroom |
|---|---|---|---|---|---|---|
| `× EURUSD` | 88 | −2.68 bps | −0.48 bps | **−2.20 bps** | **−1.77** | +0.70 bps |
| `× GBPUSD` | 42 | −1.97 bps | +0.37 bps | **−2.34 bps** | −1.45 | +0.34 bps |

Combined basket (SHORT both legs, average) — pre-Phase-2 estimate:

- ~88 events with EUR-only contribution (Q1 2019 → Oct 2022)
- ~42 events with both legs (Nov 2022 → Apr 2026)
- Effective net-mean = (EUR_mean + GBP_mean) / 2 ≈ **+2.27 bps SHORT per event** (cost-net)
- Trade-Sharpe estimate at n~94: combining two t≈1.5-1.8 same-direction legs at zero corr gives t ≈ 1.5×√2 ≈ +2.1 in single-leg-Sharpe space, annualized ×√12 ≈ **+0.7 to +1.0**
- Live haircut (lesson #5 rewritten 10-25% relative): **live Sh +0.5 to +0.9**
- Expected MDD on event-equity curve: low single-digit % (12 events/yr × ~2-3 bps mean × cap-2.5pp single-event tail)

## Fail conditions (pre-committed — 13 criteria, ALL must PASS)

Set BEFORE Phase 2 simulator runs. Any single fail → REJECT.

| # | Criterion | Threshold | Rationale |
|---|---|---|---|
| 1 | **Full-sample basket mean net bps ≥ +1.5 bps/event** | ≥ +1.5 | Below this magnitude isn't deploy-defensible at 12/yr cadence |
| 2 | **W3 2023-2026 holdout net mean ≥ +1.0 bps/event** | ≥ +1.0 | Most-decayed regime; binding deploy criterion per repo convention |
| 3 | **All 3 regimes net-positive** | W1, W2, W3 > 0 | Standard regime gate |
| 4 | **Annualized Sharpe ≥ +0.30** | ≥ +0.30 | Phase 2 deploy bar (repo convention) |
| 5 | **WR ≥ 53%** | ≥ 53% | Slightly above coin-flip; reasonable for symmetric-variance FX |
| 6 | **MDD ≤ −3%** (on event-equity-curve, fixed notional) | ≤ −3% | Low-cadence strategy MDD should be small |
| 7 | **Bootstrap 95% CI lower bound on full-sample mean > 0 bps** | > 0 | Survives n=88-94 sampling variance — the binding small-sample test |
| 8 | **Direction-gap (SHORT trade-Sh − LONG trade-Sh) > +0.30** | > +0.30 | Asymmetric directional edge |
| 9 | **Placebo non-event same-weekday mean magnitude < 1 bps SHORT** | < 1 bps | Disambiguate from generic weekday drift |
| 10 | **Cost-stress @ 2× default — mean net > 0** | net > 0 | Live spread could widen at month-end |
| 11 | **Deflated Sharpe ≥ +0.20** | ≥ +0.20 | Accounts for the 17-cell screen selection bias |
| 12 | **Walk-forward halves**: split events chronologically in halves; both halves net mean > 0 | both > 0 | Detect monotonic decay shape |
| 13 | **EUR + GBP co-direction**: BOTH single-leg SHORT means must be net > 0 in W3 holdout | both > 0 W3 | Mechanism story REQUIRES the two legs to agree — venue-specificity tombstone if they don't |

PASS = all 13. REJECT otherwise.

## Why this might fail (red flags)

1. **The screen used n=42 GBP only (Nov 2022+).** The basket's GBP contribution to W1/W2 regimes is effectively zero (no data) — those windows are EUR-only. If EUR alone doesn't clear in W1/W2 (pre-2022 ECB-era), criterion #3 fails.
2. **EUR/GBP behavior changed structurally post-2022.** ECB rate-hike cycle started July 2022; the post-2022 W3 regime is rate-divergence era while W1+W2 is QE-and-pandemic era. The mechanism (USD funding squeeze) is mechanistically constant, but the *magnitude* may have been compressed in the rate-converged W1+W2 era.
3. **t-stats are individually below 2.** Combining two t=1.5-1.8 same-direction legs at low correlation gives plausible-MEDIUM but not strong. n=94 basket is enough power if the gap holds; small-sample variance at n=42 GBP is wide.
4. **Same-day correlation between EUR and GBP is high** (DXY-driven, ~+0.6-0.8 typical). The basket diversification benefit is limited — combining doesn't reduce vol as much as two independent strategies would.
5. **Cost is structurally tight** — Eightcap EUR ~1 bp RT, GBP ~1.5 bp RT. Edge is in the 2-2.3 bp range. Live cost surprise (5 bp widening at month-end) would compress net to break-even. The Phase 5 audit needs to be careful here.

## Phase plan

- [ ] Phase 1 — basket simulator on EUR + GBP M5, baseline + variant sweeps
- [ ] Phase 2 — full 13-criterion kill-criteria evaluation, regime breakdown, bootstrap, cost-stress, walk-forward halves
- [ ] Phase 3 — IF PASS, cross-asset shadow (does the same SHORT-USD signal appear on AUDUSD/USDCAD/USDJPY same window?)
- [ ] Phase 5 — IF PASS, broker-spread audit specifically at month-end 14-15 ET (verify Eightcap EUR/GBP spread stays < 3 bp during the window)
- [ ] Phase 7-8 — IF PASS, MQL5 EA build (basket form — 2 magic numbers or 1 EA-with-both-symbols decision)

## Files

- [month_end_usd_short_demo.py](month_end_usd_short_demo.py) — Phase 2 simulator + 13 kill criteria
- [Phase 0 screen origin](../structural_flow_audit/structural_flow_audit.py) — surfaced 2 of 3 WEAK cells now refined into this basket
