# Project State

Index of every experiment with verdict + headline numbers. Truth is in the linked thesis docs.
Lessons → [RESEARCH_NOTES.md](RESEARCH_NOTES.md). Rejects → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md).

- **Live** = MT5 VPS only (private). QC retired 2026-05.
- **Tradeability**: datalake M5 ⇒ broker-confirmed; D1-only ⇒ verify via `scripts/mt5_fetch.py --list-symbols`.
- **Datalake**: private; configured via `DATALAKE_URL` / `DATALAKE_API_KEY` env vars. Endpoints: `/catalog`, `/instruments/<symbol>`, `/query`.

---

## Snapshot (2026-05-16)

| Status | Count | Names |
|---|---|---|
| Live (MT5 VPS, paper) | 3 | `orb_dax`, `lunch_fade`, `xau_session` |
| Retired from live | 1 | `xs_momentum` |
| Validated, blocked at broker | 2 | `treasury_trend` (no bonds), `softs_ensemble` (D1 depth too short) |
| Keep-for-reference / watch-list | 4 | `tsmom`, `btc_trend`, `btc_intraday`, `macro_drift` (Phase 0 done 2026-05-17 — pre-FOMC drift real (full Sh +0.92) but W3-concentrated (n=16 +0.70%) with marginal W4 (n=18 +0.12%, WR 44%); revisit 2026-11/2027-05 for more W4 events) |
| Pending Phase 2 | 1 | `gold_trend` |
| Unvalidated (inherited) | 1 | `imbalance` |
| Institutional-only | 3 | `fx_session` (retail RT cost eats edge); `xag_session` (Eightcap XAG 8bp spread eats Variant C gross); `xpt_session` (Eightcap XPT Asia 23bp spread; killed without Phase 2 — cost ceiling decisive) |
| Rejected | 29 | → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) |
| **Total** | **44** | |

---

## DEPLOYED (MT5 VPS)

### [orb_dax](../experiments/orb/orb.md) — DEPLOYED_PAPER
- GER40 H1 | Sh 0.76 / holdout 0.93 / MDD -7.8% / dir-gap +1.04 | 1440 trades (197/yr)
- Xetra opening-range breakout, OR=30min, T+180min exit, LONG-only
- 3/3 regimes positive; cost headroom ~1.3pt RT
- closed 2026-04-19 / deployed 2026-04-22

### [lunch_fade](../experiments/lunch_fade/lunch_fade.md) — DEPLOYED_PAPER
- NDX100 M5 | Sh 1.02 / holdout 1.51 / MDD -4.2% / dir-gap +1.87 | 117 trades (16/yr LONG)
- Fade 09:30-11:30 ET morning move during 11:30-13:30 ET liquidity vacuum
- 3/3 regimes positive, holdout BEST; cost-insensitive (-0.04 Sh/pt RT)
- closed 2026-05-12 / deployed 2026-05-13

### [xau_session](../experiments/xau_session/xau_session.md) — DEPLOYED_PAPER
- XAUUSD H1 | Sh 0.79 / W4 binding 1.23 / MDD -3.7% / dir-gap +2.28 | 321 trades (39/yr)
- Variant C 23:00→08:00 UTC 9h hold + DOWN-med prior-NY filter
- Phases 2-7 all PASS in one session; control-hold confirms session-specific
- closed 2026-05-16 / deployed 2026-05-16

---

## RETIRED FROM LIVE

### [xs_momentum](../experiments/xs_momentum/xs_momentum.md) — RETIRED_FROM_LIVE
- 24-instr multi-asset | Sh 0.92 research / **0.35 live** / holdout 1.33 / MDD -23.1%
- 189d trailing return, long top-5 EW, quarterly rebal
- Ran QC paper through early 2026. Retired 2026-05 (QC no longer deploy path)
- Canonical "research-to-live haircut" reference: -0.57 Sh observed

---

## VALIDATED — BROKER ACCESS REQUIRED

### [treasury_trend](../experiments/treasury_trend/treasury_trend.md) — VALIDATED_NO_DEPLOY
- IEF (Tiingo D1, 24y) | Sh 0.67 / holdout 0.42 / MDD -8.1% | 77 trades (7/yr)
- Multi-horizon TSMOM (1M/3M/12M) with BIL/SHY cash flat
- All 7 phases PASS; ~0 corr vs xs_momentum
- **Blocker**: Eightcap MT5 does not offer US Treasury CFDs (confirmed 2026-05-13)

### [softs_ensemble](../experiments/softs_ensemble/softs_ensemble.md) — VALIDATED_NO_DEPLOY
- 6 softs (Yahoo continuous) | Sh 0.85 / holdout 1.44 / MDD -13.3%
- Equal-weight TSMOM ensemble (multi-horizon 1M/3M/12M)
- Phases 2-7 PASS. Q1 2026 real-OOS +1.10% vs B&H -6.57% through cocoa crash
- **Blocker**: Eightcap D1 history for available softs only 332-382 bars (~16-18 months); 12M-lookback TSMOM needs longer

---

## KEEP-FOR-REFERENCE

