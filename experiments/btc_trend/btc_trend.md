# BTC trend following (BTCUSD MH-LO + pyramid)

**Status (2026-05-13):** RETIRED — KEEP_FOR_REFERENCE.

Phases 2-5 + 7-8 PASS clean. Phase 6 (single split) FAIL by 0.04. **Walk-forward Phase 6
(5 rolling splits) FAIL by 0.05 on mean degradation (+0.548 vs 0.5 bar).** Two of five
splits had +1.13 and +1.70 degradation — both parabola-top → V-bottom transitions
(2021→2022, 2025→2026), showing a structural TSMOM weakness rather than lottery noise.
S4 IS Sharpe +0.37 (lowest IS window) corroborates the W4 regime-decay signal.

**Verdict:** **KEEP_FOR_REFERENCE** — mechanism works on steady-trend regimes (median
degradation +0.26 passes; 4/5 splits OOS-positive; fade-gap +1.65; Phase 8 captured the
real-OOS drawdown). But the strategy is structurally vulnerable to parabola-V transitions
in a regime that is also showing institutionalization decay. Not a deploy candidate at
research-pass costs and risk budget. Thesis preserved as the negative-result reference
for TSMOM-on-crypto and as a methodological example of walk-forward catching what a
single-split Phase 6 missed.

## Phase 1 (origin)


## Origin

Pivoted from `experiments/gold_trend/` after a single-instrument scan across 26
trend-prone instruments. BTCUSD topped the scan on Sharpe (+0.93) and alpha
vs B&H (+0.27), at a 5 bps/side cost assumption. The gold experiment itself
concluded that TSMOM on XAUUSD doesn't beat buy-and-hold, but the same
mechanics flagged BTCUSD as the best single-instrument candidate in the
scanned universe.

## Mechanism

BTC has exhibited extreme regime-conditional trends:

- **Trends up:** flagship bull runs 2019-2021 and 2023-2025, driven by
  adoption cycles + halvings + macro liquidity.
- **Trends down:** 2018 and 2022 crypto winters, large multi-month drawdowns
  (-75% to -80% peak-to-trough) driven by deleveraging cascades, exchange
  failures, and regulatory shocks.

TSMOM should particularly help on the downside: buy-and-hold absorbed full
80%+ MDDs, whereas a trend-following rule goes flat during bear signals.
The scan bore this out — the edge comes almost entirely from cutting
drawdowns, not from enhanced returns.

## Why retail-accessible

- Monthly rebalance cadence, not microstructure.
- Crypto is retail-dominated; institutional TSMOM programs haven't scaled
  into this market meaningfully (compliance/custody frictions).
- BTCUSD is tradable retail via CFDs, perps, or spot — deep liquidity,
  24/7 markets, ~10 bps/side spreads typical on CFDs.

## Universe / Period

- Single instrument: **BTCUSD** (spot, D1).
- Period: **2018-01-01 → 2025-08-31** (7.7 years, 2,456 daily bars).
- Cash leg when flat: 0%.

## Signal + sizing

Inherited from gold_trend:
- **Multi-horizon** TSMOM: average of `sign(r_1M)`, `sign(r_3M)`, `sign(r_12M)`.
- **Pyramid**: K=3 units, ATR(14) × 1.0 favorable trigger per add, cap at
  full vol-target (cap = 1.00× — the path-only variant).
- **Vol-target**: 15% annualized.
- **Rebalance**: monthly (21 bars).
- **Cost**: 10 bps/side (honest BTCUSD CFD — *up from 5 bps in the scan,
  which overstated the edge*).

## Expected Sharpe range

- Scan (5 bps/side): 0.93.
- Expected at honest 10 bps/side: 0.80-0.90. If it drops below 0.70, the
  "edge" was mostly cost-subsidized.
- Institutional crypto TSMOM programs (AQR, Man): reported 0.7-1.0 Sharpe
  since 2018.

## Fail conditions (pre-committed)

