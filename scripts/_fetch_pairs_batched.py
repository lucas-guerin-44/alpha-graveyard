"""One-shot batched fetcher for the equity_pairs demo.

Yahoo rate-limits aggressive unauthenticated requests. After a ban, the
IP-session needs 15-30 min of silence before it clears. This script:

  1. Sleeps 25 min upfront to let a prior ban clear.
  2. Uses a SINGLE yf.download call (one HTTP request for all 20 tickers).
  3. Falls back to per-ticker with 1s gaps only if the batch fails.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _datalake import DATA_DIR, merge_with_existing, write_csv  # noqa: E402

try:
    import yfinance as yf  # type: ignore
except ImportError as e:
    sys.stderr.write(f"yfinance import failed: {e}\n")
    sys.exit(2)

TICKERS = [
    "KO", "PEP", "XOM", "CVX", "JPM", "BAC", "V", "MA", "HD", "LOW",
    "UNH", "CI", "PG", "CL", "WMT", "TGT", "LMT", "RTX", "GS", "MS",
]

START = "2015-01-01"
END = "2026-04-18"

INITIAL_COOLDOWN = 1500   # 25 min
PER_TICKER_DELAY = 1.0    # used only in fallback path


def save_ticker(ticker: str, df: pd.DataFrame) -> None:
    ts = pd.to_datetime(df.index)
    if ts.tz is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    out = pd.DataFrame({
        "instrument": ticker,
        "timeframe": "D1",
        "timestamp": ts,
        "open": df["Open"].astype(float).values,
        "high": df["High"].astype(float).values,
        "low": df["Low"].astype(float).values,
        "close": df["Close"].astype(float).values,
    }).dropna(subset=["open", "high", "low", "close"])
    path = DATA_DIR / f"{ticker}_D1.csv"
    if path.exists():
        merged = merge_with_existing(out, path)
    else:
        merged = out
    write_csv(merged, path)
    print(f"  {ticker}: {len(out)} bars "
          f"{out['timestamp'].iloc[0].date()} -> {out['timestamp'].iloc[-1].date()} "
          f"-> {path.name}", flush=True)


def try_batch() -> int:
    """Single yf.download for all tickers. Returns count saved."""
    syms = " ".join(TICKERS)
    print(f"Batch fetch: {len(TICKERS)} tickers in one call...", flush=True)
    df = yf.download(
        syms,
        start=START,
        end=END,
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
        group_by="ticker",
    )
    if df is None or df.empty:
        print("  Batch returned empty.", flush=True)
        return 0
    saved = 0
    for t in TICKERS:
        try:
            sub = df[t].dropna(subset=["Close"])
        except KeyError:
            print(f"  {t}: missing from response", flush=True)
            continue
        if sub.empty:
            print(f"  {t}: empty after dropna", flush=True)
            continue
        save_ticker(t, sub)
        saved += 1
    return saved


def try_sequential() -> int:
    """Fallback: one call per ticker with 1s spacing."""
    print("Falling back to sequential per-ticker fetch...", flush=True)
    saved = 0
    for i, t in enumerate(TICKERS):
        if i > 0:
            time.sleep(PER_TICKER_DELAY)
        try:
            df = yf.download(
                t, start=START, end=END, interval="1d",
                auto_adjust=True, progress=False, threads=False,
            )
        except Exception as e:
            print(f"  {t}: EXCEPTION {type(e).__name__}: {e}", flush=True)
            continue
        if df is None or df.empty:
            print(f"  {t}: empty", flush=True)
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        save_ticker(t, df)
        saved += 1
    return saved


def main() -> int:
    print(f"Sleeping {INITIAL_COOLDOWN}s ({INITIAL_COOLDOWN // 60} min) for rate-limit cooldown...",
          flush=True)
    start = time.time()
    time.sleep(INITIAL_COOLDOWN)
    print(f"Woke at {datetime.now(timezone.utc).isoformat()}. Elapsed: {time.time() - start:.0f}s",
          flush=True)

    saved = try_batch()
    if saved < len(TICKERS):
        remaining = [t for t in TICKERS if not (DATA_DIR / f"{t}_D1.csv").exists()]
        if remaining:
            print(f"After batch: {saved}/{len(TICKERS)}; missing: {remaining}", flush=True)
            saved_seq = try_sequential()
            saved = max(saved, saved_seq)

    print(f"\nDONE: {saved}/{len(TICKERS)} tickers available in cache", flush=True)
    return 0 if saved == len(TICKERS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
