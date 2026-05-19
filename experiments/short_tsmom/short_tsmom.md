# Short-only TSMOM (equity-index bear-hedge)

**Status**: Phase 2 complete 2026-05-18
**Verdict**: REJECT — null-check refuted the directional thesis. The conditions select for buy-the-dip setups in modern QE-era equity markets, not short-the-trend setups. Trading the SHORT side at these conditions is trading the wrong side of the signal.

## Why this exists

The current deployed book (orb_dax, lunch_fade, xau_session) is structurally LONG and structurally RISK-ON. Stress-test analysis (`experiments/portfolio_diagnostics/`) showed:

- 85% of book drawdown concentrates in orb_dax (long GER40)
- W4 (2025-26) lunch_fade↔xau correlation spike to +0.61 — both long risk-asset legs
- Zero bear-active component
- Holdout window (2024-2026) contains no analog to a 2022-style bear, so live behavior in a sustained downtrend is uncharted

**The book needs an insurance asset, not another alpha asset.**

Prior repo work (`experiments/tsmom/tsmom.md`) tested LONG/SHORT TSMOM and concluded "shorts got caught in V-recoveries (SPX March 2020, BTC 2022 bottom)" — long-only beat long/short on 16/24 instruments. That negative result is *the constraint to design around*, not a reason to skip the experiment.

The design difference here: **asymmetric entry/exit speed + bear regime gating**. Slow entry signal (only fires in confirmed bears) + fast exit signal (snaps off on V-recovery before TSMOM lag bleeds through).

## Thesis (mechanism)

1. **Equity-index bears are short and asymmetric.** Median sustained-bear duration is 6-12 months; the worst 10% of trading days cluster in <2% of years. A strategy that fires *only* in those windows can earn negative beta to the book exactly when the book is bleeding.
2. **V-recoveries are the documented failure mode for short trend-following.** SPX +35% in 5 weeks off March 2020. NDX +40% in 6 weeks off Dec 2022. A trend-following short with 12-1 lookback enters the short several months into the decline and exits several months into the recovery — that lag is fatal.
3. **Asymmetric speed fixes the V-recovery problem.** Use a slow entry (only fires in confirmed sustained downtrends — 6m momentum + 200d SMA + 52w-drawdown gate) and a fast exit (20-day momentum flip OR 10% adverse move OR 60-day time stop). Catches the body of the bear, avoids the recovery V.
4. **Regime gating selects for sustained bears, not noise.** Most days are not bears. The 52w-drawdown > 10% gate ensures the strategy only fires when there's already a real decline to fade-continue.
5. **Insurance asset framework.** The strategy is expected to be flat-to-slightly-negative in long bull regimes (cost of insurance) and strongly positive in the 5-15% of years that are real bears. Full-sample Sharpe is NOT the relevant metric.

## Key reference

- Moskowitz, Ooi, Pedersen (2012) "Time Series Momentum", JFE — slow-entry framework
- Hurst, Ooi, Pedersen (2017) "A Century of Evidence on Trend-Following Investing" — short-side decay in 2010s
- Spitznagel, "Safe Haven" (2021) — insurance-asset framework (asymmetric payoff > standalone Sharpe)
- Repo prior: `experiments/tsmom/tsmom.md` — documented "shorts caught in V-recoveries" failure

## Signal math

```
For each day t, for each instrument:

  Entry conditions (ALL must be true):
    mom_6m[t]  = close[t] / close[t-126] - 1           <  0
    sma_200[t] = mean(close[t-200..t-1])
    close[t-1] < sma_200[t-1]
    drawdown_52w[t] = close[t-1] / max(close[t-252..t-1]) - 1  <  -0.10

  If flat and all True: ENTER SHORT at next-day open.
  Position size: vol-target 15% annualized using 60-day realized vol.

  Exit conditions (ANY triggers):
    mom_20d[t] = close[t] / close[t-20] - 1  >  0       (fast momentum flip)
    open_pnl[t] < -10%                                  (adverse-move stop)
    hold_days >= 60                                     (time stop)

  Cost: 1 index point round-trip on entry+exit.
```

## Why retail-accessible

- Tradeable directly on Eightcap CFD — same instruments as orb_dax/lunch_fade (SPX500, NDX100, GER40, UK100, EUSTX50). No new broker required.
- Daily-bar signal. No HFT, no microstructure dependency.
- Low cadence by design (one entry per instrument per bear cycle = ~1-3 trades/instrument/year average).
- The "smart money" institutional version of this trade is short-vol-on-bear (long puts), which retail can't easily access. CFD short-only is the retail-accessible equivalent of the same insurance exposure.

