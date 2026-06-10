# Monthly Gamma Cycle Overlay — NDX OPEX-week regime diagnostic

**Status**: Phase 0 diagnostic, 2026-06-10. NOT a standalone strategy — calendar-based regime-split overlay on existing NDX strategies (`lunch_fade`, `ndx_trend_day`). Closed.

**Verdict**: REJECT — placebo confound, not gamma cycle. 3 of 5 pre-committed criteria FAIL.

---

## Thesis (mechanism)

1. Post-0DTE (2022+), dealer gamma exposure follows a predictable monthly cycle phase-locked to OPEX (monthly option expiration, 3rd Friday):
   - **OPEX-7 to OPEX-2d (W-1)**: Dealers accumulate long gamma (selling front-month series). Market → choppier, mean-reverting (dealers' long-gamma hedging dampens directional moves). Favours `lunch_fade`.
   - **OPEX-1d to OPEX (W0)**: Peak long gamma then unwind. Market → calm, pinned.
   - **OPEX+1 to OPEX+7d (W+1)**: Front month expires, new series starts. Dealers sell straddles → net short gamma. Market → trendier, amplified (dealer short-gamma hedging is trend-amplifying). Favours `ndx_trend_day`.
   - **OPEX+8 to OPEX+14d (W+2)**: Short gamma saturates as dealers delta-hedge. Market → mixed transitional.

2. This gamma cycle is **calendar-orthogonal** to every signal-based overlay attempted (sentiment, vol-target, Hurst). It doesn't predict direction — it predicts **regime type** (MR-favourable vs trend-favourable). Therefore:
   - `lunch_fade` (mean reversion) should have higher Sharpe in pre-OPEX weeks (dealers long gamma → chop/reversion).
   - `ndx_trend_day` (trend continuation) should have higher Sharpe in post-OPEX weeks (dealers short gamma → trend amplification).

3. If the cycle validates, the deploy implication is: **rotate sizing** between the two NDX strategies based on OPEX cycle phase. A risk-budget tilt, not an on/off switch.

## Results (2026-06-10)

Simple NDX lunch_fade and trend_day replicas split by OPEX-cycle phase on 147,174 M5 bars (2019-01 → 2026-06-05).

### Phase-split Sharpe

| Phase | lunch_fade Sh | trend_day Sh | bars |
|---|---|---|---|
| W-1 LONG GAMMA | −0.50 | +0.62 | 27,379 |
| W0 PEAK UNWIND | −0.97 | +1.96 | 13,604 |
| W+1 SHORT GAMMA | −0.73 | +0.67 | 33,466 |
| W+2 GAMMA SAT | −0.37 | +0.03 | 33,364 |
| OTHER | −0.39 | +0.26 | 39,361 |

### Pre-committed criteria check

| Criterion | Result | Verdict |
|---|---|---|
| lunch_fade W-1 − W+1 ≥ +0.20 | +0.23 | PASS |
| trend_day W+1 − W-1 ≥ +0.20 | +0.05 | FAIL |
| Same ordering across 3 regime windows | flips every window | FAIL |
| Placebo (+7d) deltas < +0.10 | −0.31 / −0.88 | FAIL |
| Each phase ≥ 200 bars | all ≥ 13,604 | PASS |

### Regime stability

| Regime | W-1 l_Sh | W+1 l_Sh | W-1 t_Sh | W+1 t_Sh | l_delta | t_delta |
|---|---|---|---|---|---|---|
| 2019-2020 | −1.63 | −0.16 | +0.71 | +1.52 | −1.47 | +0.82 |
| 2021-2022 | +2.64 | −2.92 | +3.25 | +0.57 | +5.56 | −2.67 |
| 2023-2026 | −1.74 | +0.51 | −1.23 | +0.11 | −2.25 | +1.35 |

### Mechanistic interpretation

**The gamma cycle does not produce a deployable regime split at weekly resolution.** Three independent signals converge on the same verdict:

1. **Placebo failure is decisive.** The +7d shifted OPEX produced *larger* deltas (−0.31 / −0.88) than the real alignment (+0.23 / +0.05). The weekly OPEX label proxies for mid-month concentration of scheduled macro events (FOMC, CPI, NFP all cluster near the 3rd Friday), not for dealer gamma dynamics. This is a **macro-calendar confound**, not a gamma cycle.

2. **Sign-flips across every regime window** — the effect direction changes in every sub-period. No regime-conditional deploy path exists.

3. **lunch_fade W-1 vs W+1 barely passes** (+0.23 vs +0.20 bar) but both phases have *negative* Sharpe. The "advantage" is less-bad in W-1, not positive. The trend_day delta (+0.05) is a decisive miss.

The null result is informative: OPEX-week labels partition the calendar in a way that roughly aligns with macro-event concentration, not gamma cycle. The `opex_pin_fade` finding (Friday-only, sign-inverted) is not rescued by widening to a weekly window — the gamma signal is either absent at weekly resolution or too weak to survive the macro-calendar confound.

## Why NOT the same as `opex_pin_fade` (REJECT)

`opex_pin_fade` tested a specific directional trade: fade the Friday PM pin on OPEX day. It REJECTed because 0DTE gamma makes dealers short-gamma on the Friday itself (trend amplification, not pin).

This thesis tests whether the **full 4-week gamma cycle** creates a predictive weekly regime pattern. If the effect is Friday-only (as `opex_pin_fade` found for the pin trade), the diagnostic shows that. If the cycle spreads across weeks, it's a live sizing lever.

## Key reference

- Ni, Pearson & Poteshman (2005). "Stock Price Clustering on Option Expiration Dates." *JFE* 78(1).
- Golez & Jackwerth (2012). "Decoding the PIN." Working paper.
- CME 0DTE data reports 2022-2026.
- **Repo lesson #42**: `opex_pin_fade` REJECT.
- **Repo lesson #43**: post-2022 MR sign-inversion.
- **Repo lesson #40**: vol-target sizing as variance reshuffle (N/A — calendar-based not vol-based).
- **Repo lesson #41**: calendar gating diagnostic (variance-share vs day-share check applies to placebo shift).

## Signal math — no standalone signal

This overlay does NOT generate its own entries/exits. It produces per-bar **regime labels** applied post-hoc to existing NDX strategy returns:

```
OPEX = 3rd Friday of each month

Week mapping (Mon-Fri):
  W-1: OPEX-7  to OPEX-2d   → long gamma accumulation
  W0:  OPEX-1d to OPEX day  → peak + unwind
  W+1: OPEX+1  to OPEX+7d   → short gamma build (trend regime)
  W+2: OPEX+8  to OPEX+14d  → short gamma saturated

Per-bar (NDX RTH 09:30-16:00 ET):
  phase = label_from_opex_week(date)

Compare + print:
  lunch_fade returns split by phase
  ndx_trend_day returns split by phase
  Placebo: shift OPEX +7d, re-run
```

## Expected performance (prior)

Not a Sharpe target. The overlay's value is the delta between phases. Pre-committed bars:
- `lunch_fade` Sharpe(W-1) − Sharpe(W+1) > +0.30.
- `ndx_trend_day` Sharpe(W+1) − Sharpe(W-1) > +0.30.
- 3 of 4 regime windows show same ordering.
- Placebo (+7d shift) deltas collapse to < +0.10.

## Fail conditions (pre-committed)

Diagnostic FAIL (do not proceed to sizing recommendation) if ANY:
- `lunch_fade` W-1 vs W+1 Sharpe delta < +0.20 absolute, OR
- `ndx_trend_day` W+1 vs W-1 Sharpe delta < +0.20 absolute, OR
- Ordering flips sign across regimes (regime-conditional cycle not deployable), OR
- Any of the 4 primary phases has < 200 bars over the full sample.

## Why this might fail (red flags)

1. **Gamma cycle too weak at weekly resolution**: Effect may be concentrated in final 24-48h before OPEX, not spread across weeks. `opex_pin_fade` found Friday effect sign-inverted; weekly spread may be zero.
2. **Macro calendar overlap**: OPEX week often overlaps with FOMC/CPI/NFP. The gamma label may proxy for event concentration. Placebo shift catches this.
3. **Regime-conditional**: Pre-2022 (pre-0DTE ramp), the cycle didn't exist. Effect should be concentrated post-2022; pre-2022 bars are flat across all phases.
4. **Over-rotation risk**: If cycle validates and sizing tilts too aggressively, a regime break (OPEX calendar rule change, settlement reform) leaves sizing wrong-footed.

## Files

- Thesis: this file (`experiments/gamma_cycle_overlay/gamma_cycle_overlay.md`)
- Diagnostic: `experiments/gamma_cycle_overlay/gamma_cycle_diagnostic.py`
- Data: `ohlc_data/NDX100_M5.csv`
- Run: `venv/Scripts/python.exe experiments/gamma_cycle_overlay/gamma_cycle_diagnostic.py`
