#!/usr/bin/env python3
"""
NDX Intraday Semi Divergence — Phase 2 demo.

Thesis: experiments/ndx_semi_divergence/ndx_semi_divergence.md

Signal:
  Semi basket (equal-weight NVDA, AMD, AVGO, MRVL, QCOM) cumulative return
  minus NDX100 cumulative return since session start.  When |z-score|
  of the trailing-20-bar spread exceeds THRESHOLD, enter in the direction
  of the semi basket vs NDX (long when semis outperform, short when they
  underperform).  Exit on divergence reversion, time-stop, or cash close.

Cost model: 1 index point round-trip (~0.8 bp, sweeped).

Data:
  ohlc_data/NDX100_M5.csv
  ohlc_data/NVDA_M5.csv, AMD_M5.csv, AVGO_M5.csv, MRVL_M5.csv, QCOM_M5.csv
"""

from __future__ import annotations

import os
import sys
from datetime import time as dtime

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))

from data import fetch_ohlc


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TIMEFRAME = "M5"
START_DATE = "2019-01-01"
END_DATE = "2026-06-10"

RTH_OPEN = dtime(9, 30)
RTH_CLOSE = dtime(16, 0)
SESSION_TZ = "US/Eastern"

# Semi basket constituents (expand/swap if individual symbols lack data).
SEMI_TICKERS = ["NVDA", "AMD", "AVGO", "MRVL", "QCOM"]
NDX_TICKER = "NDX100"

# Bar count before we start looking for entries (skip opening vol).
BARS_SKIP_OPEN = 6  # 30 min *skip* (09:30-10:00 ET)

# Lookback for rolling z-score of divergence.
Z_LOOKBACK = 20  # trailing bars (~100 min)

# Entry threshold (z-score magnitude); sweep default.
THRESHOLD = 2.0  # sigma

# Time-stop after entry (bars).
TOD_EXIT_BARS = 24  # ~120 min

# Cost model: index points per round-trip.
COST_POINTS = 1.0  # ~0.8 bp on NDX100

BARS_PER_YEAR = int(((RTH_CLOSE.hour - RTH_OPEN.hour) * 60 / 5) * 252)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def load_m5(symbol: str) -> pd.DataFrame:
    raw = fetch_ohlc(symbol, TIMEFRAME, START_DATE, END_DATE)
    if raw is None or raw.empty:
        raise RuntimeError(f"No bars for {symbol} {TIMEFRAME} on disk.")
    df = raw[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.index = df.index.tz_convert(SESSION_TZ)
    times = df.index.time
    mask = (times >= RTH_OPEN) & (times < RTH_CLOSE)
    df = df.loc[mask]
    df = df.loc[df.index.dayofweek < 5]
    return df


def align_bars(main: pd.DataFrame, *others: pd.DataFrame) -> pd.DataFrame:
    """Align multiple dataframes on the main index via reindex."""
    for i, df in enumerate(others):
        main = main.join(df, how="inner", lsuffix=f"_{i}", rsuffix=f"_{i+1}")
    return main


def max_drawdown(eq: np.ndarray) -> float:
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min()) if len(dd) else 0.0


