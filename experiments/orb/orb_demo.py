#!/usr/bin/env python3
"""
Opening-Range Breakout on index CFDs (M5) -- Phase 2 demo (instrument-agnostic).

Thesis: experiments/orb/orb.md

Rules:
  Opening range = first OR_MINUTES of the session.
  After OR close, on M5 close > OR_high -> enter long next-bar-open.
             on M5 close < OR_low  -> enter short next-bar-open.
  Stop: opposite OR boundary.
  Exit: stop hit, opposite side broken, or EXIT_MIN_BEFORE_CLOSE minutes before close.
  Max 1 round-trip per direction per day.
  Flat overnight.

Cost model: 1 index point round-trip (pessimistic retail CFD),
applied as a return drag of COST_POINTS / entry_price per trade.

Expects data at ``ohlc_data/<SYMBOL>_M5.csv`` produced by::

    python scripts/mt5_fetch.py --symbols <SYMBOL> --timeframes M5 --from 2019-01-01

Instrument + session via env vars. Examples::

    ORB_SYMBOL=SPX500 python experiments/orb/orb_demo.py               # US session (default)
    ORB_SYMBOL=NDX100 python experiments/orb/orb_demo.py
    ORB_SYMBOL=GER40  ORB_SESSION=EU python experiments/orb/orb_demo.py
    ORB_SYMBOL=UK100  ORB_SESSION=UK python experiments/orb/orb_demo.py
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

from utils import fetch_ohlc  # noqa: E402  (research-repo util, lazy import path)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SYMBOL = os.environ.get("ORB_SYMBOL", "SPX500")
TIMEFRAME = "M5"
START_DATE = "2019-01-01"
END_DATE = "2026-04-18"

# Opening range window, in minutes after RTH open.
OR_MINUTES = 30

# No new entries more than this many minutes after RTH open (stale breakouts).
ENTRY_CUTOFF_MIN = 180  # 12:30 ET

# Hard exit this many minutes before RTH close.
EXIT_MIN_BEFORE_CLOSE = 5  # 15:55 ET

# Cash session per market. Controlled via ORB_SESSION env var (default: US).
SESSIONS = {
    "US": (dtime(9, 30), dtime(16, 0), "US/Eastern"),       # NYSE / Nasdaq cash
    "EU": (dtime(9, 0), dtime(17, 30), "Europe/Berlin"),    # Xetra / Euronext
    "UK": (dtime(8, 0), dtime(16, 30), "Europe/London"),    # LSE
}
SESSION_KEY = os.environ.get("ORB_SESSION", "US").upper()
if SESSION_KEY not in SESSIONS:
    raise RuntimeError(f"Unknown ORB_SESSION={SESSION_KEY!r}; options: {list(SESSIONS)}")
RTH_OPEN, RTH_CLOSE, SESSION_TZ = SESSIONS[SESSION_KEY]

# Cost model: index points per round-trip.
# SPX500 CFD typical: 0.4-0.8 pt spread + 0.1 pt commission, pessimistic 1pt.
COST_POINTS_ROUND_TRIP = 1.0

# For Sharpe annualization: session-length-dependent.
_rth_minutes = (RTH_CLOSE.hour * 60 + RTH_CLOSE.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)
BARS_PER_DAY = _rth_minutes // 5
DAYS_PER_YEAR = 252
BARS_PER_YEAR = BARS_PER_DAY * DAYS_PER_YEAR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def load_m5(symbol: str) -> pd.DataFrame:
    """Load M5 bars and normalize to US/Eastern RTH session."""
    raw = fetch_ohlc(symbol, TIMEFRAME, START_DATE, END_DATE)
    if raw is None or raw.empty:
        raise RuntimeError(
            f"No bars for {symbol} {TIMEFRAME}. Fetch with:\n"
            f"  python scripts/mt5_fetch.py --symbols {symbol} --timeframes M5 "
            f"--from {START_DATE}"
        )
    df = raw[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # Convert to the configured session timezone. MT5 broker-time is already UTC
    # per mt5_fetch.py (uses ``unit='s', utc=True``).
    df.index = df.index.tz_convert(SESSION_TZ)

    # Filter to RTH only.
    times = df.index.time
    mask = (times >= RTH_OPEN) & (times < RTH_CLOSE)
    df = df.loc[mask]

    # Drop weekends (defensive — should already be empty on MT5).
    df = df.loc[df.index.dayofweek < 5]

    return df


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

def simulate_orb(
    bars: pd.DataFrame,
    or_minutes: int = OR_MINUTES,
    entry_cutoff_min: int = ENTRY_CUTOFF_MIN,
    exit_min_before_close: int = EXIT_MIN_BEFORE_CLOSE,
    cost_points: float = COST_POINTS_ROUND_TRIP,
    stop_frac: float = 1.0,       # stop distance = stop_frac * OR_width (1.0 = opposite side)
    trend_filter: pd.Series | None = None,  # daily bias: +1 long-only, -1 short-only, 0 both
    fade: bool = False,           # if True, short breakouts and long breakdowns (anti-ORB)
    rr_target: float | None = None,  # if set, take-profit at rr_target * stop_distance above entry
    tod_exit_minutes: int | None = None,  # exit this many minutes after entry (on top of EOD)
    min_or_width_pct: float | None = None,  # require OR_width / entry_px >= this (e.g. 0.003 = 0.3%)
) -> tuple[pd.Series, list[dict]]:
    """Bar-level ORB simulator.

    Returns
    -------
    bar_ret : pd.Series
        Bar-by-bar strategy return (net of costs), indexed by bar timestamp.
    trades : list[dict]
        One entry per completed round-trip.
    """
    bars = bars.copy()
    bars["date"] = bars.index.date
    bars["minute_of_day"] = (bars.index.hour * 60 + bars.index.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)
    # minute_of_day = 0 at 09:30, increments in 5-min steps through session.

    ret = pd.Series(0.0, index=bars.index)
    trades: list[dict] = []

    for day, day_bars in bars.groupby("date", sort=True):
        if len(day_bars) < (or_minutes // 5) + 4:
            continue  # half-day or truncated session

        or_end = or_minutes
        entry_cutoff = entry_cutoff_min
        rth_minutes = (RTH_CLOSE.hour * 60 + RTH_CLOSE.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)
        exit_cutoff = rth_minutes - exit_min_before_close

        or_mask = day_bars["minute_of_day"] < or_end
        post_or = day_bars["minute_of_day"] >= or_end

        or_window = day_bars.loc[or_mask]
        if or_window.empty:
            continue
        or_high = float(or_window["high"].max())
        or_low = float(or_window["low"].min())
        if not (np.isfinite(or_high) and np.isfinite(or_low)) or or_high <= or_low:
            continue
        or_width = or_high - or_low

        # Daily trend bias: +1 = long-only, -1 = short-only, 0 = both allowed.
        bias = 0
        if trend_filter is not None:
            try:
                bias = int(trend_filter.loc[day])
            except (KeyError, ValueError):
                bias = 0

        # Include the exit-cutoff bar itself so forced-close fires.
        tradable = day_bars.loc[post_or]
        if tradable.empty:
            continue

        # State machine: one round-trip per direction per day.
        # Reset each day — no overnight carry.
        position = 0           # -1 short, 0 flat, +1 long
        entry_px = np.nan
        entry_ts = None
        entry_bar_idx = -1
        stop_px = np.nan
        take_px = np.nan
        long_taken = False
        short_taken = False

        idx_list = list(tradable.index)
        n = len(idx_list)
        for i, ts in enumerate(idx_list):
            bar = tradable.loc[ts]
            mod = int(bar["minute_of_day"])
            is_last_bar = (i == n - 1)

            # Mark-to-market if currently positioned (prev close -> this close).
            if position != 0 and i > 0:
                prev_ts = idx_list[i - 1]
                prev_close = float(tradable.loc[prev_ts, "close"])
                cur_close = float(bar["close"])
                ret.loc[ts] = position * (cur_close - prev_close) / prev_close

            # Exit conditions (check BEFORE entry to prevent same-bar entry+exit race).
            if position != 0:
                hit_stop = (position == 1 and bar["low"] <= stop_px) or \
                           (position == -1 and bar["high"] >= stop_px)
                hit_take = False
                if rr_target is not None and np.isfinite(take_px):
                    hit_take = (position == 1 and bar["high"] >= take_px) or \
                               (position == -1 and bar["low"] <= take_px)
                tod_forced = (tod_exit_minutes is not None and entry_bar_idx >= 0
                              and (i - entry_bar_idx) * 5 >= tod_exit_minutes)
                forced_close = mod >= exit_cutoff or is_last_bar or tod_forced
                if hit_stop or hit_take or forced_close:
                    if hit_stop:
                        exit_px = stop_px
                        exit_reason = "stop"
                    elif hit_take:
                        exit_px = take_px
                        exit_reason = "take"
                    elif tod_forced:
                        exit_px = float(bar["close"])
                        exit_reason = "tod"
                    else:
                        exit_px = float(bar["close"])
                        exit_reason = "eod"
                    # Rebook this bar's return at the exit price instead of bar close.
                    if i > 0:
                        prev_close = float(tradable.loc[idx_list[i - 1], "close"])
                        ret.loc[ts] = position * (exit_px - prev_close) / prev_close
                    else:
                        ret.loc[ts] = position * (exit_px - entry_px) / entry_px
                    # Charge round-trip cost on exit.
                    cost_ret = cost_points / entry_px
                    ret.loc[ts] = ret.loc[ts] - cost_ret
                    trades.append({
                        "date": day,
                        "direction": "LONG" if position == 1 else "SHORT",
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "entry_px": entry_px,
                        "exit_px": exit_px,
                        "pnl_pct": position * (exit_px - entry_px) / entry_px - cost_ret,
                        "reason": exit_reason,
                    })
                    position = 0
                    entry_px = np.nan
                    stop_px = np.nan
                    take_px = np.nan
                    entry_bar_idx = -1
                    continue

            # Entry conditions — only if within entry cutoff and a next bar exists for fill.
            if position == 0 and mod < entry_cutoff and i + 1 < n:
                cur_close = float(bar["close"])
                next_bar = tradable.loc[idx_list[i + 1]]
                next_open = float(next_bar["open"])

                up_break = cur_close > or_high
                down_break = cur_close < or_low

                # Resolve direction via bias + fade flag.
                long_ok = (bias >= 0) and not fade
                short_ok = (bias <= 0) and not fade
                fade_long_ok = (bias >= 0) and fade
                fade_short_ok = (bias <= 0) and fade

                want_long = (up_break and long_ok) or (down_break and fade_long_ok)
                want_short = (down_break and short_ok) or (up_break and fade_short_ok)

                if not long_taken and want_long:
                    # Optional min-OR-width filter (conviction gate).
                    if min_or_width_pct is not None and or_width / next_open < min_or_width_pct:
                        pass
                    else:
                        position = 1
                        entry_px = next_open
                        stop_px = entry_px - stop_frac * or_width
                        take_px = entry_px + rr_target * stop_frac * or_width if rr_target is not None else np.nan
                        entry_ts = idx_list[i + 1]
                        entry_bar_idx = i + 1
                        long_taken = True
                elif not short_taken and want_short:
                    if min_or_width_pct is not None and or_width / next_open < min_or_width_pct:
                        pass
                    else:
                        position = -1
                        entry_px = next_open
                        stop_px = entry_px + stop_frac * or_width
                        take_px = entry_px - rr_target * stop_frac * or_width if rr_target is not None else np.nan
                        entry_ts = idx_list[i + 1]
                        entry_bar_idx = i + 1
                        short_taken = True

        # Safety: if position is still open at end of day (shouldn't happen — last bar
        # force-closes), close at last bar's close.
        if position != 0:
            last_ts = idx_list[-1]
            last_close = float(tradable.loc[last_ts, "close"])
            cost_ret = cost_points / entry_px
            trades.append({
                "date": day,
                "direction": "LONG" if position == 1 else "SHORT",
                "entry_ts": entry_ts,
                "exit_ts": last_ts,
                "entry_px": entry_px,
                "exit_px": last_close,
                "pnl_pct": position * (last_close - entry_px) / entry_px - cost_ret,
                "reason": "eod-safety",
            })

    bar_ret = ret.fillna(0.0)
    bar_ret.name = "orb_ret"
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
    trades_per_week = n_trades / (years * 52) if years > 0 else 0.0
    wins = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = len(wins) / n_trades if n_trades else 0.0
    gross_win = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gross_loss = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0.0
    losses = [t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]
    avg_loss = np.mean(losses) if losses else 0.0

    print(f"  [{label}]")
    print(f"    period      : {bar_ret.index[0].date()} -> {bar_ret.index[-1].date()} ({years:.1f}y)")
    print(f"    total ret   : {total * 100:+.2f}%")
    print(f"    CAGR        : {cagr * 100:+.2f}%")
    print(f"    Sharpe      : {sh:+.2f}")
    print(f"    Max DD      : {mdd * 100:+.2f}%")
    print(f"    trades      : {n_trades}  ({trades_per_week:.2f}/week)")
    print(f"    win rate    : {win_rate * 100:.1f}%")
    print(f"    profit fac. : {pf:.2f}")
    print(f"    avg win     : {avg_win * 100:+.3f}%   avg loss: {avg_loss * 100:+.3f}%")


def kill_criteria_check(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    sh = annualized_sharpe(bar_ret.to_numpy())
    eq = (1.0 + bar_ret).cumprod()
    mdd = max_drawdown(eq.to_numpy())
    n_trades = len(trades)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    win_rate = len(wins) / n_trades if n_trades else 0.0
    gw = sum(t["pnl_pct"] for t in trades if t["pnl_pct"] > 0)
    gl = -sum(t["pnl_pct"] for t in trades if t["pnl_pct"] < 0)
    pf = gw / gl if gl > 0 else float("inf")

    def v(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"  [{label}]")
    print(f"    Sharpe > 0.30       : {v(sh > 0.30)}  ({sh:+.2f})")
    print(f"    Max DD < 25%        : {v(abs(mdd) < 0.25)}  ({mdd * 100:+.2f}%)")
    print(f"    Trades >= 200       : {v(n_trades >= 200)}  ({n_trades})")
    print(f"    WR>=38 or PF>=1.1   : {v(win_rate >= 0.38 or pf >= 1.1)}  "
          f"(WR {win_rate * 100:.1f}%, PF {pf:.2f})")


def regime_breakdown(bar_ret: pd.Series, trades: list[dict]) -> None:
    windows = [
        ("2019-2020 pre/COVID", "2019-01-01", "2020-12-31"),
        ("2021-2022 vol",       "2021-01-01", "2022-12-31"),
        ("2023-2026 holdout",   "2023-01-01", "2026-12-31"),
    ]
    for label, s, e in windows:
        sub_ret = bar_ret.loc[s:e]
        sub_trades = [t for t in trades if s <= str(t["date"]) <= e]
        if len(sub_ret) < 200:
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
    section(f"Loading {SYMBOL} {TIMEFRAME}")
    try:
        bars = load_m5(SYMBOL)
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"  bars     : {len(bars):,}")
    print(f"  range    : {bars.index[0]} -> {bars.index[-1]}")
    print(f"  session  : {bars.index.time.min()} -> {bars.index.time.max()} (US/Eastern)")
    print(f"  days     : {bars['date' if 'date' in bars else bars.index.date].nunique() if False else len(set(bars.index.date))}")

    section("Baseline run (OR=30min, cost=1pt)")
    bar_ret, trades = simulate_orb(bars)
    report_run("baseline", bar_ret, trades)

    section("Phase 2 kill-criteria")
    kill_criteria_check("baseline", bar_ret, trades)

    section("Regime breakdown")
    regime_breakdown(bar_ret, trades)

    section("Variant sweep (OR window)")
    for or_min in (15, 30, 60):
        r_v, t_v = simulate_orb(bars, or_minutes=or_min)
        eq = (1.0 + r_v).cumprod()
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        print(f"  OR={or_min:>3d}min  Sharpe {sh:>+6.2f}  "
              f"MDD {mdd * 100:>+7.2f}%  trades {len(t_v):>4d}")

    section("Variant sweep (cost sensitivity)")
    for cost in (0.5, 1.0, 2.0, 3.0):
        r_v, t_v = simulate_orb(bars, cost_points=cost)
        sh = annualized_sharpe(r_v.to_numpy())
        print(f"  cost={cost:>3.1f}pt  Sharpe {sh:>+6.2f}  trades {len(t_v):>4d}")

    # Build daily trend series (prior-day close vs 20-day SMA of daily closes).
    daily = bars.groupby(bars.index.date)["close"].last()
    daily.index = pd.to_datetime(daily.index)
    sma20 = daily.rolling(20).mean()
    trend = pd.Series(0, index=daily.index, dtype=int)
    trend[daily.shift(1) > sma20.shift(1)] = 1
    trend[daily.shift(1) < sma20.shift(1)] = -1
    trend.index = trend.index.date  # key by date for groupby match

    section("Variant sweep (stop tightness — from opposite side [1.0] to 25% of OR [0.25])")
    for sf in (1.0, 0.75, 0.5, 0.33, 0.25):
        r_v, t_v = simulate_orb(bars, stop_frac=sf)
        eq = (1.0 + r_v).cumprod()
        sh = annualized_sharpe(r_v.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        n_trades = len(t_v)
        wr = sum(1 for t in t_v if t["pnl_pct"] > 0) / max(n_trades, 1)
        gw = sum(t["pnl_pct"] for t in t_v if t["pnl_pct"] > 0)
        gl = -sum(t["pnl_pct"] for t in t_v if t["pnl_pct"] < 0)
        pf = gw / gl if gl > 0 else float("inf")
        print(f"  stop={sf:>4.2f}x  Sharpe {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  "
              f"trades {n_trades:>4d}  WR {wr * 100:>4.1f}%  PF {pf:>4.2f}")

    section("Variant: trend-filter (daily bias via 20d SMA of daily close)")
    r_v, t_v = simulate_orb(bars, trend_filter=trend)
    report_run("trend-filter", r_v, t_v)

    section("Variant: fade (short up-breaks, long down-breaks)")
    r_v, t_v = simulate_orb(bars, fade=True)
    report_run("fade", r_v, t_v)

    section("Variant: tight-stop (0.33x) + trend-filter")
    r_v, t_v = simulate_orb(bars, stop_frac=0.33, trend_filter=trend)
    report_run("tight+trend", r_v, t_v)
    kill_criteria_check("tight+trend", r_v, t_v)
    regime_breakdown(r_v, t_v)

    section("Summary")
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    eq = (1.0 + bar_ret).cumprod()
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    print(f"  baseline : CAGR {cagr * 100:+.2f}%  Sharpe {annualized_sharpe(bar_ret.to_numpy()):+.2f}  "
          f"MDD {max_drawdown(eq.to_numpy()) * 100:+.2f}%  "
          f"trades {len(trades)} ({len(trades) / max(years * 52, 1e-9):.2f}/week)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
