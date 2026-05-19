# Project State — Graveyard

Rejected/tombstoned experiments. One row per reject. Detail lives in the linked thesis doc.
Active state → [STATE.md](STATE.md). Lessons → [RESEARCH_NOTES.md](RESEARCH_NOTES.md).

---

## Intraday CFD (17)

| name | verdict | killed | Sh full / holdout | dir-gap | load-bearing failure mode | date |
|---|---|---|---|---|---|---|
| [orb_spx500](../experiments/orb/orb.md) | REJECT | Phase 2 | -0.92 | ~0 | No directional content; multi-venue diffuse open dilutes opening-impulse | 2026-04-19 |
| [orb_ndx100](../experiments/orb/orb.md) | REJECT | Phase 4 | 0.03 / 0.19 | small | Marginal even with weak signal; every refinement that helped GER40 hurt NDX | 2026-04-19 |
| [orb_uk100](../experiments/orb/orb.md) | REJECT | Phase 2 | -0.54 | n/a | No opening-impulse — FTSE commodities-heavy + ADR-priced overnight | 2026-04-19 |
| [orb_eustx50](../experiments/orb/orb.md) | REJECT | Phase 2 | -1.54 | n/a | Multi-venue basket; FESX futures lead cash open by 60min | 2026-04-19 |
| [ndx_mean_reversion](../experiments/ndx_mean_reversion/ndx_mean_reversion.md) | REJECT | Phase 2 | -0.68 | -0.28 | Fade-gap inverted (momentum wins); generic z-score MR fails on NDX M5 | 2026-04-19 |
| [bb_reversion](../experiments/bb_reversion/bb_reversion.md) | REJECT | Phase 2 | -0.34 (NDX best) | +0.50 NDX | Weak fade-gap NDX but absolute Sh negative even at zero cost; SPX/UK no signal | 2026-04-19 |
| [dax_zscore_momentum](../experiments/dax_zscore_momentum/dax_zscore_momentum.md) | MARGINAL | Phase 2 | -0.12 / -0.09 | +0.82 | Mechanism real but ORB captures it cleaner — tombstoned in favor of orb_dax | 2026-04-19 |
| [vix_term_structure](../experiments/vix_term_structure/vix_term_structure.md) | REJECT | Phase 4 | 0.31 / -0.45 | n/a | Holdout -0.45 from 0DTE compression + post-2022 vol regime change | N/A |
| [eod_unwind](../experiments/eod_unwind/eod_unwind.md) | REJECT | Phase 2 | -0.85 SPX / -1.90 | +0.46 | Fade-gaps positive (real mechanism) but absolute Sh + holdout decay both fail; 0DTE inverted SPX | 2026-04-20 |
| [dax_overnight](../experiments/dax/overnight.md) | REJECT | Phase 8 | 0.80 / 0.85 / **live -0.34** | n/a | **CFD-vs-futures artifact** — dealer-constructed overnight prices don't survive on real FDAX | 2026-04-20 |
| [dax_pre_auction](../experiments/dax/pre_auction.md) | REJECT | Phase 2 | -0.66 | -0.33 | Sign-inverted; no Xetra public imbalance feed during continuous trading | 2026-04-20 |
| [dax_us_lead](../experiments/dax/us_lead.md) | REJECT | Phase 2 | -0.48 | -0.42 | Sign-inverted; DAX over-extended by SPX via futures arb by 15:45 Berlin | 2026-04-20 |
| [dax_gap_fade](../experiments/dax/gap_fade.md) | REJECT | Phase 2 | -1.04 | -1.16 | Strongly sign-inverted; DAX gaps CONTINUE (Xetra auction under-prices info → pile-on) | 2026-04-20 |
| [preclose_drift](../experiments/preclose_drift/preclose_drift.md) | REJECT | Phase 2 | -0.41 NDX / 0.57 | +0.74 NDX | NDX edge real but no threshold cell satisfies Sh>0.30 AND trades>=200 at M5 CFD friction | 2026-05-12 |
| [vwap_fade](../experiments/vwap_fade/vwap_fade.md) | REJECT | Phase 2 | -0.77 SPX / -1.41 | -0.15 SPX | Sign-inverted on NDX; 0DTE trend amplification killed late-session MR outside lunch vacuum | 2026-05-13 |
| [gap_continuation](../experiments/gap_continuation/gap_continuation.md) | REJECT | Phase 2 | -0.88 SPX | -0.48 / -0.92 NDX | Sign-inverted both — US-index gaps DON'T continue (opposite of DAX); 18h pre-market over-extends info | 2026-05-13 |
| [wti_session](../experiments/wti_session/wti_session.md) | REJECT | Phase 1 + 6 | 0.32 / **W4 -0.58** | +1.53 | W4-floor binding fail — Asian-session family decay-side (mechanism real 2018-2023, reversed 2024+) | 2026-05-16 |

