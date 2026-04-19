#!/usr/bin/env python3
"""
BTCUSD trend following (MH-LO + pyramid) -- Phase 2/3/4/5/6 validation.

Thesis: experiments/btc_trend/btc_trend.md

Rebuilds the scan-winning config at HONEST retail BTCUSD CFD costs
(10 bps/side, vs 5 bps used in the scan), then runs the statistical,
regime-stability, parameter-sensitivity, and holdout batteries.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'gold_trend'))  # simulator reuse

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    PYRAMID_STEPS, PYRAMID_ATR_MULT,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid, simulate_tsmom,
)
from backtesting.statistics import compute_statistical_report, compute_sharpe


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

SYMBOL = "BTCUSD"
START = "2018-01-01"
END = "2026-04-18"
COST_BPS_HONEST = 10.0    # BTCUSD CFD realistic spread (vs 5 bps scan)

# n_trials counted honestly:
#   26 instruments in the scan
#   +  9 pyramid configs tested on gold (assumed applicable to BTC)
#   = 35
N_TRIALS_TESTED = 35


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def metrics(r: pd.Series) -> dict:
    eq = (1.0 + r).cumprod().to_numpy()
    years = (r.index[-1] - r.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(r.to_numpy())
    mdd = max_drawdown(eq)
    return {"years": years, "total": total, "cagr": cagr,
            "sharpe": sh, "mdd": mdd, "n_bars": len(r)}


def run_btc(
    close: pd.Series, high: pd.Series, low: pd.Series,
    cost_bps: float = COST_BPS_HONEST,
    steps: int = PYRAMID_STEPS, atr_mult: float = PYRAMID_ATR_MULT,
    max_units: int | None = None,
) -> tuple[pd.Series, dict]:
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)
    return simulate_tsmom_pyramid(
        close, sig, rv, atr, "BTC-MH-LO-P",
        long_only=True, steps=steps, atr_mult=atr_mult, max_units=max_units,
        cost_bps_per_side=cost_bps,
    )


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    section(f"Loading {SYMBOL}")
    df = load_series(SYMBOL)
    if df is None:
        print(f"Missing {SYMBOL} data; abort.")
        return 1
    close, high, low = df["close"], df["high"], df["low"]
    print(f"  {SYMBOL:<8s} {len(df):>5,} bars  "
          f"{df.index[0].date()} -> {df.index[-1].date()}  "
          f"({(df.index[-1] - df.index[0]).days / 365.25:.1f} years)")

    # ======================================================================
    # Phase 2 -- MVI at honest BTC CFD costs
    # ======================================================================
    section("Phase 2 -- MVI at 10 bps/side (honest BTCUSD CFD)")
    ret_strat, stats = run_btc(close, high, low, cost_bps=COST_BPS_HONEST)
    m = metrics(ret_strat)
    bh = close.pct_change().fillna(0.0)
    bh_m = metrics(bh)
    print(f"  strategy      : CAGR {m['cagr'] * 100:+6.2f}%  Sharpe {m['sharpe']:+.2f}  "
          f"MDD {m['mdd'] * 100:+6.2f}%  trades {stats['trades']}")
    print(f"  buy & hold    : CAGR {bh_m['cagr'] * 100:+6.2f}%  Sharpe {bh_m['sharpe']:+.2f}  "
          f"MDD {bh_m['mdd'] * 100:+6.2f}%")
    alpha_sh = m['sharpe'] - bh_m['sharpe']
    print(f"  alpha vs B&H  : {alpha_sh:+.2f} Sharpe")

    # Phase 2 kill: we tighten the Sharpe bar from 0.30 to 0.50 per thesis,
    # and also require alpha >= +0.10 vs B&H.
    p2_sharpe = m['sharpe'] > 0.50
    p2_mdd = abs(m['mdd']) < 0.30
    p2_trades = stats['trades'] >= 50
    p2_alpha = alpha_sh >= 0.10
    def v(c: bool) -> str: return "PASS" if c else "FAIL"
    print(f"\n  Sharpe > 0.50            : {v(p2_sharpe)}  ({m['sharpe']:+.2f})")
    print(f"  MDD < 30%                : {v(p2_mdd)}  ({m['mdd'] * 100:+.2f}%)")
    print(f"  Trades >= 50             : {v(p2_trades)}  ({stats['trades']})")
    print(f"  Alpha vs B&H >= +0.10    : {v(p2_alpha)}  ({alpha_sh:+.2f})")
    if not (p2_sharpe and p2_mdd and p2_trades and p2_alpha):
        print("\n  Phase 2 OVERALL: FAIL -- at honest costs, edge is gone.")
        return 1
    print("\n  Phase 2 OVERALL: PASS -- proceeding to Phase 3.")

    # ======================================================================
    # Phase 3 -- Statistical battery
    # ======================================================================
    section(f"Phase 3 -- Stat battery (n_trials_tested={N_TRIALS_TESTED})")
    equity = (1.0 + ret_strat).cumprod().to_numpy()
    observed_sharpe = compute_sharpe(equity)
    report = compute_statistical_report(
        equity_curve=equity,
        trades=[],  # use return-shuffle internally (we run a position-shuffle below)
        n_trials_tested=N_TRIALS_TESTED,
        n_bootstrap=10_000,
        n_permutations=5_000,
        seed=42,
    )

    # [1] Bootstrap CI
    ci = report.bootstrap_ci
    ci_pass = ci.significant
    print("  [1] Bootstrap 95% CI on annualized Sharpe")
    print(f"      observed Sharpe    : {ci.observed_sharpe:+.4f}")
    print(f"      95% CI             : [{ci.ci_lower:+.4f}, {ci.ci_upper:+.4f}]")
    print(f"      CI excludes zero   : {v(ci_pass)}")
    print()

    # [2] Position-shuffle permutation -- the proper null for continuous-weight
    #     strategies (shuffle WHEN we hold each weight; preserve marginal
    #     weight distribution and actual returns).
    rng = np.random.default_rng(42)
    w_real = stats['w']
    ret_arr = stats['ret']
    cost_rate = stats['cost_bps_per_side'] * 1e-4

    observed_net = w_real * ret_arr - np.abs(np.diff(w_real, prepend=0.0)) * cost_rate
    observed_eq = np.cumprod(1.0 + observed_net)
    observed_sh_2 = compute_sharpe(observed_eq)

    N_PERMS = 5000
    null_sharpes = np.empty(N_PERMS)
    for i in range(N_PERMS):
        w_shuf = rng.permutation(w_real)
        dw_shuf = np.abs(np.diff(w_shuf, prepend=0.0))
        net_shuf = w_shuf * ret_arr - dw_shuf * cost_rate
        eq_shuf = np.cumprod(1.0 + net_shuf)
        null_sharpes[i] = compute_sharpe(eq_shuf)
    perm_p = float(np.mean(null_sharpes >= observed_sh_2))
    perm_pass = perm_p < 0.05
    print("  [2] Position-shuffle permutation (shuffle weight timing;")
    print("      preserve marginal weight distribution and actual returns)")
    print(f"      observed Sharpe    : {observed_sh_2:+.4f}")
    print(f"      null Sharpe mean   : {null_sharpes.mean():+.4f}")
    print(f"      null Sharpe p95    : {np.percentile(null_sharpes, 95):+.4f}")
    print(f"      p(null >= observed): {perm_p:.4f}")
    print(f"      p < 0.05           : {v(perm_pass)}")
    print()

    # [3] Deflated Sharpe
    dsr = report.deflated_sharpe
    if dsr is None:
        print("  [3] Deflated Sharpe: skipped (n_trials<=1 or empty curve)")
        dsr_pass = False
    else:
        dsr_pass = dsr.significant
        print("  [3] Deflated Sharpe (Bailey & Lopez de Prado 2014)")
        print(f"      observed Sharpe    : {dsr.observed_sharpe:+.4f}")
        print(f"      deflated Sharpe    : {dsr.deflated_sharpe:+.4f}")
        print(f"      n_trials_tested    : {dsr.n_trials_tested}")
        print(f"      p-value            : {dsr.p_value:.4f}")
        print(f"      p < 0.05           : {v(dsr_pass)}")
    print()

    phase3_pass = ci_pass and perm_pass and dsr_pass
    if not phase3_pass:
        print("  Phase 3 OVERALL: FAIL -- at least one stat test rejected.")
        return 1
    print("  Phase 3 OVERALL: PASS -- proceeding to Phase 4.")

    # ======================================================================
    # Phase 4 -- Regime stability (4 non-overlapping windows)
    # ======================================================================
    section("Phase 4 -- Regime stability (4 non-overlapping windows)")
    print("  Each window gets a 252-bar warmup prepended from prior data.\n")
    WINDOWS = [
        ("W1 2018-2019 (crypto winter)    ", "2018-01-01", "2019-12-31"),
        ("W2 2020-2021 (bull + parabola) ", "2020-01-01", "2021-12-31"),
        ("W3 2022-2023 (2022 bear -> thaw)", "2022-01-01", "2023-12-31"),
        ("W4 2024-2025 (post-halving run) ", "2024-01-01", "2026-04-18"),
    ]
    print(f"  {'window':<34s} {'bars':>5s} {'trades':>7s} "
          f"{'ret':>9s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    window_results = []
    for wname, ws, we in WINDOWS:
        ws_ts = pd.Timestamp(ws, tz="UTC")
        we_ts = pd.Timestamp(we, tz="UTC")
        pos_s = close.index.searchsorted(ws_ts)
        pos_e = min(close.index.searchsorted(we_ts, side="right"), len(close))
        warm_s = max(0, pos_s - max(LOOKBACKS))
        sub_close = close.iloc[warm_s:pos_e]
        sub_high = high.iloc[warm_s:pos_e]
        sub_low = low.iloc[warm_s:pos_e]
        wr, ws_stats = run_btc(sub_close, sub_high, sub_low, cost_bps=COST_BPS_HONEST)
        wr_window = wr.loc[ws:we]
        if len(wr_window) < 50:
            print(f"  {wname:<34s} <no data>")
            continue
        wm = metrics(wr_window)
        window_results.append({"name": wname.strip(), **wm, "trades": ws_stats['trades']})
        print(f"  {wname:<34s} {wm['n_bars']:>5d} {ws_stats['trades']:>7d} "
              f"{wm['total'] * 100:>+8.2f}% {wm['cagr'] * 100:>+7.2f}% "
              f"{wm['sharpe']:>+7.2f} {wm['mdd'] * 100:>+7.2f}%")

    positive_windows = sum(1 for w in window_results if w["sharpe"] > 0)
    total_ret_sum = sum(w["total"] for w in window_results)
    max_share = 0.0
    if abs(total_ret_sum) > 1e-9:
        max_share = max(abs(w["total"]) / abs(total_ret_sum) for w in window_results)
    p4_sharpe = positive_windows >= 3
    p4_dom = max_share < 0.80
    print()
    print(f"  Windows with Sharpe > 0 : {positive_windows}/4  ({v(p4_sharpe)} -- need >= 3)")
    print(f"  Max single-window share : {max_share * 100:.1f}%  ({v(p4_dom)} -- need < 80%)")
    phase4_pass = p4_sharpe and p4_dom
    print()
    if not phase4_pass:
        print("  Phase 4 OVERALL: FAIL -- regime-dependent.")
        return 1
    print("  Phase 4 OVERALL: PASS -- proceeding to Phase 5.")

    # ======================================================================
    # Phase 5 -- Parameter sensitivity
    # ======================================================================
    section("Phase 5 -- Parameter sensitivity (plateau vs peak)")
    baseline_sh = m['sharpe']
    print(f"  Baseline (K=3 atr=1.0 cap=1.00x lookbacks=(21,63,252) rebal=21 vt=0.15)")
    print(f"  Baseline Sharpe = {baseline_sh:+.3f}\n")

    def sweep_run(
        fn: Callable[[], tuple[pd.Series, dict]],
    ) -> tuple[float, int, float]:
        r, s = fn()
        em = metrics(r)
        return em['sharpe'], s['trades'], em['mdd']

    # Sweep 1: pyramid cap (1.00x, 1.33x, 1.67x, 2.00x)
    print("  [Sweep 1] Pyramid cap (max_units / K)")
    print(f"  {'cap':>6s} {'Sharpe':>7s} {'trades':>7s} {'MDD':>8s}  {'vs-base':>9s}")
    sw1 = []
    for mu in (3, 4, 5, 6):
        sh, tr, mdd = sweep_run(lambda mu=mu: run_btc(close, high, low, max_units=mu))
        cap = mu / PYRAMID_STEPS
        mark = " <<" if mu == 3 else ""
        print(f"  {cap:>5.2f}x {sh:>+7.3f} {tr:>7d} {mdd * 100:>+7.2f}%  "
              f"{(sh / baseline_sh - 1) * 100:>+8.1f}%{mark}")
        sw1.append(sh)

    # Sweep 2: ATR multiplier (0.5, 1.0, 1.5, 2.0)
    print("\n  [Sweep 2] Pyramid ATR trigger")
    print(f"  {'atr_mult':>8s} {'Sharpe':>7s} {'trades':>7s} {'MDD':>8s}  {'vs-base':>9s}")
    sw2 = []
    for amul in (0.5, 1.0, 1.5, 2.0):
        sh, tr, mdd = sweep_run(lambda amul=amul: run_btc(close, high, low, atr_mult=amul))
        mark = " <<" if abs(amul - 1.0) < 1e-6 else ""
        print(f"  {amul:>8.2f} {sh:>+7.3f} {tr:>7d} {mdd * 100:>+7.2f}%  "
              f"{(sh / baseline_sh - 1) * 100:>+8.1f}%{mark}")
        sw2.append(sh)

    # Sweep 3: lookback structure
    print("\n  [Sweep 3] Lookback structure")
    print(f"  {'lookbacks':<22s} {'Sharpe':>7s} {'trades':>7s} {'MDD':>8s}  {'vs-base':>9s}")
    sw3 = []
    lookback_variants = [
        ((63,),             "3M only"),
        ((252,),            "12M only"),
        ((21, 252),         "1M+12M"),
        ((21, 63, 252),     "1M+3M+12M (baseline)"),
        ((21, 63, 126, 252),"1M+3M+6M+12M"),
    ]
    for lbs, lbl in lookback_variants:
        # monkey-patch LOOKBACKS for run_btc
        import gold_trend_demo as gt
        orig = gt.LOOKBACKS
        gt.LOOKBACKS = lbs
        try:
            sh, tr, mdd = sweep_run(lambda: run_btc(close, high, low))
        finally:
            gt.LOOKBACKS = orig
        mark = " <<" if lbs == (21, 63, 252) else ""
        print(f"  {str(lbs):<22s} {sh:>+7.3f} {tr:>7d} {mdd * 100:>+7.2f}%  "
              f"{(sh / baseline_sh - 1) * 100:>+8.1f}%{mark}")
        sw3.append(sh)

    # Sweep 4: vol target (0.10, 0.12, 0.15, 0.20, 0.25)
    print("\n  [Sweep 4] Vol target (annualized)")
    print(f"  {'vt':>5s} {'Sharpe':>7s} {'trades':>7s} {'MDD':>8s}  {'vs-base':>9s}")
    sw4 = []
    for vt in (0.10, 0.12, 0.15, 0.20, 0.25):
        import gold_trend_demo as gt
        orig = gt.VOL_TARGET_ANN
        gt.VOL_TARGET_ANN = vt
        try:
            sh, tr, mdd = sweep_run(lambda: run_btc(close, high, low))
        finally:
            gt.VOL_TARGET_ANN = orig
        mark = " <<" if abs(vt - 0.15) < 1e-6 else ""
        print(f"  {vt:>5.2f} {sh:>+7.3f} {tr:>7d} {mdd * 100:>+7.2f}%  "
              f"{(sh / baseline_sh - 1) * 100:>+8.1f}%{mark}")
        sw4.append(sh)

    all_sweeps = sw1 + sw2 + sw3 + sw4
    min_sh = min(all_sweeps)
    neg_count = sum(1 for s in all_sweeps if s < 0)

    # ±20% check on the two most obvious scale params: vol_target (0.12 & 0.20
    # are both in sweep 4) and cap (1.33 is within +33% of 1.00x so
    # conservative proxy).
    vt_012 = sw4[1]
    vt_020 = sw4[3]
    drop_vt = max(abs(vt_012 - baseline_sh), abs(vt_020 - baseline_sh)) / abs(baseline_sh)
    p5_drop = drop_vt < 0.50
    p5_neg = neg_count == 0
    print()
    print(f"  Min Sharpe across sweep : {min_sh:+.3f}")
    print(f"  Negative configs        : {neg_count}/{len(all_sweeps)}")
    print(f"  Max Sharpe drop ±20% vt : {drop_vt * 100:.1f}%  ({v(p5_drop)} -- need < 50%)")
    print(f"  No negative in sweep    : {v(p5_neg)}")
    phase5_pass = p5_drop and p5_neg
    print()
    if not phase5_pass:
        print("  Phase 5 OVERALL: FAIL -- fragile under param perturbation.")
        return 1
    print("  Phase 5 OVERALL: PASS -- proceeding to Phase 6.")

    # ======================================================================
    # Phase 6 -- True holdout
    # ======================================================================
    section("Phase 6 -- True holdout (IS 2018-2021, OOS 2022-2025)")
    print("  4-year IS followed by ~3.7-year OOS. No param re-fitting.\n")

    def split_run(ws: str, we: str, label: str) -> dict:
        ws_ts = pd.Timestamp(ws, tz="UTC")
        we_ts = pd.Timestamp(we, tz="UTC")
        pos_s = close.index.searchsorted(ws_ts)
        pos_e = min(close.index.searchsorted(we_ts, side="right"), len(close))
        warm_s = max(0, pos_s - max(LOOKBACKS))
        sub_close = close.iloc[warm_s:pos_e]
        sub_high = high.iloc[warm_s:pos_e]
        sub_low = low.iloc[warm_s:pos_e]
        r, s = run_btc(sub_close, sub_high, sub_low, cost_bps=COST_BPS_HONEST)
        r_win = r.loc[ws:we]
        mx = metrics(r_win)
        return {"label": label, **mx, "trades": s['trades']}

    IS = split_run("2018-01-01", "2021-12-31", "IS train 2018-2021")
    OOS = split_run("2022-01-01", "2026-04-18", "OOS test 2022-2025")

    print(f"  {'split':<24s} {'years':>5s} {'trades':>7s} "
          f"{'ret':>9s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    for r in (IS, OOS):
        print(f"  {r['label']:<24s} {r['years']:>5.1f} {r['trades']:>7d} "
              f"{r['total'] * 100:>+8.2f}% {r['cagr'] * 100:>+7.2f}% "
              f"{r['sharpe']:>+7.2f} {r['mdd'] * 100:>+7.2f}%")
    degrad = IS['sharpe'] - OOS['sharpe']
    print()
    print(f"  IS Sharpe           : {IS['sharpe']:+.3f}")
    print(f"  OOS Sharpe          : {OOS['sharpe']:+.3f}")
    print(f"  Degradation (IS-OOS): {degrad:+.3f}")
    print()
    p6_oos = OOS['sharpe'] > 0
    p6_deg = degrad < 0.5
    print(f"  OOS Sharpe > 0   : {v(p6_oos)}  ({OOS['sharpe']:+.3f})")
    print(f"  Degradation < 0.5: {v(p6_deg)}  ({degrad:+.3f})")
    phase6_pass = p6_oos and p6_deg
    print()
    if phase6_pass:
        print("  Phase 6 OVERALL: PASS -- BTC MH-LO+pyramid survived all phases.")
    else:
        print("  Phase 6 OVERALL: FAIL -- did not generalize out-of-sample.")
    return 0 if phase6_pass else 1


if __name__ == "__main__":
    sys.exit(main())
