#!/usr/bin/env python3
"""
DAX gap fade — on large |gap| (prev close -> today open), fade the gap in first HOLD_MIN.

Thesis: experiments/dax/gap_fade.md

Run:
    venv/Scripts/python.exe experiments/dax/gap_fade_demo.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from _common import (  # noqa: E402
    annualized_sharpe,
    compute_day_groups,
    compute_minute_of_day,
    kill_criteria_check,
    load_dax_m5,
    max_drawdown,
    regime_breakdown,
    report_run,
    section,
)


def simulate_gap_fade(
    bars: pd.DataFrame,
    gap_min_atr: float = 0.5,
    hold_min: int = 30,
    cost_points: float = 1.0,
    direction: str = "fade",       # 'fade' (baseline) | 'cont'
    leg: str = "both",             # 'both' | 'long' (down-gap only) | 'short' (up-gap only)
    atr_lookback_days: int = 20,
) -> tuple[pd.Series, list[dict]]:
    idx = bars.index
    n_bars = len(idx)
    if n_bars == 0:
        return pd.Series(dtype=float, name="gap_ret"), []

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)
    minute_of_day = compute_minute_of_day(idx)
    dates, day_starts, day_ends = compute_day_groups(idx)

    n_days = len(day_starts)
    daily_open = np.array([open_arr[int(s)] for s in day_starts])
    daily_close = np.array([close_arr[int(e) - 1] for e in day_ends])
    abs_cc = np.abs(np.diff(daily_close, prepend=daily_close[0]))
    atr_arr = np.zeros(n_days, dtype=np.float64)
    for d_i in range(n_days):
        lo = max(0, d_i - atr_lookback_days)
        atr_arr[d_i] = abs_cc[lo:d_i].mean() if d_i > 0 else 0.0

    bars_hold = max(1, hold_min // 5)

    ret_arr = np.zeros(n_bars, dtype=np.float64)
    trades: list[dict] = []

    for d_i in range(1, n_days):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        n = e - s
        if n < bars_hold + 4:
            continue

        prev_close = float(daily_close[d_i - 1])
        today_open = float(daily_open[d_i])
        if prev_close <= 0:
            continue
        gap_px = today_open - prev_close
        atr = float(atr_arr[d_i])
        if not np.isfinite(atr) or atr <= 0:
            continue
        if abs(gap_px) < gap_min_atr * atr:
            continue

        sign_gap = 1.0 if gap_px > 0 else -1.0
        if direction == "fade":
            pos = -sign_gap
        else:
            pos = sign_gap

        # leg filter (applied to the POSITION direction)
        if leg == "long" and pos < 0:
            continue
        if leg == "short" and pos > 0:
            continue

        entry_bar = 1  # 09:05 open (second bar of day)
        if entry_bar + 1 >= n:
            continue
        day_open = open_arr[s:e]
        day_close = close_arr[s:e]

        entry_px = float(day_open[entry_bar])
        exit_bar = min(entry_bar + bars_hold, n - 1)
        exit_px = float(day_close[exit_bar])
        cost_ret = cost_points / entry_px
        pnl = pos * (exit_px / entry_px - 1.0) - cost_ret

        for j in range(entry_bar, exit_bar + 1):
            prev = entry_px if j == entry_bar else day_close[j - 1]
            cur = exit_px if j == exit_bar else day_close[j]
            step = pos * (cur - prev) / prev
            if j == exit_bar:
                step -= cost_ret
            ret_arr[s + j] = step

        trades.append({
            "date": dates[s],
            "direction": "LONG" if pos > 0 else "SHORT",
            "entry_ts": idx[s + entry_bar],
            "exit_ts": idx[s + exit_bar],
            "entry_px": entry_px,
            "exit_px": exit_px,
            "gap_px": float(gap_px),
            "atr_px": float(atr),
            "gap_atr": float(gap_px / atr),
            "pnl_pct": float(pnl),
            "reason": "scheduled",
        })

    return pd.Series(ret_arr, index=idx, name="gap_ret"), trades


def main() -> int:
    section("Loading GER40 M5 (EU session, 09:00-17:30 Berlin)")
    bars = load_dax_m5()
    print(f"  bars: {len(bars):,}   range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    section("Baseline (fade, gap_min=0.5*ATR, hold=30min, cost=1pt)")
    r, t = simulate_gap_fade(bars)
    report_run("baseline", r, t)

    section("Phase 2 kill-criteria")
    kill_criteria_check("baseline", r, t, trade_min=150, wr_min=0.50, pf_min=1.10)

    section("Regime breakdown")
    regime_breakdown(r, t)

    section("Variant sweep — gap threshold")
    for thr in (0.25, 0.5, 1.0, 1.5, 2.0):
        r_v, t_v = simulate_gap_fade(bars, gap_min_atr=thr)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  thr={thr:>4.2f}  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — hold window (min)")
    for h in (15, 30, 60, 120):
        r_v, t_v = simulate_gap_fade(bars, hold_min=h)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  hold={h:>3d}min  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — cost sensitivity")
    for c in (0.5, 1.0, 2.0, 3.0):
        r_v, t_v = simulate_gap_fade(bars, cost_points=c)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={c:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    section("Leg split (fade-LONG = down-gap-fade / fade-SHORT = up-gap-fade)")
    for lg in ("both", "long", "short"):
        r_v, t_v = simulate_gap_fade(bars, leg=lg)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  leg={lg:<6s}  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Null-check — continuation direction (opposite sign)")
    r_n, t_n = simulate_gap_fade(bars, direction="cont")
    report_run("continuation", r_n, t_n)
    base_sh = annualized_sharpe(r.to_numpy())
    null_sh = annualized_sharpe(r_n.to_numpy())
    gap = base_sh - null_sh
    print(f"\n  direction-gap (fade - cont) = {gap:+.2f}")
    if gap >= 0.30:
        print("    PASS: fade signal has directional content.")
    elif gap <= -0.30:
        print("    INVERTED: continuation wins.")
    else:
        print("    FAIL: |gap| < 0.30 — no directional content.")

    section("Summary")
    eq = (1 + r).cumprod()
    years = (r.index[-1] - r.index[0]).days / 365.25
    print(f"  baseline : CAGR {(float(eq.iloc[-1])) ** (1/max(years,1e-9)) - 1:+.2%}  "
          f"Sharpe {base_sh:+.2f}  MDD {max_drawdown(eq.to_numpy())*100:+.2f}%  "
          f"trades {len(t)} ({len(t)/max(years*52,1e-9):.2f}/week)  "
          f"dir-gap {gap:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
