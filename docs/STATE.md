# Project State

**Where are we now, and what's been done.** Index of every experiment with verdict + headline numbers — **truth is in the linked thesis docs**, keep entries terse.
Lessons → [RESEARCH_NOTES.md](RESEARCH_NOTES.md). Rejects → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md). Live-book posture → [BOOK_PLAN.md](BOOK_PLAN.md).

- **Live** = MT5 VPS only (private)
- **Tradeability**: datalake M5 ⇒ broker-confirmed; D1-only ⇒ verify via `scripts/mt5_fetch.py --list-symbols`.

---

## Snapshot (2026-05-29)

| Status | Count | Names |
|---|---|---|
| Live (MT5 VPS) | **9** | one book, per-strategy detail private (`experiments/_live/`, `live_tracking/`); posture → [BOOK_PLAN.md](BOOK_PLAN.md). |
| Validated, blocked at broker | 3 | `treasury_trend` (no bonds), `softs_ensemble` (Eightcap subset fails), `pead_midcap` (CFD-swap-cost) |
| Keep-for-reference | 3 | `tsmom`, `btc_trend`, `btc_intraday` |
| Portfolio overlay — PASS | 1 | `portfolio_risk_parity` (quarterly sizing review) |
| Diagnostic (no deploy path) | 2 | `regime_hurst_diagnostic` (MARGINAL); `regime_classifier_diagnostic` (queued ~2027) |
| Institutional-only | 3 | `fx_session`, `xag_session`, `xpt_session` |
| Rejected | 92 | → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) |
| **Total** | **111** | |

---

## LIVE BOOK

**9 strategies live on MT5 VPS** as of 2026-06-01 (`holiday_calendar` deployed 2026-05-28; `ndx_trend_day` tail-convex overlay deployed 2026-05-29; `global_settlement_short` settlement-flow basket live-confirmed 2026-05-30 at EA-default flat 0.50%/leg, first fires 2026-06-12 SQ / 06-19 witch). Per-strategy thesis, mechanism, instrument, params, sizing, and live tracking are deliberately **not** in this committed doc, they live in `experiments/_live/<name>/`, `live_tracking/<name>.md`, and `deploy/` (all gitignored). **The book is the unit that matters here, not the legs.** Book-level posture, sizing tiers, validation gates, and expected results → [BOOK_PLAN.md](BOOK_PLAN.md).

---

## VALIDATED — BROKER ACCESS REQUIRED

### [treasury_trend](../experiments/treasury_trend/treasury_trend.md) — VALIDATED_NO_DEPLOY
- IEF (Tiingo D1, 24y) | Sh 0.67 / holdout 0.42 / MDD -8.1% | 77 trades (7/yr). MH TSMOM, ~0 corr vs equities. All 7 phases PASS
- **Blocker**: Eightcap has no US Treasury CFDs (confirmed 2026-05-13)

### [softs_ensemble](../experiments/softs_ensemble/softs_ensemble.md) — VALIDATED_NO_DEPLOY
- 6 softs (Yahoo continuous) | Sh 0.85 / holdout 1.44 / MDD -13.3%. EW MH-TSMOM ensemble. Phases 2-7 PASS
- **Blocker**: Eightcap D1 depth too short to validate; and the tradeable + swap-survivable subset (COCOA+COFFEE only — cotton/corn swap-dead ~17%/yr, soybean/cattle not offered) is a one-window-wonder (Sh +0.59, 82% in 2023-26 bull, null-gap +0.24). REJECT for Eightcap 2026-05-29; 6-name research unchanged. Lesson #86

### [pead_midcap](../experiments/pead_midcap/pead_midcap.md) — VALIDATED_BLOCKED_AT_COST (2026-05-24)
- 168-name non-Mag7 universe | per-event PEAD (MIN_SUE=5%, HOLD=20d, 10bp comm): Sh +0.76 / concurrent-MDD -24.8% / 1663 events / dir-gap +1.71 / 3/3 regimes positive. All 4 Phase-2 kill criteria PASS
- **Blocker**: 20-day-hold CFD swap (~110bp RT) eats >50% of gross → live Sh ~0. NOT a research failure (pre-commit omitted CFD swap). Deployable on cash equities (IBKR); short-hold variants don't survive compression. Lesson #59

