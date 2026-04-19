# Research Notes — running log

Narrative log of what's been tried, what's been learned, and what's next. Paired with the tombstone docs adjacent to each strategy's code.

---

## Current state

- **Live strategy (paper)**: XS-momentum long-only. See [experiments/xs_momentum/xs_momentum.md](../experiments/xs_momentum/xs_momentum.md).
- **Deployed to**: QuantConnect with Interactive Brokers brokerage model. File at [deploy/qc_xs_momentum.py](../deploy/qc_xs_momentum.py).
- **Live backtest Sharpe**: 0.35 (vs research 0.92). Gap primarily from ETF substitutions for CFDs and softs futures not firing.
- **Cleared Phases 2-7**: IEF Treasury trend, multi-horizon variant (1M+3M+12M). See [experiments/treasury_trend/treasury_trend.md](../experiments/treasury_trend/treasury_trend.md). First strategy in the project to clear the full validation pipeline end-to-end. OOS 2015-2026 Sharpe 0.42, degradation 0.40 (under 0.5 kill). Near-zero correlation with XS-mom. Next step: Phase 8 QC deployment.

## Strategies status

| Strategy | Location | Verdict |
|---|---|---|
| XS-momentum | [experiments/xs_momentum/xs_momentum.md](../experiments/xs_momentum/xs_momentum.md) | KEEP — live paper trading |
| TSMOM long-only | [experiments/tsmom/tsmom.md](../experiments/tsmom/tsmom.md) | KEEP — too correlated with XS-mom (+0.69) to blend |
| TSMOM filtered | [experiments/tsmom/tsmom_filtered.md](../experiments/tsmom/tsmom_filtered.md) | REJECT — filter worsened results |
| Imbalance/FVG | [experiments/imbalance/imbalance.md](../experiments/imbalance/imbalance.md) | TODO — inherited, not validated |
| FX Carry (pure) | [experiments/fx_carry/fx_carry.md](../experiments/fx_carry/fx_carry.md) | REJECT — Sharpe -0.38, regime killed it |
| FX Carry + Trend | [experiments/fx_carry_trend/fx_carry_trend.md](../experiments/fx_carry_trend/fx_carry_trend.md) | REJECT — filter didn't rescue carry |
| FX Mean Reversion | [experiments/fx_mean_reversion/fx_mean_reversion.md](../experiments/fx_mean_reversion/fx_mean_reversion.md) | REJECT — robust rejection, all 12 params negative |
| Blended portfolio (TSMOM + XS-mom) | [experiments/blended_portfolio/blended_portfolio.md](../experiments/blended_portfolio/blended_portfolio.md) | REJECT — correlation 0.69, no diversification |
| Dual Momentum | [experiments/_archived/dual_momentum.md](../experiments/_archived/dual_momentum.md) | REJECT — IS return negative |
| VIX term-structure (VRP) | [experiments/vix_term_structure/vix_term_structure.md](../experiments/vix_term_structure/vix_term_structure.md) | REJECT — full-period Sharpe 0.31; 2024-2026 sub-window Sharpe -0.19, post-2022 vol compression killed the edge |
| Equity pairs (mega-cap) | [experiments/equity_pairs/equity_pairs.md](../experiments/equity_pairs/equity_pairs.md) | REJECT — full Sharpe -0.99 across 10 pairs; 9/10 pairs negative, all 5 regime windows negative including calm 2015-2017. Mega-cap US pairs 2015-2026 are not mean-reverting at 60-bar windows |
| Treasury trend (IEF-MH) | [experiments/treasury_trend/treasury_trend.md](../experiments/treasury_trend/treasury_trend.md) | **PASS Phases 2-7** — IEF multi-horizon (1M+3M+12M per MOP 2012). Full 24y sample: Sharpe 0.67. Phase 4 (regime): 4/4 windows positive. Phase 5 (param sens): max drop 4% on ±20% change, plateau confirmed. Phase 6 (holdout 2002-2014/2015-2026): IS 0.82, OOS 0.42, degradation 0.40. Phase 7: monthly corr XS-mom -0.01. Ready for Phase 8 (QC deployment). |
| ORB index M5 (cross-instrument) | [experiments/orb/orb.md](../experiments/orb/orb.md) | SPX500 REJECT (Sh -0.92). **NDX100 MARGINAL — do NOT deploy**: every refinement path that helped GER40 hurts NDX100; baseline EOD Sh +0.03 full / +0.19 holdout is the ceiling. **GER40 PASS with T+180min exit refinement**: Sh +0.58 full, all 3 regimes ≥ +0.55 incl. 2023-26 holdout +0.55, MDD -12%, fade-gap +1.04 (real directional edge confirmed under symmetric R:R). First intraday strategy in project with real edge + positive holdout. LIVE paper on MT5 GER40 CFD. |

