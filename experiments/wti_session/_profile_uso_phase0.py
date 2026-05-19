#!/usr/bin/env python3
"""USOUSD Phase 0 profile — three energy theses in one pass.

Inputs: ohlc_data/USOUSD_H1.csv (run _fetch_uso_h1.py first).

Theses surveyed (all timestamps UTC):

  A. EIA-Wednesday inventory release drift
     EIA crude inventory: Wed 10:30 ET = 15:30 UTC (16:30 UTC during US DST).
     H1 bar containing release: 15:00-16:00 UTC (winter) / 16:00-17:00 UTC (summer).
     Test: post-release bar (close 16-17 UTC winter / 17-18 UTC summer) drift on
     Wed vs non-Wed at the same hour. Cleanest signal is the comparison.

  B. Asian-session drift on USOUSD (xau_session analog)
     Hour-of-day mean/Sharpe across full 24h, broken down by W1-W4 regime.
     Looking for a hour-00 UTC drift family (Asian open) or any other
     structurally consistent session-handoff window.

  C. NYMEX pit-close drift (14:30 ET = 19:30 UTC winter / 20:30 UTC summer)
     Pit-close settlement-window microstructure. Compare bars surrounding
     19-21 UTC across days.

W1 = 2018-2019, W2 = 2020-2021, W3 = 2022-2023, W4 = 2024-2026.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
DATA_PATH = _ROOT / "ohlc_data" / "USOUSD_H1.csv"

REGIMES = [
    ("W1", 2018, 2019),
    ("W2", 2020, 2021),
    ("W3", 2022, 2023),
    ("W4", 2024, 2026),
]


def section(t: str) -> None:
    print(f'\n{"=" * 96}\n  {t}\n{"=" * 96}')


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[df["timestamp"] >= pd.Timestamp("2018-01-01", tz="UTC")].copy()
    df["hour"] = df["timestamp"].dt.hour
    df["dow"] = df["timestamp"].dt.day_name()
    df["dow_idx"] = df["timestamp"].dt.weekday  # Mon=0..Sun=6
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["bar_ret"] = df["close"].pct_change()
    return df


def regime_of(year: int) -> str:
    for tag, ys, ye in REGIMES:
        if ys <= year <= ye:
            return tag
    return "??"


def annualized_sharpe(r: np.ndarray, periods_per_year: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    if s == 0 or not np.isfinite(s):
        return 0.0
    return float(r.mean() / s * np.sqrt(periods_per_year))


# ---------------------------------------------------------------------------
# Thesis A — EIA Wednesday inventory release drift
# ---------------------------------------------------------------------------

def thesis_a_eia(df: pd.DataFrame) -> None:
    section("THESIS A — EIA Wednesday inventory release drift")
    print("""
EIA crude inventory release is Wed 10:30 ET (15:30 UTC winter, 14:30 UTC US-DST summer).
With H1 bars on UTC clock, the release falls inside one of:
  - bar 15:00-16:00 UTC (winter; release at 30min into bar)
  - bar 14:00-15:00 UTC (summer; release at 30min into bar)
We test 3 hypotheses:
  H1: post-release bar (close-of-release-bar -> close of next bar) on Wed
      drifts differently than other days at same hour
  H2: pre-release bar (bar before release) on Wed differs vs non-Wed (positioning)
  H3: post-release 3h window (release+1h -> release+4h) shows drift on Wed