## Daily-frequency multi-asset / FX / equities (13)

| name | verdict | killed | Sh full / holdout | dir-gap | load-bearing failure mode | date |
|---|---|---|---|---|---|---|
| [fx_carry](../experiments/fx_carry/fx_carry.md) | REJECT | Phase 2 | -0.38 | n/a | 2015-2026 carry graveyard — rate convergence, COVID, Fed hikes vs EM weakness | N/A |
| [fx_carry_trend](../experiments/fx_carry_trend/fx_carry_trend.md) | REJECT | Phase 2 | -0.38 | n/a | 3M momentum filter fired sparingly; bad-carry pairs still lost | N/A |
| [fx_mean_reversion](../experiments/fx_mean_reversion/fx_mean_reversion.md) | REJECT | Phase 2 | -0.17 | n/a | All 12 param configs negative; 58.5% WR but avg-loss > avg-win, cost bled | N/A |
| [tsmom_filtered](../experiments/tsmom/tsmom_filtered.md) | REJECT | Phase 2 | -0.02 | n/a | EMA(200) filter whipsaws on FX crosses; worse than tsmom baseline | N/A |
| [equity_pairs](../experiments/equity_pairs/equity_pairs.md) | REJECT | Phase 2 | -0.99 | n/a | 9/10 mega-cap US pairs negative all 5 regimes; Gatev/Goetzmann/Rouwenhorst half-life ran out post-2002 | N/A |
| [blended_portfolio](../experiments/blended_portfolio/blended_portfolio.md) | REJECT | Phase 7 | 0.64 | n/a | tsmom + xs_momentum correlation +0.69 — blending just interpolates same-bet | N/A |
| [dual_momentum](../experiments/_archived/dual_momentum.md) | REJECT | Phase 2 | 0.39 (IS -0.13) | n/a | Positive full-sample only from 2023+ bull; cash filter actively hurts | N/A |
| lumber_oats_tsmom | REJECT | Phase 2 | 0.18 | -0.35 (fade wins) | Sign error — physical-supply commodities mean-revert, not trend (12-1 mom +0.18 vs fade +0.52) | 2026-04-21 |
| [btc_volbreak](../experiments/btc_volbreak/btc_volbreak.md) | REJECT | Phase 2+4+6 | 0.40 / **W4 0.18** | +1.17 | One-window wonder — W2 2020-21 Sh +1.58 carries everything; W1/W3/W4 below floor. MDD -52% also fails | 2026-05-13 |
| [btc_weekend](../experiments/btc_weekend/btc_weekend.md) | REJECT | Phase 2+4 | 0.61 / W4 +1.81 (inverted) | +1.86 | Mechanism activates post-2022 but MDD -40% accumulated in pre-activation W1-W2 dormancy | 2026-05-13 |
| [short_tsmom](../experiments/short_tsmom/short_tsmom.md) | REJECT | Phase 2 | -0.25 / 2022 +0.28 / 2020-Q1 +0.02 | **-0.89** | **Null-check INVERTED — same conditions long-side +0.64; QE-era equity drawdowns are buy-the-dip EV, not trend-continuation EV** | 2026-05-18 |
| [fx_safe_haven](../experiments/fx_safe_haven/fx_safe_haven.md) | REJECT | Phase 2 | -0.32 / 2020 COVID +1.39 / 2022 -0.91 | **-0.55** | **Regime-conditional mechanism — works COVID-style liquidity shock, breaks 2022 Fed-BoJ rate-divergence stress; JPY-haven property NOT structural in modern data** | 2026-05-18 |
| [usd_safe_haven](../experiments/usd_safe_haven/usd_safe_haven.md) | REJECT | Phase 2 + walk-forward | -0.08 / 2022 +0.63 PASS standalone / **holdout Calmar 2.55 → 2.26 at hedge_w=0.5** | -0.13 | **Full-sample integration test misled (Calmar 1.18→1.20); walk-forward 2023-2026 holdout shows EVERY hedge weight degrades book Calmar — improvement was 2022-in-sample fitting; dynamic scaling rules also fail OOS** | 2026-05-18 |
