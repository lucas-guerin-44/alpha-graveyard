#!/usr/bin/env python3
"""
GER40 ORB T+180 long/short asymmetry split.

Question: is the +0.58 full-sample Sharpe symmetric across long/short trades,
or dominated by one side? If only longs (or only shorts) pay, we can halve
the trade count and potentially clean up the holdout Sharpe further.

Reuses orb_demo.simulate_orb() for the simulation; does post-hoc trade
filtering for direction split.
"""

from __future__ import annotations

import os
import sys

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


def equity_from_trades(trades: list[dict], bar_index: pd.DatetimeIndex) -> pd.Series:
    """Build a bar-return series from trades (already net of costs).

    Allocates each trade's pnl to its exit bar; all other bars = 0. Good enough
    for Sharpe / MDD at daily-equivalent granularity since we're flat overnight.
    """
    ret = pd.Series(0.0, index=bar_index)
    for t in trades:
        exit_ts = t["exit_ts"]
        if exit_ts in ret.index:
            # Pnl is already total trade pnl (net of cost). Stamp it to exit bar.
            ret.loc[exit_ts] += t["pnl_pct"]
    return ret


def stats_for_trades(trades: list[dict], bar_index: pd.DatetimeIndex) -> dict:
    if not trades:
        return dict(n=0, sh=0.0, mdd=0.0, cagr=0.0, wr=0.0, pf=0.0)
    ret = equity_from_trades(trades, bar_index)
    eq = (1.0 + ret).cumprod()
    years = (bar_index[-1] - bar_index[0]).days / 365.25
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    # For Sharpe we annualize based on BARS_PER_YEAR like the baseline.
    sh = annualized_sharpe(ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    wins = [x for x in trades if x["pnl_pct"] > 0]
    wr = len(wins) / len(trades)
    gw = sum(x["pnl_pct"] for x in trades if x["pnl_pct"] > 0)
    gl = -sum(x["pnl_pct"] for x in trades if x["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    return dict(n=len(trades), sh=sh, mdd=mdd, cagr=cagr, wr=wr, pf=pf)


def report(label: str, s: dict) -> None:
    print(f"  {label:<22s}  n={s['n']:>5d}  Sharpe {s['sh']:>+6.2f}  "
          f"CAGR {s['cagr']*100:>+6.2f}%  MDD {s['mdd']*100:>+7.2f}%  "
          f"WR {s['wr']*100:>4.1f}%  PF {s['pf']:.2f}")


WINDOWS = [
    ("FULL 2019-2026",       "2019-01-01", "2026-12-31"),
    ("2019-2020 pre/COVID",  "2019-01-01", "2020-12-31"),
    ("2021-2022 vol",        "2021-01-01", "2022-12-31"),
    ("2023-2026 holdout",    "2023-01-01", "2026-12-31"),
]


def main() -> int:
    section("Loading GER40 M5 (EU session)")
    bars = load_m5("GER40")
    print(f"  bars: {len(bars):,}   range: {bars.index[0]} -> {bars.index[-1]}")

    # Run the leading GER40 candidate: T+180min exit, no RR target, 1pt cost.
    section("Running GER40 ORB T+180 baseline (the deploy candidate)")
    bar_ret, trades = simulate_orb(bars, tod_exit_minutes=180)
    print(f"  total trades: {len(trades)}")

    # Convert to DataFrame for slicing.
    tdf = pd.DataFrame(trades)
    tdf["date"] = pd.to_datetime(tdf["date"])

    for win_label, s, e in WINDOWS:
        section(f"Window: {win_label}  ({s} -> {e})")
        mask = (tdf["date"] >= s) & (tdf["date"] <= e)
        window_trades = tdf[mask].to_dict("records")
        bar_idx = bar_ret.loc[s:e].index
        if len(bar_idx) < 200:
            print("  (insufficient bars)")
            continue

        all_s = stats_for_trades(window_trades, bar_idx)
        long_s = stats_for_trades([t for t in window_trades if t["direction"] == "LONG"], bar_idx)
        short_s = stats_for_trades([t for t in window_trades if t["direction"] == "SHORT"], bar_idx)

        report("ALL",   all_s)
        report("LONG-only",  long_s)
        report("SHORT-only", short_s)

        # Imbalance summary
        print(f"\n  Long-vs-Short Sharpe delta : {long_s['sh'] - short_s['sh']:+.2f}")
        print(f"  Long share of trades       : {long_s['n'] / max(all_s['n'], 1) * 100:.1f}%")

    section("Exit-reason attribution on long-only vs short-only (full sample)")
    for direction in ("LONG", "SHORT"):
        dir_trades = [t for t in trades if t["direction"] == direction]
        reason_pnl: dict[str, list[float]] = {}
        for t in dir_trades:
            reason_pnl.setdefault(t["reason"], []).append(t["pnl_pct"])
        print(f"\n  [{direction}]")
        for reason, pnls in sorted(reason_pnl.items()):
            arr = np.array(pnls)
            print(f"    {reason:<8s} n={len(arr):>4d}  "
                  f"avg={arr.mean()*100:+.3f}%  total={arr.sum()*100:+.2f}%  "
                  f"wr={(arr > 0).mean()*100:>4.1f}%")

    section("Summary read")
    print("  Look at full-sample delta and holdout delta. If LONG-only has")
    print("  better holdout Sharpe than SHORT-only, the edge is asymmetric and")
    print("  a long-only restriction may halve trade count with minimal Sharpe loss.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