""")
    # Use a Wed-aware comparison. We'll test the 15-16 UTC bar (winter EIA close-1)
    # and the 16-17 UTC bar (winter EIA close+1). Then 14-15 / 15-16 (summer EIA).
    # Quick & honest: don't bother splitting by DST — just look at all combinations
    # and see which ones show a Wed effect.

    # Per-bar return = close pct change (already computed in df.bar_ret)
    # Mean return of bar at (dow=Wed, hour=H) vs (dow != Wed, hour=H), all years
    print(f"  {'hour':>4s}  {'Wed mean (bps)':>16s}  {'Wed n':>7s}  "
          f"{'Wed t':>8s}  {'!Wed mean (bps)':>16s}  {'!Wed n':>7s}  "
          f"{'gap (bps)':>11s}")
    print("  " + "-" * 90)
    for h in range(13, 22):  # focus on US morning -> US close zone (13-21 UTC = 09-17 ET)
        sub = df[df["hour"] == h]
        wed = sub[sub["dow_idx"] == 2]["bar_ret"].dropna().to_numpy()
        oth = sub[sub["dow_idx"] != 2]["bar_ret"].dropna().to_numpy()
        if len(wed) < 30 or len(oth) < 30:
            continue
        wed_mean = wed.mean()
        oth_mean = oth.mean()
        wed_t = wed_mean / (wed.std(ddof=1) / np.sqrt(len(wed)))
        gap = (wed_mean - oth_mean) * 1e4
        marker = " <-- EIA-bar?" if h in (14, 15, 16) else ""
        print(f"  {h:>4d}  {wed_mean * 1e4:>+15.2f}  {len(wed):>7d}  "
              f"{wed_t:>+8.2f}  {oth_mean * 1e4:>+15.2f}  {len(oth):>7d}  "
              f"{gap:>+11.2f}{marker}")

    print("\n  Per-regime Wed-only hour 15+16+17 UTC bar return (covers winter+summer EIA-bar zone):")
    print(f"  {'regime':<12s} {'hour':>5s} {'mean (bps)':>12s} {'n':>6s} {'t':>7s} {'Sh*':>7s}")
    for tag, ys, ye in REGIMES:
        reg = df[(df["year"] >= ys) & (df["year"] <= ye)]
        for h in (14, 15, 16, 17):
            wed = reg[(reg["hour"] == h) & (reg["dow_idx"] == 2)]["bar_ret"].dropna().to_numpy()
            if len(wed) < 10:
                continue
            mean = wed.mean()
            t = mean / (wed.std(ddof=1) / np.sqrt(len(wed))) if len(wed) > 1 else 0.0
            sh = annualized_sharpe(wed, periods_per_year=52)  # ~52 Wed/yr
            print(f"  {tag:<12s} {h:>5d} {mean * 1e4:>+11.2f}  {len(wed):>6d} {t:>+7.2f} {sh:>+7.2f}")


# ---------------------------------------------------------------------------
# Thesis B — hour-of-day drift across full 24h (Asian session focus)
# ---------------------------------------------------------------------------

def thesis_b_hod(df: pd.DataFrame) -> None:
    section("THESIS B — Hour-of-day drift profile (Asian-session focus)")
    print("""
Per-hour mean H1 bar return, FULL + W1-W4 regime breakdown. We look for hours
with consistently positive (or negative) drift across all 4 regimes — these
are session-handoff structural windows. xau_session has hour-00 UTC up; we
check whether USOUSD shows the same family or a different cycle entirely.
""")
    header = f"  {'hour':>4s}  {'FULL n':>7s}  {'FULL bps':>9s}  {'FULL t':>7s}  "
    for tag, _, _ in REGIMES:
        header += f"{tag + ' bps':>8s}  "
    print(header)
    print("  " + "-" * (16 + 9 * 6))
    for h in range(0, 24):
        row = f"  {h:>4d}  "
        sub_all = df[df["hour"] == h]["bar_ret"].dropna().to_numpy()
        if len(sub_all) < 30:
            row += "(insufficient)"
            print(row)
            continue
        mean_all = sub_all.mean()
        t_all = mean_all / (sub_all.std(ddof=1) / np.sqrt(len(sub_all)))
        row += f"{len(sub_all):>7d}  {mean_all * 1e4:>+8.2f}  {t_all:>+7.2f}  "
        for tag, ys, ye in REGIMES:
            sub = df[(df["hour"] == h) & (df["year"] >= ys) & (df["year"] <= ye)]["bar_ret"].dropna()
            if len(sub) < 20:
                row += f"{'-':>8s}  "
            else:
                row += f"{sub.mean() * 1e4:>+8.2f}  "
        print(row)


# ---------------------------------------------------------------------------
# Thesis C — NYMEX pit-close drift (14:30 ET = 19:30 UTC winter, 18:30 UTC summer)
# ---------------------------------------------------------------------------

def thesis_c_pit(df: pd.DataFrame) -> None:
    section("THESIS C — NYMEX pit-close settlement-window drift")
    print("""