## Key lessons

1. **FX crosses 2015-2026 is a graveyard for non-momentum factors.** Carry, carry+trend, short-term mean reversion all produced negative Sharpe. Only slow momentum (XS-mom and TSMOM-LO) made money.

2. **Low correlation ≠ useful diversifier.** FX carry and FX MR both had correlation < 0.3 with XS-mom (mechanically independent), but negative Sharpe means blending them subtracts returns. Correlation alone doesn't justify inclusion; positive standalone Sharpe does.

3. **Negative IS-OOS degradation is not automatic good news.** Every strategy we tested had OOS Sharpe > IS Sharpe, driven by the 2023+ momentum regime. The honest long-run estimate is the IS number, not the OOS or full-sample.

4. **"Different mechanic, same universe" = same bet.** TSMOM and XS-mom are both momentum on the same instruments; correlation turned out to be +0.69 despite different math. To get real diversification, need either a different factor OR a different market (equity single-names, crypto perps, vol products).

5. **Research backtesting overestimates live Sharpe.** QC live-backtest of XS-mom came in at 0.35 vs research 0.92. The 2.5× gap was mostly universe adaptations (ETFs ≠ CFDs) plus realistic broker costs. Plan for a 50-70% Sharpe haircut research → live.

6. **Regime decay ≠ bad strategy, but still a REJECT.** VIX term-structure VRP had Sharpe 1.14 in 2015-2017 (textbook VRP era), survived Volmageddon via backwardation filter, then died post-2022 (2024-2026 Sharpe -0.19). 0-DTE option flow + compressed VX curve appear to have thinned the underlying premium. Regime-dependent edges don't get a pass just because they "worked in the right era" — the forward-looking window is all that matters for deployment.

7. **Weight literature decay warnings heavily.** Equity pairs thesis cited the 1962-2002 Gatev/Goetzmann/Rouwenhorst paper AND the post-2002 decay research from Do & Faff (2010). Estimated Sharpe 0.4-0.7; actual -0.99. The decay warning deserved as much weight as the headline number — maybe more. When a mechanism's academic half-life has been measured, the recent number matters more than the canonical number. Mega-cap US pairs 2015-2026 is now a graveyard alongside FX non-momentum 2015-2026.

8. **"Active return over cash" can be tiny and the strategy still valuable as diversifier.** Treasury trend (IEF) gained +2.14%/yr vs BIL's +1.89%/yr — only +0.25%/yr active return. Standalone this is underwhelming. But it has Sharpe 0.54, MDD -9%, caught the 2022 bond crash (+1.41% vs TLT -29%), and has ≈ 0 correlation with XS-mom. Blended into a 70/30 XS-mom + IEF-trend book, you give up little return and gain meaningful DD-reduction in regimes where bonds work AND unchanged exposure when they don't. Diversifiers shouldn't be judged on standalone CAGR — they should be judged on whether they help the existing book in the regimes where the existing book hurts.

9. **Match filter speed to asset duration.** Same 252-day TSMOM signal on TLT (18y duration, ~15% vol) vs IEF (8y duration, ~7% vol) gave Sharpe 0.14 vs 0.54. TLT's vol creates 10-15% transitional drawdowns in the 6-month filter lag window that IEF's lower vol absorbs. When designing trend on a given instrument, the filter lookback must be proportional to the instrument's own vol — a rule that was implicit but not stated in the existing XS-mom / TSMOM work.

