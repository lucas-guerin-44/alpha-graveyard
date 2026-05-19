#!/usr/bin/env python3
"""
DAX pre-auction drift (continuation of last-60min momentum into 17:30 Xetra close).

Thesis: experiments/dax/pre_auction.md

Run:
    venv/Scripts/python.exe experiments/dax/pre_auction_demo.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from _common import (  # noqa: E402
    BARS_PER_YEAR,
    RTH_MINUTES,
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


def simulate_pre_auction(
    bars: pd.DataFrame,
    lookback_min: int = 60,
    entry_min_before_close: int = 15,
    min_move_atr: float = 0.25,
    cost_points: float = 1.0,
    direction: str = "cont",   # 'cont' (baseline) | 'fade'
    atr_lookback_days: int = 20,
) -> tuple[pd.Series, list[dict]]:
    idx = bars.index
    n_bars = len(bars)
    if n_bars == 0:
        return pd.Series(dtype=float, name="pa_ret"), []

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)
    minute_of_day = compute_minute_of_day(idx)
    dates, day_starts, day_ends = compute_day_groups(idx)

    # Rolling per-day m5 single-bar abs return ATR proxy.
    bar_abs_ret = np.abs(np.diff(close_arr, prepend=close_arr[0])) / np.maximum(close_arr, 1e-9)
    n_days = len(day_starts)
    daily_vol = np.zeros(n_days, dtype=np.float64)
    for d_i in range(n_days):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        daily_vol[d_i] = np.mean(bar_abs_ret[s:e]) if e > s else 0.0
    atr_arr = np.zeros(n_days, dtype=np.float64)
    for d_i in range(n_days):
        lo = max(0, d_i - atr_lookback_days)
        if d_i == 0:
            atr_arr[d_i] = 0.0
        else:
            atr_arr[d_i] = daily_vol[lo:d_i].mean()

    entry_target_mod = RTH_MINUTES - entry_min_before_close
    lookback_bars = lookback_min // 5

    ret_arr = np.zeros(n_bars, dtype=np.float64)
    trades: list[dict] = []

    for d_i in range(n_days):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        n = e - s
        if n < lookback_bars + 4:
            continue

        day_mod = minute_of_day[s:e]
        day_close = close_arr[s:e]
        day_open = open_arr[s:e]

        cand = np.flatnonzero(day_mod >= entry_target_mod)
        if cand.size == 0:
            continue
        entry_bar = int(cand[0])
        lookback_bar = entry_bar - lookback_bars
        if lookback_bar < 0 or entry_bar + 1 >= n:
            continue

        close_now = float(day_close[entry_bar])
        close_prev = float(day_close[lookback_bar])
        if close_prev <= 0:
            continue
        r_look = close_now / close_prev - 1.0

        atr_m5 = float(atr_arr[d_i])
        if not np.isfinite(atr_m5) or atr_m5 <= 0:
            continue
        # Scale ATR proxy by lookback length (per-bar -> per-lookback).
        thr = min_move_atr * atr_m5 * lookback_bars
        if abs(r_look) < thr:
            continue

        sign_move = 1.0 if r_look > 0 else -1.0
        pos = sign_move if direction == "cont" else -sign_move

        entry_fill = entry_bar + 1
        entry_px = float(day_open[entry_fill])
        exit_bar = n - 1
        exit_px = float(day_close[exit_bar])

        cost_ret = cost_points / entry_px
        pnl = pos * (exit_px / entry_px - 1.0) - cost_ret

        for j in range(entry_fill, exit_bar + 1):
            prev = entry_px if j == entry_fill else day_close[j - 1]
            cur = exit_px if j == exit_bar else day_close[j]
            step = pos * (cur - prev) / prev
            if j == exit_bar:
                step -= cost_ret
            ret_arr[s + j] = step

        trades.append({
            "date": dates[s],
            "direction": "LONG" if pos > 0 else "SHORT",
            "entry_ts": idx[s + entry_fill],
            "exit_ts": idx[s + exit_bar],
            "entry_px": entry_px,
            "exit_px": exit_px,
            "r_look": r_look,
            "pnl_pct": float(pnl),
            "reason": "eod",
        })

    return pd.Series(ret_arr, index=idx, name="pa_ret"), trades


def main() -> int:
    section("Loading GER40 M5 (EU session, 09:00-17:30 Berlin)")
    bars = load_dax_m5()
    print(f"  bars: {len(bars):,}   range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    section("Baseline (cont, lookback=60min, entry=T-15, thr=0.25, EOD exit, cost=1pt)")
    r, t = simulate_pre_auction(bars)
    report_run("baseline", r, t)

    section("Phase 2 kill-criteria")
    kill_criteria_check("baseline", r, t, wr_min=0.48, pf_min=1.05)

    section("Regime breakdown")
    regime_breakdown(r, t)

    section("Variant sweep — lookback window (min)")
    for lb in (30, 60, 90):
        r_v, t_v = simulate_pre_auction(bars, lookback_min=lb)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  LB={lb:>3d}min  Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — entry (min before close)")
    for em in (5, 10, 15, 25):
        r_v, t_v = simulate_pre_auction(bars, entry_min_before_close=em)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  T-{em:>2d}min  Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — threshold")
    for thr in (0.0, 0.25, 0.5, 1.0):
        r_v, t_v = simulate_pre_auction(bars, min_move_atr=thr)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  thr={thr:>4.2f}  Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — cost sensitivity")
    for c in (0.5, 1.0, 2.0, 3.0):
        r_v, t_v = simulate_pre_auction(bars, cost_points=c)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={c:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    section("Null-check — fade direction (opposite sign)")
    r_n, t_n = simulate_pre_auction(bars, direction="fade")
    report_run("fade", r_n, t_n)
    base_sh = annualized_sharpe(r.to_numpy())
    null_sh = annualized_sharpe(r_n.to_numpy())
    gap = base_sh - null_sh
    print(f"\n  direction-gap (cont - fade) = {gap:+.2f}")
    if gap >= 0.30:
        print("    PASS: continuation signal has directional content.")
    elif gap <= -0.30:
        print("    INVERTED: fade wins — thesis sign is wrong.")
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
