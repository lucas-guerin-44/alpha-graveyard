"""
Phase 3 Control C3 follow-up: real NY-AM XAUUSD spread audit from datalake ticks.
Replaces the conservative M5-range proxy with actual bid-ask spread from tick data.

Fetches 13:00-15:00 UTC ticks across N representative trading days in 2024-2025,
computes spread = ask - bid, reports median / mean / p95 / p99 / max.

Pre-committed C3 bars:
- PASS:     p95 NY-AM spread ≤ 0.30 USD
- MARGINAL: 0.30 < p95 ≤ 0.50 USD
- FAIL:     p95 > 0.50 USD
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env")

DATALAKE_URL = os.getenv("DATALAKE_URL", "").rstrip("/")
DATALAKE_API_KEY = os.getenv("DATALAKE_API_KEY", "")
if not DATALAKE_URL or not DATALAKE_API_KEY:
    sys.exit("DATALAKE_URL and DATALAKE_API_KEY must be set in .env")

# 5 representative trading days across 2024-2025 (avoid Mondays-after-holiday + payroll days
# initially, then add 1-2 release days for stress)
SAMPLE_DAYS = [
    "2024-04-17",  # Wed mid-month, no major release
    "2024-09-11",  # Wed, CPI release day (high-vol stress)
    "2025-01-15",  # Wed, CPI release day
    "2025-05-14",  # Wed mid-month
    "2025-10-15",  # Wed mid-month
]
WINDOW_START = time(13, 0)  # 13:00 UTC = 09:00 ET
WINDOW_END = time(15, 0)    # 15:00 UTC = 11:00 ET


def fetch_ticks_for_window(day_iso: str) -> pd.DataFrame:
    """Fetch all XAUUSD ticks for the 13-15 UTC window on `day_iso`. Handles pagination."""
    start = f"{day_iso} {WINDOW_START.strftime('%H:%M:%S')}"
    end = f"{day_iso} {WINDOW_END.strftime('%H:%M:%S')}"
    all_rows: list[dict] = []
    cursor = None
    page = 0
    while True:
        params = {
            "instrument": "XAUUSD",
            "start": start,
            "end": end,
            "limit": 10000,
        }
        if cursor:
            params["cursor"] = cursor
        r = requests.get(
            f"{DATALAKE_URL}/ticks",
            params=params,
            headers={"X-API-Key": DATALAKE_API_KEY},
            timeout=120,
        )
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", [])
        all_rows.extend(rows)
        page += 1
        pag = payload.get("pagination", {})
        if not pag.get("has_more") or not pag.get("next_cursor"):
            break
        cursor = pag["next_cursor"]
        if page > 100:  # safety bound; ~1M ticks max per day-window
            print(f"  [warn] pagination exceeded 100 pages for {day_iso}, stopping early")
            break
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.dropna(subset=["bid", "ask"])
    df["spread"] = df["ask"] - df["bid"]
    df = df[df["spread"] >= 0]  # discard glitches
    return df


def summarize(label: str, spreads: np.ndarray) -> dict:
    if len(spreads) == 0:
        return {"label": label, "n": 0}
    return {
        "label": label,
        "n": len(spreads),
        "mean": float(spreads.mean()),
        "median": float(np.median(spreads)),
        "p75": float(np.percentile(spreads, 75)),
        "p95": float(np.percentile(spreads, 95)),
        "p99": float(np.percentile(spreads, 99)),
        "max": float(spreads.max()),
    }


def verdict(p95: float) -> str:
    if p95 <= 0.30:
        return "PASS"
    if p95 <= 0.50:
        return "MARGINAL"
    return "FAIL"


def main() -> None:
    print(f"Datalake: {DATALAKE_URL}")
    print(f"Sample days ({len(SAMPLE_DAYS)}): {', '.join(SAMPLE_DAYS)}")
    print(f"Window: {WINDOW_START}-{WINDOW_END} UTC  (NY 09:00-11:00 ET)")
    print()

    per_day: list[dict] = []
    all_spreads: list[np.ndarray] = []
    for day in SAMPLE_DAYS:
        print(f"Fetching {day} ...")
        try:
            df = fetch_ticks_for_window(day)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        if df.empty:
            print(f"  no ticks returned")
            continue
        spreads = df["spread"].to_numpy()
        all_spreads.append(spreads)
        summary = summarize(day, spreads)
        per_day.append(summary)
        print(
            f"  n={summary['n']:>6}  "
            f"median={summary['median']:.3f}  "
            f"p95={summary['p95']:.3f}  "
            f"p99={summary['p99']:.3f}  "
            f"max={summary['max']:.3f}"
        )

    if not all_spreads:
        sys.exit("No spread data returned across all sample days.")

    pooled = np.concatenate(all_spreads)
    overall = summarize("ALL DAYS", pooled)

    print()
    print("=" * 70)
    print("Per-day NY-AM spread summary")
    print("=" * 70)
    df_per_day = pd.DataFrame(per_day).set_index("label")
    print(df_per_day.to_string(float_format=lambda x: f"{x:.3f}"))

    print()
    print("=" * 70)
    print(f"POOLED NY-AM spread (n={overall['n']:,})")
    print("=" * 70)
    print(f"  mean    = {overall['mean']:.3f} USD")
    print(f"  median  = {overall['median']:.3f} USD")
    print(f"  p75     = {overall['p75']:.3f} USD")
    print(f"  p95     = {overall['p95']:.3f} USD")
    print(f"  p99     = {overall['p99']:.3f} USD")
    print(f"  max     = {overall['max']:.3f} USD")
    print()
    print(f"C3 verdict (bar: PASS <=0.30, MARGINAL 0.30-0.50, FAIL >0.50): "
          f"{verdict(overall['p95'])}  (p95 = {overall['p95']:.3f})")


if __name__ == "__main__":
    main()
