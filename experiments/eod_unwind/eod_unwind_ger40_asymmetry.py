#!/usr/bin/env python3
"""
GER40 EOD-unwind long/short asymmetry split + per-regime.

Tests whether the +0.98 fade-gap on GER40 is directionally symmetric (both legs
contribute) or concentrated on one side. On a secular-up-drift instrument
(DAX 2019-2026: 10,600 -> 22,000+), the fade of up-days is a short working
against drift; fade of down-days is a long in the direction of drift. If the
edge is LONG-only, full-sample Sharpe should improve materially with
halved trade count.

Run:
    venv/Scripts/python.exe experiments/eod_unwind/eod_unwind_ger40_asymmetry.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

# Force GER40 / EU session regardless of env state.
os.environ["EOD_SYMBOL"] = "GER40"
os.environ["EOD_SESSION"] = "EU"

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from eod_unwind_demo import (  # noqa: E402
    annualized_sharpe,
    load_m5,
    max_drawdown,
    simulate_eod_unwind,
)


def summarize(label: str, bar_ret: pd.Series, trades: list[dict]) -> dict:
    eq = (1.0 + bar_ret).cumprod()
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n = len(trades)
    wins = sum(1 for t in trades if t["pnl_pct"] > 0)
    wr = wins / n if n else 0.0
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    tpw = n / (years * 52) if years > 0 else 0.0
    print(f"  {label:<20s} n={n:<4d}  Sh {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  "
          f"PF {pf:>4.2f}  WR {wr * 100:>4.1f}%  trades/wk {tpw:>4.2f}")
    return {"label": label, "sharpe": sh, "mdd": mdd, "n": n, "pf": pf, "wr": wr}


def regime_split(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026HO", "2023-01-01", "2026-12-31"),
    ]
    parts: list[str] = []
    for wlabel, s, e in windows:
        sub = bar_ret.loc[s:e]
        sub_n = sum(1 for t in trades if s <= str(t["date"]) <= e)
        if len(sub) < 200:
            parts.append(f"{wlabel} (n/a)")
            continue
        sh = annualized_sharpe(sub.to_numpy())
        eq = (1.0 + sub).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        parts.append(f"{wlabel} Sh {sh:>+5.2f} MDD {mdd * 100:>+6.1f}% n {sub_n}")
    print(f"  {label:<20s}  " + "  |  ".join(parts))


def section(t: str) -> None:
    print(f"\n{'=' * 90}\n  {t}\n{'=' * 90}\n")


def main() -> int:
    section("Loading GER40 M5 (EU session, 09:00-17:30 Berlin)")
    bars = load_m5("GER40")
    print(f"  bars: {len(bars):,}   range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    # --- Threshold sweep per leg, cost 1pt, baseline T-45 entry, EOD exit ---
    section("LEG split at baseline thresholds (T-45 entry, EOD exit, cost=1pt)")
    print(f"  {'leg':<20s}")
    rows = []
    for thr in (0.25, 0.5, 1.0, 1.5):
        print(f"\n  threshold = {thr} * ATR20")
        for leg in ("both", "long", "short"):
            r, t = simulate_eod_unwind(bars, min_move_atr=thr, leg=leg)
            rows.append({
                "thr": thr, "leg": leg,
                **summarize(f"  {leg:<6s}", r, t),
                "bar_ret": r, "trades": t,
            })

    # --- Regime-splits on the key candidate combinations ---
    section("Regime split — key candidates (T-45 entry, EOD exit, cost=1pt)")
    print(f"  {'config':<20s}  {'(2019-2020 vs 2021-2022 vs 2023-2026 holdout)'}\n")
    candidates = [
        ("both, thr=0.5",  {"min_move_atr": 0.5, "leg": "both"}),
        ("LONG, thr=0.5",  {"min_move_atr": 0.5, "leg": "long"}),
        ("SHORT, thr=0.5", {"min_move_atr": 0.5, "leg": "short"}),
        ("both, thr=1.0",  {"min_move_atr": 1.0, "leg": "both"}),
        ("LONG, thr=1.0",  {"min_move_atr": 1.0, "leg": "long"}),
        ("SHORT, thr=1.0", {"min_move_atr": 1.0, "leg": "short"}),
    ]
    for label, kw in candidates:
        r, t = simulate_eod_unwind(bars, **kw)
        regime_split(label, r, t)

    # --- Cost sensitivity on the strongest long-only candidate ---
    section("Cost sensitivity — LONG-only, thr=0.5 and thr=1.0")
    print(f"  {'thr':<4s} {'cost':<6s}  {'full':<10s}  {'holdout':<10s}")
    for thr in (0.5, 1.0):
        for cost in (0.5, 1.0, 1.5, 2.0):
            r, t = simulate_eod_unwind(bars, min_move_atr=thr, leg="long", cost_points=cost)
            full_sh = annualized_sharpe(r.to_numpy())
            ho = r.loc["2023-01-01":"2026-12-31"]
            ho_sh = annualized_sharpe(ho.to_numpy()) if len(ho) > 200 else 0.0
            print(f"  {thr}  {cost}pt    Sh {full_sh:>+5.2f}     Sh {ho_sh:>+5.2f}")

    # --- Entry timing x threshold interaction, LONG-only ---
    section("Entry-timing x threshold interaction — LONG-only, cost=1pt")
    print(f"  {'entry':<10s} " + "  ".join(f"thr={t:<4.2f}" for t in (0.5, 1.0, 1.5)))
    for em in (30, 45, 60, 90):
        vals = []
        for thr in (0.5, 1.0, 1.5):
            r, t = simulate_eod_unwind(bars, entry_min_before_close=em, min_move_atr=thr, leg="long")
            sh = annualized_sharpe(r.to_numpy())
            vals.append(f"{sh:>+6.2f}")
        print(f"  T-{em}min   " + "  ".join(f"{v:<8s}" for v in vals))

    # --- Honesty check: the "just be long the close" benchmark ---
    # Long GER40 from T-45 to close every day (no signal). This quantifies how
    # much of any LONG-only edge is just secular drift vs genuine unwind alpha.
    section("Honesty benchmark — LONG every day T-45 -> close (no signal)")
    idx = bars.index
    rth_open_min = bars.index[0].hour * 60 + bars.index[0].minute  # not precise; use session
    # Use same session constants as the demo.
    from datetime import time as dtime
    RTH_OPEN = dtime(9, 0)
    RTH_CLOSE = dtime(17, 30)
    rth_open_min = RTH_OPEN.hour * 60 + RTH_OPEN.minute
    rth_close_min = RTH_CLOSE.hour * 60 + RTH_CLOSE.minute
    rth_minutes = rth_close_min - rth_open_min
    mod = np.asarray(idx.hour) * 60 + np.asarray(idx.minute) - rth_open_min
    entry_target = rth_minutes - 45
    exit_target = rth_minutes - 5
    close_arr = bars["close"].to_numpy()
    open_arr = bars["open"].to_numpy()
    dates = np.asarray(idx.date)
    change = np.empty(len(idx), dtype=bool)
    change[0] = True
    change[1:] = dates[1:] != dates[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = len(idx)
    ret_arr = np.zeros(len(idx))
    trades: list[dict] = []
    for d_i in range(len(day_starts)):
        s, e = int(day_starts[d_i]), int(day_ends[d_i])
        n = e - s
        if n < 4:
            continue
        day_mod = mod[s:e]
        day_close = close_arr[s:e]
        cand_entry = np.flatnonzero(day_mod >= entry_target)
        cand_exit = np.flatnonzero(day_mod >= exit_target)
        if cand_entry.size == 0 or cand_exit.size == 0:
            continue
        entry_bar = int(cand_entry[0])
        exit_bar = int(cand_exit[0])
        if entry_bar + 1 >= n or exit_bar <= entry_bar + 1:
            continue
        entry_px = float(open_arr[s + entry_bar + 1])
        exit_px = float(day_close[exit_bar])
        cost_ret = 1.0 / entry_px
        for j in range(entry_bar + 1, exit_bar + 1):
            prev = entry_px if j == entry_bar + 1 else day_close[j - 1]
            cur = exit_px if j == exit_bar else day_close[j]
            ret_arr[s + j] = (cur - prev) / prev
        ret_arr[s + exit_bar] -= cost_ret
        trades.append({"date": dates[s], "pnl_pct": (exit_px - entry_px) / entry_px - cost_ret})
    bench_ret = pd.Series(ret_arr, index=idx)
    summarize("long-always", bench_ret, trades)
    regime_split("long-always", bench_ret, trades)

    return 0


if __name__ == "__main__":
    sys.exit(main())
