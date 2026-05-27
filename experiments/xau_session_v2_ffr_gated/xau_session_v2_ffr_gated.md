# XAU Session v2 — FFR-direction gated — Phase 2 thesis

**Status**: Phase 2 REJECT (2026-05-27). Mechanism real, magnitude sub-threshold.
**Type**: Regime-gated v2 of a DEPLOYED strategy (`xau_session`, deployed 2026-05-16).
**Verdict**: **REJECT — both v2a (9/11) and v2b (10/11) fail criterion #1 (full Sh ≥ +1.20) by ~0.10-0.12.** The gate DOES lift Sharpe by +0.30 (parent +0.79 → v2 +1.08-1.11) but my pre-commit threshold was calibrated to the diagnostic's active-aware numbers, which over-stated the deployable lift due to in-regime cadence overestimation. Parent `xau_session` stays deployed unconditionally. Methodological refinement: future gated-v2 theses should target +0.15-0.20 lift, not +0.40.

## Phase 2 results

| Variant | Sh | W3 holdout | Retention | Result | Failing criteria |
|---|---|---|---|---|---|
| Parent (unconditional) | +0.79 | +1.23 | 100% | (deployed) | — |
| **v2a** (TIGHTENING-only) | +1.11 | +1.86 | 41% | **REJECT 9/11** | #1 Sh +1.11 < +1.20; #7 cross-cycle (logic bug, no post-2024-07 data) |
| **v2b** (NOT-NEUTRAL) | +1.08 | +1.63 | 59% | **REJECT 10/11** | #1 Sh +1.08 < +1.20 |

