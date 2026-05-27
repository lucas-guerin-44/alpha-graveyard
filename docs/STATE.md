# Project State

Index of every experiment with verdict + headline numbers. Truth is in the linked thesis docs.
Lessons → [RESEARCH_NOTES.md](RESEARCH_NOTES.md). Rejects → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md). Live-book posture (expected results, sizing tiers, gates, cadence, candid fears) → [BOOK_PLAN.md](BOOK_PLAN.md).

- **Live** = MT5 VPS only (private). QC retired 2026-05.
- **Tradeability**: datalake M5 ⇒ broker-confirmed; D1-only ⇒ verify via `scripts/mt5_fetch.py --list-symbols`.
- **Datalake**: private; configured via `DATALAKE_URL` / `DATALAKE_API_KEY` env vars. Endpoints: `/catalog`, `/instruments/<symbol>`, `/query`.

---

## Snapshot (2026-05-27)

| Status | Count | Names |
|---|---|---|
| Live (MT5 VPS, paper) | 7 + 1 watchlist | `orb_dax`, `lunch_fade`, `xau_session`, `event_calendar`, `xau_br_m15`, `xau_br_h1`, `quarter_end_xau_short` (strict-PASS deploys) + **`pre_boj_drift`** (watchlist-paper-deploy, half-size, C2/C5 must clear by 2026-12-18 or revert) |
| Retired from live | 1 | `xs_momentum` |
| Validated, blocked at broker | 3 | `treasury_trend` (no bonds), `softs_ensemble` (D1 depth too short), `pead_midcap` (research-PASS Sh +0.76 / 3-of-3 regimes / dir-gap +1.71, but **20d hold × CFD swap ~110bp RT eats >half of 100-200bp gross** — deployable on cash equities, not on CFD book) |
| Keep-for-reference / watch-list | 3 | `tsmom`, `btc_trend`, `btc_intraday` |
| Pending Phase 2 | 0 | (none — `gold_trend` REJECTED 2026-05-27) |
| Watch-list | 0 | |
| **Portfolio overlay — PASS** | 1 | **`portfolio_risk_parity` (inv-vol sizing across 10 components; re-audited 2026-05-27 with `quarter_end_xau_short` as 10th, sparse-cap policy tightened to 25% — book Sh **+2.19 EQ → +2.57 RP** (+0.37 lift), 4/4 regimes positive; deploy = static quarterly EA sizing review)** |
| Diagnostic studies (no deploy path) | 2 | `regime_hurst_diagnostic` (MARGINAL — TSMOM-side only); **`regime_classifier_diagnostic`** (methodology validated, 2 v2 Phase 2 attempts REJECT-marginal at current n; queued for ~2027-2028 re-evaluation when sample sizes grow) |
| Institutional-only | 3 | `fx_session` (retail RT cost eats edge); `xag_session` (Eightcap XAG 8bp spread eats Variant C gross); `xpt_session` (Eightcap XPT Asia 23bp spread; killed without Phase 2 — cost ceiling decisive) |
| Rejected | 66 | → [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) |
| Deploy-paper ready (Phase 2-3 PASS) | 0 | |
| **Total** | **85** | |

---

## DEPLOYED (MT5 VPS — full thesis, params, EA, and sizing are private)

Each entry below shows research-level metrics and the deploy date; mechanism is summarised at the *type* level. Exact parameters, sizing, EA file, and live tracking are kept private to preserve the edge.

### `orb_dax` — DEPLOYED_PAPER
- GER40 H1 | Sh +0.76 / holdout +0.93 / MDD -7.8% / dir-gap +1.04 | 1440 trades (197/yr)
- Mechanism: Xetra opening-range breakout family, LONG-only
- 3/3 regimes positive; cost headroom > 1pt RT
- deployed 2026-04-22

### `lunch_fade` — DEPLOYED_PAPER
- NDX100 M5 | Sh +1.02 / holdout +1.51 / MDD -4.2% / dir-gap +1.87 | 117 trades (16/yr LONG)
- Mechanism: lunch-vacuum fade of NY-AM directional impulse
- 3/3 regimes positive, holdout BEST; very cost-insensitive
- deployed 2026-05-13

### `xau_session` — DEPLOYED_PAPER
- XAUUSD H1 | Sh +0.79 / W4 binding +1.23 / MDD -3.7% / dir-gap +2.28 | 321 trades (39/yr)
- Mechanism: Asian-session-handoff variant with conditional prior-NY filter
- Phases 2-7 all PASS in one session; control-hold confirms session-specific
- deployed 2026-05-16

