#!/usr/bin/env python3
"""
GER40 LONG-only ORB vs unconditional intraday drift benchmark.

Question: how much of LONG-only ORB T+180's +0.76 Sharpe is actually just
capturing DAX's 2019-2026 upward drift baseline vs real breakout alpha?

Benchmarks:
  1. "Long from HH:MM Berlin to HH:MM+180min every day" — no trigger, no
     breakout conditioning. Just sit long for 3h starting at various
     fixed anchor times within the 09:30-12:00 Berlin entry window.
  2. "Long from 09:30 to 17:25 Berlin every day" — whole-session unconditional
     long (more extreme drift-capture benchmark).

If benchmark Sharpe >= ORB LONG-only Sharpe, ORB adds no real alpha over
calendar-timed drift. If ORB is decisively higher, the breakout trigger is
adding real signal beyond drift.

Cost: 1pt RT per trade (matches research convention).
"""

from __future__ import annotations

import os
import sys
from datetime import time as dtime

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

os.environ.setdefault("ORB_SYMBOL", "GER40")
os.environ.setdefault("ORB_SESSION", "EU")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from orb_demo import (  # noqa: E402
    load_m5, simulate_orb, annualized_sharpe, max_drawdown, BARS_PER_YEAR
)


def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


WINDOWS = [
    ("FULL 2019-2026",       "2019-01-01", "2026-12-31"),
    ("2019-2020 pre/COVID",  "2019-01-01", "2020-12-31"),
    ("2021-2022 vol",        "2021-01-01", "2022-12-31"),
    ("2023-2026 holdout",    "2023-01-01", "2026-12-31"),
]


def drift_benchmark(bars: pd.DataFrame, entry_hour: int, entry_min: int,
                    hold_minutes: int, cost_points: float = 1.0) -> tuple[pd.Series, list[dict]]:
    """
    Enter long at the bar with minute-of-day matching entry_hour:entry_min
    (use its open as entry price). Exit at entry+hold_minutes (use that bar's
    close). Apply 1pt RT cost.
    """
    bars = bars.copy()
    bars["date"] = bars.index.date

    ret = pd.Series(0.0, index=bars.index)
    trades: list[dict] = []

    entry_mod = entry_hour * 60 + entry_min
    session_start_mod = 9 * 60  # Berlin 09:00

    for day, day_bars in bars.groupby("date", sort=True):
        if len(day_bars) < 20:
            continue
        hours = day_bars.index.hour.values
        mins = day_bars.index.minute.values
        day_mod = hours * 60 + mins
        entry_idx_arr = np.where(day_mod == entry_mod)[0]
        if len(entry_idx_arr) == 0:
            continue
        entry_idx = int(entry_idx_arr[0])

        # exit index = entry_idx + hold_minutes/5
        exit_bars_ahead = hold_minutes // 5
        exit_idx = entry_idx + exit_bars_ahead
        if exit_idx >= len(day_bars):
            exit_idx = len(day_bars) - 1

        entry_px = float(day_bars.iloc[entry_idx]["open"])
        exit_px = float(day_bars.iloc[exit_idx]["close"])
        exit_ts = day_bars.index[exit_idx]

        # Mark-to-market across held bars
        closes = day_bars["close"].values
        for i in range(entry_idx, exit_idx + 1):
            ts = day_bars.index[i]
            if i == entry_idx:
                prev = entry_px
            else:
                prev = closes[i - 1]
            cur = closes[i]
            if i == exit_idx:
                cur = exit_px
            ret.loc[ts] = (cur - prev) / prev

        cost_ret = cost_points / entry_px
        ret.loc[exit_ts] = ret.loc[exit_ts] - cost_ret

        trades.append({
            "date": day,
            "direction": "LONG",
            "entry_ts": day_bars.index[entry_idx],
            "exit_ts": exit_ts,
            "entry_px": entry_px,
            "exit_px": exit_px,
            "pnl_pct": (exit_px - entry_px) / entry_px - cost_ret,
            "reason": "drift",
        })

    bar_ret = ret.fillna(0.0)
    bar_ret.name = f"drift_{entry_hour:02d}{entry_min:02d}_h{hold_minutes}"
    return bar_ret, trades


