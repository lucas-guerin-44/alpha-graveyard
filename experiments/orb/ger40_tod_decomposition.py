#!/usr/bin/env python3
"""
GER40 ORB T+180 time-of-day edge decomposition.

Question: where in the 8.5h Xetra session (09:00-17:30 Berlin) does the
T+180 edge actually come from? Entries by hour — does it fire mostly morning
or mid-session? PnL by entry hour — is there an obvious sub-window that
carries the edge, or is it evenly distributed?

This informs whether to narrow ENTRY_CUTOFF_MIN to exclude late-session
entries that might add noise without alpha.

Also splits by LONG-only vs ALL per Phase 2e's asymmetry finding.
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
    load_m5, simulate_orb, annualized_sharpe, max_drawdown
)


def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def hour_bucket(ts: pd.Timestamp) -> int:
    return ts.hour


def report_by_hour(trades: list[dict], label: str) -> None:
    if not trades:
        print(f"  [{label}] (no trades)")
        return
    df = pd.DataFrame(trades)
    df["entry_ts"] = pd.to_datetime(df["entry_ts"])
    df["entry_hour"] = df["entry_ts"].dt.hour

    print(f"  [{label}]  total trades: {len(df)}")
    print(f"  {'hour':>5}  {'n':>5}  {'share':>6}  {'avg_pnl':>9}  "
          f"{'total':>9}  {'WR':>6}  {'tod_wr':>7}  {'stop_wr':>7}")
    print(f"  {'-'*5}  {'-'*5}  {'-'*6}  {'-'*9}  {'-'*9}  {'-'*6}  {'-'*7}  {'-'*7}")

    hours = sorted(df["entry_hour"].unique())
    for h in hours:
        sub = df[df["entry_hour"] == h]
        n = len(sub)
        share = n / len(df) * 100
        avg = sub["pnl_pct"].mean() * 100
        total = sub["pnl_pct"].sum() * 100
        wr = (sub["pnl_pct"] > 0).mean() * 100
        tod_trades = sub[sub["reason"] == "tod"]
        stop_trades = sub[sub["reason"] == "stop"]
        tod_wr = (tod_trades["pnl_pct"] > 0).mean() * 100 if len(tod_trades) else 0.0
        stop_share = len(stop_trades) / n * 100 if n else 0.0
        print(f"  {h:>5}  {n:>5}  {share:>5.1f}%  {avg:>+8.3f}%  "
              f"{total:>+8.2f}%  {wr:>5.1f}%  {tod_wr:>6.1f}%  {stop_share:>6.1f}%")

    # Bucketed summary
    print(f"\n  Bucketed summary:")
    buckets = [
        ("early 09-11 (first 3h)",  (9, 11)),
        ("mid 11-14 (midday)",       (11, 14)),
        ("late 14-17 (US overlap)",  (14, 17)),
    ]
    total_pnl = df["pnl_pct"].sum()
    for b_label, (a, b) in buckets:
        sub = df[(df["entry_hour"] >= a) & (df["entry_hour"] < b)]
        if len(sub) == 0:
            print(f"    {b_label:<28s}  n=   0   (no trades)")
            continue
        n = len(sub)
        pnl = sub["pnl_pct"].sum()
        avg = sub["pnl_pct"].mean() * 100
        wr = (sub["pnl_pct"] > 0).mean() * 100
        pnl_share = (pnl / total_pnl * 100) if total_pnl != 0 else 0
        print(f"    {b_label:<28s}  n={n:>4d}  avg={avg:>+6.3f}%  "
              f"total={pnl*100:>+6.2f}%  share={pnl_share:>+6.1f}% of all-PnL  WR={wr:>4.1f}%")


def main() -> int:
    section("Loading GER40 M5 (EU session)")
    bars = load_m5("GER40")
    print(f"  bars: {len(bars):,}   range: {bars.index[0]} -> {bars.index[-1]}")

    section("Running GER40 ORB T+180 baseline")
    bar_ret, trades = simulate_orb(bars, tod_exit_minutes=180)
    print(f"  total trades: {len(trades)}")

    section("TOD edge decomposition — ALL trades")
    report_by_hour(trades, "ALL")

    section("TOD edge decomposition — LONG-only trades")
    long_trades = [t for t in trades if t["direction"] == "LONG"]
    report_by_hour(long_trades, "LONG-only")

    section("TOD edge decomposition — SHORT-only trades")
    short_trades = [t for t in trades if t["direction"] == "SHORT"]
    report_by_hour(short_trades, "SHORT-only")

    # Entry-cutoff variant: limit to pre-US-open (cutoff at minute-of-day < 390
    # = before 15:30 Berlin = before US cash open). Roughly 6.5h of session.
    section("Entry-cutoff variants (where does narrowing help?)")
    # minute_of_day is minutes from RTH_OPEN (09:00 Berlin).
    # 09:00-12:00 = 0-180min; 09:00-15:30 = 0-390min; 09:00-17:00 = 0-480min
    cutoffs = [180, 240, 300, 390, 480]
    for cutoff in cutoffs:
        r_v, t_v = simulate_orb(bars, tod_exit_minutes=180, entry_cutoff_min=cutoff)
        sh = annualized_sharpe(r_v.to_numpy())
        eq = (1.0 + r_v).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        wr = sum(1 for t in t_v if t["pnl_pct"] > 0) / max(len(t_v), 1)
        gw = sum(t["pnl_pct"] for t in t_v if t["pnl_pct"] > 0)
        gl = -sum(t["pnl_pct"] for t in t_v if t["pnl_pct"] < 0)
        pf = gw / gl if gl > 0 else float("inf")
        print(f"  cutoff={cutoff:>4d}min (end {9 + cutoff//60:02d}:{cutoff%60:02d} Berlin)  "
              f"Sharpe {sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  "
              f"trades {len(t_v):>4d}  WR {wr*100:>4.1f}%  PF {pf:>4.2f}")

    section("Combined LONG-only + narrow entry cutoff (best of Phase 2e + 2f)")
    # Run symmetric, then filter trades by direction + entry-hour.
    for cutoff in cutoffs:
        _, t_v = simulate_orb(bars, tod_exit_minutes=180, entry_cutoff_min=cutoff)
        longs = [t for t in t_v if t["direction"] == "LONG"]
        if not longs:
            continue
        df = pd.DataFrame(longs)
        # Build minimal ret series (exit-bar pnl) aligned to the simulate_orb bar_ret index.
        ret = pd.Series(0.0, index=bar_ret.index)
        for t in longs:
            if t["exit_ts"] in ret.index:
                ret.loc[t["exit_ts"]] += t["pnl_pct"]
        sh = annualized_sharpe(ret.to_numpy())
        eq = (1.0 + ret).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        wr = sum(1 for t in longs if t["pnl_pct"] > 0) / max(len(longs), 1)
        gw = sum(t["pnl_pct"] for t in longs if t["pnl_pct"] > 0)
        gl = -sum(t["pnl_pct"] for t in longs if t["pnl_pct"] < 0)
        pf = gw / gl if gl > 0 else float("inf")
        # Regime holdout check
        hold = [t for t in longs if str(t["date"]) >= "2023-01-01"]
        hold_ret = pd.Series(0.0, index=bar_ret.loc["2023-01-01":].index)
        for t in hold:
            if t["exit_ts"] in hold_ret.index:
                hold_ret.loc[t["exit_ts"]] += t["pnl_pct"]
        hold_sh = annualized_sharpe(hold_ret.to_numpy())
        print(f"  LONG + cutoff={cutoff:>4d}min  Sharpe {sh:>+6.2f}  "
              f"holdout Sh {hold_sh:>+6.2f}  MDD {mdd*100:>+7.2f}%  "
              f"trades {len(longs):>4d}  WR {wr*100:>4.1f}%  PF {pf:>4.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