---

## KEEP-FOR-REFERENCE

### [btc_trend](../experiments/btc_trend/btc_trend.md) — KEEP_FOR_REFERENCE
- BTCUSD D1 | Sh 0.83 / real-OOS -0.32 / walk-fwd mean OOS 0.54. MH TSMOM + ATR pyramid. Failure modes: parabola-V + institutionalization decay. closed 2026-05-13 (lesson #29)

### [tsmom](../experiments/tsmom/tsmom.md) — KEEP_FOR_REFERENCE
- 24-instr long-only | Sh 0.40 / holdout 1.14 / MDD -15.5%. Classical 12-1 TSMOM. Mechanically valid but +0.69 corr with xs_momentum → no diversification value

### [btc_intraday](../experiments/btc_intraday/btc_intraday.md) — MARGINAL
- BTCUSD H1 | Sh 0.72 / W4 0.83 / **W4-26 -2.71 (n=20) FAIL**. Hour-00 UTC drift + z-filter, 2h hold. 3/7 kill PASS. closed 2026-05-16; tombstone-or-revisit on 2026Q2-Q3 OOS

---

## PORTFOLIO OVERLAYS

### `portfolio_risk_parity` — PASS (re-audit 2026-05-29, post-tz-fix 11-comp book incl. ndx_trend_day)
- Inv-vol sizing overlay (corrected 2026-05-30 window audit; prior +0.97→+1.14 was on stale cash windows for orb/lunch/xau): EQ Sh **+1.75** → **RP +1.99** (lift +0.24); MDD -1.43% → -0.76%; 4/4 regimes positive. Deploy as **quarterly sizing review** (sparse strategies capped 25%; ndx_trend_day high-vol → inv-vol weights it ~5%)
- Book-yearly w/ per-strategy sizing: total +127.96% / CAGR +27.45% / Sh +2.60 / MDD -3.69% / Calmar +7.44 (since 2023). Methodology + weights private

---

## UPDATE PROTOCOL

**On experiment close:**
1. Verdict + numbers into `experiments/<name>/<name>.md` (truth lives there).
2. 4-line entry here (active) or one row in [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) (REJECT). Graveyard failure-mode column: one sentence (≤120 chars), no bold.
3. Cross-experiment pattern → numbered lesson in [RESEARCH_NOTES.md](RESEARCH_NOTES.md) (canonical home for meta-rules; do NOT duplicate an index here).
4. Memory: only cross-experiment patterns + user prefs + conventions.

**On graduating to DEPLOYED (paper or real):**
1. Move dir into `experiments/_live/<name>/`; fix `_ROOT`/`sys.path` (+1 `os.path.dirname()`).
2. STATE.md → move entry to DEPLOYED (public-summary, no private params); bump Live count.
3. README header counter + status paragraph + aggregate metrics (after step 6).
4. `book_review/book_yearly.py` — add `run_<name>()`, wire in, re-run tearsheet.
5. `_live/portfolio_risk_parity/portfolio_risk_parity_demo.py` — add `run_<name>()` + STRATS row; re-run audit → feeds BOOK_PLAN §2.1.
6. BOOK_PLAN §1 row, §4 Gate-0 count, §2.1 numbers (from step 5), §2.2 live-target if moved.
7. `live_tracking/<name>.md` — kill-trigger spec, starting balance, first-fire date.
8. Private deploy: `deploy/mq5/<name>.mq5` (or `.../Services/`), magic registration, hedging + margin check.
9. Memory only if the deploy surfaces a new methodological rule.

Cadence: the research-side audit (step 5) re-runs every graduation; the live-side sizing review stays quarterly per BOOK_PLAN §5.
