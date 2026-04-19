#!/usr/bin/env python3
"""
Softs TSMOM ensemble -- Phases 4 (regime), 5 (param sensitivity), 6 (holdout).

Phase 3 passed (Bootstrap CI excludes 0, permutation p=0.0000, Deflated
Sharpe p=0.0000 at n_trials=12). This script runs the remaining phases
with the same ensemble: COCOA, COFFEE, COTTON, CORN, SOYBEAN, LIVE_CATTLE.
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
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'gold_trend'))

import gold_trend_demo as gt
from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

ENSEMBLE = ["COCOA", "COFFEE", "COTTON", "CORN", "SOYBEAN", "LIVE_CATTLE"]
COST_BPS_PER_SIDE = 5.0
START = "2015-01-01"
END = "2026-04-18"


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def metrics(r: pd.Series) -> dict:
    rn = r.dropna()
    if len(rn) < 5:
        return {"years": 0, "total": 0.0, "cagr": 0.0, "sharpe": 0.0, "mdd": 0.0}
    eq = (1.0 + rn).cumprod().to_numpy()
    years = (rn.index[-1] - rn.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(rn.to_numpy())
    mdd = max_drawdown(eq)
    return {"years": years, "total": total, "cagr": cagr, "sharpe": sh,
            "mdd": mdd, "n_bars": len(rn)}


def build_blend(
    ensemble: list[str],
    cost_bps: float = COST_BPS_PER_SIDE,
    lookbacks: tuple[int, ...] = LOOKBACKS,
    vol_target: float = VOL_TARGET_ANN,
    vol_lb: int = VOL_LOOKBACK,
    pyramid_steps: int = 3,
    pyramid_atr_mult: float = 1.0,
    max_units: int | None = None,
    date_range: tuple[str, str] = (START, END),
) -> tuple[pd.Series, dict[str, pd.Series], dict[str, dict]]:
    """Run each leg and return the blend, per-leg returns, per-leg stats.

    All core simulator config is threaded through so callers can sweep.
    Monkey-patches gt.LOOKBACKS / VOL_TARGET_ANN / VOL_LOOKBACK around the
    simulator calls since the simulator reads them as module globals.
    """
    orig_lb = gt.LOOKBACKS
    orig_vt = gt.VOL_TARGET_ANN
    orig_vlb = gt.VOL_LOOKBACK
    gt.LOOKBACKS = lookbacks
    gt.VOL_TARGET_ANN = vol_target
    gt.VOL_LOOKBACK = vol_lb

    legs: dict[str, pd.Series] = {}
    stats: dict[str, dict] = {}
    try:
        for sym in ensemble:
            df = load_series(sym)
            if df is None:
                continue
            df = df.loc[date_range[0]:date_range[1]]
            close, high, low = df["close"], df["high"], df["low"]
            ret = close.pct_change().fillna(0.0)
            rv = ret.rolling(vol_lb, min_periods=vol_lb // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
            rv = rv.shift(1)
            sig = multi_horizon_signal(close, lookbacks)
            atr = atr_series(high, low, close)
            strat_ret, leg_stats = simulate_tsmom_pyramid(
                close, sig, rv, atr, sym,
                long_only=True,
                cost_bps_per_side=cost_bps,
                steps=pyramid_steps,
                atr_mult=pyramid_atr_mult,
                max_units=max_units,
            )
            legs[sym] = strat_ret
            stats[sym] = leg_stats
    finally:
        gt.LOOKBACKS = orig_lb
        gt.VOL_TARGET_ANN = orig_vt
        gt.VOL_LOOKBACK = orig_vlb

    df_legs = pd.concat([legs[s].rename(s) for s in legs], axis=1, join="inner").dropna()
    blend = df_legs.mean(axis=1).rename("softs-blend")
    return blend, df_legs, stats


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    section("Baseline run (for reference)")
    blend, df_legs, leg_stats = build_blend(ENSEMBLE)
    baseline_m = metrics(blend)
    baseline_sharpe = baseline_m["sharpe"]
    print(f"  Blend Sharpe {baseline_m['sharpe']:+.3f}  "
          f"CAGR {baseline_m['cagr'] * 100:+.2f}%  "
          f"MDD {baseline_m['mdd'] * 100:+.2f}%")
    print(f"  Period  {blend.index[0].date()} -> {blend.index[-1].date()}  "
          f"({baseline_m['years']:.1f} years, {baseline_m['n_bars']:,} bars)")

    # ======================================================================
    # Phase 4 -- Regime stability (4 non-overlapping windows)
    # ======================================================================
    section("Phase 4 -- Regime stability (4 non-overlapping windows)")
    windows = [
        ("W1 2015-2017 (post-QE)", "2015-01-01", "2017-12-31"),
        ("W2 2018-2020 (mid-cycle)", "2018-01-01", "2020-12-31"),
        ("W3 2021-2022 (supply shock era)", "2021-01-01", "2022-12-31"),
        ("W4 2023-2026 (cocoa boom/bust)", "2023-01-01", "2026-04-18"),
    ]
    print(f"  {'window':<34s} {'bars':>5s} {'ret':>9s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    window_results = []
    for wname, ws, we in windows:
        sub_blend = blend.loc[ws:we]
        if len(sub_blend) < 50:
            print(f"  {wname:<34s} <no data>")
            continue
        m = metrics(sub_blend)
        window_results.append({"name": wname.strip(), **m})
        print(f"  {wname:<34s} {m['n_bars']:>5d} {m['total'] * 100:>+8.2f}% "
              f"{m['cagr'] * 100:>+7.2f}% {m['sharpe']:>+7.2f} {m['mdd'] * 100:>+7.2f}%")

    positive_windows = sum(1 for w in window_results if w["sharpe"] > 0)
    total_ret_abs = sum(abs(w["total"]) for w in window_results)
    max_share = max(abs(w["total"]) for w in window_results) / total_ret_abs if total_ret_abs else 0.0
    p4_sharpe = positive_windows >= 3
    p4_dom = max_share < 0.80
    print()
    print(f"  Windows with Sharpe > 0 : {positive_windows}/4  "
          f"({'PASS' if p4_sharpe else 'FAIL'} -- need >= 3)")
    print(f"  Max single-window share : {max_share * 100:.1f}%  "
          f"({'PASS' if p4_dom else 'FAIL'} -- need < 80%)")
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
    print(f"  Baseline Sharpe = {baseline_sharpe:+.3f}\n")

    def one_sweep_run(**kwargs) -> float:
        """Return Sharpe for a modified ensemble run."""
        b, _, _ = build_blend(ENSEMBLE, **kwargs)
        return annualized_sharpe(b.to_numpy())

    # Sweep 1: lookback structure
    print("  [Sweep 1] Lookback structure")
    print(f"  {'lookbacks':<22s} {'Sharpe':>7s}  {'vs-base':>9s}")
    lb_variants = [
        ((63,),             "3M only"),
        ((252,),            "12M only"),
        ((21, 252),         "1M+12M"),
        ((21, 63, 252),     "1M+3M+12M (baseline)"),
        ((21, 63, 126, 252),"1M+3M+6M+12M"),
    ]
    sw1 = []
    for lbs, _lbl in lb_variants:
        sh = one_sweep_run(lookbacks=lbs)
        mark = " <<" if lbs == (21, 63, 252) else ""
        print(f"  {str(lbs):<22s} {sh:>+7.3f}  "
              f"{(sh / baseline_sharpe - 1) * 100:>+8.1f}%{mark}")
        sw1.append(sh)

    # Sweep 2: vol target
    print("\n  [Sweep 2] Vol target (annualized)")
    print(f"  {'vt':>5s} {'Sharpe':>7s}  {'vs-base':>9s}")
    sw2 = []
    for vt in (0.08, 0.10, 0.12, 0.15, 0.20, 0.25):
        sh = one_sweep_run(vol_target=vt)
        mark = " <<" if abs(vt - 0.15) < 1e-6 else ""
        print(f"  {vt:>5.2f} {sh:>+7.3f}  "
              f"{(sh / baseline_sharpe - 1) * 100:>+8.1f}%{mark}")
        sw2.append(sh)

    # Sweep 3: cost (robustness to broker fee assumption)
    print("\n  [Sweep 3] Cost per side (bps)")
    print(f"  {'bps':>5s} {'Sharpe':>7s}  {'vs-base':>9s}")
    sw3 = []
    for c in (1, 3, 5, 8, 12, 20):
        sh = one_sweep_run(cost_bps=float(c))
        mark = " <<" if c == 5 else ""
        print(f"  {c:>5d} {sh:>+7.3f}  "
              f"{(sh / baseline_sharpe - 1) * 100:>+8.1f}%{mark}")
        sw3.append(sh)

    # Sweep 4: pyramid cap
    print("\n  [Sweep 4] Pyramid cap (max_units / 3)")
    print(f"  {'cap':>6s} {'Sharpe':>7s}  {'vs-base':>9s}")
    sw4 = []
    for mu in (3, 4, 5, 6):
        sh = one_sweep_run(max_units=mu)
        cap = mu / 3
        mark = " <<" if mu == 3 else ""
        print(f"  {cap:>5.2f}x {sh:>+7.3f}  "
              f"{(sh / baseline_sharpe - 1) * 100:>+8.1f}%{mark}")
        sw4.append(sh)

    all_sweeps = sw1 + sw2 + sw3 + sw4
    min_sh = min(all_sweeps)
    neg_count = sum(1 for s in all_sweeps if s < 0)
    # ±20% check on vol-target (0.12 and 0.20 are within 33% of 0.15)
    vt_012 = sw2[2]
    vt_020 = sw2[4]
    drop_vt = max(abs(vt_012 - baseline_sharpe), abs(vt_020 - baseline_sharpe)) / abs(baseline_sharpe)
    # ±20% check on cost (3 and 8 bps vs 5 bps baseline)
    cost_3 = sw3[1]
    cost_8 = sw3[3]
    drop_cost = max(abs(cost_3 - baseline_sharpe), abs(cost_8 - baseline_sharpe)) / abs(baseline_sharpe)
    p5_drop = (drop_vt < 0.50) and (drop_cost < 0.50)
    p5_neg = neg_count == 0
    print()
    print(f"  Min Sharpe across sweep : {min_sh:+.3f}")
    print(f"  Negative configs        : {neg_count}/{len(all_sweeps)}")
    print(f"  Max drop ±20% vt        : {drop_vt * 100:.1f}%  "
          f"({'PASS' if drop_vt < 0.50 else 'FAIL'})")
    print(f"  Max drop ±20% cost      : {drop_cost * 100:.1f}%  "
          f"({'PASS' if drop_cost < 0.50 else 'FAIL'})")
    print(f"  No negative in sweep    : {'PASS' if p5_neg else 'YELLOW'}")
    phase5_pass = p5_drop and p5_neg
    print()
    if not phase5_pass:
        print("  Phase 5 OVERALL: FAIL -- fragile under perturbation.")
        return 1
    print("  Phase 5 OVERALL: PASS -- proceeding to Phase 6.")

    # ======================================================================
    # Phase 6 -- True holdout
    # ======================================================================
    section("Phase 6 -- True holdout (IS 2015-2022, OOS 2023-2026)")

    IS_START, IS_END = "2015-01-01", "2022-12-31"
    OOS_START, OOS_END = "2023-01-01", END

    blend_is, _, _ = build_blend(ENSEMBLE, date_range=(IS_START, IS_END))
    blend_oos, _, _ = build_blend(ENSEMBLE, date_range=(IS_START, OOS_END))
    # OOS slice from the full-range run (so the strategy has warmup from IS data)
    blend_oos_slice = blend_oos.loc[OOS_START:OOS_END]

    m_is = metrics(blend_is)
    m_oos = metrics(blend_oos_slice)

    print(f"  {'split':<24s} {'years':>5s} {'ret':>9s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    print(f"  {'IS train 2015-2022':<24s} {m_is['years']:>5.1f} "
          f"{m_is['total'] * 100:>+8.2f}% {m_is['cagr'] * 100:>+7.2f}% "
          f"{m_is['sharpe']:>+7.2f} {m_is['mdd'] * 100:>+7.2f}%")
    print(f"  {'OOS test 2023-2026':<24s} {m_oos['years']:>5.1f} "
          f"{m_oos['total'] * 100:>+8.2f}% {m_oos['cagr'] * 100:>+7.2f}% "
          f"{m_oos['sharpe']:>+7.2f} {m_oos['mdd'] * 100:>+7.2f}%")

    degrad = m_is["sharpe"] - m_oos["sharpe"]
    print()
    print(f"  IS Sharpe           : {m_is['sharpe']:+.3f}")
    print(f"  OOS Sharpe          : {m_oos['sharpe']:+.3f}")
    print(f"  Degradation (IS-OOS): {degrad:+.3f}")
    p6_oos = m_oos["sharpe"] > 0
    p6_deg = degrad < 0.5
    print()
    print(f"  OOS Sharpe > 0    : {'PASS' if p6_oos else 'FAIL'}  ({m_oos['sharpe']:+.3f})")
    print(f"  Degradation < 0.5 : {'PASS' if p6_deg else 'FAIL'}  ({degrad:+.3f})")
    phase6_pass = p6_oos and p6_deg
    print()
    if phase6_pass:
        print("  Phase 6 OVERALL: PASS -- Softs ensemble cleared Phases 2-6.")
    else:
        print("  Phase 6 OVERALL: FAIL -- didn't generalize out-of-sample.")
    return 0 if phase6_pass else 1


if __name__ == "__main__":
    sys.exit(main())
