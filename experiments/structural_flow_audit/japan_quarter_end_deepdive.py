#!/usr/bin/env python3
"""
Phase-0 deep-dive: Japan quarter-end Tokyo-close SHORT (JPN225).

Surfaced WEAK by structural_flow_audit_v3 (event -5.79 bp, placebo-gap -7.27, t=-1.41, gap-fill).
The screen can't see direction-null / regime / the event-specific placebo — this runs them cheaply
to decide PROCEED-to-Phase-2 vs tombstone.

Cell: JPN225 M5, 14:00-15:00 Asia/Tokyo (last cash hour), last business day of Mar/Jun/Sep/Dec, SHORT.
Mechanism hypothesis: quarter-end institutional rebalancing / de-risking concentrates SELL flow into
the Tokyo close (sibling of quarter_end_xau_short's XAU safe-haven sell + the Nikkei-SQ settlement flow).

Distinct from the deployed Nikkei-SQ leg: that fires the 2nd-Friday SQ *open*; this fires the
last-biz-day quarter-end *close* — different dates, different mechanism. Independent if real.

Usage: PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/structural_flow_audit/japan_quarter_end_deepdive.py
"""
from __future__ import annotations

import os
import sys
from datetime import date
from math import log, sqrt

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from structural_flow_audit import (  # noqa: E402
    section, load_m5, compute_window_returns, gen_jpm_collar_dates,
    gen_month_end_dates, nth_weekday_of_month, YEARS,
)

SYM = "JPN225"
TZ = "Asia/Tokyo"
WIN = (14, 0, 15, 0)        # pre-committed (the screen's cell)
COST_BP = 1.0
EVENTS_PER_YEAR = 4
N_SCREEN_CELLS = 32        # v3 grid breadth (deflation)


def ann_sh(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0: return 0.0
    return float(x.mean() / x.std(ddof=1) * sqrt(EVENTS_PER_YEAR))
def regime(d): return "W1" if d.year <= 2020 else ("W2" if d.year <= 2022 else "W3")
def wmean(arr, dts, w):
    sub = np.array([v for v, d in zip(arr, dts) if regime(d) == w])
    return float(sub.mean()) if len(sub) >= 1 else float("nan")
def pf(x):
    gw = float(x[x > 0].sum()); gl = float(-x[x <= 0].sum()); return gw/gl if gl > 0 else float("inf")
def mdd(rf):
    eq = (1 + rf).cumprod(); rm = np.maximum.accumulate(eq); return float(((eq-rm)/rm).min())
def boot_lo(x, n=10000, seed=42):
    x = np.asarray(x, float); rng = np.random.default_rng(seed)
    return float(np.quantile([rng.choice(x, len(x), True).mean() for _ in range(n)], 0.025))
def deflate(sh, n): return sh - sqrt(2*log(N_SCREEN_CELLS))/sqrt(n) if n >= 4 else sh


def short_series(dates, win=WIN, cost=COST_BP):
    bars = load_m5(SYM)
    long_bp, kept = compute_window_returns(bars, dates, TZ, *win)
    return np.array([-x - cost for x in long_bp]), kept, np.array([-x for x in long_bp])


def main() -> int:
    section("Phase-0: Japan quarter-end Tokyo-close SHORT (JPN225 14:00-15:00, last biz day Q-end)")
    qdates = gen_jpm_collar_dates(YEARS)
    net, kept, gross = short_series(qdates)
    n = len(net)
    print(f"  n={n}  mean {net.mean():+.2f}bp  annSh {ann_sh(net):+.2f}  PF {pf(net):.2f}  "
          f"MDD {mdd(net/1e4)*100:+.2f}%  boot-lo {boot_lo(net):+.2f}  deflated {deflate(ann_sh(net), n):+.2f}")

    section("Regime breakdown (one-window-wonder check)")
    for w in ("W1", "W2", "W3"):
        sub = np.array([v for v, d in zip(net, kept) if regime(d) == w])
        print(f"  {w}: n={len(sub):>2d}  mean {sub.mean() if len(sub) else float('nan'):+7.2f}bp  Sh {ann_sh(sub):+.2f}")
    allpos = all(wmean(net, kept, w) > 0 for w in ("W1", "W2", "W3"))
    print(f"  all 3 regimes positive: {allpos}")

    section("Direction null (zero-cost SHORT vs LONG)")
    dirgap = ann_sh(gross) - ann_sh(-gross)
    print(f"  SHORT zc Sh {ann_sh(gross):+.2f}  LONG zc Sh {ann_sh(-gross):+.2f}  dir-gap {dirgap:+.2f}")

    section("Placebo — quarter-end vs NON-quarter month-ends (same window)")
    mo_all = gen_month_end_dates(YEARS)
    nonq = [d for d in mo_all if d.month not in (3, 6, 9, 12)]
    m_net, m_kept, _ = short_series(nonq)
    gap = net.mean() - m_net.mean()
    print(f"  quarter-end   n={n:>3d}  mean {net.mean():+.2f}bp  W3 {wmean(net, kept, 'W3'):+.2f}")
    print(f"  non-Q mon-end n={len(m_net):>3d}  mean {m_net.mean():+.2f}bp  W3 {wmean(m_net, m_kept, 'W3'):+.2f}")
    print(f"  placebo gap {gap:+.2f}bp  ({'PASS — quarter-end-specific' if gap > 0 else 'FAIL — generic month-end-close drift'})")

    section("Cost sensitivity")
    for c in (0.0, 1.0, 2.0, 3.0):
        ns, _, _ = short_series(qdates, cost=c)
        print(f"  cost {c:>4.1f}bp  mean {ns.mean():+6.2f}bp  Sh {ann_sh(ns):+.2f}")

    section("Window robustness (diagnostic)")
    for label, w in [("13:00-15:00", (13, 0, 15, 0)), ("14:00-15:00 [PRE-COMMIT]", WIN),
                     ("14:30-15:00", (14, 30, 15, 0)), ("12:30-15:00", (12, 30, 15, 0))]:
        ws, wk, _ = short_series(qdates, win=w)
        print(f"  {label:<26s} n={len(ws):>2d}  mean {ws.mean():+6.2f}bp  Sh {ann_sh(ws):+.2f}  W3 {wmean(ws, wk, 'W3'):+6.2f}")

    section("Robustness + distinctness")
    imax = int(np.argmax(net))
    print(f"  drop largest event {kept[imax]} ({net[imax]:+.2f}bp) -> mean {float(np.delete(net, imax).mean()):+.2f}bp")
    sq_dates = set()
    for y in YEARS:
        for m in (3, 6, 9, 12):
            try: sq_dates.add(nth_weekday_of_month(y, m, weekday=4, n=2))
            except ValueError: pass
    overlap = sum(1 for d in kept if d in sq_dates)
    print(f"  date-overlap with deployed Nikkei-SQ leg (2nd-Fri): {overlap}/{n}  (0 = fully independent dates)")

    section("Phase-0 verdict")
    placebo_pass = gap > 0
    proceed = (dirgap > 0.30) and placebo_pass and allpos and (ann_sh(net) > 0.30)
    print(f"  dir-gap {dirgap:+.2f} (>0.30? {dirgap>0.30}) | placebo {gap:+.2f} ({'PASS' if placebo_pass else 'FAIL'}) | "
          f"all-regime-pos {allpos} | annSh {ann_sh(net):+.2f}")
    print(f"  VERDICT: {'PROCEED to Phase 2 (sparse JP-short candidate)' if proceed else 'TOMBSTONE / no Phase 2'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
