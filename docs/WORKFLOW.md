# Strategy Development Workflow

Step-by-step pipeline for proposing → validating → deploying a strategy. Each phase has explicit **kill criteria**: conditions that cause the strategy to be rejected *at that stage* before investing more time.

The point of kill criteria up front is to avoid the "sunk cost" trap, every hour spent polishing a flawed thesis is an hour not spent on the next one.

---

## Phase 1, Thesis (before writing any code)

Write a one-page thesis document at `experiments/<strategy_name>/<strategy_name>.md` **before implementation**. Contents:

1. **Mechanism**: what market phenomenon does this try to capture? (e.g. "investor under-reaction to slow-moving news", "currency carry persistence", "post-earnings drift")
2. **Why retail-accessible**: why hasn't this been fully arbitraged at our scale/timeframe?
3. **Universe**: which instruments, what timeframe, what period
4. **Signal math**: how the signal is computed, in formula form
5. **Expected Sharpe range** from literature / analogous strategies
6. **Fail conditions** for this thesis (specific, pre-committed)

### Kill criteria at Phase 1

- **No credible mechanism** → reject. "This pattern looks good in the data" is not a mechanism.
- **No retail-accessibility argument** → reject. If the edge exists and we can see it from public data, someone with more capital and better infrastructure is already extracting it.
- **Literature says Sharpe < 0.3 at institutional scale** → reject. Retail drag (commission, slippage, execution) usually removes 0.2-0.4 Sharpe vs. institutional numbers. Starting from 0.3 means live 0.0.

---

## Phase 2, Minimum-viable implementation

Single-file pandas/numpy simulation in `experiments/<strategy_name>/<strategy_name>_demo.py`.

Keep it brutally simple:
- One universe (no subsetting)
- Fixed params (no optimization)
- Realistic costs (commission + slippage in bps)
- Full-period run 2015-2026

### Kill criteria at Phase 2

- **Sharpe < 0 on full sample** → reject. Don't optimize a losing strategy into a winning one; that's overfitting by another name.
- **Total return < buy-and-hold benchmark** → yellow flag (not automatic reject, but requires justification).
- **Trades < 50** over 11 years → reject. Not enough data points for any statistical claim about edge.
- **Max drawdown > 50%** → reject. You will not actually hold through this in real life.

---

## Phase 3, Statistical battery

Wire the existing validators from `backtesting.statistics`:

```python
from backtesting.statistics import compute_statistical_report

report = compute_statistical_report(
    equity_curve=eq,
    trades=trades,
    n_trials_tested=N,   # number of param combos you evaluated
    n_bootstrap=10_000,
    n_permutations=5_000,
    seed=42,
)
print(report)
```

This produces three tests:

| Test | Question | Pass criterion |
|---|---|---|
| **Bootstrap CI** | Is Sharpe distinguishable from zero? | 95% CI excludes 0 |
| **Permutation test** | Could random trades produce this Sharpe? | p < 0.05 |
| **Deflated Sharpe (Bailey & López de Prado 2014)** | Is this still significant after testing N params? | p < 0.05 |

### Kill criteria at Phase 3

- **Bootstrap 95% CI includes zero** → reject. Your observed Sharpe is not distinguishable from luck.
- **Permutation p > 0.05** → reject. Random trade directions could have produced this result.
- **Deflated Sharpe p > 0.05 for the number of configs you actually tested** → reject. You're reporting the max of N random draws.

**Common mistake:** reporting `n_trials=1` when you actually tried 50 lookback values before settling on one. Be honest about `n_trials_tested`, it's the count of configurations you evaluated during development, not per-script.

---

## Phase 4, Regime stability

Split the full period into 4 non-overlapping windows (each ~2.8 years). Run the strategy independently in each. Each window needs its own warmup (prepend prior bars to avoid cold-start).

### Kill criteria at Phase 4

- **Sharpe positive in ≤ 2/4 windows** → reject. Regime-dependent; will fail when regime changes.
- **One window drives > 80% of full-sample return** → reject. You caught one trend; the rest is noise.

---

## Phase 5, Parameter sensitivity

Hold all params fixed except one. Sweep each key param across a reasonable range. Target: Sharpe should be on a plateau, not a peak.

Typical sweeps:
- Lookback: ±40-50% around baseline
- Rebalance cadence: ±50%
- Threshold / z-score cutoffs: ±40%
- Position size / vol target: ±33%

### Kill criteria at Phase 5

- **Sharpe drops > 50% with ±20% param change** → reject. Strategy is fragile; you found a lucky island, not a signal.
- **Sharpe goes negative within the sweep range** → strong yellow flag. Verify the plateau boundary is wide enough for live drift.

---

## Phase 6, True holdout

Split: `train = 2015-01 to 2022-12`, `test = 2023-01 onward`. If you've developed the strategy on the full sample, the 2023+ period is your honest holdout. Report IS + OOS numbers separately.

Compute `degradation = IS_Sharpe - OOS_Sharpe`.

### Kill criteria at Phase 6

- **OOS Sharpe ≤ 0** → reject. Whatever edge existed in-sample didn't generalize.
- **Degradation > 0.5** → strong overfitting indicator. Reject unless you can explain it (e.g. regime change, documented).

Note: **negative degradation (OOS > IS)** is NOT automatic good news. It usually means the OOS period had a favorable regime. Flag it, don't celebrate it.

---

