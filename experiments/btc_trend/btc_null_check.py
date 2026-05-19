#!/usr/bin/env python3
"""
BTC MH-LO+pyramid -- direction null check.

Per CLAUDE.md rule 6: every mechanism-hypothesis strategy ships with a
null that runs the mechanism in the OPPOSITE direction. For TSMOM the
fade null is "short when 12-1 says long; flat otherwise" -- same trigger
timing, same vol-target, same costs, opposite trade.

If both directions win  -> cost/exit model is broken (structural artifact).
If both directions lose -> signal has no directional content.
If real >> fade         -> directional content is real (fade-gap > 0.5).

The position-shuffle permutation in Phase 3 tests "is the WHEN we hold
weight informative" (it is, p=0.0016). This script tests the
complementary "is the SIGN of our trade informative".
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'gold_trend'))

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)

COST_BPS_HONEST = 10.0


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def metrics(r: pd.Series) -> dict:
    eq = (1.0 + r).cumprod().to_numpy()
    years = (r.index[-1] - r.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(r.to_numpy())
    mdd = max_drawdown(eq)
    return {"years": years, "total": total, "cagr": cagr,
            "sharpe": sh, "mdd": mdd}


def main() -> int:
    section("Loading BTCUSD")
    df = load_series("BTCUSD")
    close, high, low = df["close"], df["high"], df["low"]
    print(f"  BTCUSD  {len(df):>5,} bars  "
          f"{df.index[0].date()} -> {df.index[-1].date()}")

    ret_pre = close.pct_change().fillna(0.0)
    rv = ret_pre.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)

    # --- Real direction: long when MH-TSMOM positive -------------------
    section("REAL: long-only TSMOM on +signal")
    real_ret, real_stats = simulate_tsmom_pyramid(
        close, sig, rv, atr, "BTC-MH-LO-real", long_only=True,
        cost_bps_per_side=COST_BPS_HONEST,
    )
    real_m = metrics(real_ret)
    print(f"  CAGR {real_m['cagr'] * 100:+6.2f}%  Sharpe {real_m['sharpe']:+.2f}  "
          f"MDD {real_m['mdd'] * 100:+6.2f}%  trades {real_stats['trades']}")

    # --- Fade null: short when MH-TSMOM positive -----------------------
    # Run pyramid simulator with long_only=False and INVERT the signal.
    # Whenever real strategy would have gone long with magnitude m,
    # the fade strategy goes short with magnitude m. Same trigger, same
    # exit, same cost mechanics, opposite trade.
    section("FADE NULL: short when +signal (same mechanics, inverted)")
    fade_ret, fade_stats = simulate_tsmom_pyramid(
        close, -sig.clip(lower=0.0), rv, atr, "BTC-MH-FADE", long_only=False,
        cost_bps_per_side=COST_BPS_HONEST,
    )
    fade_m = metrics(fade_ret)
    print(f"  CAGR {fade_m['cagr'] * 100:+6.2f}%  Sharpe {fade_m['sharpe']:+.2f}  "
          f"MDD {fade_m['mdd'] * 100:+6.2f}%  trades {fade_stats['trades']}")

    # --- Fade-gap and verdict ----------------------------------------
    section("Fade gap (directional content)")
    fade_gap = real_m['sharpe'] - fade_m['sharpe']
    print(f"  Real Sharpe              : {real_m['sharpe']:+.3f}")
    print(f"  Fade Sharpe              : {fade_m['sharpe']:+.3f}")
    print(f"  Fade gap (real - fade)   : {fade_gap:+.3f}")
    print()

    if fade_gap > 0.5 and real_m['sharpe'] > 0 and fade_m['sharpe'] < 0:
        verdict = ("PASS -- real wins clean, fade loses cleanly, gap > 0.5. "
                   "Directional content is real.")
    elif fade_gap > 0.5 and real_m['sharpe'] > 0 and fade_m['sharpe'] >= 0:
        verdict = ("AMBIGUOUS -- gap > 0.5 but fade also positive. "
                   "Cost/exit asymmetry may be inflating real or muting fade. "
                   "Check sweep across cost levels.")
    elif fade_gap <= 0.5 and real_m['sharpe'] > 0:
        verdict = ("WEAK -- real positive but fade gap too small. "
                   "Some directional content but heavy noise contribution.")
    elif fade_gap < -0.3:
        verdict = ("SIGN ERROR -- fade outperforms real. "
                   "Strategy is pointing the wrong way (see lumber_oats lesson).")
    else:
        verdict = "INDETERMINATE"
    print(f"  {verdict}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
