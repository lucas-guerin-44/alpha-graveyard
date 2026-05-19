#!/usr/bin/env python3
"""Fetch USOUSD H1 from datalake into ohlc_data/USOUSD_H1.csv.

Datalake /api/query is capped at 10000 rows per request, so pull year-by-year
and concat. Matches the xau_session._fetch_xau_h1.py pattern.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
load_dotenv(_ROOT / ".env")

URL = os.environ["DATALAKE_URL"].rstrip("/")
KEY = os.environ["DATALAKE_API_KEY"]

OUT = _ROOT / "ohlc_data" / "USOUSD_H1.csv"
SYM = "USOUSD"
TF = "H1"
START = "2018-01-01"
END = "2026-12-31"


def fetch_year(y: int) -> pd.DataFrame:
    start = f"{y}-01-01"
    end = f"{y}-12-31"
    r = requests.get(
        f"{URL}/query",
        params=dict(instrument=SYM, timeframe=TF, start=start, end=end, limit=10000),
        headers={"X-API-Key": KEY},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    return df


def main() -> None:
    frames = []
    for y in range(2018, 2027):
        df = fetch_year(y)
        print(f"  {y}: {len(df):>6d} rows", flush=True)
        if len(df):
            frames.append(df)
    if not frames:
        sys.exit("No data returned from datalake")
    big = pd.concat(frames, ignore_index=True)
    big["timestamp"] = pd.to_datetime(big["timestamp"], utc=True)
    big = big.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    big.to_csv(OUT, index=False)
    print(f"\nWrote {len(big)} rows -> {OUT}")
    print(f"Range: {big['timestamp'].min()} -> {big['timestamp'].max()}")


if __name__ == "__main__":
    main()