NYMEX WTI pit physically closes 14:30 ET (19:30 UTC winter / 18:30 UTC summer).
Pit close = settlement-window microstructure: traders rebalance, MOC-like
imbalances clear. We test:
  Hour 18 UTC (summer pit close bar / winter pre-close-bar)
  Hour 19 UTC (winter pit close bar / summer post-close bar)
  Hour 20 UTC (post-pit-close)
Compare to nearby hours to check for an isolated pit-close effect.
""")
    # FULL + per-regime, hours 17-21
    print(f"  {'hour':>4s}  {'FULL n':>7s}  {'FULL bps':>9s}  {'FULL t':>7s}  "
          f"{'W1':>7s}  {'W2':>7s}  {'W3':>7s}  {'W4':>7s}")
    print("  " + "-" * 70)
    for h in range(17, 22):
        sub = df[df["hour"] == h]["bar_ret"].dropna().to_numpy()
        if len(sub) < 30:
            print(f"  {h:>4d}  (insufficient)")
            continue
        mean = sub.mean()
        t = mean / (sub.std(ddof=1) / np.sqrt(len(sub)))
        row = f"  {h:>4d}  {len(sub):>7d}  {mean * 1e4:>+8.2f}  {t:>+7.2f}  "
        for tag, ys, ye in REGIMES:
            s = df[(df["hour"] == h) & (df["year"] >= ys) & (df["year"] <= ye)]["bar_ret"].dropna()
            if len(s) < 20:
                row += f"{'-':>7s}  "
            else:
                row += f"{s.mean() * 1e4:>+7.2f}  "
        print(row)

    # Compare same hour Mon-Fri to see if pit-close hour is special vs same hour other days
    print("\n  DOW slice for pit-close hours 18/19/20 UTC (mean bps):")
    print(f"  {'dow':<10s} {'h18':>7s} {'h19':>7s} {'h20':>7s}")
    for dow_idx, dow in [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri")]:
        row = f"  {dow:<10s} "
        for h in (18, 19, 20):
            s = df[(df["hour"] == h) & (df["dow_idx"] == dow_idx)]["bar_ret"].dropna()
            if len(s) < 20:
                row += f"{'-':>7s} "
            else:
                row += f"{s.mean() * 1e4:>+7.2f} "
        print(row)


# ---------------------------------------------------------------------------
# Session aggregates — what cumulative drift does each session contribute?
# ---------------------------------------------------------------------------

def session_aggregates(df: pd.DataFrame) -> None:
    section("Session aggregate cumulative drift")
    print("""
Sum of per-bar returns over a session window = cumulative session drift.
""")
    sessions = [
        ("Asia 23-07 UTC", list(range(23, 24)) + list(range(0, 7))),
        ("London 07-13 UTC", list(range(7, 13))),
        ("US-morning 13-18 UTC", list(range(13, 18))),
        ("US-pit-close 18-20 UTC", list(range(18, 20))),
        ("US-late 20-23 UTC", list(range(20, 23))),
    ]
    print(f"  {'session':<26s}  {'FULL bps':>10s}  {'W1':>8s}  {'W2':>8s}  {'W3':>8s}  {'W4':>8s}")
    for name, hours in sessions:
        row = f"  {name:<26s}  "
        sub_all = df[df["hour"].isin(hours)]["bar_ret"].dropna()
        row += f"{sub_all.sum() / len(df['timestamp'].dt.date.unique()) * 1e4:>+9.2f}  "
        for tag, ys, ye in REGIMES:
            sub = df[(df["hour"].isin(hours)) & (df["year"] >= ys) & (df["year"] <= ye)]["bar_ret"].dropna()
            ndays = len(df[(df["year"] >= ys) & (df["year"] <= ye)]["timestamp"].dt.date.unique())
            if ndays == 0:
                row += f"{'-':>8s}  "
                continue
            row += f"{sub.sum() / ndays * 1e4:>+8.2f}  "
        print(row)


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing {DATA_PATH} — run _fetch_uso_h1.py first")
    df = load()
    print(f"Loaded {len(df):,} H1 bars: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    thesis_b_hod(df)
    thesis_a_eia(df)
    thesis_c_pit(df)
    session_aggregates(df)


if __name__ == "__main__":
    main()
