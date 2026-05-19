#!/usr/bin/env python3
"""
DAX overnight drift capture (buy last bar of session d, sell first bar open of d+1).

Thesis: experiments/dax/overnight.md

Run:
    venv/Scripts/python.exe experiments/dax/overnight_demo.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from _common import (  # noqa: E402
    DAYS_PER_YEAR,
    annualized_sharpe,
    compute_day_groups,
    kill_criteria_check,
    load_dax_m5,
    max_drawdown,
    regime_breakdown,
    report_run,
    section,
)


def simulate_overnight(
    bars: pd.DataFrame,
    direction: str = "long",       # 'long' | 'short'
    cost_points: float = 1.0,
    dow_filter: set[int] | None = None,       # e.g. {0, 4} for Mon/Fri only
    prior_direction_filter: int | None = None,  # +1 (after up-day), -1 (after down-day)
) -> tuple[pd.Series, list[dict]]:
    idx = bars.index
    if len(idx) == 0:
        return pd.Series(dtype=float, name="on_ret"), []

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)
    dates, day_starts, day_ends = compute_day_groups(idx)

    n_days = len(day_starts)
    daily_open = np.array([open_arr[int(s)] for s in day_starts])
    daily_close = np.array([close_arr[int(e) - 1] for e in day_ends])
    daily_dates = np.array([dates[int(s)] for s in day_starts])

    # Build a per-day trade return series (one observation per overnight window).
    daily_ret = np.zeros(n_days, dtype=np.float64)
    trades: list[dict] = []

    sign = 1.0 if direction == "long" else -1.0

    for d_i in range(n_days - 1):
        entry_px = float(daily_close[d_i])
        exit_px = float(daily_open[d_i + 1])

        if dow_filter is not None:
            entry_dow = pd.Timestamp(daily_dates[d_i]).weekday()
            if entry_dow not in dow_filter:
                continue

        if prior_direction_filter is not None and d_i > 0:
            prev_ret = daily_close[d_i] - daily_close[d_i - 1]
            prev_sign = 1 if prev_ret > 0 else (-1 if prev_ret < 0 else 0)
            if prev_sign != prior_direction_filter:
                continue

        cost_ret = cost_points / entry_px
        pnl = sign * (exit_px / entry_px - 1.0) - cost_ret
        daily_ret[d_i + 1] = pnl  # booked on the morning of d+1

        trades.append({
            "date": daily_dates[d_i + 1],
            "direction": "LONG" if sign > 0 else "SHORT",
            "entry_ts": idx[int(day_ends[d_i]) - 1],
            "exit_ts": idx[int(day_starts[d_i + 1])],
            "entry_px": entry_px,
            "exit_px": exit_px,
            "pnl_pct": float(pnl),
            "reason": "overnight",
        })

    # Build a Series indexed by the DAX day-opening timestamp.
    day_open_idx = pd.DatetimeIndex([idx[int(s)] for s in day_starts])
    ret_series = pd.Series(daily_ret, index=day_open_idx, name="on_ret")
    return ret_series, trades


def main() -> int:
    section("Loading GER40 M5 (EU session, 09:00-17:30 Berlin)")
    bars = load_dax_m5()
    print(f"  bars: {len(bars):,}   range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    # Overnight trades happen 1/day — use DAYS_PER_YEAR for Sharpe, not BARS_PER_YEAR.
    bpy = DAYS_PER_YEAR

    section("Baseline (always LONG overnight, cost=1pt)")
    r, t = simulate_overnight(bars)
    report_run("baseline-long", r, t, bars_per_year=bpy)

    section("Phase 2 kill-criteria (Sharpe > 0.20)")
    kill_criteria_check("baseline-long", r, t, sharpe_min=0.20, wr_min=0.50, pf_min=1.05,
                        bars_per_year=bpy)

    section("Regime breakdown")
    regime_breakdown(r, t, bars_per_year=bpy)

    section("Null-check — always SHORT overnight")
    r_s, t_s = simulate_overnight(bars, direction="short")
    report_run("short", r_s, t_s, bars_per_year=bpy)
    long_sh = annualized_sharpe(r.to_numpy(), bpy)
    short_sh = annualized_sharpe(r_s.to_numpy(), bpy)
    print(f"\n  LONG + SHORT Sharpe = {long_sh:+.2f} + {short_sh:+.2f} = {long_sh + short_sh:+.2f}")
    if long_sh + short_sh < -0.30:
        print("  PASS: sum strongly negative → real overnight drift premium exists.")
    elif long_sh > 0.10 and short_sh < -0.10:
        print("  PASS: long + short antisymmetric, mild premium.")
    else:
        print("  FAIL: no clear overnight drift signal.")

    section("Day-of-week split (LONG)")
    dow_labels = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
    for dow, label in dow_labels.items():
        r_d, t_d = simulate_overnight(bars, dow_filter={dow})
        sh = annualized_sharpe(r_d.to_numpy(), bpy)
        avg = np.mean([t["pnl_pct"] for t in t_d]) if t_d else 0.0
        wins = sum(1 for t in t_d if t["pnl_pct"] > 0)
        wr = wins / len(t_d) if t_d else 0.0
        print(f"  {label}  n={len(t_d):>4d}  Sharpe {sh:>+6.2f}  avg {avg * 100:>+.3f}%  WR {wr * 100:>4.1f}%")

    section("Prior-day direction conditional (LONG)")
    for pd_filt, label in [(1, "after UP day"), (-1, "after DOWN day")]:
        r_p, t_p = simulate_overnight(bars, prior_direction_filter=pd_filt)
        sh = annualized_sharpe(r_p.to_numpy(), bpy)
        print(f"  {label:<16s}  n={len(t_p):>4d}  Sharpe {sh:>+6.2f}")

    section("Cost sensitivity (LONG)")
    for c in (0.5, 1.0, 2.0, 3.0):
        r_c, t_c = simulate_overnight(bars, cost_points=c)
        sh = annualized_sharpe(r_c.to_numpy(), bpy)
        print(f"  cost={c:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_c):>4d}")

    section("Summary")
    eq = (1 + r).cumprod()
    years = (r.index[-1] - r.index[0]).days / 365.25
    print(f"  baseline-long : CAGR {(float(eq.iloc[-1])) ** (1/max(years,1e-9)) - 1:+.2%}  "
          f"Sharpe {long_sh:+.2f}  MDD {max_drawdown(eq.to_numpy())*100:+.2f}%  "
          f"trades {len(t)} ({len(t)/max(years*52,1e-9):.2f}/week)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