### [btc_trend](../experiments/btc_trend/btc_trend.md) — KEEP_FOR_REFERENCE
- BTCUSD D1 | Sh 0.83 / real-OOS -0.32 / walk-fwd mean OOS 0.54 / min OOS -0.03
- Multi-horizon TSMOM + K=3 ATR pyramid, vol-target 15%, monthly rebal
- Two failure modes: (1) parabola-V vulnerability (S1+S5 both blew up); (2) institutionalization decay (W4 Sh +0.50 vs +1.38/+1.61 earlier)
- closed 2026-05-13 — see lesson #29 (walk-forward replaces single-split for TSMOM)

### [tsmom](../experiments/tsmom/tsmom.md) — KEEP_FOR_REFERENCE
- 24-instr long-only | Sh 0.40 / holdout 1.14 / MDD -15.5% | 384 trades (35/yr)
- 12-1 trailing return long-when-positive, classical TSMOM
- Mechanically valid but +0.69 corr with xs_momentum → no diversification value

### [btc_intraday](../experiments/btc_intraday/btc_intraday.md) — MARGINAL
- BTCUSD H1 | Sh 0.72 / W4 0.83 / W4-25-26 binding 0.64 PASS / **W4-26 -2.71 (n=20) FAIL**
- Hour-00 UTC drift + |prior-24h z|>1.0 + Tue/Thu/Fri filter, 2h hold
- 3/7 kill criteria PASS. Honest verdict MARGINAL. Two valid options: tombstone now OR wait + re-run on OOS 2026Q2-Q3 (~2026-08-15) with unchanged pre-commits
- closed 2026-05-16; regime-gate overlays NOT valid (goalpost-moving)

---

## PENDING

### [gold_trend](../experiments/gold_trend/gold_trend.md) — UNVALIDATED
- XAUUSD | Phase 1 in-progress
- Classical 12-1 single-instrument TSMOM with vol-targeting; Phase 2 kill if doesn't beat B&H

### [imbalance](../experiments/imbalance/imbalance.md) — UNVALIDATED (inherited)
- 24-instr universe | FVG 3-bar pattern mean-reversion
- Inherited from engine repo, not yet through Phase 1-8 workflow

---

## CROSS-EXPERIMENT PATTERNS

Findings that emerged from multiple experiments and now constrain what's worth proposing. Full detail in [RESEARCH_NOTES.md](RESEARCH_NOTES.md).

-3. **Asian-session-handoff family is NOT auto-transferable across 24/7 instruments (2026-05-16).** XAU W4 +1.23 (physical/sovereign — ACTIVATING) / BTC W4 +0.64 (spot-ETF — PARTIAL decay) / WTI W4 -0.58 (overnight oil — REVERSED). Pre-commit driver type: structural-physical → activation; professional-electronic → decay.

-2. **BTC deploy-discipline: pre-commit W4 as binding constraint.** Pre-2022-only edges are not deployable, period. Tight enough that W2-only-driven full-sample pass cannot survive.

-1. **BTC institutionalization driver acts in MIRROR IMAGE across mechanism families.** Same maturation DEGRADES slow-TSMOM (btc_trend) and ACTIVATES weekend-DOW (btc_weekend). Pre-commit which side the mechanism lives.

0. **Walk-forward Phase 6 catches parabola-V vulnerabilities single-split misses.** For TSMOM-family: walk-forward replaces single-split before deploy.

1. **US/EU index intraday "fade overshoot" theses keep sign-inverting.** 11:30-13:30 ET lunch fade is the ONLY exception. Don't propose generic "fade deviation" without explicit vacuum mechanism.

2. **Holdout (2023-26) regime as 0DTE-amplification proxy.** US-index intraday MR: if 2023-26 is >0.5 Sh below 2019-20, 0DTE killed it. Lunch-fade is the only one INTENSIFIED post-2022.

3. **CFD overnight/gap theses must be validated on real futures BEFORE Phase 2 refinement.** DAX overnight +0.80 → FDAX -0.34.

4. **Microstructure prerequisite for "public-info intraday drift"**: (a) public publication during continuous trading AND (b) tradeable basket concentrated on one venue.

5. **Gap-direction effect is venue-specific.** DAX gaps continue (Xetra). NDX gaps fade (NYSE/Nasdaq). Never port across venues without re-testing.

6. **Cost-zero Sharpe as "no edge" vs "edge eaten by friction" diagnostic.** Cost-zero ≈ 0 → no signal. Cost-zero >> 0 with linear collapse → real edge eaten by spread.

7. **Generic intraday triggers on NDX M5 don't survive friction.** Time-of-day-structural triggers can. Require specific microstructure mechanism.

8. **Research-to-live Sharpe haircut is +0.30 to +0.60 absolute** (not 50% multiplicative). Plan deploy budgets with absolute-drag model.

---

## UPDATE PROTOCOL

On experiment close:
1. Write verdict + numbers into `experiments/<name>/<name>.md` (truth lives there).
2. Add a 4-line entry here (active) or one row in [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) (REJECT). Link the name to the thesis doc.
3. Cross-experiment pattern → add lesson to [RESEARCH_NOTES.md](RESEARCH_NOTES.md) + 1-line summary to patterns section above.
4. Memory: only for cross-experiment patterns + user preferences + conventions. Not per-experiment status.