10. **The engine's permutation test is meaningless for continuous-position strategies.** `backtesting.statistics.permutation_test` shuffles the return series; permutation preserves mean and std exactly, so the null is mathematically identical to the observation. This works for discrete-trade strategies (flip trade PnL signs) but degenerates for continuous-weight strategies like TSMOM. For those, use a **position-shuffle** test: shuffle the daily weight series, preserve the actual return series, recompute P&L. This tests "does the timing of the position choices add value?" — the right null. Implemented inline in `experiments/treasury_trend/treasury_trend_validation.py`; consider promoting to `backtesting.statistics` if it comes up again.

11. **Extend the sample before accepting a marginal bootstrap result.** IEF Phase 3 bootstrap 95% CI on 11 years was [-0.028, +1.138] — a near-miss that would have tombstoned under strict reading. Extending to IEF's full 24-year history (2002-2026) moved the CI to [+0.26, +1.08] and raised Sharpe from 0.55 to 0.67. If the underlying instrument has earlier data and the mechanism is expected to work across pre-sample regimes, refetch before rejecting. An overfit strategy would LOSE Sharpe on extension; a real edge gains.

12. **CFD intraday costs + tick-volume ≠ cash-equity intraday.** ORB on SPX500 M5 2019-2026 failed at Sharpe -0.92 against Zarattini/Aziz (2023) reporting Sharpe 1.65-2.81 on QQQ. Key differences: (a) CFD spread ≈ 2× their commission assumption, (b) no real share volume for filters, (c) SPX500 is less momentum-driven than QQQ, (d) broader 30-min OR vs their 5-min first-bar OR. Published intraday results on cash equities do not port 1-1 to retail CFDs even when the mechanism nominally translates — friction + noise thresholds matter more than they do at daily cadence.

13. **Test the "fade" variant as a null check on any signal-based intraday strategy.** If both the signal and its mechanical opposite produce similar loss patterns (18% WR in both directions for ORB SPX500), the signal has no informational content — it is generating noise trades, not alpha trades. ~30 lines of code, saves days of tuning a dead mechanism.

14. **Stops inside typical intrabar range = instant death.** On SPX500 M5, a stop at 25-33% of OR width is inside typical single-bar noise envelope. Tightening stops dropped WR from 18% to 4%, far faster than it shrank avg loss. For any intraday strategy: measure intrabar range against planned stop distance BEFORE committing — if stop < 0.5 × intrabar ATR, expect >80% of trades to stop-out regardless of signal quality.

15. **Cross-instrument fade test separates signal from exit-structure artifact.** Running the same ORB mechanism on SPX500, NDX100, and GER40 exposed that GER40 had the highest absolute Sharpe (+0.38) but its fade variant was also positive (+0.34) — the edge was a structural R:R artifact (full-OR stop + EOD close = asymmetric book-keeping), not directional signal. NDX100 had weaker absolute Sharpe (+0.03) but the fade variant lost 0.46, proving real directional content. For cross-instrument strategies, the **fade-gap** (baseline Sharpe minus fade Sharpe) is a cleaner edge-quality indicator than absolute Sharpe. Numerically-best ≠ deployment-best.

16. **Recent-regime (holdout) sub-period is the honest deployment signal.** NDX100 baseline ORB had full-sample Sharpe +0.03, but the 2023-2026 holdout was the strongest window at +0.19. Adding trend-filter + tight-stop raised full-sample to +0.31 but made the holdout -0.19. When a "better" config has a WORSE holdout, the full-sample improvement is overfit noise, not real improvement. Prefer the baseline with the stronger holdout over the optimized variant with the weaker holdout — always.

17. **Don't tombstone based on fade-test alone — retest under symmetric R:R first.** GER40 ORB initially looked like a structural artifact (baseline Sharpe +0.38, fade +0.34, small gap). The refinement run exposed that the EOD-close exit was giving both directions the SAME R:R asymmetry (fixed loss cap + random EOD distribution), which inflated fade's Sharpe by coincidence. Under fixed 1:1 R:R exits, baseline Sh -0.24 vs fade -1.21, gap +0.97 — real directional signal. **Rule**: when baseline and fade converge under asymmetric exits, rerun both under SYMMETRIC R:R before concluding the signal is vestigial. EOD-exit with fixed-distance stop is itself a confound.

