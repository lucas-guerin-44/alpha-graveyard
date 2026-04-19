#!/usr/bin/env python3
"""Regime breakdown on ORB top refinement candidates (instrument-agnostic).

Runs the 5 most promising variants from `orb_refine.py` on three
non-overlapping windows (2019-2020, 2021-2022, 2023-2026 holdout) to
check whether refinements generalize or are 2019-2022 overfits.

Plus a fade-test on the leading variant (confirms directional signal at the
refined exit structure, not just under the naive EOD baseline) and a cost
sensitivity sweep on the leader.

    ORB_SYMBOL=GER40 ORB_SESSION=EU python experiments/orb/orb_holdout.py

This is the second half of the per-instrument refinement workflow — run
`orb_refine.py` first to find the leading variant, then `orb_holdout.py`
to confirm the regime stability and directional-signal robustness.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# ORB_SYMBOL and ORB_SESSION must be set by caller.

import numpy as np  # noqa: E402

from orb_demo import (  # noqa: E402
    load_m5, simulate_orb, annualized_sharpe, max_drawdown, SYMBOL,
)


def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


WINDOWS = [
    ("2019-2020 pre/COVID", "2019-01-01", "2020-12-31"),
    ("2021-2022 vol",       "2021-01-01", "2022-12-31"),
    ("2023-2026 holdout",   "2023-01-01", "2026-12-31"),
]

CANDIDATES = [
    ("Baseline (EOD, full-OR stop)", dict()),
    ("1:2 R:R target, EOD",          dict(rr_target=2.0)),
    ("T+180min exit (no RR)",        dict(tod_exit_minutes=180)),
    ("T+180min + 1:2 R:R",           dict(tod_exit_minutes=180, rr_target=2.0)),
    ("T+180min + 1:1 R:R",           dict(tod_exit_minutes=180, rr_target=1.0)),
]


def regime_row(label: str, bar_ret, trades):
    windows_out = []
    for win_label, s, e in WINDOWS:
        sub_ret = bar_ret.loc[s:e]
        if len(sub_ret) < 200:
            windows_out.append((win_label, None, None, None, 0))
            continue
        eq = (1.0 + sub_ret).cumprod()
        sh = annualized_sharpe(sub_ret.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        n_trades = sum(1 for t in trades if s <= str(t["date"]) <= e)
        cagr = float(eq.iloc[-1]) ** (365.25 / max((sub_ret.index[-1] - sub_ret.index[0]).days, 1)) - 1
        windows_out.append((win_label, sh, mdd, cagr, n_trades))
    return windows_out


def main() -> int:
    section(f"Loading {SYMBOL} M5")
    bars = load_m5(SYMBOL)
    print(f"  bars: {len(bars):,}  range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    section(f"Regime breakdown across top {SYMBOL} ORB variants")
    print(f"  {'Variant':<36s} | {'2019-2020':<16s} | {'2021-2022':<16s} | {'2023-2026 HO':<16s} | full-Sh")
    print(f"  {'-' * 36}-+-{'-' * 16}-+-{'-' * 16}-+-{'-' * 16}-+-{'-' * 7}")

    for label, kwargs in CANDIDATES:
        bar_ret, trades = simulate_orb(bars, **kwargs)
        full_sh = annualized_sharpe(bar_ret.to_numpy())
        rows = regime_row(label, bar_ret, trades)
        cells = []
        for _, sh, mdd, cagr, n in rows:
            if sh is None:
                cells.append(" " * 16)
            else:
                cells.append(f"Sh {sh:>+5.2f} DD {mdd * 100:>+5.1f}%")
        print(f"  {label:<36s} | {cells[0]:<16s} | {cells[1]:<16s} | {cells[2]:<16s} | {full_sh:>+5.2f}")

    section("Fade test on leading variant (T+180min + 1:2 R:R)")
    r_base, t_base = simulate_orb(bars, tod_exit_minutes=180, rr_target=2.0)
    r_fade, t_fade = simulate_orb(bars, tod_exit_minutes=180, rr_target=2.0, fade=True)
    sh_base = annualized_sharpe(r_base.to_numpy())
    sh_fade = annualized_sharpe(r_fade.to_numpy())
    gap = sh_base - sh_fade
    print(f"  baseline Sharpe: {sh_base:+.2f}  |  fade Sharpe: {sh_fade:+.2f}  |  gap: {gap:+.2f}")
    if gap > 0.5:
        print("  -> STRONG directional edge confirmed on leading variant.")
    elif gap > 0.2:
        print("  -> Moderate directional edge.")
    else:
        print("  -> Weak edge; refinement mostly R:R-structure.")

    section("Cost sensitivity on leading variant")
    for cost in (0.5, 1.0, 1.5, 2.0):
        r_v, t_v = simulate_orb(bars, tod_exit_minutes=180, rr_target=2.0, cost_points=cost)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={cost:.1f}pt  Sharpe {sh:+.2f}  trades {len(t_v)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