def annualized_sharpe(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(BARS_PER_YEAR))


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def simulate_divergence(
    bars: pd.DataFrame,
    threshold: float = THRESHOLD,
    z_lookback: int = Z_LOOKBACK,
    tod_exit_bars: int = TOD_EXIT_BARS,
    bars_skip_open: int = BARS_SKIP_OPEN,
    cost_points: float = COST_POINTS,
    fade: bool = False,
) -> tuple[pd.Series, list[dict]]:
    """Bar-level semi-divergence simulator — numpy inner loop.

    Parameters
    ----------
    bars : DataFrame with columns ['ndx_close', 'semi_close'] and datetime index.
    fade : if True, trade AGAINST the divergence (null-check).
    """
    idx = bars.index
    n_bars = len(bars)
    if n_bars == 0:
        return pd.Series(dtype=float, name="div_ret"), []

    ndx = bars["ndx_close"].to_numpy(dtype=np.float64)
    semi = bars["semi_close"].to_numpy(dtype=np.float64)

    # Intraday cumulative returns from session start.
    # We track day boundaries to reset the cumulative baseline each day.
    dates_arr = np.asarray(idx.date)
    change = np.empty(n_bars, dtype=bool)
    change[0] = True
    change[1:] = dates_arr[1:] != dates_arr[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = n_bars

    ret_arr = np.zeros(n_bars, dtype=np.float64)
    trades: list[dict] = []

    for d_i in range(len(day_starts)):
        s = int(day_starts[d_i])
        e = int(day_ends[d_i])
        n = e - s
        if n < bars_skip_open + z_lookback:
            continue

        day_ndx = ndx[s:e]
        day_semi = semi[s:e]

        # Cumulative returns from day open (first bar of session).
        ndx_base = day_ndx[0]
        semi_base = day_semi[0]
        ndx_cum = day_ndx / ndx_base - 1.0
        semi_cum = day_semi / semi_base - 1.0
        spread = semi_cum - ndx_cum  # divergence

        position = 0
        entry_px_ndx = 0.0
        entry_global_i = -1
        entry_bar_idx = -1
        entry_spread = 0.0
        trades_today = 0

        for i in range(bars_skip_open, n):
            if position != 0 and i > entry_bar_idx:
                prev_close = day_ndx[i - 1]
                cur_close = day_ndx[i]
                ret_arr[s + i] = position * (cur_close - prev_close) / prev_close

            if position != 0:
                forced_close = False
                exit_spread = spread[i]

                # Exit on: divergence reversion (crosses 0), time stop, or EOD.
                if position == 1:
                    reverted = exit_spread <= 0.0
                else:
                    reverted = exit_spread >= 0.0

                tod_forced = (i - entry_bar_idx) >= tod_exit_bars
                is_last = (i == n - 1)

                if reverted or tod_forced or is_last:
                    exit_px = float(day_ndx[i])
                    if i > entry_bar_idx:
                        prev_close = day_ndx[i - 1]
                        ret_arr[s + i] = position * (exit_px - prev_close) / prev_close
                    else:
                        ret_arr[s + i] = position * (exit_px - entry_px_ndx) / entry_px_ndx
                    cost_ret = cost_points / entry_px_ndx
                    ret_arr[s + i] -= cost_ret

                    reason = ("reversion" if reverted
                              else "tod" if tod_forced
                              else "eod")

                    trades.append({
                        "date": dates_arr[s],
                        "direction": "LONG" if position == 1 else "SHORT",
                        "entry_ts": idx[entry_global_i],
                        "exit_ts": idx[s + i],
                        "entry_px": float(entry_px_ndx),
                        "exit_px": float(exit_px),
                        "pnl_pct": position * (exit_px - entry_px_ndx) / entry_px_ndx - cost_ret,
                        "reason": reason,
                        "divergence_at_entry": float(entry_spread),
                        "divergence_at_exit": float(exit_spread),
                    })
                    position = 0
                    trades_today += 1
                    entry_px_ndx = 0.0
                    entry_bar_idx = -1
                    continue

            if position == 0 and trades_today == 0 and i < n - 1:
                if i < z_lookback:
                    continue
                trailing = spread[i - z_lookback:i]
                mu = trailing.mean()
                sd = trailing.std(ddof=1)
                if sd < 1e-12:
                    continue
                z = (spread[i] - mu) / sd

                if abs(z) >= threshold:
                    want_long = (z < 0)  # semis outperform, buy lagging NDX
                    if fade:
                        want_long = not want_long

                    if want_long:
                        position = 1
                    else:
                        position = -1

                    entry_px_ndx = float(day_ndx[i + 1]) if i + 1 < n else float(day_ndx[i])
                    entry_global_i = s + min(i + 1, n - 1)
                    entry_bar_idx = i + 1 if i + 1 < n else i
                    entry_spread = float(spread[i])

    bar_ret = pd.Series(ret_arr, index=idx, name="div_ret")
    return bar_ret, trades


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    eq = (1.0 + bar_ret).cumprod()
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n_trades = len(trades)
    tpw = n_trades / (years * 52) if years > 0 else 0.0
    wins = [t for t in trades if t["pnl_pct"] > 0]
    wr = len(wins) / n_trades if n_trades else 0.0
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")
    avg_w = np.mean([t["pnl_pct"] for t in wins]) if wins else 0.0
    losses = [t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]
    avg_l = np.mean(losses) if losses else 0.0
    print(f"  [{label}]")
    print(f"    period      : {bar_ret.index[0].date()} -> {bar_ret.index[-1].date()} ({years:.1f}y)")
    print(f"    total ret   : {total * 100:+.2f}%")
    print(f"    CAGR        : {cagr * 100:+.2f}%")
    print(f"    Sharpe      : {sh:+.2f}")
    print(f"    Max DD      : {mdd * 100:+.2f}%")
    print(f"    trades      : {n_trades}  ({tpw:.2f}/week)")
    print(f"    win rate    : {wr * 100:.1f}%")
    print(f"    profit fac. : {pf:.2f}")
    print(f"    avg win     : {avg_w * 100:+.3f}%   avg loss: {avg_l * 100:+.3f}%")


def kill_criteria_check(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    sh = annualized_sharpe(bar_ret.to_numpy())
    eq = (1.0 + bar_ret).cumprod()
    mdd = max_drawdown(eq.to_numpy())
    n_trades = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    wr = len(wins) / n_trades if n_trades else 0.0
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")

    def v(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"  [{label}]")
    print(f"    Sharpe > +0.30               : {v(sh > 0.30)}  ({sh:+.2f})")
    print(f"    Max DD < 25%                  : {v(abs(mdd) < 0.25)}  ({mdd * 100:+.2f}%)")
    print(f"    Trades >= 100                 : {v(n_trades >= 100)}  ({n_trades})")
    print(f"    WR>=38 or PF>=1.1             : {v(wr >= 0.38 or pf >= 1.1)}  "
          f"(WR {wr * 100:.1f}%, PF {pf:.2f})")
    print(f"    W3 holdout Sh >= 0            : TBD (see regime breakdown)")


def regime_breakdown(bar_ret: pd.Series, trades: list[dict]) -> None:
    windows = [
        ("2019-2020 pre/COVID", "2019-01-01", "2020-12-31"),
        ("2021-2022 vol",       "2021-01-01", "2022-12-31"),
        ("2023-2026 holdout",   "2023-01-01", "2026-12-31"),
    ]
    for label, s, e in windows:
        sub_ret = bar_ret.loc[s:e]
        sub_trades = [t for t in trades if s <= str(t["date"]) <= e]
        if len(sub_ret) < 100:
            print(f"  {label:<22s} (insufficient bars)")
            continue
        eq = (1.0 + sub_ret).cumprod()
        years = (sub_ret.index[-1] - sub_ret.index[0]).days / 365.25
        cagr = (float(eq.iloc[-1])) ** (1 / max(years, 1e-9)) - 1
        sh = annualized_sharpe(sub_ret.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        print(f"  {label:<22s} CAGR {cagr * 100:>+7.2f}%  Sharpe {sh:>+6.2f}  "
              f"MDD {mdd * 100:>+7.2f}%  trades {len(sub_trades):>4d}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section(f"Loading {NDX_TICKER} + {len(SEMI_TICKERS)} semi components {TIMEFRAME}")
    try:
        ndx = load_m5(NDX_TICKER)
    except RuntimeError as e:
        print(f"  {e}")
        return 1

    component_dfs = {}
    for sym in SEMI_TICKERS:
        try:
            component_dfs[sym] = load_m5(sym)
        except RuntimeError:
            print(f"  WARNING: {sym} not found, skipping.")
            continue

    if len(component_dfs) < 3:
        print("  ERROR: fewer than 3 semi components available. Cannot build basket.")
        return 1

    # Build equal-weighted semi basket, re-capped daily.
    # Align all to NDX timestamps via inner join on the index.
    basket = ndx[["close"]].rename(columns={"close": "ndx_close"})
    for sym, df in component_dfs.items():
        col = f"{sym}_close"
        basket = basket.join(df[["close"]].rename(columns={"close": col}), how="inner")
    basket = basket.dropna()

    # Re-cap daily: each component starts the day at the same price.
    dates = basket.index.date
    uniq_dates = sorted(set(dates))
    semi_vals = basket[[c for c in basket.columns if c.endswith("_close")]].values
    semi_clean = np.where(np.isfinite(semi_vals), semi_vals, np.nan)
    n_components = semi_clean.shape[1]

    # We compute the daily re-capped average: each component is shifted so
    # the first bar of the day has value 100, then averaged.
    semi_reindexed = pd.DataFrame(index=basket.index, dtype=float)
    day_positions = {}
    for d in uniq_dates:
        mask = [d == dd for dd in dates]
        idxs = [i for i, m in enumerate(mask) if m]
        day_positions[d] = (idxs[0], idxs[-1] + 1)

    semi_price = np.full(len(basket), np.nan)
    for d, (s, e) in day_positions.items():
        chunk = semi_clean[s:e]
        # Avoid zero/NaN first bar.
        first_vals = chunk[0]
        if not np.isfinite(first_vals).any():
            continue
        capped = chunk / np.where(np.isfinite(first_vals), first_vals, 1.0) * 100.0
        with_mean = np.nanmean(capped, axis=1)
        semi_price[s:e] = with_mean

    basket["semi_close"] = semi_price
    basket = basket.dropna(subset=["semi_close", "ndx_close"])

    print(f"  bars     : {len(basket):,}")
    print(f"  range    : {basket.index[0]} -> {basket.index[-1]}")
    print(f"  days     : {len(uniq_dates)}")
    print(f"  components used: {', '.join(sorted(component_dfs.keys()))}")

    # -- Baseline --
    section(f"Baseline (threshold={THRESHOLD}, cost={COST_POINTS}pt)")
    bar_ret, trades = simulate_divergence(basket)
    report_run("baseline", bar_ret, trades)

    section("Phase 2 kill-criteria")
    kill_criteria_check("baseline", bar_ret, trades)

    section("Regime breakdown")
    regime_breakdown(bar_ret, trades)

    # -- Direction null-check (fade) --
    section("Null check: fade (trade AGAINST the divergence)")
    r_fade, t_fade = simulate_divergence(basket, fade=True)
    report_run("fade", r_fade, t_fade)
    sh_base = annualized_sharpe(bar_ret.to_numpy())
    sh_fade = annualized_sharpe(r_fade.to_numpy())
    print(f"\n  dir-gap (baseline - fade) = {sh_base:+.2f} - {sh_fade:+.2f} = {sh_base - sh_fade:+.2f}")
    print(f"  {'PASS (dir-gap >= +0.40)' if (sh_base - sh_fade) >= 0.40 else 'FAIL (dir-gap < +0.40)'}")

    # -- Threshold sweep --
    section("Threshold sweep")
    for thr in (1.0, 1.5, 2.0, 2.5, 3.0):
        r_v, t_v = simulate_divergence(basket, threshold=thr)
        if len(r_v) == 0:
            continue
        sh = annualized_sharpe(r_v.to_numpy())
        n_t = len(t_v)
        print(f"  thr={thr:>3.1f}s  Sharpe {sh:>+6.2f}  trades {n_t:>4d}")

    # -- Time stop sweep --
    section("Time-stop sweep (threshold=2.0)")
    for tod_bars in (12, 18, 24, 36, 0):  # 0 = EOD-only
        r_v, t_v = simulate_divergence(basket, tod_exit_bars=tod_bars)
        if len(r_v) == 0:
            continue
        sh = annualized_sharpe(r_v.to_numpy())
        eq = (1.0 + r_v).cumprod()
        mdd = max_drawdown(eq.to_numpy())
        n_t = len(t_v)
        label = f"EOD" if tod_bars == 0 else f"T+{tod_bars}b"
        print(f"  {label:<8s}  Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  trades {n_t:>4d}")

    # -- Cost sensitivity --
    section("Cost sensitivity")
    for cp in (0.0, 0.5, 1.0, 2.0, 3.0):
        r_v, t_v = simulate_divergence(basket, cost_points=cp)
        sh = annualized_sharpe(r_v.to_numpy())
        n_t = len(t_v)
        print(f"  cost={cp:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {n_t:>4d}")

    # -- Summary --
    section("Summary")
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    eq = (1.0 + bar_ret).cumprod()
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    n_t = len(trades)
    print(f"  NDX Semi Divergence (thr={THRESHOLD}, cost={COST_POINTS}pt)")
    print(f"  CAGR {cagr * 100:+.2f}%  Sharpe {sh:+.2f}  MDD {mdd * 100:+.2f}%  "
          f"trades {n_t} ({n_t / max(years * 52, 1e-9):.2f}/week)")
    print(f"  dir-gap (base - fade): {sh - sh_fade:+.2f}" if 'sh_fade' in dir() else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
