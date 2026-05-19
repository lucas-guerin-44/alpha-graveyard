"""XAU session Phase 0 — Eightcap XAUUSD spread distribution during Asian hours.

Pulls M1 bars (which include a spread column) for a recent window covering
the 22:00-02:00 UTC deploy-relevant window. Reports median/p25/p75/p90/p99
spread in points, USD, and bps.

Decision rule (pre-committed):
  median spread < 6 bps RT  → Variant C |z|>1.0 deploy bar viable
  6-10 bps RT               → Variant C DOWN-med only (lower cadence, higher margin)
  > 10 bps consistently     → tombstone xau_session

Run with no args:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/_check_xau_spread.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    print('ERROR: MetaTrader5 package not installed', file=sys.stderr)
    sys.exit(1)

SYMBOL = 'XAUUSD'
LOOKBACK_DAYS = 30
ASIA_HOURS_UTC = list(range(22, 24)) + list(range(0, 3))  # 22,23,0,1,2 UTC


def main() -> int:
    if not mt5.initialize():
        print(f'MT5 init failed: {mt5.last_error()}', file=sys.stderr)
        return 1
    try:
        info = mt5.terminal_info()
        if info:
            print(f'  Connected to: {info.company} / {info.name}')
        si = mt5.symbol_info(SYMBOL)
        if not si:
            print(f'  Symbol {SYMBOL} not found', file=sys.stderr)
            return 1
        print(f'  {SYMBOL} live: bid={si.bid}, ask={si.ask}, spread points={si.spread}, '
              f'point size={si.point}')

        # Compute live snapshot bps
        spread_usd = si.ask - si.bid
        mid = (si.ask + si.bid) / 2.0
        live_bps = spread_usd / mid * 1e4
        print(f'  Live snapshot RT spread: {spread_usd:.3f} USD = {live_bps:.2f} bps')

        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
        print(f'\n  Pulling M1 bars {start_dt.date()} -> {end_dt.date()} '
              f'(~{LOOKBACK_DAYS} days)...')
        rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            print(f'  No bars returned: {mt5.last_error()}')
            return 1
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['hour'] = df['time'].dt.hour
        df['date'] = df['time'].dt.date
        print(f'  Got {len(df):,} M1 bars; spread column present: {"spread" in df.columns}')

        if 'spread' not in df.columns:
            print('  spread column missing — using H-L as proxy')
            df['spread_pts'] = (df['high'] - df['low']) / si.point
        else:
            df['spread_pts'] = df['spread']

        df['spread_usd'] = df['spread_pts'] * si.point
        df['mid'] = (df['open'] + df['close']) / 2.0
        df['spread_bps'] = df['spread_usd'] / df['mid'] * 1e4

        def stats_block(label: str, sub: pd.DataFrame) -> None:
            if sub.empty:
                print(f'  {label}: no bars')
                return
            s = sub['spread_bps']
            print(f'  {label:<28s} n={len(sub):>6d}  '
                  f'median={s.median():>5.2f}bp  p25={s.quantile(0.25):>5.2f}  '
                  f'p75={s.quantile(0.75):>5.2f}  p90={s.quantile(0.90):>5.2f}  '
                  f'p99={s.quantile(0.99):>5.2f}  max={s.max():>5.2f}')

        print(f'\n  --- Spread distribution by session window ---\n')
        stats_block('FULL (24h, last 30d)', df)
        asia = df[df['hour'].isin(ASIA_HOURS_UTC)]
        stats_block('Asia 22-02 UTC', asia)
        deploy_entry = df[df['hour'] == 23]
        stats_block('Variant C entry (23 UTC)', deploy_entry)
        deploy_exit = df[df['hour'] == 8]
        stats_block('Variant C exit (08 UTC)', deploy_exit)
        london = df[df['hour'].between(8, 13)]
        stats_block('London 08-13 UTC', london)
        ny = df[df['hour'].between(13, 20)]
        stats_block('NY 13-20 UTC', ny)

        # Per-hour pattern (to spot broker-widening windows)
        print(f'\n  --- Median spread by UTC hour (last 30d) ---\n')
        hourly = df.groupby('hour')['spread_bps'].agg(['median', 'mean', 'count']).reset_index()
        print(f'  {"hour":>4s} {"median bp":>10s} {"mean bp":>10s} {"n":>6s}')
        for _, r in hourly.iterrows():
            marker = ''
            if r['median'] > 10:
                marker = '  <<< WIDE'
            elif r['median'] > 6:
                marker = '  <<< marginal'
            print(f'  {int(r["hour"]):>4d} {r["median"]:>9.2f}  {r["mean"]:>9.2f}  '
                  f'{int(r["count"]):>6d}{marker}')

        # Verdict
        print(f'\n  --- Verdict ---\n')
        deploy_window = df[df['hour'].isin([23, 0, 1, 2, 3, 4, 5, 6, 7, 8])]
        if deploy_window.empty:
            print('  No deploy-window bars — verdict deferred')
            return 0
        med = deploy_window['spread_bps'].median()
        p90 = deploy_window['spread_bps'].quantile(0.90)
        print(f'  Deploy window (23-08 UTC) median: {med:.2f} bp, p90: {p90:.2f} bp')
        if med < 6 and p90 < 10:
            print('  -> Variant C |z|>1.0 deploy bar VIABLE (median<6bp, p90<10bp)')
        elif med < 10:
            print('  -> Variant C DOWN-med only (median<10bp; lower-cadence higher-margin)')
        else:
            print('  -> TOMBSTONE: spread too wide for any variant')
        return 0
    finally:
        mt5.shutdown()


if __name__ == '__main__':
    sys.exit(main())