NEUTRAL-regime regret check (what we'd lose if active in NEUTRAL): **−0.01 Sharpe** on n=132. Confirms the gate is removing genuinely dead trades.

## Honest interpretation

The diagnostic's `ffr_direction` gate identified `xau_session` as regime-conditional with a +1.80 spread (TIGHTENING +1.74 / NEUTRAL −0.06, active-aware). The v2 simulator confirms that direction:
- Gated full-sample Sharpe rises from +0.79 to +1.08-1.11 (+0.30 lift)
- W3 holdout rises from +1.23 to +1.63-1.86 (+0.40-0.63 lift)
- NEUTRAL-regime trades are demonstrably dead (Sh −0.01)
- Both walk-forward halves positive for both variants

But the **full-sample lift (+0.30) is less than half the active-aware diagnostic suggested (+0.80)**. The gap is because:
1. Active-aware Sharpe uses `mean × sqrt(active_in_regime_per_year)` annualization which over-estimates the deployable cadence when active days are concentrated rather than uniformly distributed
2. Removing NEUTRAL trades cuts variance contribution but also cuts mean contribution from W1 (which has substantial NEUTRAL periods)
3. The +1.20 bar I set targeted +0.40 lift; observed +0.30 lift implies the right bar would have been ~+1.10

Per pre-commit discipline this is a REJECT. The findings are still informative:
- **The diagnostic is directionally correct** — `xau_session` IS regime-conditional via FFR direction
- **The diagnostic is magnitudinally optimistic** — active-aware Sharpe overstates deployable lift by ~2-3× for sparse strategies
- **Future v2-gated theses must calibrate the lift threshold lower** (~+0.15-0.20 lift over parent is a more realistic bar)

## What stays deployed

Parent `xau_session` unconditional. No changes to `deploy/mq5/xau_session.mq5`.

## What this informs for the next experiments (per user's plan)

- The diagnostic methodology is validated but the lift-magnitude estimate needs deflation
- Pool B expansion (next experiment) should use the calibrated lift expectation (+0.15-0.30, not +0.50)
- `last_hour_month_end_ndx_v2_vix_gated` (later in plan) — same gate-calibration caveat applies, but the parent there was REJECTed not deployed, so the gating needs to clear deployment bar (+0.30 Sh + bootstrap CI > 0), not "lift over parent"
- A *soft-gating variant* (size DOWN in NEUTRAL rather than flat) is worth considering as a v3 — captures partial lift while preserving operational simplicity

## Files

- [xau_session_v2_ffr_gated_demo.py](xau_session_v2_ffr_gated_demo.py) — Phase 2 simulator (REJECT 9/11 v2a, 10/11 v2b)

---

## Original thesis content preserved below for context


Origin: `regime_classifier_diagnostic` (2026-05-27) surfaced `xau_session × ffr_direction` as the highest-spread responder in the entire deployed book — TIGHTENING regime Sharpe +1.74 / NEUTRAL Sharpe **−0.06** (active-aware annualized) = spread +1.80. The diagnostic was the strongest single signal across 40 (strategy × gate) cells.

## Thesis (mechanism)

The deployed `xau_session` (Asian-session-handoff variant with conditional prior-NY filter, XAUUSD H1) is currently traded unconditionally across all monetary regimes. The diagnostic reveals it is **regime-conditional via FFR direction**:

1. **TIGHTENING regime** (6m FFR change > +25 bp): Sharpe +1.74 (active-aware). The mechanism (Asian-session institutional handoff + prior-NY-down-medium filter) works strongly when the Fed is hiking — likely because USD-strength environments amplify XAU-flow asymmetry, and rate-hike cycles concentrate cross-asset risk-positioning shifts at the Asian-NY handoff.
2. **EASING regime** (6m FFR change < −25 bp): Sharpe +0.66 (active-aware). Moderate signal — gold tends to rally in cutting cycles but the intraday-flow asymmetry the strategy captures is reduced.
3. **NEUTRAL regime** (|6m FFR change| < 25 bp): Sharpe **−0.06** (active-aware). The mechanism is essentially dead during steady-policy periods. This is the largest source of Sharpe drag in the unconditional deploy.

The hypothesis: removing the NEUTRAL-regime trades (gate the EA to flat when |6m FFR change| < 25 bp) should lift effective Sharpe materially without changing the mechanism story.

**Two v2 variants pre-committed (per lesson #54 best-of-direction logic adapted)**:

- **v2a (TIGHTENING-only)**: trade only when 6m FFR change > +25 bp. Maximally restrictive; highest Sharpe in active periods; lowest cadence.
- **v2b (NOT-NEUTRAL)**: trade when |6m FFR change| > 25 bp (TIGHTENING OR EASING). Softer gate; both EASING and TIGHTENING regimes are weakly-positive; medium cadence.

Both pre-committed; data direction-selects which is the deploy candidate.

## Key reference

- Internal: [`regime_classifier_diagnostic`](../regime_classifier_diagnostic/regime_classifier_diagnostic.md) — surfaced this exact gate as the highest-spread responder.
- Parent strategy: [`xau_session`](../_live/xau_session/xau_session.md) deployed 2026-05-16 (Sh +0.79 unconditional / +1.23 W3 holdout).
- Monetary regime literature: Stein (2014) "Incorporating Financial Stability Considerations into Monetary Policy"; Adrian, Etula, Muir (2014) "Financial Intermediaries and the Cross-Section of Asset Returns".

## Signal math

```
Universe          : XAUUSD H1, identical to parent xau_session
Filter            : 'dnmed' (deployed parent config — Asian-handoff with prior-NY DOWN-medium filter)
Entry/exit/cost   : identical to parent (cost_bps=2.0, direction='long')
NEW: FFR regime gate (computed from FRED DFF series, daily)
  ffr_change_180d_bp = (FFR_today - FFR_180d_ago) × 100
  regime_today =
    'TIGHTENING' if ffr_change_180d_bp > +25
    'EASING'     if ffr_change_180d_bp < -25
    'NEUTRAL'    otherwise

v2a entry filter: take trade IFF regime_today == 'TIGHTENING'
v2b entry filter: take trade IFF regime_today != 'NEUTRAL'
```

The gate uses 180-day FFR change with 25 bp neutral band — identical to the diagnostic's `ffr_direction` definition (NO post-hoc tuning).

## Universe

XAUUSD H1 (parent strategy). Sample 2018-08 → 2026-05.

## Expected performance (priors from diagnostic — sample-conditional)

| Variant | Diagnostic-derived Sh (active periods) | Cadence reduction | Expected gated full-sample Sh |
|---|---|---|---|
| **v2a** TIGHTENING-only | +1.74 (TIGHTENING regime alone) | ~50-60% (TIGHTENING covers ~2022-2024 + 2026-current) | +1.40 to +1.60 |
| **v2b** NOT-NEUTRAL | weighted avg (TIGHTENING + EASING) ≈ +1.20 | ~30-40% | +1.10 to +1.30 |
| Parent (unconditional) | +0.79 full / +1.23 W3 | 0% | +0.79 (baseline) |

Expected lift over unconditional: **+0.30 to +0.80 Sharpe**.

## Fail conditions (pre-committed — 11 criteria, ALL must PASS for the chosen variant)

Set BEFORE Phase 2 simulator runs. Any single fail → REJECT the variant. If both v2a AND v2b PASS, prefer the one with higher trade retention (more robust to regime transitions).

| # | Criterion | Threshold | Rationale |
|---|---|---|---|
| 1 | **Gated full Sh ≥ +1.20** | ≥ +1.20 | Lift over unconditional +0.79 must clear +0.40 to justify operational complexity |
| 2 | **Gated W3 holdout Sh ≥ +1.40** | ≥ +1.40 | Beats parent's W3 +1.23 by ≥ 0.17 |
| 3 | **All 3 traded regimes positive** | W1, W2, W3 each net-positive | Same regime stability bar as parent deploy |
| 4 | **NEUTRAL-regime regret Sh > −0.30** | > −0.30 | When we're flat, we're not missing big edge — sanity check on the gate |
| 5 | **Trade retention ≥ 30%** | ≥ 30% of parent's 321 trades = ≥ 96 trades | Gate must not over-prune |
| 6 | **Bootstrap 95% CI lower on gated full-sample mean > 0** | > 0 | Survives sampling variance |
| 7 | **Cross-cycle consistency**: TIGHTENING 2022-mid-2024 AND mid-2024-current both individually positive | both > 0 | Detects single-cycle overfit |
| 8 | **Walk-forward halves both net-positive** | both > 0 | Standard WF check |
| 9 | **Cost-stress @ 2× default** still net-positive | net > 0 | Cost-robustness inherited from parent |
| 10 | **Deflated Sharpe ≥ +0.50** | ≥ +0.50 | The diagnostic tested 4 gates × 10 strategies = 40 cells of selection bias; deflated Sh penalty is heavier than for un-diagnostic-selected experiments |
| 11 | **Corr-tombstone vs unconditional parent ≥ +0.85** | ≥ +0.85 | Sanity: the gated series should be a subset of the parent's trades, NOT a different mechanism |

PASS = all 11. REJECT otherwise.

## Why this might fail (red flags)

1. **Single-cycle out-of-sample risk**. The sample has ONE full Fed cycle (2018-2026): EASING 2019-2020 (Powell cuts), NEUTRAL 2020-Q4 to 2022-Q1, TIGHTENING 2022-Q2-onwards. The diagnostic's TIGHTENING bucket = essentially the 2022-onwards period. The FFR-gate may be just "post-2022 in disguise" — its forward portability across cycles is unverified. Criterion #7 (cross-cycle consistency within the available TIGHTENING period) tries to catch this but only partially.
2. **Regime transition handling**: when Fed pivots from TIGHTENING to NEUTRAL (already happening in 2024-2026 with Fed pause / cuts), the strategy goes flat. If the mechanism is gradual rather than regime-bounded, gating creates whipsaw and missed opportunity.
3. **The diagnostic's gate is one of four candidate gates**. Other gates (real_rate_sign, vix_regime) also discriminated xau_session strongly. The choice of ffr_direction is justified by it being the most universally discriminating gate (sum across strategies +7.30), not by it being the best gate for xau_session specifically. A combined gate or a different single gate might be better.
4. **Selection bias from the diagnostic itself**. We picked the best-spread (strategy × gate) pair from 40 candidates. Deflated Sharpe (criterion #10) is calibrated for this but post-hoc selection bias is harder to fully correct.
5. **Live operational complexity**: the EA must read a daily FFR series. Two implementation options: (a) FRED API call at EA daily startup, (b) ship a regime CSV updated quarterly. Both add a failure mode (network error, stale CSV) that doesn't exist in the unconditional parent.

## Phase plan

- [ ] Phase 1 — simulator + per-variant Sharpe + regime breakdown + cross-cycle test
- [ ] Phase 2 — 11 pre-committed kill criteria for each variant; if BOTH pass, pick higher-retention; if neither passes, REJECT
- [ ] Phase 3 — IF PASS, corr-tombstone vs parent + cross-cycle bootstrap
- [ ] Phase 5 — N/A (cost model inherited from parent)
- [ ] Phase 7-8 — IF PASS, write `deploy/mq5/xau_session_v2_ffr_gated.mq5` (or add gate input to existing xau_session EA)

If v2 PASSES, the deploy decision is: **replace the unconditional `xau_session` with the gated v2**. The original unconditional deploy stays as legacy comparison only.

## Files

- [xau_session_v2_ffr_gated_demo.py](xau_session_v2_ffr_gated_demo.py) — simulator + 11 kill criteria for v2a and v2b
- Parent: [`../_live/xau_session/`](../_live/xau_session/)
- Diagnostic origin: [`../regime_classifier_diagnostic/`](../regime_classifier_diagnostic/)