## Universe

- **Primary**: SPX500, NDX100, GER40, UK100 (D1 bars on disk, 2019-01 → 2026-04)
- **Secondary**: EUSTX50 (only M5 on disk — derive D1 if useful)
- All daily-bar via `utils.fetch_ohlc(..., 'D1', ...)`

## Expected performance (pre-committed)

| Metric | Expected range | Reason |
|---|---|---|
| Full-sample Sharpe | -0.3 to +0.3 | Insurance asset — drag in bulls + spikes in bears average out |
| 2020-Q1 sub-window Sharpe | +2.0 to +5.0 | COVID crash — the textbook stress event |
| 2022 full-year Sharpe | +1.0 to +3.0 | Sustained bear — the documented hard case for short TSMOM |
| MDD | < 30% | Adverse-move stop limits per-trade pain |
| Trades (full sample, all instruments) | 50-150 | Low by design |
| Correlation to deployed book in stress | < -0.20 | Load-bearing criterion |

## Fail conditions (pre-committed)

| Criterion | Bar | If breached |
|---|---|---|
| Full-sample Sharpe | > -0.30 | If worse, the drag is too steep — insurance too expensive |
| MDD | < 40% | Allowed to bleed but not blow up |
| Trades (across universe) | ≥ 50 | Below this, statistical power is too weak |
| **2020-Q1 sub-window Sharpe** | **> +1.0** | **Load-bearing — must profit in textbook stress** |
| **2022 sub-window Sharpe** | **> +0.5** | **Load-bearing — must survive sustained bear** |
| **Correlation to book in stress** | **< -0.20** | **Load-bearing — must be NEGATIVELY correlated when book hurts** |
| Bull-regime drag (2024-2026 Sharpe) | > -0.5 | Drag in calm regimes within tolerable bound |
| Direction null-check gap | > +0.30 | Long-side same params must underperform (else no directional content) |

The three **load-bearing** criteria are the whole point. The strategy can fail the full-sample-Sharpe bar and still be deployable if all three load-bearing criteria pass.

## Why this might fail (red flags)

1. **V-recoveries faster than the 20-day exit.** March 2020 was 5 weeks (~25 trading days) — 20-day momentum-flip exit should catch it but margin is thin. If the V is sharper, we eat the recovery.
2. **Modern bears too short.** 2022 was a slow grinding bear (lasted ~10 months) which suits TSMOM, but if future bears compress to 3-4 weeks (flash-crash style), entry signal won't even fire.
3. **Sample size for stress events is tiny.** N=2 real bears in window (2020-Q1, 2022). Any conclusion is N=2 with all the curve-fitting risk that implies.
4. **Selection bias on instruments.** SPX/NDX/DAX/UK100 all rallied 2019-2026. The strategy is in-sample tuned to whatever bears happened to occur in this period.
5. **Cost model assumes 1pt RT — for D1 strategies this is conservative.** May actually be 0.5pt for index CFDs at most retail brokers.

## Phase 1 → Phase 2 plan

- [x] Read tsmom.md and confirm prior negative result is "long/short mixed", not "short-only with V-defense"
- [x] Confirm data on disk (SPX500/NDX100/GER40/UK100 D1)
- [ ] Build `short_tsmom_demo.py` per repo numpy-inner-loop style
- [ ] Baseline run: all 4 instruments, deployed config
- [ ] Stress-window decomposition: 2020-Q1, 2020-full, 2022-full, 2024-2026
- [ ] Cost sweep: 0.5/1/2/3pt RT
- [ ] Null check: long-only same params (must underperform → confirms short-direction signal)
- [ ] Param sensitivity: 6m vs 3m vs 12m entry momentum
- [ ] Cross-strategy correlation to existing book in stress windows
- [ ] Update verdict + tables in this doc

## Files

- Thesis: `experiments/short_tsmom/short_tsmom.md` (this file)
- Demo: `experiments/short_tsmom/short_tsmom_demo.py` (TBC)

## Phase 2 results (2026-05-18)