### `event_calendar` — DEPLOYED_PAPER
- NDX100 H1 | 4-event book (FOMC, CPI, RS, NFP) | ~44 trades/yr | MDD -8.65%
- Per-event research Sh range: +0.37 to +1.22; direction conditional (LONG/SHORT) per event family
- Single multi-event EA; FOMC live 2026-05-22; CPI/RS/NFP paper-enabled 2026-05-24
- XAU cross-asset extension REJECTED 2026-05-25 (lesson #62)

### `xau_break_retest_m15` — DEPLOYED_PAPER
- XAUUSD M15 NY-AM session | BoS+retest **FADE** | Sh +1.49 / W1 +1.50 / W2 +1.70 / W3 +1.36 | MDD -2.17% | 753 trades (95/yr)
- Mechanism: MM re-anchoring at broken levels + absence of NY-AM directional drift on XAU
- All 11/11 Phase 2 + 4/4 Phase 3 controls PASS; real-tick spread audit PASS (n=47,941)
- deployed 2026-05-25

### `xau_break_retest_h1` — DEPLOYED_PAPER
- XAUUSD H1 NY 12-18 UTC | BoS+retest **FADE** | Sh +1.50 / W1 +1.21 / W2 +1.59 / W3 +1.66 | MDD -1.68% | 924 trades (119/yr)
- Mechanism: same as M15 NY-AM, at coarser TF and wider window (lesson #-15 — TF×window M-shape; H1 12-18 is the local maximum)
- 6/6 Phase 3 controls PASS; corr +0.12 vs M15 sibling → co-deploy as separate EA (hedging account, separate magic number)
- deployed 2026-05-26

### `quarter_end_xau_short` — DEPLOYED_PAPER
- XAUUSD M5 SHORT, 14-16 ET last biz day of Mar/Jun/Sep/Dec | Sh +1.14 / W1 +0.89 / W2 +2.96 / W3 +1.19 | MDD -0.30% | 27 events (4/yr)
- Mechanism: quarter-end institutional rebalancing (pension/SWF) — XAU is the marginal safe-haven sell in 14-16 ET deepest-liquidity hour
- 12/12 Phase 2 + Phase 5 broker-spread audit PASS (p95 0.72bp = T-7d control); first deploy from `structural_flow_audit` pipeline
- deployed 2026-05-27

### `pre_boj_drift` — DEPLOYED_PAPER (WATCHLIST, half-size)
- USDJPY M5 LONG, 24h pre-BoJ MPM | Sh +0.51 (full) / W4 +1.55 (n=19) | MDD -2.35% | 29 events (8/yr); Phase 3 STRONG MARGINAL (3/4 binding PASS, C2 bootstrap FAIL by 0.01 = sample-size)
- Mechanism: carry-position-maintain into modal-non-event BoJ MPMs (lesson #66 / mechanism C); direction LONG = OPPOSITE user's SHORT carry-unwind prior
- **Watchlist-deploy at half-size (0.25% risk)** — auto-reverts if C2/C5 don't clear by n=22-23 (2026-12-18 hard deadline); rolling-3 OOS Sh < 0 kill trigger; precedent-creating Phase 3 MARGINAL paper-deploy
- deployed 2026-05-27; first fire 2026-06-17

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

### [pead_midcap](../experiments/pead_midcap/pead_midcap.md) — VALIDATED_BLOCKED_AT_COST (2026-05-24)
- 168-name Eightcap non-Mag7 NAS+NYS universe | D1 bars MT5-fetched, 13,541 yfinance earnings events
- Per-event PEAD (drift, MIN_SUE=5%, HOLD=20d, commission=10bp): Sh **+0.76** / concurrent-MDD **-24.76%** (marginal) / 1663 events 11.2y / WR 53.6% / PF 1.24
- All 4 Phase 2 commission-only kill criteria PASS; dir-gap **+1.71** (decisive); 3/3 regimes positive incl. holdout +0.77; cost-insensitive to 30bp commission
- HOLD sweep monotonic: 20d Sh +0.76 → 60d Sh +1.05; MIN_SUE peak 5%; XS-decile basket REJECTS (tails don't drift; deploy form = per-event book NOT XS)
- **Blocker**: 20-day-hold CFD swap cost. Eightcap (and all CFD brokers) charge ~7% annualized financing on long stock-CFDs = **~55bp per side per 20d hold = ~110bp RT** on long-short basket. Per-event gross 100-200bp → swap eats >50% → live Sharpe ~0 or negative on CFD execution. NOT a research failure; the pre-commit cost model omitted CFD swap (which is unique to CFDs and doesn't appear in equity-cash backtests).
- Deployable shapes elsewhere: (a) cash equities (IBKR margin, prime brokerage) where 20d holds have negligible carry — viable at any AUM > $250k; (b) shorter-hold variants (HOLD ≤ 3 days) on CFD if Sharpe holds — backtest sweep showed HOLD=1d Sh +0.15, HOLD=5d Sh +0.01 — does NOT survive short-hold compression; the multi-day drift IS the signal.
- See [RESEARCH_NOTES.md lesson #59](RESEARCH_NOTES.md) for the CFD-swap-ceiling Phase 0 gate now required on all multi-day-hold CFD theses.

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

### [pre_boj_drift](../experiments/pre_boj_drift/pre_boj_drift.md) — WATCH-LIST (Phase 3 strong MARGINAL, 2026-05-26)
- USDJPY M5 24h pre-BoJ MPM | Phase 2 W4 Sh +1.55 (n=19) / MDD -2.35% / 9/9 Phase 2 pre-commits PASS
- Phase 3 binding: C1 modal-outcome PASS (no-action n=16 Sh +2.75 vs policy-shift n=3 Sh -1.90, **Δ +4.65 Sh**) | C3 Deflated Sh +0.75 PASS | C4 SPX shadow ruled out (SPX t=-0.17, USDJPY-SPX corr -0.16) PASS | **C2 bootstrap Sh lower-95 +0.29 FAILS by 0.01** (sample-size, not signal-quality)
- Mechanism (#66 / mechanism C): carry-position-maintain through modal-non-event BoJ MPMs; direction LONG USDJPY refutes user's SHORT carry-unwind prior (3rd consecutive #54 win)
- **Cleanest mechanism-classification result in recent macro book** — C1+C4 decisively distinguish FX-independent flow from DXY-equity shadow (mechanism C vs B)
- **Revisit trigger**: re-run Phase 3 after each new BoJ MPM (next 2026-06-17). At n=22-23 W4 the bootstrap CI tightens enough to clear C2; if mechanism direction holds in next 3-4 events, promote to deploy with kill-trigger (rolling-3-event live OOS Sh < 0).

### [regime_hurst_diagnostic](../experiments/regime_hurst_diagnostic/regime_hurst_diagnostic.md) — MARGINAL (asymmetric, 2026-05-23)
- 8 D1 instruments (SPX/NDX/GER/BTC/ETH/XAU/USO/EUR) | rolling 252d DFA Hurst
- TSMOM-side PASS: 6/8 full-sample, 3/5 W4-eligible post-2023 (Δ Sharpe ≥ +0.30 in H>0.55 vs H<0.45)
- MR-side FAIL: 4/8 full-sample, **0/5 post-2023** — same 0DTE-MR-kill that took down opex_pin_fade / earnings_continuation_mag7 / eth_btc_ratio_mr
- Hurst-as-MR-gate now tombstoned at universe level (corroborates lesson #43)
- Follow-up `tsmom_hurst_gated` ran 2026-05-23 → REJECT (gate redundant with 12-1 signal at portfolio level; null-check failed)
- Combined verdict: Hurst-overlay family fully tombstoned for the existing repo's momentum-family strategies

---

## DEPLOY CANDIDATES (Phase 2 PASS, pending Phase 7-8 build)

(none currently — `quarter_end_xau_short` graduated to DEPLOYED 2026-05-27)

---

## PORTFOLIO OVERLAYS

### `portfolio_risk_parity` — PHASE 2 PASS (2026-05-24)
- Inv-vol sizing overlay across the deployed book
- Research: book Sh **+1.71 EQ → +1.92 RP (lift +0.21)** | MDD essentially flat | **3/4 regimes positive incl. holdout**
- Key insight: dynamic monthly rebal contributes ~0; static inv-vol gives the entire lift (sparse-event strategies fall back to full-sample vol). Deploy as **quarterly sizing review**, not pipelined rebal.
- Re-audit 2026-05-25 (8th component `xau_br_m15`): book Sh +2.33 RP, MDD -0.75% audit notional
- Re-audit 2026-05-26 (9th component `xau_br_h1`): book Sh +2.16 EQ → +2.67 RP (+0.51 lift), MDD -1.10% EQ / -0.60% RP, 4/4 regimes positive (W1 +2.82 / W2 +1.74 / W3 +3.82 / W4 +2.48), max pairwise corr +0.12 (m15↔h1)
- Re-audit **2026-05-27 (10th component `quarter_end_xau_short`)**: initial run at 35% global cap showed book Sh +2.19 EQ → +2.60 RP / MDD -0.54% RP / QEXS allocated 34.7% mean weight. Cap-policy revisit applied same day — sparse strategies (cadence < 12/yr) now capped at **25%** instead of 35% as insurance against inv-vol over-trusting sparse low-realized-variance signal. Post-revisit: book Sh **+2.19 EQ → +2.57 RP (+0.37 lift)**, MDD -0.99% EQ / -0.63% RP, 4/4 regimes positive (W1 +2.58 / W2 +1.67 / W3 +3.85 / W4 +2.37). Research-side cost of cap revisit is small (−0.03 RP Sh / −0.09pp MDD); paid premium for live-failure-mode protection on sparse components.
- Detailed methodology + weights + implementation: private

---

## CROSS-EXPERIMENT PATTERNS

Findings that emerged from multiple experiments and now constrain what's worth proposing. Full detail in [RESEARCH_NOTES.md](RESEARCH_NOTES.md).

-21. **Single-instrument TSMOM on retail-CFD post-2014 samples needs B&H benchmark + direction null-check as Phase 0 gates — kill criteria alone hide passive-beta-with-extra-steps (2026-05-27).** `gold_trend` REJECT decisive (full thesis [here](../experiments/gold_trend/gold_trend.md)). MH 12-1 TSMOM on XAUUSD D1 2015-2026 (5bp/side, 15% vol target, 1M/3M/12M lookbacks averaged, optional ATR pyramid). All 4 numeric kill criteria PASS technically on best variant (Sh +0.80 / MDD −16.5% / 85 trades / +127%) but the two pre-committed fail conditions both trip and the canonical null fails: (a) Sh +0.80 < XAU B&H +0.85 → strategy underperforms passive on a 62%-long-bias vol-targeted approach; (b) 2023-2026 holdout Sh +1.59 vs other 4 windows −0.14/+0.10/+0.46/−0.21 → 100% of alpha from one regime; (c) inverted-signal LO Sh +0.54 full-sample positive in 4-of-5 regimes (including 2015-17 at +1.44, 2022 at +0.89 where MH-LO is negative) → null-gap only +0.21, below +0.30 convention threshold; (d) L/S Sh +0.45 ≪ L-only +0.75 → short side LOSES money cleanly, signal has no negative-direction skill. Mechanism interpretation: TSMOM literature (MOP 2012, HOP 2017) holds on 30-200y futures samples; the post-2014 retail-tradeable sample is dominated by one bull regime and produces passive-beta-with-extra-steps. Adds nothing to the deployed 24-instrument `tsmom` basket (which already includes XAU and benefits from cross-asset diversification). **Operational rule (Phase 0 gate, binding)**: for any future single-instrument-TSMOM thesis on a retail-CFD sample under 15 years, pre-commit BOTH (i) "Sh > buy-and-hold of same instrument over same window" AND (ii) "Sh − inverted-signal-LO Sh > +0.30" as kill criteria, BEFORE running the Phase 2 simulator. Full-sample Sharpe is uninformative on a long-bias single-asset strategy when the asset has strong unconditional drift — what you actually measure is "is the signal better than random sign for going long this drift," not "does the signal predict returns." Companion to lesson #29 (walk-forward replaces single-split for TSMOM): even walk-forward PASS is insufficient without B&H + null-check on retail-CFD single-instrument samples. See lesson #73.

-20. **Structural-flow calendar audit IS a productive idea-source — first deploy candidate from the methodology lands at Phase 2 12/12 PASS (2026-05-27).** Live-book origin audit (2026-05-27) showed 58% literature / 33% external-agent / 17% discretionary / **0% structural-or-enumeration-derived** deploys, with structural-first identified as the deepest untapped well. The first audit run ([`structural_flow_audit`](../experiments/structural_flow_audit/structural_flow_audit.py)) screened 17 (event × instrument × intraday-window) cells from forced-flow calendar mechanisms (JPM collar, month-end FX fix, VIX SOQ, OPEX day-after, triple-witch close, month-end USD funding squeeze, quarter-end last 2h) on 6 retail-tradeable Eightcap instruments. **One STRONG cell surfaced — `quarter_end_xau_short` (XAU SHORT 14-16 ET last biz day of Mar/Jun/Sep/Dec, t=−3.28 / null-gap −13.32 bps / n=27)** plus 3 WEAK cells worth refinement and 13 REJECTs (pre-tombstoning candidate theses that would otherwise have absorbed cycles). Phase 0+ diagnostics (regime breakdown + direction null + corr-tombstone vs deployed `xau_br_h1`) all PASSED. Phase 2 simulator delivered **12/12 pre-committed kill criteria** (net +11.83 bp/event, ann-Sh +1.14, MDD −0.30%, bootstrap CI [+4.77, +20.11], deflated-Sh +0.68 selection-bias-adjusted). Mechanism: quarter-end pension/SWF/insurance institutional rebalancing forces XAU SHORT-side flow as the marginal safe-haven sell when equity-overweight portfolios rebalance back to target weights; 14-16 ET concentrates spot XAU institutional liquidity (London PM + NY peak overlap). **Operational lesson for idea-source pipeline**: (a) the structural-flow audit takes ~1 day to build and surfaces deploy-grade candidates at ~6% strict-hit rate (1 STRONG of 17) and ~25% worth-investigating rate (1 STRONG + 3 WEAK of 17) — competitive with literature mining; (b) the screen pre-tombstones REJECT cells, saving cycles on candidates the user would otherwise have manually proposed; (c) the screen + Phase 0+ + Phase 2 pipeline produces the same kill-criteria discipline as literature-derived strategies, no methodology compromise. **Project-level lesson**: the deploy book's source-distribution is now actionable evidence — when literature is over-represented (58%) and structural is 0%, run a structural audit; when audit produces ~1 PASS per ~17 cells, the methodology is positive-EV per hour. **Forward priority**: re-run the screen quarterly with widened universe (multi-day mechanisms like Japan FYE, tax-loss harvesting; PBOC/ECB calendar events once external-calendar sources are integrated) — each quarter we should expect ~1 candidate worth Phase 2 thesis lock. **Methodological side-finding**: the screen's `COST_FLOOR_BPS` dict had a 10× scaling error on indices and XAU (e.g. XAU set at 7 bp when actual is 0.7 bp); the bug made the screen STRICTER than intended, so no false positives, but several REJECTs may surface on rerun with corrected costs. Fix scheduled.

-19. **"Institutional-absence" framing tombstoned a second time — absence-of-arb does not predict absence-of-alternative-flow, and the flow that fills the gap may have W2/W3-sign-inversion shape (2026-05-26).** `retail_overshoot_fade` REJECT (7/9 binding fail) on 7-name retail-concentrated single-name CFD basket (TSLA NVDA PLTR COIN MSTR HOOD RDDT after Phase 0 dropped 5/12 not-on-broker; FADE on 5%/1h spike, 2-day hold, 5% stop). Second deliberate application of the "chase mechanisms institutional capital structurally cannot/will-not access" reframing after `cfd_wed_rollover_eurusd` (lesson #-18, capacity-moat ≠ edge). **Headline finding is the W2→W3 sign-inversion**: 2021-2022 vol regime Sh **+1.30** (MDD -23%, near deploy bar) and 2023-2026 holdout Sh **-1.07** (MDD -69%). Direction null-check FAILS cleanly: FADE -0.26 vs CONT -0.16, gap -0.10 (no directional content remains). Cost-zero gross Sh **+0.00** — signal-absent per lesson #26 diagnostic, NOT friction-eaten. WF 3/3 OOS negative (mean -1.37). MDD -71% catastrophic at basket level (red flag #3 fired exactly as written: COIN/MSTR move together on BTC, PLTR/RDDT on sentiment cycles). HOLD_DAYS=5 outperforms HOLD_DAYS=2 (+0.14 vs -0.24) — consistent with TikTok-era retail-attention half-life extending past the 1-3d window (red flag #6). **Mechanistic interpretation extending lesson #-18**: the institutional-absence framing identifies *who is NOT in the window*, not *what flow IS in the window*. In 2021-2022 the void was filled by retail-flow-exhaustion (the thesis's binding mechanism, and W2 Sh +1.30 confirms it existed). In 2023-2026 the void is filled by *something else* — 0DTE-gamma desks, prop CFD MMs, long-vol ETF rebalancing — and that fill produces zero-directional-content noise around random spikes. Capacity-moat / institutional-inaccessibility is necessary but not sufficient; the binding additional question is "what fills the absence, and is that flow persistent across regimes?" **Operational rule (tightened)**: future institutional-absence theses must pre-specify a diagnostic distinguishing **absence-with-MR-flow** (deployable, e.g. `lunch_fade`'s cash/futures basis-arb fill), **absence-with-momentum-flow** (deployable inverse direction), and **absence-with-no-persistent-flow** (un-deployable noise — this experiment in W3). Without that pre-specification, the framing is a research-priority filter, not a Phase 2 entry ticket. **Pairs with #-18 (cfd_wed_rollover_eurusd, magnitude-failure) and #-15 (lunch_fade is NDX/NQ-arb-specific)** — together they bound three sub-failures of institutional-absence theses: (a) magnitude-below-cost-bar even at zero arb pressure, (b) mechanism-by-analogy-fails at the price-impact-channel level, (c) **regime-dependent fill-flow that worked in W2 and inverted in W3 to no-directional-content (this experiment)**. **Project-level lesson reinforced**: do NOT deploy from a single-regime PASS. Quoted standalone the W2 +1.30 looks like a deploy-bar clear; the W3 -1.07 and the cost-zero gross +0.00 reveal it is not. The 3-window regime split (CLAUDE.md convention) prevents the deploy mistake. Methodological win: HOLD_DAYS sweep also yields a falsifiable forward prediction — if retail-attention half-life *is* extending in the TikTok regime, the next institutional-absence single-name thesis should pre-commit on a 5-10d hold window with cost-budget pre-calibrated to extended-swap; pre-committing on the thesis's 1-3d window will reproduce this REJECT.

-18. **Capacity-moat / "institutionally invisible" framing is a deploy-prerequisite, NOT a deploy-predictor — capacity moat ≠ edge (2026-05-26).** `cfd_wed_rollover_eurusd` REJECT (3/10 binding, full Sh -0.04, W3 sign-flipped to -1.16 bps, u-shaped rate-diff tercile). Second deliberate application of the "chase mechanisms institutional capital structurally cannot access" reframing (after deployed `lunch_fade`). Thesis was retail-CFD Wednesday triple-swap unwind on EURUSD — venue truly is microstructurally walled off from spot/futures/PB FX (capacity-moat clause VALID), but full-sample gross was only +0.58 bps vs the +3-12 bps Phase-1 prior. Lesson: institutional-inaccessibility means no entity exists that *could* arb the mechanism — it does NOT imply the mechanism exists at detectable magnitude. `lunch_fade` works because BOTH (a) the venue is walled AND (b) the cash/futures basis-arb produces detectable M5-scale reversion; this experiment validated (a) and assumed (b). **Operational rule**: future "institutionally invisible" theses must independently argue the mechanism produces detectable price impact, with the bar set by Phase 2 gross > 3-5× venue spread, not by mechanistic plausibility alone. Failure to clear the gross-magnitude prior in Phase 1 reasoning (we predicted +3-12 bps; observed +0.58 bps) is the gating signal — capacity-moat by itself is necessary, not sufficient. Pairs with #-15 (lunch-fade is NDX/NQ-arb-specific, not generic basis-arb): both establish that mechanism-by-analogy expansions need direct empirical validation of the price-impact channel, not the structural-access argument alone. Secondary sub-finding: third 2026-05 instance of retail-positioning-direction-on-EURUSD being wrong-signed in W3 (after #-16 ×2) — "retail is structurally long EURUSD" is now data-refuted three times in the post-2022 rate-divergence regime.

-17. **Lesson #-16 (DXY-mechanical-mirror) confirmed across PASS-primary AND FAIL-primary equity vessels (2026-05-26).** `pre_ecb_drift_eurusd` REJECT tests the FX-mirror prediction on an event whose *primary equity vessel had already FAILED* (`pre_ecb_drift` GER40, REJECTED 2026-05-23, W3 mean −0.159% / Sh −0.50). DXY-mirror prediction: EURUSD W3 ≈ −ρ(DXY, DAX) × GER40-W3-drift = opposite sign, similar order of magnitude, decay-first. Observed: EURUSD W3 mean **+0.213% (Sh +1.14)** — opposite sign of GER40 W3, similar magnitude; W4 collapses to mean −0.063% (Sh −0.46, cutting cycle inverts) ahead of GER40 W4 (mean +0.023%, Sh +0.09). Same FX-mirror-decays-first pattern as `pre_fomc_drift` (where primary NDX×FOMC PASSED). **Lesson #-16 is now a two-confirmation structural pattern, not a single-experiment hypothesis.** Operational consequence (tightened): FX-side legs of *any* event×index pair — PASS-primary or FAIL-primary — are pre-tombstoned by mechanism inheritance. The mirror is mechanical, the magnitude is shadow-of-primary, the W4 decay crosses zero on the smaller FX vessel. Pre-CPI / pre-RS / pre-NFP FX-side legs (already pre-tombstoned by #-16) plus pre-BOE on GBPUSD / pre-BOJ on USDJPY (newly pre-tombstoned by #-17's stronger frame): do not spin up. The clean transplant primitive (per #-15) remains same-instrument-family, different-TF-on-the-window-that-peaks-at-that-TF. Methodologically, this experiment also validates the "test the lesson on its other case" disciplined-falsification move: a single-experiment lesson should be cross-validated on the inverse case (primary-pass vs primary-fail) before being treated as a structural rule.


-17. **FX has independent pre-CB-event flow only when (a) no equity primary mechanism is in the way to shadow AND (b) the event's modal outcome is a non-event — direction is carry-position-MAINTAIN, NOT carry-unwind (2026-05-26; Phase 3 corroborated same day).** `pre_boj_drift` (USDJPY 24h pre-BoJ MPM, n=29 events 2022-10→2026-04 — the cleanest available no-equity-primary CB test). Phase 2: 9/9 binding pre-commits PASS (W4 Sh +1.55 on n=19, null-gap +1.15 Sh, walk-forward W4-OOS +1.55, MDD -2.35%, cost-robust to 2bp). **Phase 3 (same day): 3/4 binding PASS — STRONG MARGINAL, watch-list, sample-size-limited not mechanism-limited.** Decisive: **C1 modal-outcome partition** Sh +2.75 (no-action n=16) vs -1.90 (policy-shift n=3) = +4.65 Sh delta; **C4 cross-asset shadow ruled out** (SPX W4 mean -0.04% t=-0.17, USDJPY-SPX corr -0.16 — mechanism C cleanly distinguished from mechanism B); **C3 deflated Sh +0.75** survives 20-cell sweep deflation. **C2 bootstrap Sh lower-95 +0.29 FAILS by 0.01** — small-sample (n=19), resolves at n=22-23 after 3-4 more events. **Direction is LONG USDJPY = OPPOSITE the user's SHORT-prior (carry-unwind hypothesis)** — third consecutive macro-event-FX experiment where the user's directional intuition was wrong-signed and lesson #54 was the load-bearing safeguard (after `pre_fomc_drift` and `pre_ecb_drift_eurusd`). Mechanism: speculators *maintain* JPY-funded carry positions through the 24h pre-window of modal-non-event BoJ meetings (W4 2024-2026 = 17 of 19 meetings non-events; 2 hawkish surprises 2024-07-31 / 2025-01-24 are net-negative contributors the strategy survives — single-event sensitivity STRENGTHENS the W4 result on dropping these). W3 2022-10→2023 is regime-conditional FAIL (mean -0.14%, Sh -0.72) because the YCC-policy-shift era had high surprise frequency — same mechanism is wrong-signed in a high-uncertainty regime. **Three-mechanism decomposition of the macro-event-drift family now**: (1) equity-primary on US-macro events (deployed `event_calendar`); (2) FX-magnitude-shadow on equity-primary events (REJECTED #-16 series — rides cross-asset mechanical correlation, decays first); (3) **FX-independent on no-primary-equity CB events** (this experiment, MARGINAL/Phase-3-candidate) — different mechanism, opposite direction prior from (2), regime-conditional on event-modal-outcome. **Operational consequence**: do NOT auto-extend this finding to pre-ECB-on-EURUSD, pre-FOMC-on-USDJPY, etc. — those have equity primaries OR mechanical-shadow paths and are already pre-tombstoned by #-16. The independent-FX-flow shape requires the specific combination (no-equity-primary AND modal-non-event), which currently identifies BoJ-on-USDJPY uniquely; SNB/CHF, Riksbank/SEK, BoC/CAD are theoretical candidates if their MPMs are modal-non-events on the relevant carry pair, but they have far smaller carry magnitude and would need their own Phase 2. **Forward-looking degradation risk**: the mechanism breaks if BoJ enters another policy-uncertainty regime (large hikes, YCC reintroduction, JPY intervention regime); deploy must include rolling-3-event OOS Sh < 0 kill-trigger as a hard pre-commit. Methodologically validates lesson #54 (pre-commit BOTH directions) for the third time in 2026-05; the user-stated SHORT-USDJPY prior was coherent (carry-unwind narrative) but data-refuted, same as #-16 and the SHORT-EURUSD-pre-FOMC prior. Pairs with #-16 — together they enumerate the three macro-event-flow mechanism families and which conditions select between them.

-16. **Secondary cross-asset vessels of an event-flow mechanism are magnitude-shadows of the primary vessel — they ride the same flow via cross-correlation, decay first, and don't deploy (2026-05-26).** `pre_fomc_drift` (EURUSD, FX-side falsification test of deployed NDX-LONG-pre-FOMC). User-posed binary: PASS ⇒ USD-risk-premium-flow leg exists ⇒ refines lesson #-13; FAIL ⇒ mechanism is equity-vessel-only ⇒ sharpens lesson #62. **Third-outcome reject** sharpens the framework more than either pre-posed answer: full-sample directional signal IS there (null-gap +0.75 Sh, placebo clean at mean -0.025% t -0.55), BUT (a) the signal points **LONG EURUSD = USD weakens pre-FOMC**, OPPOSITE the user's SHORT-prior, and (b) the W4 deploy-relevant window is dead (mean -0.0093%, Sh -0.07 on n=19) AND walk-forward third split (deploy-binding per lesson #29) is negative (OOS Sh -0.07). The LONG-EURUSD direction is the **mechanical DXY-equity negative correlation** (post-2022 dovish-pivot regime): pre-FOMC equity risk-on co-occurs with USD weakening, so the *same* equity risk-on flow shows up as a FX-mirror leg via the DXY-equity coefficient, not as an independent USD-risk-premium accumulation flow. Magnitude on FX = ρ(DXY,SPX) × primary-vessel-magnitude, which is necessarily smaller than the primary; that smaller-magnitude shadow decays first as the primary mechanism decays. macro_drift's W4 fell from Sh +2.38 (W3) to +0.41 (still deploy-viable); EURUSD's W4 fell from Sh +0.48 (W3) to -0.07 (dead). Same fractional decay; the FX leg started smaller and crossed zero. **Operational consequence**: don't propose "FX-side of <deployed equity event-drift>" extensions. Pre-CPI / pre-RetailSales FX-side legs are pre-tombstoned by mechanism inheritance from this experiment (they'd be the same DXY-mirror shadow, same direction-inverted vs user intuition, same W4-already-decayed shape). **Methodological consequence**: the user's PASS/FAIL binary was incomplete — when proposing a cross-asset extension of a deployed flow strategy, the *third* outcome ("signal exists on secondary vessel via cross-asset mechanical correlation, not via an independent flow leg") is the most-likely outcome and should be the primary pre-posed answer, with the user's PASS being the rare case of a genuinely-independent parallel flow. Pairs with #-14 / #-15 — together they bound three failed transplant axes: (a) same-instrument-different-session, (b) same-instrument-different-TF-on-wider-window, (c) different-asset-class-via-cross-asset-correlation. The clean transplant primitive remains very narrow: same instrument family, different TF where the M-shape peaks.

-15. **TF×window is a 2-D search; wider session windows only become extractable at coarser timeframes (M-shape across the TF ladder) (2026-05-26).** `xau_break_retest_h1` (H1 NY 12-18 FADE Sh +1.50, all 6 Phase 3 controls PASS, deploy-paper ready) combined with cross-TF agent finding: same FADE mechanism scored M15 13-15 UTC Sh +1.49 (deployed), **M15 12-18 UTC Sh +1.09 (WORSE than M15 13-15 — wider M15 window dilutes)**, H1 12-18 UTC Sh +1.50 (best at H1), H4 lb=4 tol=0.5 Sh +1.37. The M-shape across the TF ladder is a structural property: at M15, the extra noise from the 12-13 pre-cash and 15-18 NY-PM hours dilutes faster than the extra signal accumulates; at H1, the lower bar count makes the wider window net-additive. **Operational consequence (binding rule)**: a naive "extend the deployed M15 strategy's session window" would REGRESS production (M15 12-18 < M15 13-15 by Sh -0.40). Wider-window deploys must be done at the timeframe where the M-shape peaks, not by stretching the existing TF. **Methodological consequence**: for any future intraday-microstructure thesis, the candidate search space is 2-D (TF × window width), not 1-D — finding the local maximum requires the grid sweep, and the "best at M15" need not be the "best overall". Pairs with lesson #-14 — together they tombstone two naive transplant strategies: (a) same-instrument-same-TF-different-session (LDN-AM REJECT), (b) same-instrument-same-session-wider-TF (M15 12-18 < M15 13-15). The deploy-grade transplant is same-instrument-different-TF-on-the-window-that-peaks-at-that-TF.

-14. **Session-portability ON THE SAME INSTRUMENT is not free — intraday-microstructure edge does NOT auto-transfer across session windows (2026-05-26).** `xau_ldn_am_fade` REJECT decisive: identical M15 BoS+retest FADE simulator, identical XAU instrument, identical 0.20pt cost — only the session window moves from deployed NY-AM 13-15 UTC (Sh +1.49 / W1 +1.50 / W2 +1.70 / W3 +1.36) to LDN-AM 07-10 UTC. Result: baseline Sh −0.25 / W1 +0.10 / W2 −0.63 / W3 −0.28 / n=1048. Fade-gap stays positive (+0.44) so the *direction* of the mechanism is preserved, but absolute magnitude collapses to ~zero gross. Cost-stress @0.40pt Sh −1.23. ATR-floor variants all INSUFFICIENT_N (atr-10 FADE Sh +0.68 / n=16 / 0.9y is a post-mid-2025 vol-regime artefact). Trade-by-trade correlation vs deployed NY-AM FADE = −0.07 over 1372 shared days — confirms REJECT is signal-absence-driven, NOT redundancy-driven. **Mechanistic reasons LDN-AM kills the mechanism**: (a) `xau_session` already captures positive drift through ~08 UTC; residual drift bleeds into 07-10 UTC and punishes fade entries; (b) LME AM auction (10:30 UTC) one-way real-money flow pre-positions in the entry window; (c) the MM re-anchoring mechanism needs an *absence-of-drift* environment to clear (xau_break_retest_m15 Phase 3 C1 control shows NY-AM in-session vs off-sessions Δ Sh > +1.7), and LDN-AM does not satisfy that prerequisite. Extends lesson #-3 from cross-instrument (XAU/BTC/WTI) to cross-session-same-instrument (XAU NY-AM vs XAU LDN-AM) — the mechanism is asymmetric across BOTH axes. **New methodological rule**: before transplanting an intraday-microstructure strategy to a second session window on the same instrument, explicitly run the in-session-vs-off-sessions C1 control on the candidate window FIRST; if Δ Sh < +0.50, do not run full Phase 2. (This rule would have killed `xau_ldn_am_fade` in 10 minutes instead of 50.) Also sharpens the XAG `_xag_deep_dive.py` Test 4 framework: zero-cost gross session-screens are NOT a transplant primitive — they screen for *direction*, not deploy-grade Sharpe; transplant decisions need a positive zero-cost Sharpe in all of W1/W2/W3 as a prerequisite, which the XAG hint did not satisfy.

-13. **Scheduled US-macro LONG drift on NDX is *first-read-mid-month-mid-cycle* specific — PCE falsifies lesson #56's broad framing (2026-05-24).** `pre_pce_drift` REJECT decisive: LONG full Sh +0.07 / **W4 Sh −1.23** (vs CPI W4 Sh +1.15 on near-identical inflation info), WF 3/3 OOS NEGATIVE monotonic decay (−0.14 → −0.55 → −1.23), null-gap +0.161 (half +0.30 threshold), 6/9 binding pre-commits FAIL. **Placebo benign** (mean −0.040%, t −0.29) RULES OUT month-end structural-drift confound — rejection is PCE-specific signal failure, NOT calendar artefact. The distinguishing axes (extracted ex-post): FOMC (mid-cycle Wed, first-read) PASSES LONG; CPI (mid-month Tue/Wed/Thu, first-read inflation) PASSES LONG; Retail Sales (mid-month Wed, first-read real economy) PASSES LONG; NFP (first-Friday, first-read, Friday-microstructure exception) PASSES SHORT; **PCE (end-of-month Friday-dominated 76%, confirming-read after CPI) has NO drift either side**. Refined framework: only events that align on (a) mid-month/mid-cycle calendar position, (b) non-Friday day-of-week, AND (c) first-read information-cycle position inherit the LONG drift. Macro-event book is therefore **NOT auto-expandable** to every US-macro release — each new candidate (PPI, JOLTS, ISM, GDP, durable goods, consumer confidence) needs explicit 3-axis screening before pre-commit. **Strengthens CPI's deploy stance** (placebo benign rules out the generic-08:30-ET-weekday null). Methodological win: the canonical-test design (close-twin event as falsification test, not diversification add) generated a sharper framework refinement than three diverse extensions would have. Pairs with #-12 — together these bound the macro-event-drift family on two axes: venue-of-asset (index, not own-commodity) AND event-shape (first-read mid-month/cycle, not confirming-read end-of-month Friday). See lesson #62.

-12. **Macro-event-drift family does NOT auto-port from index-on-US-macro to commodity-on-own-fundamental (2026-05-24).** `pre_natgas_eia` REJECT decisive: 24h pre-EIA NG Storage Report on XNGUSD M5 (Eightcap CFD, 2023-2026, 177 events). LONG -0.235% / Sh -0.53 / null-gap +0.13 (below +0.30 threshold). W3 (2023 post-Ukraine collapse) drags -1.20% mean; W4 tentatively LONG (+0.179% / Sh +0.39 / WF OOS mean +0.76) but doesn't clear null-gap or full-sample pre-commits. SHORT side loses more (-0.365%). NG-CFD cost (30bp default, 50bp realistic) eats anything < +0.30% mean gross. The macro_drift / pre_cpi_drift / pre_nfp_drift family's institutional-equity-risk-premium-accumulation flow story does NOT apply when the asset is the *underlying* of the event (XNGUSD ↔ Henry-Hub storage), the print is direct fundamentals (not policy context), weather + pipeline data leak the magnitude in advance, and asymmetric bearish tail discourages pre-event LONG positioning. **Future commodity-on-own-event theses (EIA crude, USDA WASDE)** require asset-specific positioning gates (COT, weather-error, seasonal carry) — neutral prior, no equity LONG-by-default. See lesson #61.

-11. **OPEX-pin family is fully tombstoned for US equities — 0DTE has leaked to non-Mag7 single stocks (2026-05-24).** `opex_pin_singlestock` REJECT on 15-name mid/large-cap basket (LULU, COIN, MSTR, NFLX, SHOP, CRWD, NET, AVGO, ASML, MU, ROKU, DOCU, PLTR, SNOW, NOW) — Sh -1.24, BOTH directions lose (fade -1.24, cont -0.58), holdout WORST regime (Sh -1.27 on n=360), all-Friday null delta -0.06 (calendar lock NOT load-bearing), cost-zero Sh -0.33 (signal-driven loss). Mirrors `opex_pin_fade` index REJECT exactly. Premise that mid-cap names with concentrated monthly OPEX OI would preserve the pin mechanism is REFUTED — 0DTE structural-short-gamma has metastasized from Mag7 (lesson #43) to the broader high-IV single-stock universe. **Tombstone the entire OPEX-pin family for US equities, 2023-2026.** Future "options-expiry hedging flow" theses should pivot to non-US venues, different calendar events, or genuinely low-0DTE single-stock subsets (defensives/REITs/utilities — completely different population). For any future single-stock thesis, the regime filter must be an *external* 0DTE-share indicator (CBOE single-stock 0DTE OI vs total OI), not just population selection. Methodologically, the "all-X null" test (OPEX-only vs all-Friday delta) was the cleanest mechanism falsification — when a generic baseline exists for a calendar-restricted strategy, the delta is the strongest available null.

-10. **PEAD direction-inversion is Mag7-specific, NOT market-wide (2026-05-24).** `pead_midcap` PHASE 1 PASS on 168-name Eightcap non-Mag7 mid/large-cap universe: drift Sh +0.76, dir-gap +1.71 (DECISIVE drift > fade), 3/3 regimes positive INCLUDING holdout (+0.77). Refutes the concern that lesson #43's "post-2022 fade-direction inversion on Mag7" had metastasized to the broader US single-stock universe. The Mag7-specific 0DTE-gamma flow that flipped earnings_continuation_mag7 / earnings_fade / opex_pin_fade / opex_pin_singlestock direction stays Mag7-specific (now also extending to high-IV non-Mag7 single stocks per #-11 above, but ONLY at the intraday/options-expiry mechanism level). On the broader 168-name mid-large-cap universe at the multi-day PEAD horizon, classical Bernard-Thomas drift direction is preserved. Operational implication: the deployable PEAD universe is non-Mag7 (Mag7 quarantined to regime-conditional path per `earnings_continuation_mag7`); strategy form is per-event (NOT cross-sectional decile — tails don't drift). Methodologically, `pead_midcap` introduces the **concurrent-position equity curve** as the proper MDD diagnostic for multi-day-hold overlapping strategies: entry-day-aggregated curve overstates MDD by 3-4× because it ignores diversification across concurrent positions. Apply this to any future strategy with HOLD ≥ 10 days.

-9. **Hurst-regime classifier is asymmetric: useful for TSMOM, dead for MR/fade (2026-05-23).** `regime_hurst_diagnostic` 8-instrument D1 study: TSMOM Δ Sharpe in H>0.55 vs H<0.45 regime passes pre-commit (6/8 full, 3/5 post-2023 eligible); MR Δ FAILS (4/8 full, **0/5 post-2023**). The MR-side null-collapse is not a Hurst failure — it's the same post-2022 0DTE-amplification taking down MR independent of regime label (lesson #43). Operational implication: future fade/MR rescue proposals via "add a Hurst gate" are pre-tombstoned; future TSMOM-family proposals (tsmom / btc_trend / gold_trend) can legitimately consider a Hurst entry filter (next experiment: `tsmom_hurst_gated`).

-8. **Lunch-fade mechanism is INDEX-CASH-vs-FUTURES-BASIS-ARB specific, NOT basket-generalizable (2026-05-22).** single_stock_lunch_fade REJECT decisive: zero of 24 names positive, basket Sh -1.06 (cost=4bp), holdout -1.26, walk-forward 3/3 OOS negative, dir-gap -0.53 (sign-flipped vs NDX +1.87). Sharpens #27 — future "lunch fade on X" proposals require X to have a liquid cash-vs-futures basis-arb counterpart compressing during 11:30-13:30 ET local. FDAX/cash-DAX and FESX/cash-EUSTX50 are candidate next-targets. Single names, FX, niche commodities are mechanism-empty.

-7. **Mag7 single-stock earnings mechanism FLIPS SIGN at 2022/2023 boundary — direction is regime-conditional, not directional (2026-05-22).** earnings_continuation_mag7 REJECT directly tests lesson #43 pre-commit rule: full-sample fade Sh = continuation Sh = -0.18 (dir-gap -0.02), but fade holdout -1.67 vs continuation holdout +0.78 (Δ +2.45). 0DTE-ramp 2022→2024 is the inflection. earnings_fade_nonmag7 also REJECT — passes Phase 2 (Sh +0.57 / dir-gap +1.63 / both regimes positive) but FAILS walk-forward by 0.03 Sharpe (mean OOS +0.27 vs +0.30 floor); OOS Sharpe decays monotonically (+0.47 → +0.27 → +0.06) showing same 0DTE arb is bleeding non-Mag7 over time.

-6. **Single-stock earnings-fade survives on lower-0DTE-OI large-caps but is arbed on Mag7 (2026-05-22).** earnings_fade REJECT on 24-name universe (full Sh +0.37, holdout −0.22) but with dir-gap +1.35 — mechanism real, sign correct, regime-decay REJECT. Holdout sub-universe split: Mag7 Sh −1.67 / non-Mag7 Sh +0.67 (Δ +2.34). Same dealer-short-gamma flow as opex_pin_fade (#-5) but at single-stock event level. Pre-commit 0DTE-OI as universe-selection variable for any future single-stock intraday-fade thesis; pivot to `earnings_fade_nonmag7` requires fresh pre-committed kill criteria + walk-forward, NOT within-experiment refit.

-5. **Monthly-OPEX pin-fade is dead on US-index M5 post-0DTE (2026-05-22).** opex_pin_fade REJECT both NDX and SPX: dir-gap −0.48/−1.33 (INVERTED), holdout worst regime on both, calendar lock anti-load-bearing. Fourth independent US-index intraday MR sign-inversion. Pre-commit *continuation* direction for any new "last-2h-of-Friday" mechanism; 0DTE structural-short-dealer-gamma flips the sign.

-4. **Sentiment intuition mirror-inverts on opening-impulse strategies (2026-05-21).** orb_dax_sentiment REJECT: pre-committed "risk-on = better breakouts" falsified; Q5 risk-on is only losing bucket (-0.0026% avg). Mirror direction has Sh +0.10 lift but null-gap only +0.10 (half of +0.20 threshold) and 2021-2022 breaks under hypothesized filter. Generic rule: discretionary "trade in calm conditions" intuition is wrong-signed on opening-impulse strategies — pre-commit the mirror form.

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

8. **Research-to-live Sharpe haircut is CONFOUND-SPECIFIC, not a generic multiplier (rewritten 2026-05-22).** Original framing ("0.30-0.60 absolute haircut") was a one-data-point overgeneralization from `xs_momentum` (QC port 0.92 → 0.35). That 0.57 gap had three separable sources — universe-swap (Yahoo ETF → MT5 CFD), cost-model differential, QC's risk-free-subtracted Sharpe formula (lesson #21). **None of those confounds apply to the current 4-strategy book** (all researched on actual Eightcap CFD data, conservative cost models, raw Sharpe both sides). **Expected haircut for current book: 10-25% relative, under 0.20 absolute** — NOT 0.30-0.60. Per lesson #5 rewrite, propagate the new framing rather than blanket-applying the old number. Mechanism decay (lessons #6, #28) and sample-size variance remain real haircut sources, but are mechanism-specific and direction-known, not a generic prior.

---

## UPDATE PROTOCOL

On experiment close:
1. Write verdict + numbers into `experiments/<name>/<name>.md` (truth lives there).
2. Add a 4-line entry here (active) or one row in [STATE_GRAVEYARD.md](STATE_GRAVEYARD.md) (REJECT). Link the name to the thesis doc. **Graveyard `load-bearing failure mode` column: one short sentence (≤ ~120 chars), no bold, no multi-clause analysis — overview only. Detail lives in the thesis doc.**
3. Cross-experiment pattern → add lesson to [RESEARCH_NOTES.md](RESEARCH_NOTES.md) + 1-line summary to patterns section above.
4. Memory: only for cross-experiment patterns + user preferences + conventions. Not per-experiment status.

On strategy graduating to DEPLOYED (Phase 8 — paper or real):
1. **Move the strategy directory into `experiments/_live/<name>/`** if it isn't already there. Fix any `_ROOT` / `sys.path` references in its `.py` files (add one more `os.path.dirname()` since the dir is now one level deeper).
2. **`docs/STATE.md`** — move the entry from `DEPLOY CANDIDATES` to `DEPLOYED`. Rewrite to the public-summary format (research metrics + mechanism + deploy date; **no** params, EA filename, sizing, or operational gating — those are private). Bump the snapshot table's `Live` count + add the short slug to the names list. Zero out the `Deploy-paper ready` row if this was the last candidate.
3. **`README.md`** — bump the header counter table (`live`); update the `## Current status` paragraph if the new strategy changes the instrument/asset-class footprint; update the aggregate book metrics table after step 6.
4. **`experiments/book_review/book_yearly.py`** — add `run_<new_name>()` and wire it into `parts = [...]` and the per-strategy contribution loop; add a sizing-base entry. Run to refresh `book_yearly.csv`, `per_strategy_yearly.csv`, and the `book_yearly.png` tearsheet.
5. **`experiments/_live/portfolio_risk_parity/portfolio_risk_parity_demo.py`** — add `run_<new_short_name>()` returning a daily-PnL series; add the slug to `STRATS`; wire into `load_all_daily()`. Re-run to refresh the 9+ component audit. The new EQ / RP / regime numbers are what go into `BOOK_PLAN.md` §2.1.
6. **`docs/BOOK_PLAN.md`** — add a row to `## 1. Current book composition`; update `## 4. Gate 0` "newest strategy" + count; **replace** `## 2.1` Sharpe / CAGR / MDD / TID / corr / regime numbers with the re-run portfolio_risk_parity outputs from step 5; bump `## 2.2`'s "live target" range if the audit Sh moved materially (e.g. ±0.20).
7. **Live tracking** — create `live_tracking/<name>.md` with the per-strategy kill-trigger spec, starting balance, and first-trade-due date. Cross-link from BOOK_PLAN's `## 7. Realism / sanity references` block.
8. **Private deploy state** — write `deploy/mq5/<name>.mq5`, register magic number, hedging-account check, margin headroom check (these are private; not committed to the public tree).
9. **Memory** — usually nothing to save (deploy state is per-strategy, not a cross-experiment lesson). Exception: if the deploy surfaces a *new* methodological rule (e.g. "co-deploy of two TFs on same instrument requires hedging-mode account and separate magic numbers"), add it to feedback memory.

Note on cadence: the *research-side audit* (step 5) gets re-run on every deploy graduation so BOOK_PLAN §2.1 reflects current book composition. The *live-side sizing review* (i.e. shifting the actual EA risk multipliers based on inv-vol weights) stays on the **quarterly cadence per BOOK_PLAN §5** — re-running the audit doesn't trigger a live sizing change mid-quarter.
