#!/usr/bin/env python3
"""LBMA Gold Price fix calendar — Europe/London local 10:30 / 15:00 -> UTC.

DST-aware. Skips Sat/Sun. Returns a long-format DataFrame:
    [date, session, fix_utc]   session in {"AM", "PM"}

Holiday filtering is implicit downstream: if no XAUUSD M1 bar exists within the
tolerance window of the fix time (LBMA closed, broker closed, or Christmas
Eve early close), the trade simply skips. This avoids hand-maintaining an
LBMA holiday list and keeps the calendar a pure DST-conversion artifact.

A side-effect of NOT hard-coding holidays is that a small number of
non-fix-days (UK bank holidays etc.) get generated and then dropped by the
data-presence check in the simulator. The drop-rate is logged in Phase 0b
so we can sanity-check the count vs the ~10 LBMA closed days/yr expected.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9 fallback
    from backports.zoneinfo import ZoneInfo  # type: ignore

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

AM_FIX_LOCAL = (10, 30)   # 10:30 London
PM_FIX_LOCAL = (15, 0)    # 15:00 London


def build_fix_calendar(start: str = "2018-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    rows = []
    days = pd.date_range(start, end, freq="D")
    for d in days:
        if d.dayofweek >= 5:  # Sat, Sun
            continue
        for session, (hh, mm) in (("AM", AM_FIX_LOCAL), ("PM", PM_FIX_LOCAL)):
            local = pd.Timestamp(d.year, d.month, d.day, hh, mm, tz=LONDON)
            utc = local.tz_convert(UTC)
            rows.append({"date": d.normalize(), "session": session, "fix_utc": utc})
    df = pd.DataFrame(rows)
    df["fix_utc"] = pd.to_datetime(df["fix_utc"], utc=True)
    return df


def main() -> int:
    cal = build_fix_calendar()
    out = Path(__file__).parent / "fix_calendar.csv"
    cal.to_csv(out, index=False)
    print(f"Wrote {len(cal):,} fix events ({cal['date'].min().date()} -> {cal['date'].max().date()}) to {out}")
    n_days = cal["date"].nunique()
    print(f"  {n_days:,} weekdays; {n_days*2:,} expected events ({len(cal):,} actual)")
    # DST sanity-check: log a few sample dates around DST boundaries
    print("\nDST sanity-check (UTC hour of fix at boundary dates):")
    sample_dates = [
        "2024-03-29", "2024-04-02",   # spring transition
        "2024-10-25", "2024-10-29",   # autumn transition
    ]
    for ds in sample_dates:
        sub = cal[cal["date"] == pd.Timestamp(ds).normalize()]
        if not len(sub):
            continue
        for _, r in sub.iterrows():
            print(f"  {ds} {r['session']} fix UTC = {r['fix_utc']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
