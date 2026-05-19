#!/usr/bin/env python3
"""
DAX overnight drift refinement — combined drop-Friday + after-DOWN-day filter.

Builds on overnight_demo.py Phase 2 findings:
  - Baseline always-LONG: Sh +0.42, MDD -32% (FAIL)
  - Friday overnight: Sh -0.40 (drag)
  - After-DOWN-day: Sh +0.54 (concentrated premium)

Tests whether combining both filters clears the Phase 2 bar (Sh > 0.20, MDD < 25%,
>= 2 of 3 regime windows positive) under single-rule discipline.
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
    kill_criteria_check,
    load_dax_m5,
    max_drawdown,
    regime_breakdown,
    report_run,
    section,
)
from overnight_demo import simulate_overnight  # noqa: E402

NON_FRIDAY_DOW = {0, 1, 2, 3}  # Mon-Thu (Friday = 4 excluded)


def summarize(label: str, r: pd.Series, t: list[dict], bpy: int) -> dict:
    eq = (1 + r).cumprod()
    sh = annualized_sharpe(r.to_numpy(), bpy)
    mdd = max_drawdown(eq.to_numpy())
    n = len(t)
    wr = sum(1 for x in t if x["pnl_pct"] > 0) / n if n else 0.0
    gw = sum(x["pnl_pct"] for x in t if x["pnl_pct"] > 0)
    gl = -sum(x["pnl_pct"] for x in t if x["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    years = (r.index[-1] - r.index[0]).days / 365.25
    tpw = n / (years * 52) if years > 0 else 0.0
    print(f"  {label:<24s} n={n:<4d}  Sh {sh:>+5.2f}  MDD {mdd*100:>+7.2f}%  "
          f"PF {pf:>4.2f}  WR {wr*100:>4.1f}%  t/wk {tpw:>4.2f}")
    return {"sh": sh, "mdd": mdd, "n": n}


def regime_compact(label: str, r: pd.Series, t: list[dict], bpy: int) -> None:
    windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026HO", "2023-01-01", "2026-12-31"),
    ]
    parts = []
    for w, s, e in windows:
        sub = r.loc[s:e]
        sub_t = [x for x in t if s <= str(x["date"]) <= e]
        if len(sub) < 50:
            parts.append(f"{w} (n/a)")
            continue
        sh = annualized_sharpe(sub.to_numpy(), bpy)
        eq = (1 + sub).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        parts.append(f"{w} Sh {sh:>+5.2f} MDD {mdd*100:>+6.1f}% n {len(sub_t)}")
    print(f"  {label:<24s}  " + "  |  ".join(parts))


def main() -> int:
    section("Loading GER40 M5")
    bars = load_dax_m5()
    print(f"  bars: {len(bars):,}   range: {bars.index[0].date()} -> {bars.index[-1].date()}")
    bpy = DAYS_PER_YEAR

    section("Filter sweep — baseline + each filter + combined (always LONG, cost=1pt)")
    r_b, t_b = simulate_overnight(bars)
    summarize("baseline", r_b, t_b, bpy)
    r_nf, t_nf = simulate_overnight(bars, dow_filter=NON_FRIDAY_DOW)
    summarize("drop-Fri", r_nf, t_nf, bpy)
    r_dn, t_dn = simulate_overnight(bars, prior_direction_filter=-1)
    summarize("after-DOWN", r_dn, t_dn, bpy)
    r_c, t_c = simulate_overnight(bars, dow_filter=NON_FRIDAY_DOW, prior_direction_filter=-1)
    summarize("combined", r_c, t_c, bpy)

    section("Regime split — each variant (2019-2020 / 2021-2022 / 2023-2026 holdout)")
    regime_compact("baseline", r_b, t_b, bpy)
    regime_compact("drop-Fri", r_nf, t_nf, bpy)
    regime_compact("after-DOWN", r_dn, t_dn, bpy)
    regime_compact("combined", r_c, t_c, bpy)

    section("Combined detail (drop-Fri + after-DOWN)")
    report_run("combined", r_c, t_c, bars_per_year=bpy)

    section("Phase 2 kill-criteria — combined")
    kill_criteria_check("combined", r_c, t_c, sharpe_min=0.20, mdd_max=0.25,
                        trade_min=200, wr_min=0.50, pf_min=1.05, bars_per_year=bpy)

    section("Regime breakdown — combined (full detail)")
    regime_breakdown(r_c, t_c, bars_per_year=bpy)

    section("Cost sensitivity — combined")
    for c in (0.5, 1.0, 1.5, 2.0, 3.0):
        r_v, t_v = simulate_overnight(bars, dow_filter=NON_FRIDAY_DOW,
                                      prior_direction_filter=-1, cost_points=c)
        sh = annualized_sharpe(r_v.to_numpy(), bpy)
        eq = (1 + r_v).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        print(f"  cost={c:>3.1f}pt  Sh {sh:>+5.2f}  MDD {mdd*100:>+7.2f}%  n {len(t_v):>4d}")

    section("Null-check — combined SHORT (Drop-Fri + after-UP-day)")
    r_null, t_null = simulate_overnight(bars, direction="short",
                                        dow_filter=NON_FRIDAY_DOW,
                                        prior_direction_filter=1)
    summarize("null-short", r_null, t_null, bpy)
    sh_long_combined = annualized_sharpe(r_c.to_numpy(), bpy)
    sh_null = annualized_sharpe(r_null.to_numpy(), bpy)
    print(f"\n  combined-LONG Sharpe       : {sh_long_combined:+.2f}")
    print(f"  mirror SHORT Sharpe        : {sh_null:+.2f}")
    print(f"  sum                        : {sh_long_combined + sh_null:+.2f}")
    if sh_long_combined + sh_null < -0.30:
        print("  PASS: strong antisymmetry → filters capture a real conditional premium.")
    elif sh_long_combined > 0 and sh_null < 0:
        print("  PASS-mild: directionally antisymmetric but smaller magnitude.")
    else:
        print("  FAIL: filters are not capturing a structural asymmetry.")

    section("Summary — combined (drop-Fri + after-DOWN-day)")
    eq = (1 + r_c).cumprod()
    years = (r_c.index[-1] - r_c.index[0]).days / 365.25
    cagr = float(eq.iloc[-1]) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(r_c.to_numpy(), bpy)
    mdd = max_drawdown(eq.to_numpy())
    print(f"  CAGR {cagr*100:+.2f}%  Sharpe {sh:+.2f}  MDD {mdd*100:+.2f}%  "
          f"n {len(t_c)} ({len(t_c)/max(years*52,1e-9):.2f}/week)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
