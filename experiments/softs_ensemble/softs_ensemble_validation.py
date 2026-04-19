#!/usr/bin/env python3
"""
Softs TSMOM ensemble -- Phase 3 statistical battery.

Three questions per docs/WORKFLOW.md Phase 3:
  1. Bootstrap 95% CI on blend Sharpe -- does it exclude zero?
  2. Position-shuffle permutation -- does coordinated timing beat random
     timing at the same marginal weight distribution?
  3. Deflated Sharpe (Bailey & Lopez de Prado 2014) -- adjusted for the
     number of configurations we evaluated.

n_trials_tested = 12 (the number of candidate instruments screened to
find the 6 ensemble survivors). Parameter set itself (LOOKBACKS=(21,63,252),
vol_target 15%, pyramid K=3/atr=1.0/cap=1.0) was inherited from the
gold/BTC work and not re-tuned on softs.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'gold_trend'))

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)
from backtesting.statistics import compute_statistical_report, compute_sharpe


# --------------------------------------------------------------------------
# Config (matches softs_ensemble_demo.py survivors)
# --------------------------------------------------------------------------

ENSEMBLE = ["COCOA", "COFFEE", "COTTON", "CORN", "SOYBEAN", "LIVE_CATTLE"]
COST_BPS_PER_SIDE = 5.0
START = "2015-01-01"
END = "2026-04-18"
N_TRIALS_TESTED = 12  # number of candidate instruments screened

N_BOOTSTRAP = 10_000
N_PERMUTATIONS = 5_000


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def run_one_leg(sym: str) -> dict | None:
    df = load_series(sym)
    if df is None:
        return None
    df = df.loc[START:END]
    close, high, low = df["close"], df["high"], df["low"]
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)
    strat_ret, stats = simulate_tsmom_pyramid(
        close, sig, rv, atr, sym,
        long_only=True, cost_bps_per_side=COST_BPS_PER_SIDE,
    )
    return {"sym": sym, "ret": strat_ret, "stats": stats, "index": close.index}


def main() -> int:
    section("Running per-instrument strategy legs")
    legs: dict[str, dict] = {}
    for sym in ENSEMBLE:
        r = run_one_leg(sym)
        if r is None:
            print(f"  {sym}: load failed")
            return 1
        legs[sym] = r
        print(f"  {sym:<14s} bars={len(r['ret'])}  "
              f"Sharpe={annualized_sharpe(r['ret'].to_numpy()):+.2f}  "
              f"trades={r['stats']['trades']}")

    # Align all legs on the common index and build the blend.
    section("Building equal-weight blend")
    df_strat = pd.concat(
        [legs[s]["ret"].rename(s) for s in ENSEMBLE], axis=1, join="inner"
    ).dropna()
    blend = df_strat.mean(axis=1).rename("softs-blend")
    equity = (1.0 + blend).cumprod().to_numpy()
    obs_sharpe = compute_sharpe(equity)
    print(f"  Aligned bars   : {len(blend):,}")
    print(f"  Period         : {blend.index[0].date()} -> {blend.index[-1].date()}")
    print(f"  Blend Sharpe   : {obs_sharpe:+.4f}")
    print(f"  Blend CAGR     : {((equity[-1]) ** (252 / len(equity)) - 1) * 100:+.2f}%")
    print(f"  Blend MDD      : {max_drawdown(equity) * 100:+.2f}%")

    # ======================================================================
    # [1] Bootstrap CI on Sharpe
    # ======================================================================
    section(f"[1] Bootstrap 95% CI on Sharpe ({N_BOOTSTRAP:,} resamples)")
    report = compute_statistical_report(
        equity_curve=equity,
        trades=[],
        n_trials_tested=N_TRIALS_TESTED,
        n_bootstrap=N_BOOTSTRAP,
        n_permutations=N_PERMUTATIONS,
        seed=42,
    )
    ci = report.bootstrap_ci
    ci_pass = ci.significant
    print(f"  observed Sharpe    : {ci.observed_sharpe:+.4f}")
    print(f"  95% CI             : [{ci.ci_lower:+.4f}, {ci.ci_upper:+.4f}]")
    print(f"  CI excludes zero   : {'PASS' if ci_pass else 'FAIL'}")

    # ======================================================================
    # [2] Position-shuffle permutation (per-leg independent shuffle, rebuild
    #     blend). Tests whether the JOINT timing of all legs beats random
    #     timing at the same marginal weight distributions.
    # ======================================================================
    section(f"[2] Position-shuffle permutation ({N_PERMUTATIONS:,} perms)")
    print("  Per-leg independent weight shuffle. Preserves each leg's")
    print("  marginal weight distribution and actual returns; destroys")
    print("  the timing match between signal and instrument return.\n")

    # Pre-align each leg's weight array + returns on the common index so
    # we can shuffle and re-blend consistently.
    common_idx = blend.index
    leg_data = {}
    for sym in ENSEMBLE:
        leg = legs[sym]
        w_full = pd.Series(leg["stats"]["w"], index=leg["index"])
        r_full = pd.Series(leg["stats"]["ret"], index=leg["index"])
        # Align to common index.
        w = w_full.reindex(common_idx).fillna(0.0).to_numpy()
        r = r_full.reindex(common_idx).fillna(0.0).to_numpy()
        leg_data[sym] = {"w": w, "r": r}

    rng = np.random.default_rng(42)
    cost_rate = COST_BPS_PER_SIDE * 1e-4
    n_leg = len(ENSEMBLE)

    # Re-compute observed blend Sharpe from the same (aligned) leg series
    # so null comparison is consistent.
    obs_blend = np.zeros(len(common_idx))
    for sym in ENSEMBLE:
        w = leg_data[sym]["w"]
        r = leg_data[sym]["r"]
        dw = np.abs(np.diff(w, prepend=0.0))
        leg_net = w * r - dw * cost_rate
        obs_blend += leg_net
    obs_blend = obs_blend / n_leg
    obs_eq = np.cumprod(1.0 + obs_blend)
    obs_sh = compute_sharpe(obs_eq)

    null_sharpes = np.empty(N_PERMUTATIONS)
    for i in range(N_PERMUTATIONS):
        null_blend = np.zeros(len(common_idx))
        for sym in ENSEMBLE:
            w_shuf = rng.permutation(leg_data[sym]["w"])
            r = leg_data[sym]["r"]
            dw = np.abs(np.diff(w_shuf, prepend=0.0))
            leg_net = w_shuf * r - dw * cost_rate
            null_blend += leg_net
        null_blend = null_blend / n_leg
        null_eq = np.cumprod(1.0 + null_blend)
        null_sharpes[i] = compute_sharpe(null_eq)

    perm_p = float(np.mean(null_sharpes >= obs_sh))
    perm_pass = perm_p < 0.05
    print(f"  observed Sharpe    : {obs_sh:+.4f}")
    print(f"  null Sharpe mean   : {null_sharpes.mean():+.4f}")
    print(f"  null Sharpe std    : {null_sharpes.std():.4f}")
    print(f"  null Sharpe p95    : {np.percentile(null_sharpes, 95):+.4f}")
    print(f"  null Sharpe max    : {null_sharpes.max():+.4f}")
    print(f"  p(null >= observed): {perm_p:.4f}")
    print(f"  p < 0.05           : {'PASS' if perm_pass else 'FAIL'}")

    # ======================================================================
    # [3] Deflated Sharpe
    # ======================================================================
    section(f"[3] Deflated Sharpe (n_trials_tested={N_TRIALS_TESTED})")
    dsr = report.deflated_sharpe
    if dsr is None:
        print("  skipped (n_trials<=1 or empty curve)")
        dsr_pass = False
    else:
        dsr_pass = dsr.significant
        print(f"  observed Sharpe    : {dsr.observed_sharpe:+.4f}")
        print(f"  deflated Sharpe    : {dsr.deflated_sharpe:+.4f}")
        print(f"  n_trials_tested    : {dsr.n_trials_tested}")
        print(f"  p-value            : {dsr.p_value:.4f}")
        print(f"  p < 0.05           : {'PASS' if dsr_pass else 'FAIL'}")

    # ======================================================================
    # Verdict
    # ======================================================================
    section("Phase 3 verdict")
    print(f"  Bootstrap CI excludes 0  : {'PASS' if ci_pass else 'FAIL'}  "
          f"[{ci.ci_lower:+.4f}, {ci.ci_upper:+.4f}]")
    print(f"  Permutation p < 0.05     : {'PASS' if perm_pass else 'FAIL'}  "
          f"(p={perm_p:.4f})")
    if dsr is not None:
        print(f"  Deflated Sharpe p < 0.05 : {'PASS' if dsr_pass else 'FAIL'}  "
              f"(p={dsr.p_value:.4f})")

    phase3_pass = ci_pass and perm_pass and (dsr_pass if dsr is not None else False)
    print()
    if phase3_pass:
        print("  Phase 3 OVERALL: PASS -- edge is not luck. Proceed to Phase 4.")
    else:
        print("  Phase 3 OVERALL: FAIL -- at least one stat test rejected.")
    return 0 if phase3_pass else 1


if __name__ == "__main__":
    sys.exit(main())
