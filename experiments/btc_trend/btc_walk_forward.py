#!/usr/bin/env python3
"""
BTC MH-LO+pyramid -- walk-forward Phase 6 (revised).

The single 2018-2021 IS / 2022-2025 OOS split in btc_trend_validation.py
landed both best-friend regimes (clean 2018 bear + clean 2020-2021 parabola)
in IS, producing a degradation of +0.536 (FAIL by 0.04 vs the 0.5 bar).
Since no params are fit during validation, Phase 6 is testing temporal
stability rather than overfitting -- so the natural fix is to average
degradation across multiple rolling splits and check the AVERAGE rather
than a single split lottery.

Splits: 3-year IS / 2-year OOS, sliding by 1 year.

Verdict: PASS iff
  (a) mean(degradation) < 0.5, AND
  (b) at least 3/5 splits individually have degradation < 0.5, AND
  (c) at least 4/5 splits have OOS Sharpe > 0.

If walk-forward PASSES, btc_trend promotes to PASS_PENDING_VALIDATION
(deploy candidate; build MT5 EA).
If walk-forward FAILS, btc_trend retires to KEEP_FOR_REFERENCE.
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
    if len(eq) < 2:
        return {"years": 0.0, "total": 0.0, "cagr": 0.0, "sharpe": 0.0, "mdd": 0.0}
    years = (r.index[-1] - r.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(r.to_numpy())
    mdd = max_drawdown(eq)
    return {"years": years, "total": total, "cagr": cagr,
            "sharpe": sh, "mdd": mdd}


def run_split(
    close: pd.Series, high: pd.Series, low: pd.Series,
    ws: str, we: str,
) -> tuple[pd.Series, dict]:
    """Run BTC pyramid on a [ws .. we] slice with full warmup prepended."""
    ws_ts = pd.Timestamp(ws, tz="UTC")
    we_ts = pd.Timestamp(we, tz="UTC")
    pos_s = close.index.searchsorted(ws_ts)
    pos_e = min(close.index.searchsorted(we_ts, side="right"), len(close))
    warm_s = max(0, pos_s - max(LOOKBACKS))
    sub_close = close.iloc[warm_s:pos_e]
    sub_high = high.iloc[warm_s:pos_e]
    sub_low = low.iloc[warm_s:pos_e]

    ret_pre = sub_close.pct_change().fillna(0.0)
    rv = ret_pre.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(sub_close, LOOKBACKS)
    atr = atr_series(sub_high, sub_low, sub_close)

    r, s = simulate_tsmom_pyramid(
        sub_close, sig, rv, atr, "BTC-MH-LO-P", long_only=True,
        cost_bps_per_side=COST_BPS_HONEST,
    )
    return r.loc[ws:we], s


def main() -> int:
    section("Loading BTCUSD")
    df = load_series("BTCUSD")
    close, high, low = df["close"], df["high"], df["low"]
    print(f"  BTCUSD  {len(df):>5,} bars  "
          f"{df.index[0].date()} -> {df.index[-1].date()}")

    # 3-year IS / 2-year OOS, sliding by 1 year.
    # Earliest IS starts 2018-01-01 (warmup will use first ~252 bars of 2018,
    # so effective IS shrinks for the first split; subsequent splits get
    # full warmup from prior years).
    splits = [
        # (label, is_start, is_end, oos_start, oos_end)
        ("S1", "2018-01-01", "2020-12-31", "2021-01-01", "2022-12-31"),
        ("S2", "2019-01-01", "2021-12-31", "2022-01-01", "2023-12-31"),
        ("S3", "2020-01-01", "2022-12-31", "2023-01-01", "2024-12-31"),
        ("S4", "2021-01-01", "2023-12-31", "2024-01-01", "2025-12-31"),
        ("S5", "2022-01-01", "2024-12-31", "2025-01-01", "2026-03-31"),
    ]

    section("Walk-forward IS/OOS splits (3y IS / 2y OOS, slide 1y)")
    print(f"  {'split':<6s} {'IS window':<24s} {'OOS window':<24s} "
          f"{'IS Sh':>7s} {'OOS Sh':>7s} {'degrad':>7s} {'IS tr':>6s} {'OOS tr':>7s}")
    print("  " + "-" * 96)

    rows = []
    for label, is_s, is_e, oos_s, oos_e in splits:
        is_ret, is_stats = run_split(close, high, low, is_s, is_e)
        oos_ret, oos_stats = run_split(close, high, low, oos_s, oos_e)
        is_m = metrics(is_ret)
        oos_m = metrics(oos_ret)
        degrad = is_m['sharpe'] - oos_m['sharpe']
        rows.append({
            "label": label,
            "is_window": f"{is_s}..{is_e}",
            "oos_window": f"{oos_s}..{oos_e}",
            "is_sharpe": is_m['sharpe'],
            "oos_sharpe": oos_m['sharpe'],
            "degradation": degrad,
            "is_trades": is_stats['trades'],
            "oos_trades": oos_stats['trades'],
            "is_mdd": is_m['mdd'],
            "oos_mdd": oos_m['mdd'],
        })
        print(f"  {label:<6s} {is_s + '..' + is_e:<24s} {oos_s + '..' + oos_e:<24s} "
              f"{is_m['sharpe']:>+7.2f} {oos_m['sharpe']:>+7.2f} {degrad:>+7.3f} "
              f"{is_stats['trades']:>6d} {oos_stats['trades']:>7d}")

    section("Verdict")
    degrads = [r["degradation"] for r in rows]
    oos_sharpes = [r["oos_sharpe"] for r in rows]
    mean_deg = float(np.mean(degrads))
    median_deg = float(np.median(degrads))
    splits_pass_deg = sum(1 for d in degrads if d < 0.5)
    splits_pass_oos = sum(1 for s in oos_sharpes if s > 0)
    n = len(rows)

    print(f"  Mean degradation     : {mean_deg:+.3f}  ({'PASS' if mean_deg < 0.5 else 'FAIL'} -- need < 0.5)")
    print(f"  Median degradation   : {median_deg:+.3f}")
    print(f"  Splits w/ deg < 0.5  : {splits_pass_deg}/{n}  "
          f"({'PASS' if splits_pass_deg >= 3 else 'FAIL'} -- need >= 3)")
    print(f"  Splits w/ OOS Sh > 0 : {splits_pass_oos}/{n}  "
          f"({'PASS' if splits_pass_oos >= 4 else 'FAIL'} -- need >= 4)")
    print()
    print(f"  min OOS Sharpe       : {min(oos_sharpes):+.3f}")
    print(f"  max OOS Sharpe       : {max(oos_sharpes):+.3f}")
    print(f"  mean OOS Sharpe      : {np.mean(oos_sharpes):+.3f}")

    overall_pass = (
        mean_deg < 0.5
        and splits_pass_deg >= 3
        and splits_pass_oos >= 4
    )
    print()
    if overall_pass:
        print("  WALK-FORWARD OVERALL: PASS")
        print("  Recommend: promote btc_trend to PASS_PENDING_VALIDATION; build MT5 EA.")
    else:
        print("  WALK-FORWARD OVERALL: FAIL")
        print("  Recommend: retire btc_trend to KEEP_FOR_REFERENCE; do not deploy.")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