## Phase 7, Cross-strategy correlation (blending candidates only)

If the strategy survives through Phase 6, measure correlation of daily returns vs. existing live strategies.

### Decision criteria at Phase 7

- **Correlation < 0.3** → real diversifier. Consider adding to blend.
- **0.3 ≤ Correlation < 0.6** → weak diversifier. Only add if Sharpe > 0.5 standalone.
- **Correlation ≥ 0.6** → redundant. Don't blend; pick the higher-Sharpe one.

---

## Phase 8, Live deployment

Only reached if all prior phases pass.

1. **Port to MT5 EA** (`deploy/mq5/ea/<strategy_name>.mq5` for trading strategies, `deploy/mq5/services/<name>.mq5` for utility EAs).
2. **Backtest on QC**, confirm results match research within ~20%. Gaps usually come from universe differences or realistic costs. Document the gap.
3. **Paper trade 3-6 months**, real-time fills, real slippage, no capital at risk. Compare live equity curve to QC backtest.
4. **Go live small**, start at 10-20% of intended size. Monitor first drawdown carefully; psychology is the real failure mode.

### Kill criteria at Phase 8

- **MT5 backtest Sharpe < 50% of research Sharpe** → investigate before deploying. The universe/cost gap is eating the edge.
- **Paper trade diverges > 30% from MT5 backtest over 3 months** → something structural (timing, fills, data) is wrong. Don't go live.
- **First live drawdown > research max DD × 1.5** → strategy is operating in a worse regime than training. Pause and re-validate.

---

## Summary: the pipeline

```
Phase 1 Thesis          → no mechanism / retail-accessibility / Sharpe room
Phase 2 MVI             → Sharpe < 0 / <50 trades / DD > 50%
Phase 3 Stat battery    → Bootstrap CI hits 0 / permutation p>0.05 / DSR p>0.05
Phase 4 Regime          → positive in ≤2/4 windows / one-window-dominance
Phase 5 Param sens.     → Sharpe -50% on ±20% param / goes negative in range
Phase 6 True holdout    → OOS Sharpe ≤ 0 / degradation > 0.5
Phase 7 Correlation     → corr ≥ 0.6 with existing live strategies
Phase 8 Live            → MT5 Sharpe < 50% research / paper divergence > 30%
```

Each phase that kills a strategy saves the hours you would have spent on the next one.

---

## Where things live

| Kind | Location | Pattern |
|---|---|---|
| Thesis doc | `experiments/<name>/<name>.md` | One page, pre-implementation |
| Experiment sim (standalone) | `experiments/<name>/<name>_demo.py` | Pandas/numpy loop |
| Validation run | `experiments/<name>/<name>_validation.py` | Runs the phases above |
| Re-baseline after param search | `experiments/<name>/<name>_rebaseline.py` | IS-only grid search + honest holdout |
| Live algorithm (trading) | `deploy/mq5/ea/<name>.mq5` | MT5 EA |
| Data fetchers | `scripts/*.py` | CSV cache into `ohlc_data/` |
| Narrative | `docs/RESEARCH_NOTES.md` | Rolling log of what's been tried and learned |
| Vectorized signal fns (optional, for speed) | `experiments/<name>/` | Pure numpy→numpy function |

---

## Performance: custom vectorized signals without polluting the engine

When a research strategy starts needing thousands of parameter-sweep backtests, the event-driven `Backtester` becomes the bottleneck. The engine's `VectorizedBacktester` is ~50-500× faster but expects `(entries, sides, stops, tps)` numpy arrays as input. These arrays are the contract, where they come from is not the engine's concern.

### Pattern: research-repo-defined vectorized signals

Put the vectorized signal function in the research repo (not in `backtesting/vectorized_signals.py`), then feed its output arrays to the engine's runner.

```python
# experiments/tsmom/tsmom_signals.py
import numpy as np
from backtesting.indicators import atr_array  # engine primitives are fair game

def tsmom_signals(open, high, low, close, lookback_bars=252, skip_bars=21, ...):
    """Returns (entries, sides, stops, tps), all np.ndarray, len == len(close)."""
    # ... numpy logic
    return entries, sides, stops, tps
```

Usage in an experiment:

```python
from backtesting.vectorized import VectorizedBacktester
from experiments.tsmom.tsmom_signals import tsmom_signals

entries, sides, stops, tps = tsmom_signals(o, h, lo, c, lookback_bars=252)
eq = VectorizedBacktester(o, h, lo, c, starting_cash=100_000).run(
    entries, sides, stops, tps, risk_per_trade=0.02, cooldown_bars=0,
)
```

No plugin interface, no registration, no engine modification. The function is pure numpy→numpy and lives next to the research strategy it supports.

### Caveat: optimizer dispatch

The engine's `optimizer.optimize(..., engine="vectorized")` has hard-coded dispatch to the built-in vectorized signal functions (`trend_following_signals`, `momentum_signals`, etc.). It does NOT auto-discover research-defined signal functions. Two ways to get research-vectorized speed through an Optuna search:

1. **Use `engine="event"`**, the event-driven path accepts any `Strategy` subclass. Slower, but no adapter code needed.
2. **Write a custom Optuna objective**, skip the engine's optimizer wrapper entirely, write a ~30-line objective that calls your research signal fn + `VectorizedBacktester` inline. Fast AND research-owned.

Rule of thumb: if you're sweeping a research strategy with > 500 trials, it's worth writing the custom objective.
