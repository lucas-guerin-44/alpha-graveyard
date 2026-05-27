# Regime classifier diagnostic — methodology experiment

**Status**: Complete (2026-05-27). Diagnostic methodology validated; verdict HAS LEGS at research level but two Phase 2 v2 attempts both REJECT-marginal due to small-sample / deflated-Sharpe issues. Banked as repo infrastructure for future re-evaluation when sample sizes grow.
**Type**: Cross-strategy diagnostic, NOT a deploy-candidate thesis.
**Goal**: Answer the bounded question "do the 7 deployed strategies behave regime-conditionally, and if so which gate predicts it best?" before committing to building a regime-classifier infrastructure or regime-segmented book architecture.
**Outcome**: methodology empirically validated (predicted v2 Sh within 0.02-0.04 of observed); both Phase 2 v2 attempts (xau_session_v2_ffr_gated 9-10/11, last_hour_month_end_ndx_v2_vix_gated 8/10) REJECT-marginal at currently-available sample sizes. Lessons #74-#76 captured. Re-evaluate ~2027-2028 when n grows.

## Background

Three documented mechanism-family REJECTs in the repo share the same shape: same mechanism, opposite sign across monetary regimes.

- Lesson #-7 (`earnings_continuation_mag7`): 2022/2023 boundary flips fade-vs-continuation sign on Mag7 single-stock earnings (Sh −1.67 fade-side / +0.78 cont-side in W3 vs symmetric in W1+W2)
- Lesson #43 family / lesson #2 (US-index intraday MR): 2023+ holdout shows 0DTE-amplification-driven sign-inversion across opex_pin_fade, ndx_mean_reversion, vwap_fade etc.
- Lesson #74 (`last_hour_month_end_ndx`, 2026-05-27): W2 2021-2022 QE/pandemic regime inverts last-hour-of-month-end direction (SHORT wins W1+W3, LONG wins W2)

All three driven by *monetary regime change*. The deployed book is currently regime-unaware — strategies run unconditionally across all regimes, picking up edge where they fire. Question: does regime-segmenting the book produce structural alpha lift, or are the deployed mechanisms regime-stable enough that gating adds operational complexity without Sharpe benefit?

## Hypothesis (pre-committed)

If the deployed book is genuinely regime-conditional, at least 2 of the 7 strategies should show **Sharpe spread ≥ +0.50 across regime states under at least ONE candidate gate**. Below that threshold the regime-book vision doesn't have empirical legs on this specific book.

## Methodology

1. **Pull macro series from FRED** (free fredgraph CSV endpoint, no API key):
   - `DFF` — Federal Funds Effective Rate (daily)
   - `DGS10` — 10y Treasury yield (daily)
   - `DGS2` — 2y Treasury yield (daily)
   - `T10YIE` — 10y breakeven inflation (daily)
   - `VIXCLS` — VIX (daily)

2. **Define 5 candidate regime gates** (all observable at trade time, no lookahead):

   | Gate | States | Definition |
   |---|---|---|
   | `ffr_direction` | EASING / NEUTRAL / TIGHTENING | sign(FFR_today − FFR_180d_ago); NEUTRAL if |Δ| < 25 bp |
   | `real_rate_sign` | POSITIVE / NEGATIVE | sign(DGS10 − T10YIE) |
   | `yield_curve_sign` | INVERTED / NORMAL | sign(DGS10 − DGS2) |
   | `vix_regime` | CALM / NORMAL / STRESS | 60d trailing median: CALM < 15, STRESS ≥ 22, else NORMAL |
   | `ndx_rv_regime` | LOW / NORMAL / HIGH | NDX 60d realized vol annualized: LOW < 15%, HIGH ≥ 25%, else NORMAL |

