#!/usr/bin/env python3
"""
BTC MH-LO+pyramid -- real out-of-sample test on Sep 2025 - Mar 2026 data.

Validation was run with data through 2025-08-31 (last available bar at the
time). MT5 has now backfilled Sep 2025 - Mar 2026, covering a -44% BTC
drawdown peak-to-trough from the Oct 2025 top ($121k) to Mar 2026 ($68k).

This is the honest post-training OOS test -- no re-fitting allowed.
Reports:
  1. Trained-period performance (2018-01 to 2025-08, matches Phase 6 numbers)
  2. Real-OOS performance (2025-09 to 2026-03, 7 months)
  3. Full-period combined (2018-01 to 2026-03)
  4. Position weight trajectory through Sep 2025 - Mar 2026 so we can see
     whether the strategy correctly cut exposure.
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
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)

COST_BPS_HONEST = 10.0
TRAIN_END = "2025-08-31"
OOS_START = "2025-09-01"


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
            "sharpe": sh, "mdd": mdd, "n_bars": len(r)}


def main() -> int:
    section("Loading BTCUSD (extended through Mar 2026)")
    df = load_series("BTCUSD")
    close, high, low = df["close"], df["high"], df["low"]
    print(f"  BTCUSD  {len(df):>5,} bars  "
          f"{df.index[0].date()} -> {df.index[-1].date()}  "
          f"({(df.index[-1] - df.index[0]).days / 365.25:.1f} years)")
    last_train_price = float(close.loc[:TRAIN_END].iloc[-1])
    last_oos_price = float(close.iloc[-1])
    oos_peak = float(close.loc[OOS_START:].max())
    oos_trough = float(close.loc[OOS_START:].min())
    print(f"\n  Last training close (2025-08-31)     : ${last_train_price:>10,.0f}")
    print(f"  Post-training peak                    : ${oos_peak:>10,.0f}")
    print(f"  Post-training trough                  : ${oos_trough:>10,.0f}")
    print(f"  Final close (2026-03-31)              : ${last_oos_price:>10,.0f}")
    print(f"  Peak-to-trough OOS                    : {(oos_trough / oos_peak - 1) * 100:+.1f}%")
    print(f"  End-to-end OOS (train-end to now)     : {(last_oos_price / last_train_price - 1) * 100:+.1f}%")

    # ----- Run full-period strategy ---------------------------------------
    section("Running MH-LO + pyramid on FULL extended series")
    ret_pre = close.pct_change().fillna(0.0)
    rv = ret_pre.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)
    ret, stats = simulate_tsmom_pyramid(
        close, sig, rv, atr, "BTC-MH-LO-P", long_only=True,
        cost_bps_per_side=COST_BPS_HONEST,
    )
    w_ser = pd.Series(stats["w"], index=close.index, name="w")
    print(f"  trades (full)  : {stats['trades']}")
    print(f"  frac-long      : {stats['frac_long'] * 100:.1f}%")

    # ----- Segment results ------------------------------------------------
    section("Performance: trained vs real-OOS vs full")
    train = ret.loc[:TRAIN_END]
    oos = ret.loc[OOS_START:]
    full = ret

    print(f"  {'segment':<26s} {'years':>5s} {'ret':>10s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    for lbl, r in (("Train 2018-01 -> 2025-08", train),
                   ("OOS 2025-09 -> 2026-03", oos),
                   ("FULL 2018-01 -> 2026-03", full)):
        mx = metrics(r)
        print(f"  {lbl:<26s} {mx['years']:>5.1f} {mx['total'] * 100:>+9.2f}% "
              f"{mx['cagr'] * 100:>+7.2f}% {mx['sharpe']:>+7.2f} {mx['mdd'] * 100:>+7.2f}%")

    # ----- B&H side-by-side ----------------------------------------------
    section("Buy & hold side-by-side (same segments)")
    bh = close.pct_change().fillna(0.0)
    print(f"  {'segment':<26s} {'years':>5s} {'ret':>10s} {'CAGR':>8s} {'Sharpe':>7s} {'MDD':>8s}")
    for lbl, r in (("Train 2018-01 -> 2025-08", bh.loc[:TRAIN_END]),
                   ("OOS 2025-09 -> 2026-03", bh.loc[OOS_START:]),
                   ("FULL 2018-01 -> 2026-03", bh)):
        mx = metrics(r)
        print(f"  {lbl:<26s} {mx['years']:>5.1f} {mx['total'] * 100:>+9.2f}% "
              f"{mx['cagr'] * 100:>+7.2f}% {mx['sharpe']:>+7.2f} {mx['mdd'] * 100:>+7.2f}%")

    # ----- Position trajectory through OOS -------------------------------
    section("Position weight trajectory through OOS (month-end snapshots)")
    oos_slice = w_ser.loc[OOS_START:]
    oos_price = close.loc[OOS_START:]
    oos_sig = sig.loc[OOS_START:]
    months = oos_slice.resample("ME").last()
    months_px = oos_price.resample("ME").last()
    months_sig = oos_sig.resample("ME").last()
    print(f"  {'month-end':<12s} {'price':>10s} {'signal':>8s} {'weight':>8s}  "
          f"{'commentary':<40s}")
    for ts in months.index:
        w_v = float(months.loc[ts])
        px_v = float(months_px.loc[ts])
        sg_v = float(months_sig.loc[ts])
        if w_v > 0.6:
            state = "full / near-full long"
        elif w_v > 0.2:
            state = "partial long (mid pyramid)"
        elif w_v > 0.01:
            state = "toe-in (1 unit)"
        else:
            state = "FLAT (signal killed position)"
        print(f"  {ts.date()!s:<12s} {px_v:>10,.0f} {sg_v:>+8.2f} "
              f"{w_v:>8.3f}  {state:<40s}")

    # ----- OOS drawdown focus --------------------------------------------
    section("OOS drawdown detail: what strategy did vs buy & hold")
    oos_ret = ret.loc[OOS_START:]
    oos_bh = bh.loc[OOS_START:]
    oos_eq = (1.0 + oos_ret).cumprod()
    oos_bh_eq = (1.0 + oos_bh).cumprod()
    print(f"  Strategy end-to-end OOS : {oos_eq.iloc[-1] - 1:>+7.2%}  "
          f"MDD: {max_drawdown(oos_eq.to_numpy()):+7.2%}")
    print(f"  B&H      end-to-end OOS : {oos_bh_eq.iloc[-1] - 1:>+7.2%}  "
          f"MDD: {max_drawdown(oos_bh_eq.to_numpy()):+7.2%}")

    # Count bars in each regime state
    flat_days = int((oos_slice < 0.05).sum())
    partial_days = int(((oos_slice >= 0.05) & (oos_slice < 0.7)).sum())
    full_days = int((oos_slice >= 0.7).sum())
    total_days = len(oos_slice)
    print(f"\n  Days flat (w<0.05)      : {flat_days:>4d} / {total_days}  ({flat_days / total_days * 100:.1f}%)")
    print(f"  Days partial (0.05-0.7) : {partial_days:>4d} / {total_days}  ({partial_days / total_days * 100:.1f}%)")
    print(f"  Days full long (w>=0.7) : {full_days:>4d} / {total_days}  ({full_days / total_days * 100:.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
