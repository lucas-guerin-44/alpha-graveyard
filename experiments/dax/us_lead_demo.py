#!/usr/bin/env python3
"""
US -> DAX lead-lag: SPX first-N-min return at 09:30-09:45 ET signals DAX 15:45-17:15 Berlin.

Thesis: experiments/dax/us_lead.md

Run:
    venv/Scripts/python.exe experiments/dax/us_lead_demo.py
"""

from __future__ import annotations

import os
import sys
from datetime import time as dtime

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
    load_spx_m5_et,
    max_drawdown,
    regime_breakdown,
    report_run,
    section,
)


def build_spx_signals(spx_bars: pd.DataFrame, signal_window_min: int = 15,
                      atr_lookback_days: int = 20) -> dict[pd.Timestamp.date, tuple[float, float]]:
    """For each SPX trading day, return (first_window_return, rolling_ATR20_of_this_signal)."""
    idx = spx_bars.index
    if len(idx) == 0:
        return {}
    open_arr = spx_bars["open"].to_numpy(dtype=np.float64)
    close_arr = spx_bars["close"].to_numpy(dtype=np.float64)
    dates = np.asarray(idx.date)
    hours = np.asarray(idx.hour, dtype=np.int32)
    minutes = np.asarray(idx.minute, dtype=np.int32)
    mod = hours * 60 + minutes - (9 * 60 + 30)  # minutes since 09:30 ET

    change = np.empty(len(idx), dtype=bool)
    change[0] = True
    change[1:] = dates[1:] != dates[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = len(idx)

    signals: list[tuple] = []  # (date, signal_return)
    for d_i in range(len(day_starts)):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        n = e - s
        if n < 4:
            continue
        day_mod = mod[s:e]
        if day_mod[0] > 5:  # day started late, skip
            continue
        open_bar = 0
        cand = np.flatnonzero(day_mod >= signal_window_min)
        if cand.size == 0:
            continue
        end_bar = int(cand[0])
        o = float(open_arr[s + open_bar])
        c = float(close_arr[s + end_bar])
        if o <= 0:
            continue
        r = c / o - 1.0
        signals.append((dates[s], r))

    # Rolling ATR of |r|.
    by_date: dict = {}
    arr_abs = np.array([abs(r) for _, r in signals])
    for i, (d, r) in enumerate(signals):
        lo = max(0, i - atr_lookback_days)
        atr = float(arr_abs[lo:i].mean()) if i > 0 else 0.0
        by_date[d] = (float(r), atr)
    return by_date


def simulate_us_lead(
    dax_bars: pd.DataFrame,
    spx_signals: dict,
    entry_berlin: dtime = dtime(15, 45),
    exit_berlin: dtime = dtime(17, 15),
    min_move_atr: float = 0.25,
    cost_points: float = 1.0,
    direction: str = "cont",       # 'cont' | 'fade'
) -> tuple[pd.Series, list[dict]]:
    idx = dax_bars.index
    n_bars = len(idx)
    if n_bars == 0:
        return pd.Series(dtype=float, name="us_lead_ret"), []

    open_arr = dax_bars["open"].to_numpy(dtype=np.float64)
    close_arr = dax_bars["close"].to_numpy(dtype=np.float64)
    minute_of_day = compute_minute_of_day(idx)
    dates, day_starts, day_ends = compute_day_groups(idx)

    entry_mod = (entry_berlin.hour * 60 + entry_berlin.minute) - (9 * 60)
    exit_mod = (exit_berlin.hour * 60 + exit_berlin.minute) - (9 * 60)

    ret_arr = np.zeros(n_bars, dtype=np.float64)
    trades: list[dict] = []

    for d_i in range(len(day_starts)):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        n = e - s
        if n < 10:
            continue

        day_date = dates[s]
        sig = spx_signals.get(day_date)
        if sig is None:
            continue
        r_spx, atr_spx = sig
        if not np.isfinite(atr_spx) or atr_spx <= 0:
            continue
        if abs(r_spx) < min_move_atr * atr_spx:
            continue

        day_mod = minute_of_day[s:e]
        day_close = close_arr[s:e]
        day_open = open_arr[s:e]

        cand_entry = np.flatnonzero(day_mod >= entry_mod)
        cand_exit = np.flatnonzero(day_mod >= exit_mod)
        if cand_entry.size == 0 or cand_exit.size == 0:
            continue
        entry_bar = int(cand_entry[0])
        exit_bar = int(cand_exit[0])
        if entry_bar + 1 >= n or exit_bar <= entry_bar + 1:
            continue

        sign_spx = 1.0 if r_spx > 0 else -1.0
        pos = sign_spx if direction == "cont" else -sign_spx

        entry_px = float(day_open[entry_bar + 1])
        exit_px = float(day_close[exit_bar])
        cost_ret = cost_points / entry_px
        pnl = pos * (exit_px / entry_px - 1.0) - cost_ret

        for j in range(entry_bar + 1, exit_bar + 1):
            prev = entry_px if j == entry_bar + 1 else day_close[j - 1]
            cur = exit_px if j == exit_bar else day_close[j]
            step = pos * (cur - prev) / prev
            if j == exit_bar:
                step -= cost_ret
            ret_arr[s + j] = step

        trades.append({
            "date": day_date,
            "direction": "LONG" if pos > 0 else "SHORT",
            "entry_ts": idx[s + entry_bar + 1],
            "exit_ts": idx[s + exit_bar],
            "entry_px": entry_px,
            "exit_px": exit_px,
            "r_spx": float(r_spx),
            "atr_spx": float(atr_spx),
            "pnl_pct": float(pnl),
            "reason": "scheduled",
        })

    return pd.Series(ret_arr, index=idx, name="us_lead_ret"), trades


def main() -> int:
    section("Loading SPX500 M5 (ET) and GER40 M5 (Berlin)")
    spx = load_spx_m5_et()
    dax = load_dax_m5()
    print(f"  SPX bars: {len(spx):,}  range: {spx.index[0].date()} -> {spx.index[-1].date()}")
    print(f"  DAX bars: {len(dax):,}  range: {dax.index[0].date()} -> {dax.index[-1].date()}")

    section("Building SPX 09:30-09:45 ET signal map (20-day rolling ATR)")
    signals = build_spx_signals(spx, signal_window_min=15)
    print(f"  days with signal: {len(signals):,}")

    section("Baseline (cont, SPX 15m signal, DAX 15:45-17:15, thr=0.25, cost=1pt)")
    r, t = simulate_us_lead(dax, signals)
    report_run("baseline", r, t)

    section("Phase 2 kill-criteria")
    kill_criteria_check("baseline", r, t, wr_min=0.48, pf_min=1.05)

    section("Regime breakdown")
    regime_breakdown(r, t)

    section("Variant sweep — SPX signal window")
    for w in (5, 15, 30):
        sig_w = build_spx_signals(spx, signal_window_min=w)
        r_v, t_v = simulate_us_lead(dax, sig_w)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  window={w:>2d}min  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — hold window (entry 15:45, exit varies)")
    for hrs_mins in [(16, 45), (17, 15), (17, 25)]:
        exit_t = dtime(*hrs_mins)
        r_v, t_v = simulate_us_lead(dax, signals, exit_berlin=exit_t)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  exit={exit_t}  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    section("Variant sweep — threshold")
    for thr in (0.0, 0.25, 0.5, 1.0):
        r_v, t_v = simulate_us_lead(dax, signals, min_move_atr=thr)
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown((1 + r_v).cumprod().to_numpy())
        print(f"  thr={thr:>4.2f}  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep — cost sensitivity")
    for c in (0.5, 1.0, 2.0, 3.0):
        r_v, t_v = simulate_us_lead(dax, signals, cost_points=c)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={c:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    section("Null-check — fade direction")
    r_n, t_n = simulate_us_lead(dax, signals, direction="fade")
    report_run("fade", r_n, t_n)
    base_sh = annualized_sharpe(r.to_numpy())
    null_sh = annualized_sharpe(r_n.to_numpy())
    gap = base_sh - null_sh
    print(f"\n  direction-gap (cont - fade) = {gap:+.2f}")
    if gap >= 0.30:
        print("    PASS: US lead signal has directional content.")
    elif gap <= -0.30:
        print("    INVERTED: fading the US lead wins — mechanism wrong sign.")
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
