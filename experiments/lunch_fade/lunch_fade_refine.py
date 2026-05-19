#!/usr/bin/env python3
"""Fine refinement on lunch-fade — dir-gap at every threshold, regime
breakdown at the cadence-passing thr=0.25 cell, LB x AE grid, long/short
asymmetry at the trade-floor-passing variant.

Run:
    venv/Scripts/python.exe experiments/lunch_fade/lunch_fade_refine.py
    LUNCH_SYMBOL=NDX100 venv/Scripts/python.exe experiments/lunch_fade/lunch_fade_refine.py
"""

from __future__ import annotations

import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from lunch_fade_demo import (  # noqa: E402
    SYMBOL,
    annualized_sharpe,
    load_m5,
    max_drawdown,
    section,
    simulate_lunch_fade,
)


def main() -> int:
    section(f"Loading {SYMBOL} M5")
    bars = load_m5(SYMBOL)
    print(f"  bars: {len(bars):,}   days: {len(set(bars.index.date))}")

    section("Fine threshold sweep (fade vs cont, cost=1pt)")
    print(f"  {'thr':<6} {'Sh_fade':>8} {'Sh_cont':>8} {'dir-gap':>8} {'trades':>7} {'MDD':>8} {'WR':>6} {'PF':>5}")
    for thr in (0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.75, 1.0):
        r_f, t_f = simulate_lunch_fade(bars, min_move_atr=thr, direction="fade")
        r_c, _ = simulate_lunch_fade(bars, min_move_atr=thr, direction="cont")
        sh_f = annualized_sharpe(r_f.to_numpy())
        sh_c = annualized_sharpe(r_c.to_numpy())
        mdd = max_drawdown((1 + r_f).cumprod().to_numpy()) * 100
        wins = [t for t in t_f if t["pnl_pct"] > 0]
        wr = len(wins) / max(len(t_f), 1) * 100
        gw = sum(t["pnl_pct"] for t in t_f if t["pnl_pct"] > 0)
        gl = -sum(t["pnl_pct"] for t in t_f if t["pnl_pct"] < 0)
        pf = gw / gl if gl > 0 else float("inf")
        print(f"  {thr:>4.2f}   {sh_f:>+7.2f}  {sh_c:>+7.2f}  {sh_f - sh_c:>+7.2f}  "
              f"{len(t_f):>6d}  {mdd:>+7.2f}%  {wr:>5.1f}%  {pf:>4.2f}")

    section("Regime breakdown @ thr=0.25 (trade-floor-passing variant)")
    r, t = simulate_lunch_fade(bars, min_move_atr=0.25)
    windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026", "2023-01-01", "2026-12-31"),
    ]
    print(f"  {'window':<10} {'Sharpe':>8} {'trades':>7} {'MDD':>8} {'WR':>6}")
    for label, s, e in windows:
        sub_r = r.loc[s:e]
        sub_t = [tt for tt in t if s <= str(tt["date"]) <= e]
        sh = annualized_sharpe(sub_r.to_numpy())
        mdd = max_drawdown((1 + sub_r).cumprod().to_numpy()) * 100
        wins = [tt for tt in sub_t if tt["pnl_pct"] > 0]
        wr = len(wins) / max(len(sub_t), 1) * 100
        print(f"  {label:<10} {sh:>+7.2f}  {len(sub_t):>6d}  {mdd:>+7.2f}%  {wr:>5.1f}%")

    section("Regime breakdown @ thr=0.5 (highest-conviction variant)")
    r5, t5 = simulate_lunch_fade(bars, min_move_atr=0.5)
    for label, s, e in windows:
        sub_r = r5.loc[s:e]
        sub_t = [tt for tt in t5 if s <= str(tt["date"]) <= e]
        sh = annualized_sharpe(sub_r.to_numpy())
        mdd = max_drawdown((1 + sub_r).cumprod().to_numpy()) * 100
        wins = [tt for tt in sub_t if tt["pnl_pct"] > 0]
        wr = len(wins) / max(len(sub_t), 1) * 100
        print(f"  {label:<10} {sh:>+7.2f}  {len(sub_t):>6d}  {mdd:>+7.2f}%  {wr:>5.1f}%")

    section("Morning x Afternoon grid (Sharpe @ thr=0.25)")
    mornings = (60, 90, 120, 150, 180)
    afternoons = (180, 210, 240, 270, 300, 330)
    label_ma = "M/A"
    header = "  " + f"{label_ma:<6}" + "".join(f"  {a:>4d}" for a in afternoons)
    print(header)
    for me in mornings:
        row = [f"  {me:>3d}m  "]
        for ae in afternoons:
            if ae <= me:
                row.append(f"  {'-':>5}")
                continue
            r_v, _ = simulate_lunch_fade(bars, morning_end_min=me, afternoon_end_min=ae, min_move_atr=0.25)
            row.append(f"  {annualized_sharpe(r_v.to_numpy()):>+5.2f}")
        print("".join(row))

    section("Long/short asymmetry @ thr=0.25")
    r_l, t_l = simulate_lunch_fade(bars, min_move_atr=0.25, long_only=True)
    r_s, t_s = simulate_lunch_fade(bars, min_move_atr=0.25, short_only=True)
    print(f"  LONG-only  (fade morning-down) Sharpe {annualized_sharpe(r_l.to_numpy()):+.2f}  "
          f"MDD {max_drawdown((1+r_l).cumprod().to_numpy())*100:+.2f}%  trades {len(t_l)}")
    print(f"  SHORT-only (fade morning-up)   Sharpe {annualized_sharpe(r_s.to_numpy()):+.2f}  "
          f"MDD {max_drawdown((1+r_s).cumprod().to_numpy())*100:+.2f}%  trades {len(t_s)}")
    for label, s, e in windows:
        sub_l = r_l.loc[s:e]
        sub_s = r_s.loc[s:e]
        sub_lt = [tt for tt in t_l if s <= str(tt["date"]) <= e]
        sub_st = [tt for tt in t_s if s <= str(tt["date"]) <= e]
        sh_l = annualized_sharpe(sub_l.to_numpy())
        sh_s = annualized_sharpe(sub_s.to_numpy())
        print(f"    {label}  LONG {sh_l:>+6.2f} ({len(sub_lt)} tr)   "
              f"SHORT {sh_s:>+6.2f} ({len(sub_st)} tr)")

    section("Cost sensitivity @ thr=0.25")
    for c in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
        r_v, t_v = simulate_lunch_fade(bars, min_move_atr=0.25, cost_points=c)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={c:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
