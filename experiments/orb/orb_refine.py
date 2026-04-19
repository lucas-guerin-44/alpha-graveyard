#!/usr/bin/env python3
"""
ORB refinement battery (instrument-agnostic).

Runs the diagnostic sweep that exposed GER40's real directional edge behind
the EOD-exit confound. Applied to any ORB instrument via env vars:

    ORB_SYMBOL=GER40 ORB_SESSION=EU python experiments/orb/orb_refine.py
    ORB_SYMBOL=NDX100 ORB_SESSION=US python experiments/orb/orb_refine.py
    ORB_SYMBOL=UK100 ORB_SESSION=UK python experiments/orb/orb_refine.py
    ...

Tests (in order of diagnostic value):

1. Symmetric R:R exit — if baseline beats fade under fixed 1:1 / 1:2 / 1:3
   take-profits (no EOD-close asymmetry), there is a real directional edge.
   If fade-gap stays near zero, the apparent baseline edge is a structural
   R:R artifact. If fade-gap goes negative, short-term mean reversion
   dominates (potential inverse-strategy seed).

2. Time-of-day exit (T+60/120/180/240 min) vs EOD — exposes the half-life
   of the opening-impulse edge for this instrument.

3. OR-width filter — checks whether filtering for high-conviction opens
   (wide OR) improves Sharpe or just kills trade count.

Results vary wildly by instrument (GER40 benefits from T+180min exit; NDX100
wants EOD; UK100 fails everywhere). See experiments/orb/orb.md for the
full cross-instrument record.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# ORB_SYMBOL and ORB_SESSION must be set by caller (no sensible default —
# running without explicitly picking an instrument is likely an error).

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from orb_demo import (  # noqa: E402
    load_m5, simulate_orb, annualized_sharpe, max_drawdown,
    SYMBOL, SESSION_KEY,
)


def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def summary(label: str, bar_ret, trades):
    eq = (1.0 + bar_ret).cumprod()
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n = len(trades)
    wr = sum(1 for t in trades if t["pnl_pct"] > 0) / max(n, 1)
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    avg_w = np.mean([t["pnl_pct"] for t in trades if t["pnl_pct"] > 0]) if any(t["pnl_pct"] > 0 for t in trades) else 0.0
    avg_l = np.mean([t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]) if any(t["pnl_pct"] <= 0 for t in trades) else 0.0
    print(f"  {label:<34s} Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  "
          f"trades {n:>4d}  WR {wr * 100:>4.1f}%  PF {pf:>5.2f}  "
          f"avgW {avg_w * 100:>+6.3f}%  avgL {avg_l * 100:>+6.3f}%")


def main() -> int:
    section(f"Loading {SYMBOL} M5 ({SESSION_KEY} session)")
    bars = load_m5(SYMBOL)
    print(f"  bars: {len(bars):,}  range: {bars.index[0].date()} -> {bars.index[-1].date()}")

    # ----------------------------------------------------------------------
    # 1. Symmetric R:R diagnostic: baseline vs fade under fixed R:R targets.
    # ----------------------------------------------------------------------
    section("1. Symmetric R:R diagnostic (baseline vs fade under fixed R:R)")
    print("  Test: if baseline Sharpe-gap over fade > 0.2 under 1:1 R:R, there")
    print(f"  is a real directional edge on {SYMBOL}. Otherwise the apparent ORB edge is structural.\n")
    print(f"  {'variant':<34s} {'Sharpe':>7s}  {'MDD':>8s}  "
          f"{'trades':>6s}  {'WR':>5s}  {'PF':>5s}")
    # EOD exit (current baseline) is already tested. Add fixed R:R variants.
    for rr in (1.0, 1.5, 2.0, 3.0):
        r_base, t_base = simulate_orb(bars, rr_target=rr)
        r_fade, t_fade = simulate_orb(bars, fade=True, rr_target=rr)
        sh_base = annualized_sharpe(r_base.to_numpy())
        sh_fade = annualized_sharpe(r_fade.to_numpy())
        gap = sh_base - sh_fade
        summary(f"baseline RR=1:{rr}", r_base, t_base)
        summary(f"fade     RR=1:{rr}", r_fade, t_fade)
        signal_verdict = "REAL SIGNAL" if gap > 0.2 else "ARTIFACT" if abs(gap) < 0.15 else "WEAK"
        print(f"  >> Sharpe-gap @ RR={rr}: {gap:+.2f} -> {signal_verdict}\n")

    # ----------------------------------------------------------------------
    # 2. Time-of-day exit: does the edge live in the first N hours?
    # ----------------------------------------------------------------------
    section("2. Time-of-day exit (hold for N minutes then close)")
    print(f"  {'variant':<34s} {'Sharpe':>7s}  {'MDD':>8s}  "
          f"{'trades':>6s}  {'WR':>5s}  {'PF':>5s}")
    for hold_min in (60, 120, 180, 240, None):
        label = f"exit at T+{hold_min}min" if hold_min else "exit at EOD (baseline)"
        r_v, t_v = simulate_orb(bars, tod_exit_minutes=hold_min)
        summary(label, r_v, t_v)

    # Fade under TOD exit (check if structural effect dissolves).
    print()
    for hold_min in (120, 180):
        r_fade, t_fade = simulate_orb(bars, fade=True, tod_exit_minutes=hold_min)
        summary(f"fade  T+{hold_min}min", r_fade, t_fade)

    # ----------------------------------------------------------------------
    # 3. OR-width filter: only trade high-conviction opens.
    # ----------------------------------------------------------------------
    section("3. OR-width filter (only trade wide-range opens)")
    print(f"  {'variant':<34s} {'Sharpe':>7s}  {'MDD':>8s}  "
          f"{'trades':>6s}  {'WR':>5s}  {'PF':>5s}")
    for pct in (None, 0.003, 0.005, 0.007, 0.010):
        label = f"OR width >= {pct * 100:.1f}%" if pct else "no OR-width filter"
        r_v, t_v = simulate_orb(bars, min_or_width_pct=pct)
        summary(label, r_v, t_v)

    # ----------------------------------------------------------------------
    # 4. Cost re-check under best-looking refinement.
    # ----------------------------------------------------------------------
    section("4. Recommendation — diagnostic conclusion")
    r_base_rr1, t_base_rr1 = simulate_orb(bars, rr_target=1.0)
    r_fade_rr1, t_fade_rr1 = simulate_orb(bars, fade=True, rr_target=1.0)
    gap1 = annualized_sharpe(r_base_rr1.to_numpy()) - annualized_sharpe(r_fade_rr1.to_numpy())
    print(f"  Fade-gap under 1:1 R:R: {gap1:+.2f}")
    if gap1 > 0.2:
        print("  -> Real directional edge exists; GER40 ORB worth further tuning.")
    elif abs(gap1) < 0.15:
        print("  -> Edge is structural artifact (EOD-exit asymmetry). GER40 ORB cannot")
        print("     be refined into directional alpha with this mechanism. Move on or")
        print("     redesign entirely (volume-filter Zarattini variant, different instrument).")
    else:
        print("  -> Weak / ambiguous signal. Worth one more refinement pass with volume")
        print("     filter (tick-volume > 20d-avg on OR-bar) before deciding.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