1. **Sharpe ≤ 0.50 at honest 10 bps/side** → reject; effectively uninvestible.
2. **Phase 3 Deflated Sharpe p > 0.05** with n_trials_tested = 35 (scan + 
   pyramid configs): we picked the best of 26 instruments + explored 9 
   pyramid configs; must survive the cherry-picking correction.
3. **Phase 4: Sharpe positive in ≤ 2/4 windows, OR one window > 80% of return**
   → reject; regime-dependent.
4. **Phase 6: OOS Sharpe ≤ 0, OR degradation > 0.5** → reject; doesn't 
   generalize across the 2018-2021 → 2022-2025 split.
5. **Alpha vs B&H collapses (< +0.10 Sharpe)** at honest costs → reject;
   no reason to run the strategy over just buying and HODLing.

---

## Phase 2-8 results (2026-05-13)

Run config: BTCUSD D1 2018-01-01 → 2026-03-31 (2,665 bars, 8.2 years). MH-LO+pyramid baseline:
LOOKBACKS=(21,63,252), K=3 pyramid, ATR×1.0 trigger, cap=1.00x, vol-target 15% annualized,
rebal every 21 bars, cost 10 bps/side. Script: `btc_trend_validation.py`.

### Phase 2 — MVI at honest costs

| metric | value | bar | verdict |
|---|---|---|---|
| Sharpe | +0.83 | > 0.50 | PASS |
| MDD | -17.22% | < 30% | PASS |
| Trades | 88 | ≥ 50 | PASS |
| Alpha vs B&H | +0.27 | ≥ +0.10 | PASS |
| CAGR | +9.97% | — | (B&H +21.78%) |

### Phase 3 — Statistical battery (n_trials = 35)

| test | observed | bar | verdict |
|---|---|---|---|
| Bootstrap 95% CI on Sharpe | [+0.17, +1.38] | excludes 0 | PASS |
| Position-shuffle permutation (5k) | observed +0.77 vs null mean +0.02, p=0.0016 | p < 0.05 | PASS |
| Deflated Sharpe (Bailey-Lopez de Prado 2014) | DSR +0.72, p=0.0000 | p < 0.05 | PASS |

### Phase 4 — Regime stability (4 non-overlapping windows)

| window | bars | trades | ret | Sharpe | MDD |
|---|---|---|---|---|---|
| 2018-2019 (crypto winter) | 562 | 10 | +13.83% | +1.38 | -7.87% |
| 2020-2021 (bull + parabola) | 556 | 24 | +53.22% | +1.61 | -9.39% |
| 2022-2023 (bear → thaw) | 728 | 18 | +16.91% | +0.90 | -6.35% |
| 2024-2025 (post-halving) | 816 | 31 | +16.98% | +0.50 | -11.93% |

4/4 windows positive; max share 52.7% (need < 80%). **PASS.**

### Phase 5 — Parameter sensitivity

Tested 18 configs across pyramid cap (1.00/1.33/1.67/2.00x), ATR trigger (0.5/1.0/1.5/2.0),
lookback structure (5 variants), and vol-target (0.10/0.12/0.15/0.20/0.25). **Zero negative
configs.** Sharpe range [+0.74, +0.83]. **PASS** — extremely flat plateau, no peak-finding.

### Phase 6 — True holdout (IS 2018-2021, OOS 2022-2025)

| split | years | trades | CAGR | Sharpe | MDD |
|---|---|---|---|---|---|
| IS 2018-2021 | 4.0 | 35 | +12.23% | +1.28 | -17.22% |
| OOS 2022-2025 | 4.2 | 49 | +9.08% | +0.74 | -12.07% |

Degradation +0.536 — **FAIL by 0.04** (threshold +0.5). OOS Sharpe +0.74 is well above
the +0.50 standalone bar from Phase 2, but the IS was unusually strong because 2018-2021
contains both a clean bear (2018) and a clean parabola (2020-2021) — exactly the regimes
MH-TSMOM+pyramid is designed to exploit. This is a high-IS-bar problem rather than a
collapsing-OOS problem.

