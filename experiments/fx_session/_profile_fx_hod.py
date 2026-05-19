"""FX session Phase 0a — hour-of-day profile across major pairs.

Template: experiments/xau_session/_profile_xau_hod.py.

Goal: identify whether any FX pair has a structural intraday window
(hour-of-day mean return + t-stat) that's deployable as a strategy.
Specifically looking for time-of-day-structural signals — same mechanism
family that worked for lunch_fade (NDX) and xau_session (XAU).

Pairs loaded:
  EURUSD — multi-regime (2018-2025) via xau_session cross_cache OR fresh CSV
  USDJPY — W4 only (2024-2026) via fresh Eightcap MT5 pull
  GBPUSD — multi-regime via datalake
  AUDUSD, USDCAD, NZDUSD — recent only (~6 months) via Eightcap MT5 pull

Output: per-pair hour-of-day mean, t-stat, FULL + per-regime breakdown,
plus a final cross-pair comparison table at hour-00 UTC (the xau_session
benchmark hour) so we can see at a glance which pairs share the gold
pattern vs which have distinct intraday structure.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/fx_session/_profile_fx_hod.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)

# Data sources: prefer datalake/ohlc_data CSVs; fall back to xau_session cross_cache
_CACHE_FILES = {
    'EURUSD': [
        os.path.join(_ROOT, 'experiments', 'xau_session', 'cross_cache', 'EURUSD_H1.csv'),
        os.path.join(_ROOT, 'ohlc_data', 'EURUSD_H1.csv'),
    ],
    'USDJPY': [
        os.path.join(_ROOT, 'ohlc_data', 'USDJPY_H1.csv'),
    ],
    'GBPUSD': [
        os.path.join(_ROOT, 'ohlc_data', 'GBPUSD_H1.csv'),
    ],
    'AUDUSD': [
        os.path.join(_ROOT, 'ohlc_data', 'AUDUSD_H1.csv'),
    ],
    'USDCAD': [
        os.path.join(_ROOT, 'ohlc_data', 'USDCAD_H1.csv'),
    ],
    'NZDUSD': [
        os.path.join(_ROOT, 'ohlc_data', 'NZDUSD_H1.csv'),
    ],
    'GBPJPY': [
        os.path.join(_ROOT, 'ohlc_data', 'GBPJPY_H1.csv'),
    ],
    'AUDJPY': [
        os.path.join(_ROOT, 'ohlc_data', 'AUDJPY_H1.csv'),
    ],
    'EURJPY': [
        os.path.join(_ROOT, 'ohlc_data', 'EURJPY_H1.csv'),
    ],
}

REGIME_WINDOWS = [
    ('W1 2018-2019', '2018-01-01', '2019-12-31'),
    ('W2 2020-2021', '2020-01-01', '2021-12-31'),
    ('W3 2022-2023', '2022-01-01', '2023-12-31'),
    ('W4 2024-2026', '2024-01-01', '2026-12-31'),
]


def load_h1(symbol: str) -> pd.DataFrame | None:
    """Try cache paths in order; return first non-empty."""
    for path in _CACHE_FILES.get(symbol, []):
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path, parse_dates=['timestamp'])
        if df.empty:
            continue
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.sort_values('timestamp').reset_index(drop=True)
        df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
        df['ret_pct'] = df['close'].pct_change() * 100.0
        df['hour'] = df['timestamp'].dt.hour
        df = df.dropna(subset=['ret_pct'])
        return df
    return None


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def hour_profile_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    g = df.groupby('hour')['ret_pct']
    for h, ser in g:
        n = len(ser)
        if n < 5:
            continue
        mean = ser.mean()
        std = ser.std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if (se is not np.nan and se > 0) else 0.0
        rows.append({'hour': h, 'n': n, 'mean_pct': mean, 'std_pct': std, 't': t})
    return pd.DataFrame(rows).sort_values('hour').reset_index(drop=True)


def print_hour_profile(label: str, prof: pd.DataFrame) -> None:
    print(f'  -- {label} --')
    print(f'  {"hour":>4s} {"n":>6s} {"mean%":>9s} {"std%":>7s} {"t-stat":>7s}')
    for _, r in prof.iterrows():
        marker = ''
        if r['t'] <= -2.0:
            marker = '  <<< neg'
        elif r['t'] >= 2.0:
            marker = '  <<< pos'
        print(f"  {int(r['hour']):>4d} {int(r['n']):>6d} {r['mean_pct']:>+8.4f}% "
              f"{r['std_pct']:>6.3f}% {r['t']:>+6.2f}{marker}")


def cross_pair_summary(profiles: dict, focus_hours: list[int]) -> None:
    section(f'Cross-pair comparison at focus hours UTC {focus_hours}')
    print(f'  {"symbol":<10s} ' + ' '.join(f'h{h:02d}_mean'.rjust(11) for h in focus_hours))
    print(f'  {"":<10s} ' + ' '.join(f'h{h:02d}_t'.rjust(11) for h in focus_hours))
    print('  ' + '-' * (12 + 12 * len(focus_hours)))
    for sym, prof in profiles.items():
        if prof is None or prof.empty:
            print(f'  {sym:<10s} (no data)')
            continue
        means = []
        ts = []
        for h in focus_hours:
            row = prof[prof['hour'] == h]
            if row.empty:
                means.append('--')
                ts.append('--')
            else:
                means.append(f"{row['mean_pct'].values[0]:+.4f}%")
                ts.append(f"{row['t'].values[0]:+.2f}")
        print(f'  {sym:<10s} ' + ' '.join(m.rjust(11) for m in means))
        print(f'  {"":<10s} ' + ' '.join(t.rjust(11) for t in ts))


def session_aggregates(profiles: dict) -> None:
    """Cumulative drift per session window per pair."""
    section('Session-aggregate cumulative drift (sum of mean H1 returns)')
    SESSIONS = [
        ('Asia 01-07 UTC', range(1, 8)),
        ('LDN  08-13 UTC', range(8, 14)),
        ('NY   14-20 UTC', range(14, 21)),
        ('Late 21-23 UTC', range(21, 24)),
    ]
    print(f'  {"session":<18s} ' + ' '.join(f'{s:>10s}' for s in profiles))
    for sname, hr_range in SESSIONS:
        row = [sname]
        for sym, prof in profiles.items():
            if prof is None or prof.empty:
                row.append('--')
            else:
                s = prof[prof['hour'].isin(hr_range)]['mean_pct'].sum()
                row.append(f'{s:+.4f}%')
        print(f'  {row[0]:<18s} ' + ' '.join(f'{v:>10s}' for v in row[1:]))


def main() -> int:
    profiles_full = {}
    print('Loading H1 data for each FX pair...')
    for sym in _CACHE_FILES:
        df = load_h1(sym)
        if df is None:
            print(f'  {sym}: NOT FOUND on disk')
            profiles_full[sym] = None
            continue
        print(f'  {sym}: {len(df):,} H1 bars  {df["timestamp"].min().date()} -> {df["timestamp"].max().date()}')
        prof = hour_profile_table(df)
        profiles_full[sym] = prof
        if not prof.empty:
            section(f'{sym} — FULL hour-of-day profile')
            print_hour_profile(f'{sym} FULL', prof)
            # Per-regime if there's enough coverage
            for wname, ws, we in REGIME_WINDOWS:
                ws_ts = pd.Timestamp(ws, tz='UTC')
                we_ts = pd.Timestamp(we, tz='UTC')
                sub = df[(df['timestamp'] >= ws_ts) & (df['timestamp'] <= we_ts)]
                if len(sub) < 200:
                    continue
                wprof = hour_profile_table(sub)
                print()
                print_hour_profile(f'{sym} {wname}', wprof)

    # Per-pair vol summary (std per H1 bar, key hours)
    section('Per-pair vol comparison (std% per H1 bar, by hour)')
    vol_hours = [0, 1, 8, 14, 23]
    print(f'  {"symbol":<10s} ' + ' '.join(f'h{h:02d}_std%'.rjust(11) for h in vol_hours) + ' overall_std%')
    print('  ' + '-' * (12 + 12 * len(vol_hours) + 14))
    for sym, prof in profiles_full.items():
        if prof is None or prof.empty:
            print(f'  {sym:<10s} (no data)')
            continue
        stds = []
        for h in vol_hours:
            row = prof[prof['hour'] == h]
            if row.empty:
                stds.append('--')
            else:
                stds.append(f"{row['std_pct'].values[0]:.4f}%")
        overall = prof['std_pct'].mean()
        print(f'  {sym:<10s} ' + ' '.join(s.rjust(11) for s in stds) + f'   {overall:.4f}%')

    # Cross-pair side-by-side at key hours
    KEY_HOURS = [0, 1, 7, 8, 12, 13, 16, 22, 23]
    cross_pair_summary(profiles_full, KEY_HOURS)

    # Session aggregates
    session_aggregates(profiles_full)

    # Highlight: which pair × hour has t > +3 in FULL?
    section('STRONGEST SIGNALS — hours with |t| > 3 in FULL')
    found = False
    for sym, prof in profiles_full.items():
        if prof is None or prof.empty:
            continue
        strong = prof[prof['t'].abs() > 3.0]
        for _, r in strong.iterrows():
            found = True
            sign = 'LONG' if r['t'] > 0 else 'SHORT'
            print(f'  {sym}  hour {int(r["hour"]):>2d} UTC  '
                  f'mean {r["mean_pct"]:+.4f}%  t {r["t"]:+.2f}  n={int(r["n"])}  '
                  f'<<< {sign} candidate')
    if not found:
        print('  (no pair × hour cell with |t| > 3)')

    section('Phase 0a next step')
    print('  Look for: (1) pair × hour signals that are NOT also strong on EURUSD')
    print('  (since EURUSD-hour-00 overlaps with xau_session — needs diversification);')
    print('  (2) signals consistent across regimes (where multi-regime data exists);')
    print('  (3) mechanism-anchored windows: Tokyo-fix (00 UTC), London-open (07-08),')
    print('      NY-fix (~15-16), London-close (16-17).')
    print('  If a clean candidate emerges, proceed to Phase 0b (filter sweep).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
