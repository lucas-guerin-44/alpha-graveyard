"""XAU session Phase 0 — cross-product hour-00 UTC profile.

Tests whether the Asia-open drift (+5.26 t-stat on XAUUSD hour-00) is
gold-specific or a basket-wide "Asia opens with risk-on bias" effect.

Basket: EURUSD, GER40, SPX500, JPN225, BTCUSD.
Compared against XAUUSD baseline (loaded from local CSV).

If gold-specific: structural mechanism (Asian physical demand).
If basket-wide: signal is generic risk-on into Asia open.

Run with no args:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/_profile_xau_cross.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_CACHE_DIR = os.path.join(_HERE, 'cross_cache')
os.makedirs(_CACHE_DIR, exist_ok=True)

URL = os.environ['DATALAKE_URL'].rstrip('/')
KEY = os.environ['DATALAKE_API_KEY']

CROSS_SYMBOLS = ['EURUSD', 'GER40', 'SPX500', 'JPN225', 'BTCUSD']
TIMEFRAME = 'H1'
START_YEAR = 2018
END_YEAR = 2026


def fetch_symbol(symbol: str, force: bool = False) -> pd.DataFrame:
    cache_path = os.path.join(_CACHE_DIR, f'{symbol}_{TIMEFRAME}.csv')
    if os.path.exists(cache_path) and not force:
        return pd.read_csv(cache_path, parse_dates=['timestamp'])
    all_rows = []
    for yr in range(START_YEAR, END_YEAR + 1):
        t0 = time.time()
        try:
            r = requests.get(
                f'{URL}/api/query',
                params={
                    'instrument': symbol, 'timeframe': TIMEFRAME,
                    'start': f'{yr}-01-01', 'end': f'{yr}-12-31',
                    'limit': 10000,
                },
                headers={'X-API-Key': KEY}, timeout=120,
            )
            rows = r.json().get('data', [])
        except Exception as e:
            print(f'  {symbol} {yr}: ERROR {e}', flush=True)
            continue
        all_rows.extend(rows)
        elapsed = time.time() - t0
        print(f'  {symbol} {yr}: {len(rows)} rows in {elapsed:.1f}s (total {len(all_rows)})', flush=True)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').drop_duplicates(subset='timestamp').reset_index(drop=True)
    df.to_csv(cache_path, index=False)
    return df


def label_regime(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2019:
        return 'W1'
    if y <= 2021:
        return 'W2'
    if y <= 2023:
        return 'W3'
    return 'W4'


def profile_hour00(symbol: str, df: pd.DataFrame) -> dict:
    """Compute hour-00 UTC return profile FULL + per-regime."""
    df = df.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['ret_pct'] = df['close'].pct_change() * 100.0
    df['hour'] = df['timestamp'].dt.hour
    df = df.dropna(subset=['ret_pct'])
    hour00 = df[df['hour'] == 0].copy()
    hour00['regime'] = hour00['timestamp'].apply(label_regime)

    result = {'symbol': symbol}
    # Full
    r = hour00['ret_pct'].to_numpy()
    n = len(r)
    if n < 10:
        result['n_full'] = n
        return result
    mean = r.mean()
    std = r.std(ddof=1)
    se = std / np.sqrt(n)
    t = mean / se if se else 0.0
    sharpe = mean / std * np.sqrt(252) if std else 0.0
    result.update({
        'n_full': n, 'mean_full': mean, 't_full': t, 'sharpe_full': sharpe,
    })
    # Per-regime
    for w in ('W1', 'W2', 'W3', 'W4'):
        sub = hour00[hour00['regime'] == w]
        wn = len(sub)
        if wn < 10:
            result[f'mean_{w}'] = np.nan
            result[f't_{w}'] = np.nan
            continue
        wr = sub['ret_pct'].to_numpy()
        wmean = wr.mean()
        wstd = wr.std(ddof=1)
        wse = wstd / np.sqrt(wn) if wn > 1 else np.nan
        wt = wmean / wse if wse else 0.0
        result[f'mean_{w}'] = wmean
        result[f't_{w}'] = wt
        result[f'n_{w}'] = wn
    return result


def fmt_pct(x: float) -> str:
    if pd.isna(x):
        return '   --'
    return f'{x:+.4f}%'


def fmt_t(x: float) -> str:
    if pd.isna(x):
        return '  --'
    return f'{x:+.2f}'


def main() -> int:
    # XAU baseline from local CSV
    xau_df = pd.read_csv(os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv'),
                         parse_dates=['timestamp'])
    print('  Profiling XAUUSD (baseline)...', flush=True)
    xau_result = profile_hour00('XAUUSD', xau_df)

    results = [xau_result]
    for sym in CROSS_SYMBOLS:
        print(f'  Fetching {sym}...', flush=True)
        df = fetch_symbol(sym)
        if df.empty:
            print(f'  {sym}: no data', flush=True)
            continue
        print(f'  Profiling {sym} ({len(df):,} bars)...', flush=True)
        res = profile_hour00(sym, df)
        results.append(res)

    print('\n' + '=' * 100)
    print('  Cross-product hour-00 UTC profile (FULL + per-regime mean and t-stat)')
    print('=' * 100 + '\n')
    print(f'  {"symbol":<10s} {"n":>5s} {"FULL mean":>11s} {"t":>6s} {"Sharpe":>7s} '
          f'{"W1 mean":>11s} {"t":>6s} {"W2 mean":>11s} {"t":>6s} '
          f'{"W3 mean":>11s} {"t":>6s} {"W4 mean":>11s} {"t":>6s}')
    print('  ' + '-' * 130)
    for r in results:
        if 'mean_full' not in r:
            print(f'  {r["symbol"]:<10s} {r.get("n_full", 0):>5d} (insufficient)')
            continue
        print(f'  {r["symbol"]:<10s} {r["n_full"]:>5d} '
              f'{fmt_pct(r["mean_full"]):>11s} {fmt_t(r["t_full"]):>6s} '
              f'{r["sharpe_full"]:>+6.2f} '
              f'{fmt_pct(r.get("mean_W1", np.nan)):>11s} {fmt_t(r.get("t_W1", np.nan)):>6s} '
              f'{fmt_pct(r.get("mean_W2", np.nan)):>11s} {fmt_t(r.get("t_W2", np.nan)):>6s} '
              f'{fmt_pct(r.get("mean_W3", np.nan)):>11s} {fmt_t(r.get("t_W3", np.nan)):>6s} '
              f'{fmt_pct(r.get("mean_W4", np.nan)):>11s} {fmt_t(r.get("t_W4", np.nan)):>6s}')

    print('\n  --- Interpretation gate ---')
    print('  - If only XAUUSD has FULL t > +3: gold-specific (Asian physical demand mechanism).')
    print('  - If EURUSD, GER40, SPX500, JPN225 ALL have FULL t > +2: basket-wide risk-on bias.')
    print('  - Mixed (some yes, some no): hybrid — gold has both effects, deploy as gold-alone but flag.')
    print('  - BTCUSD as the 24/7 control: a positive result here suggests "global risk-on into Asia",')
    print('    a negative result suggests the gold effect is specifically gold (physical demand).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