18. **Time-of-day exit as an alpha discovery tool.** GER40 ORB refinement: full-sample Sharpe at EOD exit was +0.38; replacing with T+180min exit jumped to +0.58 with tighter DD. The edge in opening-impulse momentum has a half-life of about 3 hours on DAX M5 — holding longer accumulates noise. For any intraday strategy where you're exiting at EOD "because that's what the literature does", test a T+60/120/180/240min sweep — often the edge is concentrated in early bars and diluted by holding till close.

19. **Refinement paths are instrument-specific, not universal.** The T+180min exit that unlocked GER40's edge (Sh +0.38 → +0.58) was tested on NDX100 and FAILED decisively — NDX100's optimum is actually the LONGEST hold (EOD-exit Sharpe +0.03 beats T+180 of -0.09). Under tight R:R exits on NDX100, fade-variant beats baseline (-0.17 gap at 1:1 R:R) — opposite of GER40 where baseline dominates. Different instruments have different post-breakout autocorrelation profiles (DAX has clean 3h opening-impulse momentum; NDX has weak full-session drift + short-term mean reversion). When investigating a new instrument, run the symmetric-R:R-plus-TOD-sweep diagnostic from scratch — do NOT assume the previous instrument's refinement ports over.

20. **"Marginal" strategies don't become non-marginal through refinement.** NDX100 baseline was always the ceiling, not a floor — every refinement variant produced lower regime-averaged Sharpe. Lead variants that looked good in 2019-20 collapsed in 2021-26. Holdout-degradation was the kill signal each time: the "improved" variants had worse 2023-2026 holdout Sharpe than the baseline they replaced. If refinement hurts the modern-regime sub-period while "improving" the full-sample number, you're overfitting early-sample regimes. Prefer baseline.

21. **QC's Sharpe is risk-free-adjusted; our research Sharpe is raw.** First observed on Treasury-trend QC port 2026-04-19: research Sharpe 0.42 (OOS 2015-2026), QC reported Sharpe -0.263 on same period. Strategy wasn't broken — QC's formula subtracts ~3% annual risk-free rate; our `annualized_sharpe()` does not. Raw Sharpe computed from the QC equity curve (CAGR 2.26% / annualized std 3.4% = 0.66) matched research 0.67 almost exactly. For every future Phase 8 backtest: **don't compare QC-reported Sharpe directly to research-reported Sharpe**. Either compute the raw version from QC's equity output, or add risk-free-subtraction to our research sim. The comparison we actually care about (edge after realistic costs) needs the same formula on both sides. Corollary: at high rf (~4-5% post-2022), any strategy returning < 5%/year will have negative QC-reported Sharpe even if positive-returning. This is structural, not pathological.

## Open questions / TODO

- **Wire statistical battery** (`compute_statistical_report`) into all surviving strategies' validation scripts with honest `n_trials_tested` counts.
- **Add SPY benchmark** to validation scripts (alpha, beta, information ratio, tracking error) — currently only QC live run has this.
- **Debug softs futures in QC** — 0 orders despite being in universe. Likely `Futures.Softs.SUGAR_11`/`COTTON_2` constants or data-history issue.
- **Validate imbalance strategy** against Phase 1-6 workflow.
- **Explore capacity-limited niches** for next strategy attempt:
  - Crypto perp funding-rate basis (Binance/Bybit)
  - Equity single-name PEAD
  - VIX term-structure roll
- **Intraday (first retail attempt)**: ORB cross-instrument (SPX500 / NDX100 / GER40 / UK100 / FRA40) M5. Phases 1-2 + refinement complete 2026-04-19 (`experiments/orb/`). **GER40 with T+180min exit refinement is live paper on MT5 VPS** — full-sample Sh +0.58, 3/3 regimes ≥ +0.55, fade-gap +1.04 under symmetric R:R. SPX500/UK100 hard-rejected; NDX100 marginal but every refinement path hurts; FRA40 inconclusive (broker data doesn't cover Paris cash open).

## Process

See [WORKFLOW.md](WORKFLOW.md) for the strategy development pipeline with explicit kill criteria at each phase.
