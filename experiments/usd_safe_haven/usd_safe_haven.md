# USD safe-haven — short EURUSD/GBPUSD/AUDUSD/NZDUSD during equity stress

**Status**: Phase 2 + walk-forward complete 2026-05-18
**Verdict**: **REJECT** — initial full-sample integration test looked MARGINAL (Calmar 1.18→1.20) but walk-forward (train 2018-2022, holdout 2023-2026) **inverts the result entirely**: every hedge weight from 0.25 to 1.5 DEGRADES holdout Calmar vs book-only (2.55 → 2.40/2.26/2.12/2.00/1.50). The full-sample improvement was 2022-in-sample fitting; in the never-touched OOS window the hedge is dead weight. Dynamic scaling rules (binary, proportional) also fail to beat book-only on holdout. **Do NOT deploy.** The "is it overfit?" question answers itself when the holdout test runs.

## Why this exists (after two prior REJECTs)

- `short_tsmom` REJECT — equity shorts structurally broken in QE era (lesson #34)
- `fx_safe_haven` REJECT — JPY-haven property fails in rate-divergence regimes (lesson #35)

Both fails had inverted null-checks. The remaining structurally-different candidate from the same tradeable universe: **USD-long during stress**.

The thing that broke the JPY hedge — Fed hiking aggressively while BoJ stayed at zero in 2022 — is the same thing that made USD a strong safe-haven during 2022. The rate-policy asymmetry that hurts JPY *helps* USD.

Empirical pre-evidence: regressions on the deployed book's W4 (2025-26) daily PnL against EURUSD-as-USD-proxy:

- `lunch_fade` daily $-PnL beta to USD-up: **−2,521** (loses when USD strengthens)
- `xau_session` daily $-PnL beta to USD-up: **−7,697** (loses heavily)
- `orb_dax`: small negative

So the deployed book is already short USD-up in PnL terms. A USD-long-in-stress overlay would profit exactly when the book bleeds — by definition this is what a hedge does.

## Thesis (mechanism)

1. **USD is the global reserve / funding currency.** When global funding stress hits, demand for USD funding spikes (dollar shortage). Classical pattern from 2008 (DXY +20% in 5 months), 2020 March (DXY +8% in 2 weeks), 2022 (DXY +18% calendar year).
2. **Rate-divergence regimes favor USD.** Fed hiking faster/sooner than ECB/BoE/RBA/RBNZ creates USD rate advantage. The 2022 stress that destroyed the JPY hedge was EXACTLY this scenario, and USD strengthened.
3. **USD is structurally different from JPY in modern data.** BoJ ZIRP makes JPY a *funding* currency that strengthens only on forced unwinds; the Fed's higher-rate stance makes USD a *yield* currency that strengthens both on flow (carry-up) and stress (funding-demand).
4. **The deployed book is empirically short USD-up.** Two of three deployed strategies have negative USD-up beta in W4 data. Hedging that beta directly is mechanically sound, not just historical extrapolation.

## Key reference

- Avdjiev, Du, Koch, Shin (2019) "The dollar, bank leverage, and deviations from covered interest parity" — USD funding stress mechanism
- Maggiori, Neiman, Schreger (2020) "International Currencies and Capital Allocation" — USD-as-reserve role in stress
- Repo prior: lesson #35 — JPY-haven conditional on rate-policy state; USD has the opposite rate-policy state

## Signal math (identical regime detection to fx_safe_haven)

```
For each day t:
  spx_dd_60d[t]  = spx_close[t-1] / max(spx_close[t-60..t-1]) - 1
  spx_rvol_20[t] = std(spx_returns[t-20..t-1]) * sqrt(252)
  spx_sma_50[t]  = mean(spx_close[t-50..t-1])

  Triggers tested:
    V1: spx_dd_60d < -0.05
    V2: spx_rvol_20 > median * 1.5
    V3: spx_close < spx_sma_50
    V4: V1 OR V2

  Action on USD-pair (EURUSD, GBPUSD, AUDUSD, NZDUSD):
    If trigger active and flat: SHORT next-day open (= long USD), vol-target 10%
    Exit on trigger off, adverse stop -8%, max hold 90 days.
    Cost: 1 bp RT.
```

## Universe

- **Primary**: EURUSD D1, GBPUSD D1 (direct on disk)
- **Secondary**: AUDUSD (from H1), NZDUSD (from H1)
- Regime: SPX500 D1 (on disk)
- Period: 2018-01 → 2026-04

## Expected performance (pre-committed)

The 2022 regime is the binding test that JPY failed. USD should *pass* it because:
- DXY +18% during 2022 equity bear
- Short EURUSD (as USD-long proxy) should produce strongly positive 2022 Sharpe

| Metric | Expected |
|---|---|
| Full-sample Sharpe | 0 to +0.5 (insurance-asset framework) |
| 2020 COVID Sharpe | +1.5 to +3.0 |
| **2022 Sharpe** | **+0.5 to +2.0 (this is the binding test)** |
| 2024-2026 drag | −0.3 to +0.3 |
| Correlation to book in stress | < −0.30 (expected stronger than JPY hedge attempt) |

## Fail conditions (pre-committed)

Same hedge-asset framework as fx_safe_haven, with one critical addition: **2022 must pass.** That's the specific regime that broke the prior hedge attempt and the binding test for this one.

| Criterion | Bar | |
|---|---|---|
| Full-sample Sharpe > −0.50 | | |
| MDD < 40% | | |
| Trades ≥ 30 | | |
| **2020-Q1 stress Sharpe > +1.5** | **load-bearing** | |
| **2022 stress Sharpe > +0.5** | **load-bearing** | the test fx_safe_haven failed |
| **Direction null-gap > +0.30** | **load-bearing** | confirms direction has content |
| 2024-2026 drag > −0.50 | | |

## Why this might still fail

1. **2024-2026 has been mixed for USD.** DXY peaked late 2022, drifted lower through 2023, mixed 2024-2026. If the trigger fires in stress that DOESN'T have classical USD-up behavior (e.g., a future banking-crisis Fed-cut), USD-long bleeds.
2. **Triple-rejected pattern.** If this fails the null-check too, that's three independent mechanism families with inverted null-checks — strong evidence that "no SPX-stress-triggered hedge works in modern data" is a structural property, not bad design.
3. **Sample size for clean 2022-style regime is N=1.** Even if it works, attribution to "USD rate advantage" vs other 2022 specifics is hard.

## Phase 1 → Phase 2 plan

- [x] Read lessons #34 and #35 from RESEARCH_NOTES
- [x] Confirm USD-pair data on disk and book's USD beta is structurally negative
- [ ] Adapt fx_safe_haven_demo.py framework to USD pairs (short = USD-long)
- [ ] Run, identical kill criteria with 2022-binding test
- [ ] Update verdict in this doc, STATE.md, STATE_GRAVEYARD.md
- [ ] If PASS: this is genuinely deployable — write the deploy plan

## Files

- Thesis: this doc
- Demo: `experiments/usd_safe_haven/usd_safe_haven_demo.py`

## Phase 2 results (2026-05-18)

### Standalone backtest
Universe: EURUSD D1, GBPUSD D1 (full coverage 2018-2026); AUDUSD/NZDUSD too short on Eightcap datalake to contribute meaningfully.

| Pair (V4 trigger, short = long-USD) | Sharpe | Total | MDD | Trades | WR |
|---|---|---|---|---|---|
| EURUSD | −0.07 | −5.57% | −20.06% | 38 | 47.4% |
| GBPUSD | −0.08 | −6.82% | −26.86% | 38 | 55.3% |
| **PORTFOLIO V4** | **−0.08** | **−2.58%** | **−12.24%** | 76 | 51.3% |

### Regime breakdown
| Window | Sharpe | Total |
|---|---|---|
| W1 2018-2019 | +0.12 | +0.50% |
| 2020 stress (Feb 19 → Apr 30) | +0.20 | +0.31% |
| W2 2020 full | −0.10 | −0.59% |
| **W4 2022 (binding test)** | **+0.63** | **+3.82%** |
| W5 2023-2024 | −1.01 | −4.16% |
| W6 2025-2026 | −0.49 | −1.34% |

### Trigger sweep
| Trigger | Full-sample Sharpe | 2020-Q1 | **2022** |
|---|---|---|---|
| V1 drawdown | +0.11 | +0.20 | **+0.81** |
| V2 rvol_spike | −0.20 | +0.48 | +0.22 |
| V3 below SMA | −0.05 | +0.45 | +0.69 |
| V4 union (V1 OR V2) | −0.08 | +0.20 | +0.63 |

**V1 drawdown-only trigger is the cleanest** — positive Sharpe standalone, 2022 +0.81. Used for integration test.

### Kill criteria (standalone)
| Criterion | Bar | Result | |
|---|---|---|---|
| Full-sample Sharpe > −0.50 | ≥ | −0.08 | PASS |
| MDD < 40% | ≥ | −12.24% | PASS |
| Trades ≥ 30 | ≥ | 76 | PASS |
| **2020-Q1 stress Sharpe > +1.5** | LB | +0.20 | **FAIL** |
| **2022 stress Sharpe > +0.5** | **LB (binding)** | **+0.63** | **PASS** |
| **Direction null-gap > +0.30** | LB | −0.13 | FAIL (mild) |
| 2024-2026 drag > −0.50 | ≥ | −0.93 | FAIL |

3 of 7 PASS standalone — MARGINAL. The 2022 binding-test PASS is the differentiator vs `fx_safe_haven`.

### Integration test (USD hedge added to deployed book at varying weights)

| hedge_w | Book Sharpe | CAGR | MDD% | Calmar | $end | hedge_$contrib |
|---|---|---|---|---|---|---|
| 0.00 (baseline) | +1.11 | +17.7% | −14.94% | 1.18 | $38,576 | $0 |
| 0.25 | +1.13 | +17.9% | −14.98% | 1.19 | $39,161 | −$15 |
| **0.50** | **+1.13** | **+18.1%** | **−15.01%** | **1.20** | **$39,678** | **−$70** |
| 0.75 | +1.12 | +18.2% | −15.05% | 1.21 | $40,124 | −$165 |
| 1.00 | +1.11 | +18.4% | −16.45% | 1.12 | $40,495 | −$302 |
| 1.50 | +1.05 | +18.5% | −20.51% | 0.90 | $41,007 | −$702 |

**Sweet spot is hedge_w=0.50 to 0.75**: Calmar peaks at 1.21, Sharpe slightly above baseline, equity gains $1,100-1,550 over baseline. Above 1.0 the calm-regime drag dominates.

### Stress-window comparison (hedge_w=0.50 vs baseline)
| Window | Baseline $pnl | Hedged $pnl | Delta | MDD change |
|---|---|---|---|---|
| 2020 COVID (Feb 19 → Apr 30) | +$5,524 | +$5,687 | **+$163** | **+2.45pp better** |
| **2022 bear** | **+$1,589** | **+$2,590** | **+$1,001 (+63%)** | −0.68pp worse |
| 2024-2026 calm | +$16,268 | +$16,157 | −$111 (drag) | −0.52pp worse |

The 2022 +$1,001 is the headline result. 2022 was the deployed book's worst historical drawdown regime; the USD hedge contributed nearly its full annual insurance budget in that single window.

### Hedge ↔ book correlation in each regime
| Window | corr(book, hedge) | book P&L | hedge P&L |
|---|---|---|---|
| 2020-Q1 stress | −0.235 | +$5,524 | −$219 |
| 2022 stress | −0.069 | +$1,589 | +$1,897 |
| 2024-2026 calm | −0.019 | +$16,268 | −$1,382 |

In 2022 both made money; the hedge wasn't perfectly negatively correlated but provided independent positive contribution exactly when the book was at its weakest absolute period. That's the deployment case.

## Mechanistic interpretation

The cross-experiment pattern across three attempts:
- short_tsmom: equity-side hedge — fails in QE-era (Fed-put makes drawdowns mean-revert)
- fx_safe_haven (JPY): works in COVID liquidity-shock, fails in 2022 rate-divergence
- **usd_safe_haven (USD): works in 2022 rate-divergence, partial in COVID liquidity-shock**

JPY and USD safe-haven hedges are **complementary across the two modern stress-regime types**. Neither alone is a complete hedge. The deployed book is more exposed to 2022-style regime (the 1099-day drawdown), so USD hedge is the better fit if forced to choose one.

The 2022 PASS isn't a coincidence — it's the structural consequence of Fed having higher policy rates than ECB/BoE/RBA/RBNZ during equity stress. As long as that asymmetry holds, USD-long during equity drawdowns earns its keep. If the asymmetry inverts (e.g., emergency Fed cuts during a future banking crisis), the hedge inverts too.

## Walk-forward result (the deciding test)

Train: 2018-01 → 2022-12 (5 years incl. COVID + 2022 bear)
Holdout: 2023-01 → 2026-04 (28 months, never touched)

| hedge_w | TRAIN Calmar | HOLDOUT Calmar | Delta |
|---|---|---|---|
| 0 (book only) | 0.96 | **2.55** | — |
| 0.25 | 1.01 | 2.40 | −0.15 |
| 0.50 (prior recommendation) | 1.06 | 2.26 | −0.29 |
| 0.75 (train-optimal) | 1.11 | 2.12 | −0.43 |
| 1.00 | 1.05 | 2.00 | −0.55 |
| 1.50 | 0.91 | 1.50 | −1.05 |

**Every non-zero hedge weight degrades holdout Calmar.** The train Calmar improvement was 2022-fitting; with that out of sample, the hedge is dead weight.

Dynamic scaling rules tested (proportional, binary-on-drawdown) all also underperform book-only on holdout.

## Recommendation

**DO NOT DEPLOY.** The walk-forward evidence is unambiguous — the prior MARGINAL recommendation was based on the full-sample integration test which was overfit to the 2022 stress event in-sample.

### What this means in practice for the deployed book

The book remains structurally long-risk-asset. Three independent attempts (`short_tsmom`, `fx_safe_haven`, `usd_safe_haven`) have failed to produce a deployable hedge against this exposure. The cross-experiment evidence (lessons #34/#35/#36) now strongly suggests that **a robust SPX-stress-triggered hedge from the Eightcap tradeable universe does not exist** for the current macro regime.

Three honest options remain:
1. **Accept the regime.** Keep the book as-is. Hold cash buffer outside the trading account to backstop a future stress that the backtest can't predict.
2. **Reduce sizing.** The `half_orb` configuration from the allocation_sweep walk-forward is robust OOS: train rank 3, holdout rank 8 but with MDD nearly halved (~-9%).
3. **Wait for new evidence.** If a future stress event occurs in live, re-evaluate USD-hedge then. The 2022 PASS could be real but the sample is N=1.

## Cross-experiment lesson (logged to RESEARCH_NOTES.md)

**Currency-haven property is bimodal in 2018+ data, with JPY and USD covering opposite stress regimes.** A complete hedge would need both. USD-hedge alone covers the 2022-style rate-divergence regime that destroyed the JPY-hedge attempt. The two are complementary, not redundant.

## Files

- Thesis: this doc
- Demo: `experiments/usd_safe_haven/usd_safe_haven_demo.py`
- Integration test: `experiments/usd_safe_haven/book_integration.py`