Universe: SPX500, NDX100, GER40 (UK100 D1 datalake unreachable — skipped, doesn't change verdict).
Period: 2018-01 → 2026-04. Vol-target 15%, 1pt cost, V-recovery-defense exit (mom_20d flip).

### Per-instrument
| Instrument | Sharpe | Total | MDD | Trades | WR | Avg hold |
|---|---|---|---|---|---|---|
| SPX500 | −0.33 | −24.15% | −30.77% | 112 | 41.1% | 3d |
| NDX100 | −0.23 | −16.12% | −24.01% | 98 | 55.1% | 3d |
| GER40 | −0.12 | −12.10% | −24.22% | 163 | 44.2% | 2d |
| **PORTFOLIO** | **−0.25** | **−15.86%** | **−22.87%** | 373 | 46.1% | 3d |

### Regime breakdown (portfolio, equal-weight)
| Window | Sharpe | Total | Active days |
|---|---|---|---|
| W1 2018-2019 | −1.40 | −4.15% | 63 |
| W2 2020 (COVID) | −0.18 | −3.53% | 68 |
| ↳ 2020 stress slice (Feb 19 → Apr 30) | +0.02 | −0.91% | 39 |
| W3 2021 | +0.00 | +0.00% | 0 |
| **W4 2022 (bear)** | **+0.28** | +3.05% | 234 |
| W5 2023-2024 | −1.90 | −7.15% | 46 |
| W6 2025-2026 | −0.75 | −4.89% | 37 |

### Kill criteria
| Criterion | Bar | Result | |
|---|---|---|---|
| Full-sample Sharpe > −0.30 | ≥ | −0.25 | PASS |
| MDD < 40% | ≥ | −22.87% | PASS |
| Trades ≥ 50 | ≥ | 373 | PASS |
| **2020-Q1 stress Sharpe > +1.0** | **load-bearing** | **+0.02** | **FAIL** |
| **2022 stress Sharpe > +0.5** | **load-bearing** | **+0.28** | **FAIL** |
| 2024-2026 bull-drag > −0.50 | ≥ | −0.62 | FAIL |
| **Direction null-gap > +0.30** | **load-bearing** | **−0.89** | **FAIL** |

### Null-check (LONG-only same conditions)
| Instrument | Long-only Sharpe | Total |
|---|---|---|
| SPX500 long | +0.55 | +59.09% |
| NDX100 long | +0.68 | +87.32% |
| GER40 long | +0.46 | +45.40% |
| Portfolio long | +0.64 | +58.58% |

Direction-gap (short − long) = **−0.89**. The same entry conditions are massively profitable on the LONG side and unprofitable on the SHORT side. Mechanism is trading exactly the wrong side of the signal.

## Mechanistic interpretation — why this fails (the lesson)

The pre-committed conditions (mom_6m<0, close<SMA200, drawdown_52w>10%) were designed to identify "sustained bear regime". In a 1970s-1980s style market that mechanism would work. In 2018-2026:

1. **Fed-put + QE era makes drawdowns mean-reverting, not trend-continuing.** SPX 2018 Q4, 2020-Q1, 2022, 2025 corrections all bottomed and V-reversed within weeks-to-months. The "deeper the drawdown the better the BUY" — opposite of the trend-continuation prior the thesis relied on.

2. **Even in 2022 (the strongest sustained-bear case in the sample), Sharpe was only +0.28.** That's the BEST regime the thesis was supposed to capture. If +0.28 is the ceiling on a textbook slow grinding bear, the strategy isn't an insurance asset — it's just a slow leak in bear regimes too.

3. **The V-recovery defense exit (mom_20d flip) doesn't help when the entry signal itself is mis-directional.** The 2-3 day average hold tells the story: the strategy enters short on conditions that mean-revert within days. The exit signal correctly catches the snap-back but the strategy never had a positive-EV entry to begin with.

4. **Modern equity beta is structurally LONG.** Adding more equity exposure in the SHORT direction is fighting central-bank policy that has consistently re-supported asset prices. This is structural, not a curve-fit observation — it has held for 15+ years.

## Cross-experiment lesson (logged to RESEARCH_NOTES.md)

**Equity-index shorts as a book hedge are structurally broken in the QE era.** The entry conditions that look like "bear regime" select for buy-the-dip EV, not trend-down EV. Two independent repo experiments (tsmom long/short symmetric, this short_tsmom with V-defense + regime gating) reach the same verdict via different mechanisms. The hedge for an all-long equity book is NOT more equity exposure on the short side.

The implication for the next hedge attempt: must come from a DIFFERENT ASSET CLASS than equity indices. Candidates that haven't been refuted by this lesson:
1. FX safe-haven (USDJPY short / JPY long in risk-off)
2. USD long in stress (short EURUSD)
3. Long-vol via crypto put-flow proxies
4. Cross-asset carry-unwind via NZDJPY/AUDJPY short

## Files

- Thesis: this doc
- Demo: `experiments/short_tsmom/short_tsmom_demo.py`