### Phase 7 — Cross-strategy correlation

| pair | overlap | corr-daily | corr-monthly | class |
|---|---|---|---|---|
| BTC-trend / xs-mom | 2,141 | +0.120 | +0.280 | REAL DIVERSIFIER |
| BTC-trend / treasury-trend | 2,072 | -0.037 | -0.054 | REAL DIVERSIFIER |
| xs-mom / treasury-trend | 2,839 | -0.067 | -0.007 | REAL DIVERSIFIER |

Equal-weight blend of all three (2018-2026 overlap): Sharpe **+1.29** vs +0.91/+0.91/+0.64
standalone. Caveat: xs-mom and treasury-trend are both retired/blocked from live deploy
(QC retired; bond CFDs absent from Eightcap). The blend is a research bound rather than a
live-deployable book. **BTC-trend would deploy standalone alongside orb_dax and lunch_fade.**

### Phase 8 — Real out-of-sample (Sep 2025 – Mar 2026)

Trained through 2025-08-31, then run on the genuinely-unseen Sep 2025 - Mar 2026 BTC
drawdown (peak $125k → trough $63k, -49.6% peak-to-trough).

| segment | years | ret | CAGR | Sharpe | MDD |
|---|---|---|---|---|---|
| Train 2018-01..2025-08 | 7.7 | +125.77% | +11.21% | +0.93 | -17.22% |
| **OOS 2025-09..2026-03** | **0.6** | **-3.10%** | **-5.30%** | **-0.32** | **-11.72%** |
| B&H same OOS | 0.6 | -37.50% | -55.68% | -1.15 | -49.64% |

**Position trajectory through the OOS drawdown:**

| month-end | price | signal | weight | state |
|---|---|---|---|---|
| 2025-09-30 | 114,646 | +0.33 | 0.61 | near-full long |
| 2025-10-31 | 109,397 | +0.33 | 0.49 | partial long |
| 2025-11-30 | 91,172 | -0.33 | **0.00** | **FLAT (signal flipped)** |
| 2025-12-31 | 87,636 | -1.00 | 0.13 | toe-in (1 unit) |
| 2026-01-31 | 78,252 | -1.00 | 0.00 | flat |
| 2026-02-28 | 66,742 | -1.00 | 0.00 | flat |
| 2026-03-31 | 68,188 | -1.00 | 0.00 | flat |

Strategy spent 59% of OOS days flat, 0% days full-long. **The exit mechanism worked exactly
as the thesis predicted** — caught the regime change in Nov 2025, was flat through the worst
of the decline. The -3% OOS loss is the cost of the late-Oct lag and the brief Dec re-entry;
the alternative was the B&H -37%.

### Null-direction check

Per CLAUDE.md rule 6 (also see `lumber_oats_tsmom_rejected` memory — caught a sign error
on a similar TSMOM thesis). Script: `btc_null_check.py`.

| direction | Sharpe | CAGR | MDD |
|---|---|---|---|
| REAL (long when +signal) | +0.83 | +9.97% | -17.22% |
| FADE NULL (short when +signal, same mechanics) | -0.82 | -4.89% | -35.98% |

Fade-gap **+1.65** — exceptionally strong directional content. The strategy is not a
cost-or-exit artifact, and there is no sign error.

---

## Phase 9 — Walk-forward Phase 6 (revised, 2026-05-13)

Pre-2018 BTC is a methodologically different asset (no retail CFD market, $10-50M daily
volume vs $30B today, retail-cypherpunk-driven vs institutional-derivatives microstructure),
so deep-history extension was rejected. Instead, the single-split Phase 6 was replaced
with a walk-forward across 5 rolling 3y-IS / 2y-OOS splits. Script: `btc_walk_forward.py`.

