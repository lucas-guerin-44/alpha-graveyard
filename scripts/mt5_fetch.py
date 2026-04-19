"""Fetch OHLC bars from a local MetaTrader 5 terminal into the datalake.

Windows-only. Requires the ``MetaTrader5`` Python package and an MT5 terminal
installed on the machine. Credentials are optional if the terminal is already
logged in; otherwise set ``MT5_LOGIN``/``MT5_PASSWORD``/``MT5_SERVER`` in the
project ``.env`` (and optionally ``MT5_PATH`` pointing at ``terminal64.exe``).

Examples
--------
Fetch XAUUSD M15 bars from 2024 onward into ``ohlc_data/XAUUSD_M15.csv``::

    python scripts/mt5_fetch.py --symbols XAUUSD --timeframes M15 --from 2024-01-01

Fetch several symbols/timeframes in one pass, merging with existing CSVs::

    python scripts/mt5_fetch.py \\
        --symbols EURUSD,GBPUSD,AUDNZD \\
        --timeframes H1,D1 \\
        --from 2020-01-01

List symbols the broker exposes (useful to learn exact tickers)::

    python scripts/mt5_fetch.py --list-symbols --match XAU
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _datalake import DATA_DIR, PROJECT_ROOT, inject_to_datalake, merge_with_existing, write_csv

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:
    sys.stderr.write(
        "MetaTrader5 package is not installed. Install it with:\n"
        "    pip install MetaTrader5\n"
        "It is Windows-only and requires an MT5 terminal on the machine.\n"
    )
    raise

# MT5 timeframe constants are only available after import, so build the map
# lazily inside ``tf_code_to_mt5``.
TIMEFRAME_CODES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1")


def tf_code_to_mt5(code: str) -> int:
    code = code.upper()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }
    if code not in mapping:
        raise ValueError(f"Unknown timeframe {code!r}. Supported: {', '.join(TIMEFRAME_CODES)}")
    return mapping[code]


def parse_date(s: str, *, end: bool = False) -> datetime:
    """Parse a YYYY-MM-DD string as a UTC datetime (end-of-day if ``end``)."""
    dt = datetime.strptime(s, "%Y-%m-%d")
    if end:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt.replace(tzinfo=timezone.utc)


def connect() -> None:
    """Initialize the MT5 terminal connection using env credentials if provided."""
    load_dotenv(PROJECT_ROOT / ".env")

    path = os.getenv("MT5_PATH") or None
    login = os.getenv("MT5_LOGIN")
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")

    kwargs = {}
    if path:
        kwargs["path"] = path
    if login:
        kwargs["login"] = int(login)
    if password:
        kwargs["password"] = password
    if server:
        kwargs["server"] = server

    if not mt5.initialize(**kwargs):
        code, msg = mt5.last_error()
        raise RuntimeError(f"mt5.initialize failed: [{code}] {msg}")


def fetch_bars(symbol: str, tf_code: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Pull bars from MT5 and shape them into the datalake schema."""
    if not mt5.symbol_select(symbol, True):
        code, msg = mt5.last_error()
        raise RuntimeError(f"symbol_select({symbol}) failed: [{code}] {msg}")

    rates = mt5.copy_rates_range(symbol, tf_code_to_mt5(tf_code), start, end)
    if rates is None or len(rates) == 0:
        return pd.DataFrame(
            columns=["instrument", "timeframe", "timestamp", "open", "high", "low", "close"]
        )

    df = pd.DataFrame(rates)
    df["timestamp"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["instrument"] = symbol
    df["timeframe"] = tf_code
    return df[["instrument", "timeframe", "timestamp", "open", "high", "low", "close"]]


def list_symbols(match: str | None) -> list[str]:
    symbols = mt5.symbols_get() or []
    names = [s.name for s in symbols]
    if match:
        m = match.upper()
        names = [n for n in names if m in n.upper()]
    return sorted(names)


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch MT5 OHLC bars into the local datalake.")
    p.add_argument("--symbols", help="Comma-separated symbols, e.g. 'XAUUSD,EURUSD'")
    p.add_argument(
        "--timeframes",
        default="D1",
        help=f"Comma-separated timeframes ({', '.join(TIMEFRAME_CODES)}). Default: D1",
    )
    p.add_argument("--from", dest="date_from", default="2015-01-01", help="Start date YYYY-MM-DD")
    p.add_argument(
        "--to",
        dest="date_to",
        default=None,
        help="End date YYYY-MM-DD (default: today UTC)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing CSVs instead of merging new bars into them",
    )
    p.add_argument("--dry-run", action="store_true", help="Fetch and report, but don't write files")
    p.add_argument("--list-symbols", action="store_true", help="List broker symbols and exit")
    p.add_argument("--match", help="Substring filter for --list-symbols (case-insensitive)")
    p.add_argument(
        "--datalake",
        dest="datalake",
        action="store_true",
        default=True,
        help="POST bars to the datalake (default if DATALAKE_API_KEY is set)",
    )
    p.add_argument(
        "--no-datalake",
        dest="datalake",
        action="store_false",
        help="Skip the datalake POST; only write CSVs locally",
    )
    p.add_argument(
        "--csv-only",
        action="store_true",
        help="Alias for --no-datalake",
    )
    args = p.parse_args()

    connect()
    try:
        if args.list_symbols:
            for name in list_symbols(args.match):
                print(name)
            return 0

        if not args.symbols:
            p.error("--symbols is required (or use --list-symbols)")

        start = parse_date(args.date_from)
        end = parse_date(args.date_to, end=True) if args.date_to else datetime.now(timezone.utc)

        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
        tfs = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]

        inject = args.datalake and not args.csv_only and bool(os.getenv("DATALAKE_API_KEY", "").strip())

        total_new = 0
        total_injected = 0
        for sym in symbols:
            for tf in tfs:
                df_new = fetch_bars(sym, tf, start, end)
                path = DATA_DIR / f"{sym}_{tf}.csv"

                if args.overwrite or not path.exists():
                    merged = df_new
                    added = len(df_new)
                else:
                    before = pd.read_csv(path)
                    merged = merge_with_existing(df_new, path)
                    added = max(0, len(merged) - len(before))

                if args.dry_run:
                    target = "datalake+csv" if inject else "csv"
                    print(f"[dry-run] {sym} {tf}: fetched {len(df_new)} bars, +{added} new -> {target}")
                elif not df_new.empty:
                    write_csv(merged, path)
                    msg = f"{sym} {tf}: fetched {len(df_new)} bars, +{added} new -> {path}"
                    if inject:
                        try:
                            sent = inject_to_datalake(df_new, sym, tf)
                            total_injected += sent
                            msg += f" | datalake: +{sent}"
                        except Exception as e:
                            msg += f" | datalake FAILED: {e}"
                    print(msg)
                else:
                    print(f"{sym} {tf}: no bars returned for {start.date()}..{end.date()}")

                total_new += added

        print(f"\nTotal new bars written to CSV: {total_new}")
        if inject:
            print(f"Total rows injected to datalake: {total_injected}")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
