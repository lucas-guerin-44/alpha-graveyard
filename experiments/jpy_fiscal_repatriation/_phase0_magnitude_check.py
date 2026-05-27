#!/usr/bin/env python3
"""Phase 0 magnitude check for jpy_fiscal_repatriation.

Pre-committed gates (BEFORE Phase 2 expansion):
  - gross mean >= +80 bps/yr on 7-year sample
  - net mean (post spread + swap) >= +20 bps/yr
  - >= 5/7 years positive
  - 2023-2025 (W3) mean >= 0 (regime persistence)

Strategy: SHORT USDJPY from first business day >= Feb 15 to last business
day <= Mar 28 of each fiscal year.

Cost model:
  - spread:    1 pip RT = 0.7 bps (avg quote across sample)
  - swap:      SHORT USDJPY pays negative carry; ~5% annualized = 1.4 bps/day
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
USDJPY_PATH = _ROOT / "ohlc_data" / "USDJPY_D1.csv"

YEARS = list(range(2019, 2027))  # 2019-2026; 2026 incomplete in sample
ENTRY_TARGET = (2, 15)   # Feb 15
EXIT_TARGET = (3, 28)    # Mar 28

SPREAD_BPS_RT = 0.7
SWAP_BPS_PER_DAY = 1.4   # SHORT USDJPY negative carry


def first_business_day_on_or_after(df: pd.DataFrame, year: int, mm: int, dd: int) -> pd.Timestamp | None:
    """Find first trading day in `df` with date >= year-mm-dd."""
    target = pd.Timestamp(year=year, month=mm, day=dd, tz="UTC")
    dates = df["timestamp"]
    after = dates[dates >= target]
    if after.empty:
        return None
    return after.iloc[0]


def last_business_day_on_or_before(df: pd.DataFrame, year: int, mm: int, dd: int) -> pd.Timestamp | None:
    target = pd.Timestamp(year=year, month=mm, day=dd, tz="UTC") + pd.Timedelta(days=1)  # inclusive
    dates = df["timestamp"]
    before = dates[dates < target]
    if before.empty:
        return None
    return before.iloc[-1]


def load_usdjpy_d1() -> pd.DataFrame:
    df = pd.read_csv(USDJPY_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return df


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def main() -> int:
    section("jpy_fiscal_repatriation — Phase 0 magnitude check")
    if not USDJPY_PATH.exists():
        print(f"USDJPY_D1.csv not found at {USDJPY_PATH}")
        return 1

    df = load_usdjpy_d1()
    print(f"Loaded USDJPY D1: {len(df):,} bars  "
          f"range {df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")

    rows = []
    for fy in YEARS:
        entry_ts = first_business_day_on_or_after(df, fy, *ENTRY_TARGET)
        exit_ts = last_business_day_on_or_before(df, fy, *EXIT_TARGET)
        if entry_ts is None or exit_ts is None:
            print(f"  FY {fy}: entry/exit out of range — skipping")
            continue
        entry_px = float(df.loc[df["timestamp"] == entry_ts, "close"].iloc[0])
        exit_px = float(df.loc[df["timestamp"] == exit_ts, "close"].iloc[0])
        hold_days = (exit_ts - entry_ts).days
        # business days approximation (D1 csv only has business bars, so count between is BD)
        bd_idx = df[(df["timestamp"] >= entry_ts) & (df["timestamp"] <= exit_ts)]
        n_bd = len(bd_idx) - 1  # exclusive of entry bar

        # SHORT USDJPY: profit when exit < entry
        gross_pct = (entry_px - exit_px) / entry_px * 100.0       # % move
        gross_bps = gross_pct * 100.0                              # bps

        swap_drag_bps = SWAP_BPS_PER_DAY * n_bd
        net_bps = gross_bps - SPREAD_BPS_RT - swap_drag_bps

        rows.append({
            "fy": fy,
            "entry_date": entry_ts.date(),
            "exit_date": exit_ts.date(),
            "entry_px": entry_px,
            "exit_px": exit_px,
            "hold_days_cal": hold_days,
            "hold_days_business": n_bd,
            "gross_bps": gross_bps,
            "swap_drag_bps": swap_drag_bps,
            "net_bps": net_bps,
        })

    res = pd.DataFrame(rows)
    section("Per-year results")
    fmt = res.copy()
    fmt["entry_px"] = fmt["entry_px"].map(lambda x: f"{x:.2f}")
    fmt["exit_px"] = fmt["exit_px"].map(lambda x: f"{x:.2f}")
    fmt["gross_bps"] = fmt["gross_bps"].map(lambda x: f"{x:+.1f}")
    fmt["swap_drag_bps"] = fmt["swap_drag_bps"].map(lambda x: f"{x:.1f}")
    fmt["net_bps"] = fmt["net_bps"].map(lambda x: f"{x:+.1f}")
    print(fmt.to_string(index=False))

    section("Phase 0 magnitude check")
    n = len(res)
    gross_mean = res["gross_bps"].mean()
    net_mean = res["net_bps"].mean()
    gross_hit_rate = float((res["gross_bps"] > 0).mean())
    net_hit_rate = float((res["net_bps"] > 0).mean())
    gross_std = res["gross_bps"].std(ddof=1) if n > 1 else 0
    net_std = res["net_bps"].std(ddof=1) if n > 1 else 0

    # W3 = 2023-2026 holdout (per Lesson A regime persistence)
    w3 = res[res["fy"] >= 2023]
    w3_gross_mean = w3["gross_bps"].mean() if len(w3) > 0 else np.nan
    w3_net_mean = w3["net_bps"].mean() if len(w3) > 0 else np.nan

    print(f"  n = {n} fiscal years")
    print(f"  Gross mean    : {gross_mean:+.1f} bps     (Phase 0 floor: +80 bps)")
    print(f"  Net mean      : {net_mean:+.1f} bps     (Phase 0 floor: +20 bps)")
    print(f"  Gross hit rate: {gross_hit_rate*100:.0f}% ({int(gross_hit_rate*n)}/{n})  (floor: 5/{n} = {5/max(n,1)*100:.0f}%)")
    print(f"  Net hit rate  : {net_hit_rate*100:.0f}% ({int(net_hit_rate*n)}/{n})")
    print(f"  Gross std     : {gross_std:.1f} bps  -> per-year ratio mean/std = {(gross_mean/gross_std if gross_std>0 else 0):.2f}")
    print(f"  Net std       : {net_std:.1f} bps  -> ratio {(net_mean/net_std if net_std>0 else 0):.2f}")
    print()
    print(f"  W3 (2023+) gross mean: {w3_gross_mean:+.1f} bps  (n={len(w3)})   (floor: > 0)")
    print(f"  W3 (2023+) net mean  : {w3_net_mean:+.1f} bps")

    section("Phase 0 gate result")
    gates = [
        ("Gross mean >= +80 bps", gross_mean >= 80.0),
        ("Net mean >= +20 bps",  net_mean >= 20.0),
        ("Hit rate >= 5/7 (71%)", gross_hit_rate >= (5.0 / 7.0) - 1e-9),
        ("W3 (2023+) gross mean > 0", w3_gross_mean > 0),
    ]
    for label, ok in gates:
        print(f"  {label:<35s} : {'PASS' if ok else 'FAIL'}")
    overall_pass = all(ok for _, ok in gates)
    print()
    print(f"  -> Phase 0: {'PASS -> proceed to Phase 2' if overall_pass else 'REJECT (Phase 0 abort)'}")

    section("Direction null check (LONG USDJPY same window)")
    # If LONG also positive of similar magnitude, mechanism is general drift not FY-specific
    long_gross_bps = -res["gross_bps"]  # opposite direction
    long_net_bps = long_gross_bps - SPREAD_BPS_RT + SWAP_BPS_PER_DAY * res["hold_days_business"]  # LONG earns swap
    print(f"  LONG gross mean: {long_gross_bps.mean():+.1f} bps")
    print(f"  LONG net mean  : {long_net_bps.mean():+.1f} bps  (LONG earns positive carry)")
    print(f"  Direction gap (SHORT-LONG gross): {(gross_mean - long_gross_bps.mean()):+.1f} bps")
    print(f"  Direction gap (SHORT-LONG net):   {(net_mean - long_net_bps.mean()):+.1f} bps")

    return 0


if __name__ == "__main__":
    sys.exit(main())
