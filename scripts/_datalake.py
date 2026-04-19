"""Shared helpers for data fetchers: CSV merge + datalake injection.

Used by ``mt5_fetch.py`` and ``yahoo_fetch.py`` (and any future fetcher).
Internal module — the leading underscore indicates it is not a public CLI.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "ohlc_data"

CSV_COLUMNS = ["instrument", "timeframe", "timestamp", "open", "high", "low", "close"]


def merge_with_existing(df_new: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Merge new bars into an existing CSV, deduping on timestamp."""
    if not path.exists() or df_new.empty:
        return df_new

    df_old = pd.read_csv(path, parse_dates=["timestamp"])
    df_old["timestamp"] = pd.to_datetime(df_old["timestamp"], utc=True)

    combined = pd.concat([df_old, df_new], ignore_index=True)
    combined = combined.drop_duplicates(subset="timestamp", keep="last")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def write_csv(df: pd.DataFrame, path: Path) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def inject_to_datalake(df: pd.DataFrame, instrument: str, timeframe: str) -> int:
    """POST bars to the datalake as a multipart CSV upload. Returns rows sent.

    Ingest endpoint expects multipart/form-data with:
      - ``file``: CSV payload
      - ``instrument``: form field
      - ``timeframe``: form field
    Override the path via ``DATALAKE_INGEST_PATH`` in ``.env`` if needed.
    """
    if df.empty:
        return 0

    base_url = os.getenv("DATALAKE_URL", "").strip()
    api_key = os.getenv("DATALAKE_API_KEY", "").strip()
    ingest_path = os.getenv("DATALAKE_INGEST_PATH", "/ingest").strip()

    if not base_url:
        raise RuntimeError("DATALAKE_URL is not set; cannot inject to datalake")
    if not api_key:
        raise RuntimeError("DATALAKE_API_KEY is not set; cannot inject to datalake")

    url = f"{base_url.rstrip('/')}{ingest_path if ingest_path.startswith('/') else '/' + ingest_path}"
    headers = {"Authorization": f"Bearer {api_key}"}

    buf = io.StringIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue().encode("utf-8")

    files = {"file": (f"{instrument}_{timeframe}.csv", csv_bytes, "text/csv")}
    data = {"instrument": instrument, "timeframe": timeframe}

    resp = requests.post(url, files=files, data=data, headers=headers, timeout=120)
    if not resp.ok:
        body = resp.text[:2000]
        raise RuntimeError(
            f"{resp.status_code} {resp.reason} from {url}\n"
            f"Sent {len(df)} rows for {instrument} {timeframe}\n"
            f"Server response: {body}"
        )
    return len(df)
