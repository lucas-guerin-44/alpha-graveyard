#!/usr/bin/env python3
"""
BTC MH-LO+pyramid -- Phase 7 cross-strategy correlation.

Question: does BTC-trend behave differently enough from our other validated
strategies to earn a slot in a blend?

Per docs/WORKFLOW.md Phase 7:
  * corr < 0.3  -> real diversifier, consider adding
  * 0.3 - 0.6   -> weak diversifier, only add if standalone Sharpe > 0.5
  * corr >= 0.6 -> redundant, pick the higher-Sharpe one

Compares daily and monthly returns vs:
  1. XS-momentum long-only at IS-optimal params (lookback=189, skip=42,
     rebalance=63, top_k=5) -- current live QC strategy.
  2. Treasury-trend IEF-MH (1M+3M+12M, vol-target 10%) -- passes Phase 2-7,
     deployable.
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
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'xs_momentum'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'treasury_trend'))

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)
from xs_momentum_validation import (
    load_data as xs_load_data,
    run_xs_momentum,
    UNIVERSE as XS_UNIVERSE,
    COSTS_BY_SYMBOL as XS_COSTS,
)
from treasury_trend_demo import (
    simulate_tsmom as tt_simulate_tsmom,
    MULTI_LOOKBACKS as TT_MULTI_LOOKBACKS,
)

COST_BPS_HONEST = 10.0
# XS-mom and treasury_trend need 2015+ history to warm up their long lookbacks.
# BTC data only begins 2018-01-01, so we load the two reference strategies on
# their full histories, then clip to BTC's window for correlation.
XS_START = "2015-01-01"
XS_END = "2026-04-18"
CORR_START = "2018-01-01"  # BTC-era overlap
CORR_END = "2026-04-18"


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def to_date_index(s: pd.Series) -> pd.Series:
    """Normalize datetime index to midnight UTC (drop time-of-day).

    BTC MT5 data carries timestamps like 01:00:00+00:00 on weekdays and
    00:00:00+00:00 on weekends (venue idiosyncrasy). XS-mom and treasury_trend
    return series sit on midnight business-day timestamps. Without this
    normalisation an inner-join only catches the weekend bars where XS returns
    are zero -> spurious zero correlation / NaN std.
    """
    s = s.copy()
    idx = s.index
    if idx.tz is None:
        idx = pd.DatetimeIndex(idx).tz_localize("UTC")
    else:
        idx = pd.DatetimeIndex(idx).tz_convert("UTC")
    s.index = idx.normalize()
    # Collapse duplicates arising from midnight vs 01:00 same-day bars.
    s = s.groupby(s.index).sum()
    return s


def classify(corr: float) -> str:
    c = abs(corr)
    if c < 0.3:
        return "REAL DIVERSIFIER"
    if c < 0.6:
        return "weak diversifier"
    return "redundant"


def main() -> int:
    # ----- BTC -----------------------------------------------------------
    section("Running BTC MH-LO+pyramid")
    btc_df = load_series("BTCUSD")
    close = btc_df["close"]
    high = btc_df["high"]
    low = btc_df["low"]
    ret_pre = close.pct_change().fillna(0.0)
    rv = ret_pre.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)
    btc_ret, _ = simulate_tsmom_pyramid(
        close, sig, rv, atr, "BTC-MH-LO-P", long_only=True,
        cost_bps_per_side=COST_BPS_HONEST,
    )
    btc_ret = to_date_index(btc_ret.rename("btc_trend"))
    print(f"  BTC trend: {len(btc_ret):,} bars  "
          f"{btc_ret.index[0].date()} -> {btc_ret.index[-1].date()}  "
          f"Sharpe {annualized_sharpe(btc_ret.to_numpy()):+.2f}")

    # ----- XS-momentum ---------------------------------------------------
    section("Running XS-momentum (live-deployed params)")
    xs_frames: dict[str, pd.DataFrame] = {}
    for sym in XS_UNIVERSE:
        df = xs_load_data(sym, XS_START, XS_END)
        if df is None or len(df) < 400:
            continue
        xs_frames[sym] = df
    print(f"  Loaded {len(xs_frames)} XS-mom instruments.")
    xs_res = run_xs_momentum(
        xs_frames,
        start_date=XS_START, end_date=XS_END,
        lookback_bars=189, skip_bars=42, rebalance_bars=63,
        top_k=5, bottom_k=0, starting_cash=100_000.0,
        costs_bps=XS_COSTS,
    )
    xs_ret = pd.Series(xs_res["daily_returns"], index=xs_res["index"], name="xs_mom")
    xs_ret = to_date_index(xs_ret)
    print(f"  XS-mom: {len(xs_ret):,} bars  "
          f"{xs_ret.index[0].date()} -> {xs_ret.index[-1].date()}  "
          f"Sharpe {annualized_sharpe(xs_ret.to_numpy()):+.2f}")

    # ----- Treasury trend ------------------------------------------------
    section("Running Treasury-trend IEF-MH")
    ief_df = load_series("IEF")
    bil_df = load_series("BIL")
    if ief_df is None or bil_df is None:
        print("  IEF or BIL missing; skipping treasury_trend correlation.")
        tt_ret = None
    else:
        common_tt = ief_df.index.intersection(bil_df.index).sort_values()
        ief_c = ief_df["close"].reindex(common_tt)
        bil_c = bil_df["close"].reindex(common_tt)
        tt_ret, _ = tt_simulate_tsmom(ief_c, bil_c, "IEF-MH", lookbacks=TT_MULTI_LOOKBACKS)
        tt_ret = to_date_index(tt_ret.rename("treasury_trend"))
        print(f"  Treasury-trend: {len(tt_ret):,} bars  "
              f"{tt_ret.index[0].date()} -> {tt_ret.index[-1].date()}  "
              f"Sharpe {annualized_sharpe(tt_ret.to_numpy()):+.2f}")

    # ----- Pairwise correlations -----------------------------------------
    section("Pairwise correlation (daily + monthly)")
    series_list = [("btc_trend", btc_ret), ("xs_mom", xs_ret)]
    if tt_ret is not None:
        series_list.append(("treasury_trend", tt_ret))

    pairs = [
        ("btc_trend", "xs_mom"),
        ("btc_trend", "treasury_trend"),
        ("xs_mom", "treasury_trend"),
    ]
    name_to_series = dict(series_list)

    print(f"  {'pair':<32s} {'overlap':>7s}  {'corr-daily':>10s}  "
          f"{'corr-monthly':>12s}  {'classification':<20s}")
    print("  " + "-" * 82)
    for a, b in pairs:
        if a not in name_to_series or b not in name_to_series:
            continue
        ra = name_to_series[a]
        rb = name_to_series[b]
        aligned = pd.concat([ra, rb], axis=1, join="inner").dropna()
        if len(aligned) < 60:
            print(f"  {a + ' / ' + b:<32s} too little overlap ({len(aligned)})")
            continue
        cd = float(aligned[a].corr(aligned[b]))
        monthly = (1.0 + aligned).resample("ME").prod() - 1.0
        cm = float(monthly[a].corr(monthly[b]))
        cls = classify(cd)
        print(f"  {a + ' / ' + b:<32s} {len(aligned):>7d}  "
              f"{cd:>+9.3f}   {cm:>+11.3f}   {cls:<20s}")

    # ----- BTC-trend vs each XS-mom daily return for a sanity deep-dive --
    section("BTC-trend correlation deep-dive")
    aligned_bx = pd.concat([btc_ret, xs_ret], axis=1, join="inner").dropna()
    if tt_ret is not None:
        aligned_bt = pd.concat([btc_ret, tt_ret], axis=1, join="inner").dropna()
    else:
        aligned_bt = None
    print(f"  BTC-trend overlap with XS-mom        : {len(aligned_bx)} daily bars")
    if aligned_bt is not None:
        print(f"  BTC-trend overlap with Treasury-trend: {len(aligned_bt)} daily bars")

    # Rolling 252-day correlation, to see if it's stable across regimes.
    if len(aligned_bx) >= 400:
        roll_bx = aligned_bx["btc_trend"].rolling(252).corr(aligned_bx["xs_mom"])
        roll_bx = roll_bx.dropna()
        if len(roll_bx) >= 5:
            print(f"\n  BTC-trend vs XS-mom rolling 252-day corr:")
            print(f"    min    : {roll_bx.min():+.3f}")
            print(f"    median : {roll_bx.median():+.3f}")
            print(f"    max    : {roll_bx.max():+.3f}")
    if aligned_bt is not None and len(aligned_bt) >= 400:
        roll_bt = aligned_bt["btc_trend"].rolling(252).corr(aligned_bt["treasury_trend"])
        roll_bt = roll_bt.dropna()
        if len(roll_bt) >= 5:
            print(f"\n  BTC-trend vs Treasury-trend rolling 252-day corr:")
            print(f"    min    : {roll_bt.min():+.3f}")
            print(f"    median : {roll_bt.median():+.3f}")
            print(f"    max    : {roll_bt.max():+.3f}")

    # ----- Blend preview -------------------------------------------------
    section("Equal-weight blend preview")
    if tt_ret is not None:
        aligned_all = pd.concat([btc_ret, xs_ret, tt_ret], axis=1, join="inner").dropna()
    else:
        aligned_all = pd.concat([btc_ret, xs_ret], axis=1, join="inner").dropna()
    if len(aligned_all) == 0:
        print("  No common overlap -- skipping blend preview.")
        return 0
    print(f"  Common overlap: {len(aligned_all)} daily bars  "
          f"{aligned_all.index[0].date()} -> {aligned_all.index[-1].date()}")

    def stats_row(r: pd.Series, label: str) -> None:
        eq = (1.0 + r).cumprod()
        years = (r.index[-1] - r.index[0]).days / 365.25
        total = float(eq.iloc[-1] - 1.0)
        cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
        sh = annualized_sharpe(r.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        print(f"  {label:<28s} CAGR {cagr * 100:+6.2f}%  Sharpe {sh:+.2f}  MDD {mdd * 100:+7.2f}%")

    for col in aligned_all.columns:
        stats_row(aligned_all[col], col)
    blend_ret = aligned_all.mean(axis=1).rename("EW-blend")
    stats_row(blend_ret, "EW-blend (all strategies)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
