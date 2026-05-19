"""BTC intraday Phase 0c — sub-hour M5 profile within 00:00-01:00 UTC.

Question: is the hour-00 UTC drift front-loaded in the first 5-15 minutes
(Asia pile-in at the bar open) or evenly distributed across the hour?

If front-loaded, a tighter entry window (e.g. 00:00 -> 00:15 UTC) pays cost
once for similar gross — cost economics improve.
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M5.csv')


def label_regime(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2019:
        return 'W1'
    if y <= 2021:
        return 'W2'
    if y <= 2023:
        return 'W3'
    return 'W4'


# Load M5 bars within 00:00-00:59 UTC (12 M5 buckets per day)
m5 = pd.read_csv(M5_PATH, parse_dates=['timestamp'])
m5['timestamp'] = pd.to_datetime(m5['timestamp'], utc=True, format='mixed')
m5 = m5.sort_values('timestamp').reset_index(drop=True)
m5 = m5[m5['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
m5['minute'] = m5['timestamp'].dt.minute
m5['hour'] = m5['timestamp'].dt.hour
m5['regime'] = m5['timestamp'].apply(label_regime)

# Sub-hour return: close-to-close on each M5 bar
m5['ret_pct'] = m5['close'].pct_change() * 100.0
# Drop the first bar of any gap > 6 min
m5['gap_m'] = m5['timestamp'].diff().dt.total_seconds() / 60.0
m5.loc[m5['gap_m'] > 6.0, 'ret_pct'] = np.nan

# Focus on hour-00 bars (12 M5 buckets per UTC day: 00:00, 00:05, ..., 00:55)
h00 = m5[m5['hour'] == 0].dropna(subset=['ret_pct']).copy()
print(f'  Total M5 bars in hour-00 UTC: {len(h00):,}')
print(f'  Date range: {h00["timestamp"].min().date()} -> {h00["timestamp"].max().date()}\n')

# --- Per-M5-bucket profile FULL period ---
print('  === Per-M5-bucket mean (bps) — FULL period ===')
print(f'  {"minute":>6s} {"n":>5s} {"mean_bps":>9s} {"t-stat":>7s} {"cum_bps":>9s}')
cum = 0.0
for m_ in range(0, 60, 5):
    sub = h00[h00['minute'] == m_]
    n = len(sub)
    if n < 5:
        continue
    mean_bps = sub['ret_pct'].mean() * 100.0
    std = sub['ret_pct'].std(ddof=1)
    se = std / np.sqrt(n) if n > 1 else np.nan
    t = mean_bps / 100.0 / se if se and np.isfinite(se) else 0.0
    cum += mean_bps
    marker = '  <<<' if abs(t) >= 2.0 else ''
    print(f'  {m_:>6d} {n:>5d} {mean_bps:>+8.2f}  {t:>+6.2f}  {cum:>+8.2f}{marker}')

# --- Per-M5-bucket profile per regime ---
print('\n  === Per-M5-bucket mean (bps) — per regime ===')
print(f'  {"min":>4s} {"W1 mean":>9s} {"W2 mean":>9s} {"W3 mean":>9s} {"W4 mean":>9s}')
for m_ in range(0, 60, 5):
    row = [f'  {m_:>3d}']
    for w in ('W1', 'W2', 'W3', 'W4'):
        sub = h00[(h00['minute'] == m_) & (h00['regime'] == w)]
        if len(sub) < 5:
            row.append(f'{"  --":>9s}')
        else:
            mean_bps = sub['ret_pct'].mean() * 100.0
            row.append(f'{mean_bps:>+8.2f}')
    print(' '.join(row))

# --- Cumulative drift through the hour FULL period ---
print('\n  === Cumulative drift entering at 00:00, exiting at 00:MM ===')
print('  (treats each M5 bar as a successive log-return contribution)')
print(f'  {"exit min":>9s} {"cum_bps_FULL":>13s} {"cum_bps_W4":>11s} {"cost_10bp_net":>13s}')
cum_full = 0.0
cum_w4 = 0.0
for m_ in range(0, 60, 5):
    full = h00[h00['minute'] == m_]['ret_pct'].mean() * 100.0 if len(h00[h00['minute'] == m_]) >= 5 else 0.0
    w4 = h00[(h00['minute'] == m_) & (h00['regime'] == 'W4')]['ret_pct'].mean() * 100.0 \
         if len(h00[(h00['minute'] == m_) & (h00['regime'] == 'W4')]) >= 5 else 0.0
    cum_full += full
    cum_w4 += w4
    exit_min = m_ + 5
    net = cum_full / 100.0 - 0.10  # 10 bps RT cost
    flag = '  <CLEAR>' if net > 0 else ''
    print(f'  00:{exit_min:>02d}      {cum_full:>+10.2f}    {cum_w4:>+8.2f}     '
          f'{net * 100:>+8.2f} bps{flag}')

# --- Phase 0c verdict ---
print('\n  === Sub-hour cost-clearing check ===')
print('  If cumulative drift at any sub-hour exit clears 10bp RT cost AND')
print('  the cumulative drift to that exit > 50% of full-hour cumulative,')
print('  a tighter entry/exit window is the deploy candidate.\n')

full_hour_cum = sum(h00[h00['minute'] == m_]['ret_pct'].mean() * 100.0
                    for m_ in range(0, 60, 5) if len(h00[h00['minute'] == m_]) >= 5)
print(f'  Full-hour cumulative drift: {full_hour_cum:+.2f} bps')
print(f'  Full-hour clears cost?     {"YES" if full_hour_cum > 10 else "NO"}')
