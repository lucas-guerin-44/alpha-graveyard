#!/usr/bin/env python3
"""Finer threshold sweep + per-regime fade-gap on NDX100 pre-close drift.

Run:
    PRECLOSE_SYMBOL=NDX100 venv/Scripts/python.exe experiments/preclose_drift/preclose_drift_refine.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from preclose_drift_demo import (  # noqa: E402
    SYMBOL,
    annualized_sharpe,
    load_m5,
    max_drawdown,
    section,
    simulate_preclose,
)


def main() -> int:
    section(f"Loading {SYMBOL} M5")
    bars = load_m5(SYMBOL)
    print(f"  bars: {len(bars):,}   days: {len(set(bars.index.date))}")

    section("Fine threshold sweep (continuation, cost=1pt)")
    print(f"  {'thr':<6} {'Sh_cont':>8} {'Sh_fade':>8} {'dir-gap':>8} {'trades':>7} {'MDD':>8}")
    for thr in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
        r_c, t_c = simulate_preclose(bars, min_move_atr=thr, direction="cont")
        r_f, _ = simulate_preclose(bars, min_move_atr=thr, direction="fade")
        sh_c = annualized_sharpe(r_c.to_numpy())
        sh_f = annualized_sharpe(r_f.to_numpy())
        mdd = max_drawdown((1 + r_c).cumprod().to_numpy()) * 100
        print(f"  {thr:>4.2f}   {sh_c:>+7.2f}  {sh_f:>+7.2f}  {sh_c - sh_f:>+7.2f}  "
              f"{len(t_c):>6d}  {mdd:>+7.2f}%")

    section("High-threshold (thr=1.0) per-regime breakdown")
    r, t = simulate_preclose(bars, min_move_atr=1.0)
    windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026", "2023-01-01", "2026-12-31"),
    ]
    print(f"  {'window':<10} {'Sharpe':>8} {'trades':>7} {'MDD':>8}")
    for label, s, e in windows:
        sub_r = r.loc[s:e]
        sub_t = [tt for tt in t if s <= str(tt["date"]) <= e]
        sh = annualized_sharpe(sub_r.to_numpy())
        mdd = max_drawdown((1 + sub_r).cumprod().to_numpy()) * 100
        print(f"  {label:<10} {sh:>+7.2f}  {len(sub_t):>6d}  {mdd:>+7.2f}%")

    section("LB x thr grid (continuation Sharpe, cost=1pt)")
    lbs = (20, 30, 60)
    thrs = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5)
    print(f"  {'LB':<5}" + "".join(f"  thr={t_:.2f}" for t_ in thrs))
    for lb in lbs:
        row = [f"  {lb:>3d}m "]
        for thr in thrs:
            r_v, _ = simulate_preclose(bars, lookback_min=lb, min_move_atr=thr)
            row.append(f"  {annualized_sharpe(r_v.to_numpy()):>+6.2f}")
        print("".join(row))

    section("Holdout-only fine threshold (2023-2026)")
    print(f"  {'thr':<6} {'HO_Sh':>8} {'trades':>7}")
    for thr in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5):
        r_v, t_v = simulate_preclose(bars, min_move_atr=thr)
        sub_r = r_v.loc["2023-01-01":"2026-12-31"]
        sub_t = [tt for tt in t_v if str(tt["date"]) >= "2023-01-01"]
        sh = annualized_sharpe(sub_r.to_numpy())
        print(f"  {thr:>4.2f}   {sh:>+7.2f}  {len(sub_t):>6d}")

    section("Long/short split @ thr=1.0 (highest-conviction days)")
    r_l, t_l = simulate_preclose(bars, min_move_atr=1.0, long_only=True)
    r_s, t_s = simulate_preclose(bars, min_move_atr=1.0, short_only=True)
    print(f"  LONG-only   Sharpe {annualized_sharpe(r_l.to_numpy()):>+.2f}  trades {len(t_l):>4d}")
    print(f"  SHORT-only  Sharpe {annualized_sharpe(r_s.to_numpy()):>+.2f}  trades {len(t_s):>4d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
