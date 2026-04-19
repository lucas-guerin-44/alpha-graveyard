#!/usr/bin/env python3
"""
GER40 ORB — deploy config (T+180, LONG-only) sliced to Q1 2026.

What the live EA would have produced 2026-01-01 -> 2026-03-31 if it had been
running. Single-quarter, n=~50 trades — Sharpe is noisy at this sample size;
treat as a sanity check, not a verdict.

Run:
    venv/Scripts/python.exe experiments/orb/ger40_q1_2026.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# Force GER40 / EU session before importing orb_demo (which reads env at import).
os.environ.setdefault("ORB_SYMBOL", "GER40")
os.environ.setdefault("ORB_SESSION", "EU")

from orb_demo import (  # noqa: E402
    annualized_sharpe,
    load_m5,
    max_drawdown,
    section,
    simulate_orb,
)

Q1_START = "2026-01-01"
Q1_END = "2026-03-31"


def report_slice(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    if bar_ret.empty:
        print(f"  [{label}] no bars in window")
        return
    eq = (1.0 + bar_ret).cumprod()
    days = (bar_ret.index[-1] - bar_ret.index[0]).days
    years = days / 365.25 if days > 0 else 1e-9
    total = float(eq.iloc[-1] - 1.0)
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    wr = len(wins) / n if n else 0.0
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    avg_win = float(np.mean([t["pnl_pct"] for t in wins])) if wins else 0.0
    avg_loss = float(np.mean([t["pnl_pct"] for t in losses])) if losses else 0.0

    print(f"  [{label}]")
    print(f"    period      : {bar_ret.index[0].date()} -> {bar_ret.index[-1].date()} ({days}d)")
    print(f"    total ret   : {total * 100:+.2f}%")
    print(f"    ann. ret    : {((1 + total) ** (1 / years) - 1) * 100:+.2f}%")
    print(f"    Sharpe (ann): {sh:+.2f}")
    print(f"    Max DD      : {mdd * 100:+.2f}%")
    print(f"    trades      : {n}  ({n / max(years * 52, 1e-9):.2f}/wk)")
    print(f"    win rate    : {wr * 100:.1f}%")
    print(f"    profit fac. : {pf:.2f}")
    print(f"    avg win     : {avg_win * 100:+.3f}%   avg loss: {avg_loss * 100:+.3f}%")


def main() -> int:
    section("Loading GER40 M5 (EU session)")
    bars = load_m5("GER40")
    print(f"  bars: {len(bars):,}  range: {bars.index[0]} -> {bars.index[-1]}")

    # Force LONG-only via constant +1 trend bias on every date.
    all_dates = pd.Index(sorted({d for d in bars.index.date}))
    long_only_bias = pd.Series(1, index=all_dates, dtype=int)

    section("Running simulator (T+180 exit, LONG-only, 1pt RT cost)")
    bar_ret, trades = simulate_orb(
        bars,
        or_minutes=30,
        entry_cutoff_min=180,
        tod_exit_minutes=180,
        cost_points=1.0,
        trend_filter=long_only_bias,
    )
    print(f"  full-sample trades: {len(trades)}  bars: {len(bar_ret):,}")

    section(f"Q1 2026 slice ({Q1_START} -> {Q1_END})")
    q1_ret = bar_ret.loc[Q1_START:Q1_END]
    q1_trades = [t for t in trades if Q1_START <= str(t["date"]) <= Q1_END]
    report_slice("GER40 LONG-only T+180 — Q1 2026", q1_ret, q1_trades)

    if q1_trades:
        section("Q1 2026 trade ledger")
        df = pd.DataFrame(q1_trades)
        df["pnl_bp"] = df["pnl_pct"] * 10_000
        cols = ["date", "direction", "entry_ts", "exit_ts", "entry_px",
                "exit_px", "reason", "pnl_bp"]
        with pd.option_context("display.width", 200,
                               "display.max_rows", None,
                               "display.float_format", lambda x: f"{x:.2f}"):
            print(df[cols].to_string(index=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