3. **Load PnL series for two audit pools**:
   - **Pool A (deployed, 10 streams)**: via `portfolio_risk_parity_demo.load_all_daily()` — 5 deployed-base + 4 event-calendar sub-events + quarter_end_xau_short. Question: *can existing deploys be improved by adding a regime gate?*
   - **Pool B (regime-conditionally-tombstoned graveyard candidates)**: curated short-list of REJECTs whose load-bearing failure mode was "regime sign-flip" or "holdout decay" rather than "signal absent". Question: *can rejected strategies be resurrected as regime-gated v2s?* Initial Pool B list:
     - `last_hour_month_end_ndx` (2026-05-27 REJECT, criterion #13 W2 sign-flip — lesson #74) — the prototype for this question
     - `earnings_continuation_mag7` (lesson #-7, 2022/2023 sign-flip)
     - `earnings_fade_nonmag7` (lesson #-6, walk-forward marginal due to OOS Sharpe decay)
     - `opex_pin_fade` (lesson #-5, 0DTE-amplification-driven holdout sign-inversion)
     - `cfd_wed_rollover_eurusd` (lesson #-18, W3 sign-flip)
     - `xau_asia_range` (2026-05-27, bullrun-isolation gap collapsed in W4 only)
     - `pre_fomc_drift_eurusd` (lesson #-16, W4 dead but mechanism existed pre-2023)

   Pool B is the *higher-leverage* pool — strategies already filtered as REJECT may have larger regime-conditional Sharpe spreads than the curated-for-stability deployed book (selection-bias caveat in last section).

4. **For each (strategy × gate)**: partition daily PnL by regime state; compute per-regime Sharpe + per-regime active-day count + per-regime daily mean.

5. **Output**:
   - Per-gate matrix of `strategy × regime → Sharpe`
   - Per-strategy max-Sharpe-spread across regimes (= "regime conditionality score")
   - Per-gate cross-strategy discrimination score (sum of spreads across all strategies)
   - Ranked verdict: which gate(s) and which strategies are regime-conditional candidates

6. **Cross-experiment lessons inherited** (must respect):
   - Lesson #21 risk-free-subtracted Sharpe — use raw Sharpe consistently
   - Lesson #29 walk-forward is binding for TSMOM — not directly relevant but reminder that single-window Sharpe is fragile
   - Lesson #54 pre-commit both directions — N/A here (no direction choice)
   - Lesson #43 / lesson #2 — 0DTE-amplification proxy for 2023+ holdout is exactly the kind of regime gate this diagnostic is searching for

## Pre-committed verdict logic (set BEFORE running)

Evaluated separately on Pool A (deployed) and Pool B (resurrect candidates):

| Pool A outcome | Diagnostic verdict | Next action |
|---|---|---|
| ≥ 3 deployed strategies show >+0.5 Sh spread under ONE gate | **DEPLOYED-BOOK GATING HAS LEGS** | Build first gated v2 on the highest-spread deployed responder |
| 1-2 deployed show >+0.5 spread | **TARGETED DEPLOYED GATING** | Build per-strategy v2 of the deployed responders |
| No deployed shows >+0.3 spread | **DEPLOYED BOOK IS REGIME-NEUTRAL** (confirms selection-bias hypothesis — passed-Phase-2 strategies are already regime-stable) | Don't gate existing deploys; focus on Pool B |

| Pool B outcome | Diagnostic verdict | Next action |
|---|---|---|
| ≥ 2 tombstoned strategies show >+0.5 Sh spread under ONE gate AND best-regime Sh > +0.5 | **RESURRECT CANDIDATES EXIST** | Build v2-gated thesis for each resurrect-candidate; the gate becomes a binding pre-commit |
| 1 candidate shows resurrect-grade spread | **ONE RESURRECT** | Single v2 thesis; pure single-strategy refinement |
| No resurrect candidate clears | **GRAVEYARD STAYS GRAVE** | The tombstones are signal-absent rather than regime-conditional; the v2-gated approach won't work |

**Combined book vision verdict** (set BEFORE running):
- If Pool A "has legs" OR Pool B "resurrect candidates exist" → **regime-book vision empirically supported**, proceed to v2 thesis on the best responder
- If both pools are negative → **regime-book vision is wrong for this specific repo**, current generalist structure is empirically right
- If only Pool B is positive while Pool A is negative → **graveyard resurrection is the gating opportunity, not deployed-book optimization** — the diagnostic reframes the next 3-6 months of research priority

## Why this is not a deploy-candidate experiment

This is methodology infrastructure. The output is a **diagnostic matrix + verdict**, not a tradable strategy. The DEPLOY pipeline only begins once a regime-conditional candidate (strategy + gate) has been identified empirically — at which point a v2 thesis gets written with the gate as a binding pre-commit.

Analogous to `regime_hurst_diagnostic` (MARGINAL, asymmetric — lesson #-9) which audited TSMOM/MR strategies through a Hurst-regime gate. That diagnostic decided not to gate the deployed book on Hurst; this one is the analog asking the same question about monetary-regime gates.

## Files

- [regime_classifier_diagnostic.py](regime_classifier_diagnostic.py) — fetches FRED series, defines 5 gates, audits all 10 PnL streams, outputs matrices + verdict

## Open question / risk

The deployed strategies were selected through phase-2 validators that often included regime breakdown (W1/W2/W3) as a pre-commit. So they all passed "≥ 3 regimes positive Sharpe". That ALREADY filters for *some* regime-stability — meaning the diagnostic may find lower spread than would exist on a less-curated strategy set. This is honest information: the existing book may genuinely be regime-stable BECAUSE we selected for it, not because the underlying space is regime-neutral. The diagnostic verdict needs to account for selection bias: weak signal here doesn't necessarily mean weak signal in the general universe of candidate strategies — it might just mean our existing book is already regime-robust.