def report(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    if bar_ret is None or len(bar_ret) == 0:
        print(f"  {label:<40s}  (no data)")
        return
    eq = (1.0 + bar_ret).cumprod()
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n = len(trades) if trades else 0
    wr = sum(1 for t in trades if t["pnl_pct"] > 0) / max(n, 1) if trades else 0.0
    avg = np.mean([t["pnl_pct"] for t in trades]) * 100 if trades else 0.0
    print(f"  {label:<40s}  Sharpe {sh:>+6.2f}  CAGR {cagr*100:>+6.2f}%  "
          f"MDD {mdd*100:>+7.2f}%  n={n:>4d}  WR {wr*100:>4.1f}%  avg {avg:>+.3f}%")


def windowed_report(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    print(f"\n  [{label}]")
    for win_label, s, e in WINDOWS:
        sub_ret = bar_ret.loc[s:e]
        sub_trades = [t for t in trades if s <= str(t["date"]) <= e] if trades else []
        if len(sub_ret) < 200:
            print(f"    {win_label:<24s}  (insufficient bars)")
            continue
        sh = annualized_sharpe(sub_ret.to_numpy())
        eq = (1.0 + sub_ret).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        n = len(sub_trades)
        print(f"    {win_label:<24s}  Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  n={n:>4d}")


def main() -> int:
    section("Loading GER40 M5 (EU session)")
    bars = load_m5("GER40")
    print(f"  bars: {len(bars):,}   range: {bars.index[0]} -> {bars.index[-1]}")

    section("ORB T+180 LONG-only (the incumbent being compared)")
    orb_ret, orb_trades = simulate_orb(bars, tod_exit_minutes=180)
    long_trades = [t for t in orb_trades if t["direction"] == "LONG"]
    long_ret = pd.Series(0.0, index=orb_ret.index)
    for t in long_trades:
        if t["exit_ts"] in long_ret.index:
            long_ret.loc[t["exit_ts"]] += t["pnl_pct"]
    report("ORB LONG-only T+180 (expected +0.76)", long_ret, long_trades)
    windowed_report("ORB LONG-only T+180 — regime split", long_ret, long_trades)

    section("Drift benchmark — long for 180min starting at fixed Berlin time")
    print("  (No trigger, no breakout conditioning — just hold long for 3h from anchor time)\n")
    # Match the LONG-only average entry time. From tod_decomposition.py, entries
    # are 09:00-12:00 Berlin, weighted avg ~10:00-10:30. Test several anchors.
    anchors = [
        (9, 30, 180),    # enter 09:30, exit 12:30 — matches earliest ORB entries
        (10, 0, 180),    # enter 10:00, exit 13:00 — matches median ORB entry
        (10, 30, 180),   # enter 10:30, exit 13:30
        (11, 0, 180),    # enter 11:00, exit 14:00
    ]
    for h, m, hold in anchors:
        r, t = drift_benchmark(bars, h, m, hold)
        report(f"drift {h:02d}:{m:02d} -> +{hold}min", r, t)

    section("Per-regime drift vs ORB LONG-only (head-to-head)")
    # Use the 10:00 anchor as the closest match to ORB's median entry.
    drift_ret, drift_trades = drift_benchmark(bars, 10, 0, 180)
    windowed_report("Drift 10:00+180min", drift_ret, drift_trades)

    section("Alpha estimate — ORB LONG-only minus drift benchmark (per regime)")
    print("  If delta > 0.2 Sharpe meaningfully, ORB is adding real signal beyond drift.")
    print(f"\n  {'Window':<26s}  {'ORB LONG':>10s}  {'Drift 10:00':>12s}  {'delta Sh':>10s}")
    for win_label, s, e in WINDOWS:
        sub_orb = long_ret.loc[s:e]
        sub_drift = drift_ret.loc[s:e]
        if len(sub_orb) < 200 or len(sub_drift) < 200:
            continue
        sh_o = annualized_sharpe(sub_orb.to_numpy())
        sh_d = annualized_sharpe(sub_drift.to_numpy())
        print(f"  {win_label:<26s}  {sh_o:>+9.2f}   {sh_d:>+11.2f}   {sh_o - sh_d:>+9.2f}")

    section("Bonus — whole-session unconditional long (09:30-17:25 Berlin)")
    whole, whole_t = drift_benchmark(bars, 9, 30, 475)   # ~7.9h hold
    report("drift 09:30 -> session close", whole, whole_t)
    windowed_report("whole-session — regime split", whole, whole_t)

    section("Read")
    print("  - If ORB-drift Sh delta >= +0.2 on full-sample AND on holdout, the")
    print("    breakout trigger is adding real alpha on top of drift.")
    print("  - If delta is flat or negative, LONG-only ORB is roughly a drift-timer")
    print("    and the 'alpha' is mostly the 2019-2026 bull tape.")
    print("  - The MDD comparison also matters: ORB should have smaller DDs than")
    print("    unconditional-long because the stop is still being hit in the bad days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