| split | IS window | OOS window | IS Sh | OOS Sh | degradation | pass |
|---|---|---|---|---|---|---|
| S1 | 2018-2020 | 2021-2022 | +1.67 | **-0.03** | **+1.700** | ❌ |
| S2 | 2019-2021 | 2022-2023 | +1.16 | +0.90 | +0.263 | ✅ |
| S3 | 2020-2022 | 2023-2024 | +1.09 | +1.27 | -0.183 | ✅ |
| S4 | 2021-2023 | 2024-2025 | **+0.37** | +0.54 | -0.170 | ✅ |
| S5 | 2022-2024 | 2025-2026 | +1.16 | **+0.03** | **+1.130** | ❌ |

| metric | value | bar | verdict |
|---|---|---|---|
| Mean degradation | **+0.548** | < 0.5 | FAIL |
| Median degradation | +0.263 | — | (passes) |
| Splits w/ deg < 0.5 | 3/5 | ≥ 3 | PASS |
| Splits w/ OOS Sh > 0 | 4/5 | ≥ 4 | PASS |

**Mean fails by 0.05; the two failing splits (S1, S5) are both parabola-top → V-bottom
transitions.** That's a structural weakness of slow-TSMOM, not lottery noise:
- S1: 2021 parabola top + 2022 crash. Strategy was still long at the top, late to flip.
- S5: late-2025 top to $125k + Q1 2026 -50% drawdown (the same period Phase 8 covered).

**S4 IS Sharpe +0.37** is the lowest IS window observed and corroborates the W4
(2024-2025) regime decay seen in the original Phase 4 (+0.50 vs +1.38/+1.61 earlier
windows). The institutionalization-decay narrative is independently confirmed by two
different decomposition methods.

---

## Verdict (2026-05-13): **KEEP_FOR_REFERENCE** — retire, do not deploy

| phase | verdict |
|---|---|
| Phase 2 (MVI honest costs) | PASS |
| Phase 3 (stat battery) | PASS |
| Phase 4 (regime stability) | PASS |
| Phase 5 (parameter sensitivity) | PASS |
| Phase 6 (single-split IS/OOS) | FAIL by 0.04 |
| Phase 7 (cross-strategy corr) | PASS — real diversifier (with retired peers) |
| Phase 8 (real post-training OOS) | PASS — handled -50% BTC drawdown |
| Phase 9 (walk-forward Phase 6) | **FAIL** — mean degradation +0.548 |
| Null check | PASS — fade-gap +1.65 |

Two independent reasons not to deploy:

1. **Structural parabola-V vulnerability.** S1 and S5 are both real OOS observations of
   the same failure mode (long at the top, slow to flip on a sharp reversal). This is a
   known weakness of slow-TSMOM and a meaningful share of the realized OOS evidence.
2. **Institutionalization regime decay.** S4 IS +0.37 and W4 +0.50 are independent
   measurements of the same trend — the edge is halving as BTC matures into an
   institutional asset. Live deployment would inherit this decay.

Mechanism is real (fade-gap +1.65, Phase 8 drawdown-handling validated) but the edge is
too regime-conditional and too decay-prone to deploy at retail risk budget. Thesis
preserved as:
- the negative-result reference for "TSMOM-on-crypto at 2018+ retail CFD costs"
- a methodological example of walk-forward catching parabola-V vulnerabilities that
  single-split Phase 6 missed

**Not a candidate for refinement.** A vol-of-vol filter, faster signal in high-vol
regimes, or vol-of-vol-conditional sizing might mitigate S1/S5 but would be a separate
thesis (new Phase 1 doc, new pre-committed kill criteria). Per the lumber_oats lesson,
don't move goalposts on a closed experiment.

## Files

- `btc_trend.md` — this doc
- `btc_trend_validation.py` — Phases 2-6 (single split)
- `btc_phase7_correlation.py` — Phase 7
- `btc_real_oos.py` — Phase 8 (real-OOS Sep 2025 – Mar 2026)
- `btc_null_check.py` — fade-direction null check
- `btc_walk_forward.py` — Phase 9 (walk-forward Phase 6, 5 rolling splits)
