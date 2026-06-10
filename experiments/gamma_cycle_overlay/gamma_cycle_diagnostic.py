#!/usr/bin/env python3
"""
Monthly Gamma Cycle Overlay — Phase 0 diagnostic.

Thesis: experiments/gamma_cycle_overlay/gamma_cycle_overlay.md

Labels each NDX RTH bar with the OPEX-cycle phase and splits the returns of
simple (lunch_fade, ndx_trend_day) strategy replicas by phase to see whether
mean-reversion is favoured during dealer-long-gamma weeks and trend is
favoured during dealer-short-gamma weeks.

Also runs a +7d placebo shift to rule out macro-calendar overlap confound.

Data:
  ohlc_data/NDX100_M5.csv
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

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

RTH_OPEN = 570  # 09:30 ET minutes since midnight
RTH_CLOSE = 960  # 16:00 ET

SESSION_TZ = "US/Eastern"

BARS_PER_YEAR = int(((16 - 9.5) * 60 / 5) * 252)  # ~390 min / 5 * 252


# ---------------------------------------------------------------------------
# Gamma cycle label
# ---------------------------------------------------------------------------

def opex_dates(year_start: int, year_end: int) -> list[date]:
    """Return 3rd-Friday OPEX dates for every month in [year_start, year_end]."""
    from calendar import monthcalendar
    dates_list = []
    for y in range(year_start, year_end + 1):
        for m in range(1, 13):
            cal = monthcalendar(y, m)
            # Week 3 or the last week; 3rd Friday = min(15-21)
            # monthcalendar[y][m] is a list of weeks, week index 2 or 3.
            fridays = [w[4] for w in cal if w[4] != 0]
            if len(fridays) >= 3:
                third_fri = fridays[2]
            else:
                third_fri = fridays[-1]
            dates_list.append(date(y, m, third_fri))
    return dates_list


def gamma_phase(d: date, opex: date) -> str:
    """Label one date relative to the OPEX date.

    W-1:  OPEX-7  to OPEX-2d  — long gamma accumulation
    W0:   OPEX-1d to OPEX     — peak + unwind
    W+1:  OPEX+1  to OPEX+7d  — short gamma build
    W+2:  OPEX+8  to OPEX+14d — short gamma saturated
    OTHER: outside these windows.
    """
    delta = (d - opex).days
    if -7 <= delta <= -2:
        return "W-1_LONG_GAMMA"
    elif -1 <= delta <= 0:
        return "W0_PEAK_UNWIND"
    elif 1 <= delta <= 7:
        return "W+1_SHORT_GAMMA"
    elif 8 <= delta <= 14:
        return "W+2_GAMMA_SAT"
    return "OTHER"


def assign_gamma_phases(dates_arr: list[date], opex_list: list[date]) -> list[str]:
    """Assign gamma phase to each date by finding the nearest OPEX anchor."""
    phases = []
    opex_arr = sorted(opex_list)
    for d in dates_arr:
        # Find the closest OPEX date (±30 days).
        best = None
        best_delta = 999
        for o in opex_arr:
            delta = (d - o).days
            if -30 <= delta <= 30 and abs(delta) < best_delta:
                best = o
                best_delta = abs(delta)
        if best is None:
            phases.append("OTHER")
        else:
            phases.append(gamma_phase(d, best))
    return phases


# ---------------------------------------------------------------------------
# Simple NDX strategies (inline replicas of lunch_fade / ndx_trend_day)
# ---------------------------------------------------------------------------

def simple_lunch_fade_returns(bars: pd.DataFrame) -> pd.Series:
    """Minimal lunch_fade: fade the morning move at 11:30 ET, exit 13:30 ET.

    If abs(morning_return) > 0.3%, fade it.
    """
    idx = bars.index
    n = len(bars)
    if n == 0:
        return pd.Series(dtype=float)

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)
    hours = idx.hour.to_numpy()
    minutes = idx.minute.to_numpy()
    mod = hours * 60 + minutes

    dates_arr = np.asarray(idx.date)
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = dates_arr[1:] != dates_arr[:-1]
    day_starts = np.flatnonzero(change)

    ret = np.zeros(n, dtype=np.float64)

    # Day boundaries (simple detection of day changes).
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = n

    for d_i in range(len(day_starts)):
        s = int(day_starts[d_i])
        e = int(day_ends[d_i])
        day_slice = slice(s, e)
        day_mod = mod[s:e]

        # Compute morning return from open to 11:30 ET (930 min = 690).
        bars_to_1130 = np.flatnonzero(day_mod <= 690)
        if len(bars_to_1130) < 6:
            continue
        last_morning = bars_to_1130[-1]
        morning_ret = close_arr[s + last_morning] / open_arr[s] - 1.0

        if abs(morning_ret) < 0.003:
            continue  # skip weak-move days

        direction = -1 if morning_ret > 0 else 1  # fade
        entry_idx = last_morning + 1
        if entry_idx >= day_slice.stop - s:
            continue

        entry_px = open_arr[s + entry_idx] if entry_idx < day_slice.stop - s else open_arr[s + last_morning]
        if entry_px <= 0:
            continue

        exit_idx = None
        for j in range(entry_idx, day_slice.stop - s):
            if day_mod[j] >= 810:  # 13:30 ET
                exit_idx = j
                break
        if exit_idx is None:
            exit_idx = day_slice.stop - s - 1

        position_ret = direction * (close_arr[s + exit_idx] - entry_px) / entry_px
        ret[s + exit_idx] = position_ret

    return pd.Series(ret, index=idx, name="lunch_ret")


def simple_trend_day_returns(bars: pd.DataFrame) -> pd.Series:
    """Minimal ndx_trend_day: enter at 10:30 if OR expansion, exit at close."""
    idx = bars.index
    n = len(bars)
    if n == 0:
        return pd.Series(dtype=float)

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    high_arr = bars["high"].to_numpy(dtype=np.float64)
    low_arr = bars["low"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)
    hours = idx.hour.to_numpy()
    minutes = idx.minute.to_numpy()
    mod = hours * 60 + minutes

    dates_arr = np.asarray(idx.date)
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = dates_arr[1:] != dates_arr[:-1]
    day_starts = np.flatnonzero(change)

    ret = np.zeros(n, dtype=np.float64)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = n

    for d_i in range(len(day_starts)):
        s = int(day_starts[d_i])
        e = int(day_ends[d_i])
        day_mod = mod[s:e]

        # OR = 09:30-10:30 (bars with mod <= 630)
        or_mask = day_mod <= 630
        if not or_mask.any():
            continue
        or_idx_end = np.flatnonzero(or_mask)[-1]
        or_high = float(high_arr[s:s + or_idx_end + 1].max())
        or_low = float(low_arr[s:s + or_idx_end + 1].min())
        or_open = float(open_arr[s])
        if not (np.isfinite(or_high) and np.isfinite(or_low)) or or_high <= or_low:
            continue
        or_range = (or_high - or_low) / or_open
        thrust = close_arr[s + or_idx_end] - open_arr[s]
        direction = 1 if thrust > 0 else -1

        # Expansion gate: trailing 20-day median OR range.
        if d_i < 20:
            continue
        prior_ranges = []
        for pd_i in range(max(0, d_i - 20), d_i):
            ps = int(day_starts[pd_i])
            pe = int(day_ends[pd_i])
            p_or_mask = mod[ps:pe] <= 630
            if p_or_mask.any():
                p_high = float(high_arr[ps:pe][p_or_mask].max())
                p_low = float(low_arr[ps:pe][p_or_mask].min())
                p_open = float(open_arr[ps])
                if np.isfinite(p_high) and np.isfinite(p_low) and p_high > p_low:
                    prior_ranges.append((p_high - p_low) / p_open)
        if not prior_ranges:
            continue
        median_range = np.median(prior_ranges)
        if or_range <= median_range:
            continue  # no expansion, skip

        # Enter at next bar open.
        entry_idx = or_idx_end + 1
        if entry_idx >= e - s:
            continue
        entry_px = float(open_arr[s + entry_idx])
        if entry_px <= 0:
            continue

        # Exit at close.
        exit_px = float(close_arr[e - 1])
        position_ret = direction * (exit_px - entry_px) / entry_px
        ret[s + entry_idx] = position_ret

    return pd.Series(ret, index=idx, name="trend_ret")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def annualized_sharpe(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(BARS_PER_YEAR))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section("Loading NDX100 M5")
    raw = fetch_ohlc("NDX100", TIMEFRAME, START_DATE, END_DATE)
    if raw is None or raw.empty:
        print("  No data.")
        return 1
    df = raw[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.index = df.index.tz_convert(SESSION_TZ)
    mask = (df.index.hour * 60 + df.index.minute) >= RTH_OPEN
    mask &= (df.index.hour * 60 + df.index.minute) < RTH_CLOSE
    df = df.loc[mask]
    df = df.loc[df.index.dayofweek < 5]
    print(f"  bars: {len(df):,}  range: {df.index[0]} -> {df.index[-1]}")

    # Label each bar with gamma phase.
    section("Gamma cycle phase labelling")
    opex_list = opex_dates(2019, 2027)
    bar_dates = [d.date() for d in df.index]
    phases = assign_gamma_phases(bar_dates, opex_list)
    df["gamma_phase"] = phases

    phase_counts = df.groupby("gamma_phase").size()
    print("  Phase bar counts:")
    for ph, cnt in phase_counts.sort_index().items():
        print(f"    {ph:<20s}: {cnt:>6,} bars")

    # Compute simple strategy returns.
    section("Simple strategy replicas")
    lunch_ret = simple_lunch_fade_returns(df)
    trend_ret = simple_trend_day_returns(df)
    df["lunch_ret"] = lunch_ret
    df["trend_ret"] = trend_ret

    print("  Full-sample Sharpe:")
    print(f"    lunch_fade (simplified) : {annualized_sharpe(lunch_ret.to_numpy()):+.2f}")
    print(f"    trend_day (simplified)  : {annualized_sharpe(trend_ret.to_numpy()):+.2f}")

    # Split by gamma phase.
    section("Phase-split Sharpe comparison")
    sep = "-" * 80
    print(f"  {'Phase':<20s}  {'lunch_fade Sh':>13s}  {'trend_day Sh':>13s}  {'bars':>8s}")
    print(f"  {'-' * 20:s}  {'-' * 13:s}  {'-' * 13:s}  {'-' * 8:s}")

    phase_order = ["W-1_LONG_GAMMA", "W0_PEAK_UNWIND", "W+1_SHORT_GAMMA", "W+2_GAMMA_SAT", "OTHER"]
    for ph in phase_order:
        subset = df[df["gamma_phase"] == ph]
        n = len(subset)
        l_sh = annualized_sharpe(subset["lunch_ret"].to_numpy())
        t_sh = annualized_sharpe(subset["trend_ret"].to_numpy())
        print(f"  {ph:<20s}  {l_sh:>+13.2f}  {t_sh:>+13.2f}  {n:>8,}")

    # Pre-commit check: MR in W-1 vs trend in W+1.
    section("Pre-commit bars")
    wm1 = df[df["gamma_phase"] == "W-1_LONG_GAMMA"]
    wp1 = df[df["gamma_phase"] == "W+1_SHORT_GAMMA"]
    if not wm1.empty and not wp1.empty:
        l_wm1 = annualized_sharpe(wm1["lunch_ret"].to_numpy())
        l_wp1 = annualized_sharpe(wp1["lunch_ret"].to_numpy())
        t_wp1 = annualized_sharpe(wp1["trend_ret"].to_numpy())
        t_wm1 = annualized_sharpe(wm1["trend_ret"].to_numpy())

        print(f"  lunch_fade:  W-1({l_wm1:+.2f}) - W+1({l_wp1:+.2f}) = {l_wm1 - l_wp1:+.2f}  "
              f"({'PASS' if (l_wm1 - l_wp1) >= 0.20 else 'FAIL'}: need ≥+0.20)")
        print(f"  trend_day:   W+1({t_wp1:+.2f}) - W-1({t_wm1:+.2f}) = {t_wp1 - t_wm1:+.2f}  "
              f"({'PASS' if (t_wp1 - t_wm1) >= 0.20 else 'FAIL'}: need ≥+0.20)")
    else:
        print("  Insufficient data in W-1 or W+1")

    # Regime-split the phase effect (stable across 2019-2020, 2021-2022, 2023-2026?).
    section("Regime stability of gamma cycle")
    regime_windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026", "2023-01-01", "2026-12-31"),
    ]
    print(f"  {'Regime':<12s}  {'W-1 l_Sh':>9s}  {'W+1 l_Sh':>9s}  {'W-1 t_Sh':>9s}  {'W+1 t_Sh':>9s}  {'l_delta':>7s}  {'t_delta':>7s}")
    print(f"  {'-' * 12:s}  {'-' * 9:s}  {'-' * 9:s}  {'-' * 9:s}  {'-' * 9:s}  {'-' * 7:s}  {'-' * 7:s}")
    for r_label, r_start, r_end in regime_windows:
        sub = df.loc[r_start:r_end]
        sub_wm1 = sub[sub["gamma_phase"] == "W-1_LONG_GAMMA"]
        sub_wp1 = sub[sub["gamma_phase"] == "W+1_SHORT_GAMMA"]
        swl = annualized_sharpe(sub_wm1["lunch_ret"].to_numpy()) if len(sub_wm1) > 100 else -99
        swp_l = annualized_sharpe(sub_wp1["lunch_ret"].to_numpy()) if len(sub_wp1) > 100 else -99
        swt = annualized_sharpe(sub_wm1["trend_ret"].to_numpy()) if len(sub_wm1) > 100 else -99
        swp_t = annualized_sharpe(sub_wp1["trend_ret"].to_numpy()) if len(sub_wp1) > 100 else -99
        ld = swl - swp_l if -50 < swl < 50 and -50 < swp_l < 50 else -99
        td = swp_t - swt if -50 < swt < 50 and -50 < swp_t < 50 else -99
        print(f"  {r_label:<12s}  {swl:>+9.2f}  {swp_l:>+9.2f}  {swt:>+9.2f}  {swp_t:>+9.2f}  {ld:>+7.2f}  {td:>+7.2f}")

    # Placebo control: shift OPEX by +7 days.
    section("Placebo control (+7d OPEX shift)")
    shifted_opex = [d + timedelta(days=7) for d in opex_list]
    placebo_phases = assign_gamma_phases(bar_dates, shifted_opex)
    df["placebo_phase"] = placebo_phases
    df_p = df.copy()

    print(f"  {'Phase':<20s}  {'lunch_fade Sh':>13s}  {'trend_day Sh':>13s}")
    for ph in phase_order:
        subset = df_p[df_p["placebo_phase"] == ph]
        if len(subset) < 200:
            continue
        l_sh = annualized_sharpe(subset["lunch_ret"].to_numpy())
        t_sh = annualized_sharpe(subset["trend_ret"].to_numpy())
        print(f"  {ph:<20s}  {l_sh:>+13.2f}  {t_sh:>+13.2f}")

    if not wm1.empty and not wp1.empty:
        wp1_p = df_p[df_p["placebo_phase"] == "W+1_SHORT_GAMMA"]
        wm1_p = df_p[df_p["placebo_phase"] == "W-1_LONG_GAMMA"]
        if len(wm1_p) > 100 and len(wp1_p) > 100:
            pl_wm1 = annualized_sharpe(wm1_p["lunch_ret"].to_numpy())
            pl_wp1 = annualized_sharpe(wp1_p["lunch_ret"].to_numpy())
            pt_wp1 = annualized_sharpe(wp1_p["trend_ret"].to_numpy())
            pt_wm1 = annualized_sharpe(wm1_p["trend_ret"].to_numpy())
            print(f"\n  Placebo deltas (should be < +0.10):")
            print(f"    lunch_fade W-1 - W+1: {pl_wm1 - pl_wp1:+.2f}  "
                  f"({'PASS' if abs(pl_wm1 - pl_wp1) < 0.10 else 'FAIL'})")
            print(f"    trend_day  W+1 - W-1: {pt_wp1 - pt_wm1:+.2f}  "
                  f"({'PASS' if abs(pt_wp1 - pt_wm1) < 0.10 else 'FAIL'})")

    # Summary/verdict template.
    section("Summary")
    print("  Pre-committed diagnostic criteria (from thesis doc):")
    print("    1. lunch_fade W-1 - W+1 Sharpe delta >= +0.20")
    print("    2. ndx_trend_day W+1 - W-1 Sharpe delta >= +0.20")
    print("    3. Same ordering across all 3 regime windows (no sign-flip)")
    print("    4. Placebo (+7d) deltas collapse to < +0.10")
    print("    5. Each phase has >= 200 bars over full sample")
    print()
    print("  If all 5 PASS: gamma cycle is real → proceed to sizing recommendation.")
    print("  If fail but effect is strong post-2022 only: regime-conditional deploy.")
    print("  If fail on delta magnitudes: gamma cycle not NDX-deployable.")
    print("  If fail on placebo: macro-calendar confound, not gamma cycle.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
