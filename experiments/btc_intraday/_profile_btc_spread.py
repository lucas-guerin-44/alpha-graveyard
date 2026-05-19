"""BTC intraday Phase 0c #1 -- Eightcap M1 spread verification.

Loads ohlc_data/BTCUSD_M1.csv (just pulled from Eightcap via mt5_fetch).
Computes M1 H-L in bps during 00:00-07:00 UTC (Asian session, deploy-
relevant window) and compares to non-Asian hours.

H-L overestimates true bid-ask spread but is a conservative proxy for
market-order RT cost at the bar open.

Decision rule:
  median M1 H-L bps during 00:00-07:00 UTC:
    < 7 bps RT  -> Variant E clean Phase 1 PASS
    7-10 bps    -> MARGINAL, Phase 1 needs binding W4-recent kill criterion
    > 10 bps    -> KEEP_FOR_REFERENCE, tombstone Phase 0
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
M1_PATH = os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M1.csv')

m1 = pd.read_csv(M1_PATH, parse_dates=['timestamp'])
m1['timestamp'] = pd.to_datetime(m1['timestamp'], utc=True, format='mixed')
m1 = m1.sort_values('timestamp').reset_index(drop=True)
m1['hour'] = m1['timestamp'].dt.hour

# H-L in bps of close
m1['hl_bps'] = (m1['high'] - m1['low']) / m1['close'] * 10_000.0

print(f'  Loaded {len(m1):,} M1 bars  '
      f'{m1["timestamp"].min()} -> {m1["timestamp"].max()}')
print()


def stats(label: str, sub: pd.DataFrame) -> None:
    if len(sub) < 10:
        print(f'  {label}: n={len(sub)} too sparse')
        return
    hl = sub['hl_bps'].to_numpy()
    p25, p50, p75, p90, p95 = np.percentile(hl, [25, 50, 75, 90, 95])
    print(f'  {label:<30s}: n={len(sub):>5d}  '
          f'p25={p25:>5.1f}  median={p50:>5.1f}  p75={p75:>5.1f}  '
          f'p90={p90:>5.1f}  p95={p95:>5.1f}  mean={hl.mean():>5.1f}')


# Hour-by-hour breakdown for 00-07 UTC (deploy window)
print('  === Per-hour M1 H-L (bps) ===')
print(f'  {"hour":>4s} {"n":>5s} {"p25":>5s} {"med":>5s} {"p75":>5s} '
      f'{"p90":>5s} {"p95":>5s} {"mean":>5s}')
for h in range(24):
    sub = m1[m1['hour'] == h]
    if len(sub) < 10:
        continue
    hl = sub['hl_bps'].to_numpy()
    p25, p50, p75, p90, p95 = np.percentile(hl, [25, 50, 75, 90, 95])
    marker = ''
    if h == 0:
        marker = '  <<< ENTRY HOUR'
    elif 1 <= h <= 6:
        marker = '  (deploy window cont.)'
    print(f'  {h:>4d} {len(sub):>5d} {p25:>5.1f} {p50:>5.1f} {p75:>5.1f} '
          f'{p90:>5.1f} {p95:>5.1f} {hl.mean():>5.1f}{marker}')

print('\n  === Session aggregates ===')
stats('Asia 00-07 UTC (DEPLOY)', m1[m1['hour'] < 8])
stats('Europe 08-13 UTC', m1[(m1['hour'] >= 8) & (m1['hour'] < 14)])
stats('US 14-20 UTC', m1[(m1['hour'] >= 14) & (m1['hour'] < 21)])
stats('Late 21-23 UTC', m1[m1['hour'] >= 21])
stats('ALL HOURS', m1)

# Entry-specific: minute 0 of hour 00 (the exact entry minute)
entry = m1[(m1['hour'] == 0) & (m1['timestamp'].dt.minute == 0)]
print('\n  === Specific entry minute: 00:00 UTC sharp ===')
stats('Hour-00 minute-0', entry)

# Verdict
print('\n  === Deploy decision (median M1 H-L during 00-07 UTC) ===')
deploy_window = m1[m1['hour'] < 8]
median_bps = float(np.percentile(deploy_window['hl_bps'].to_numpy(), 50))
mean_bps = float(deploy_window['hl_bps'].mean())
print(f'  Median: {median_bps:.1f} bps RT (proxy)')
print(f'  Mean:   {mean_bps:.1f} bps RT (proxy)')
print(f'  Note: M1 H-L overestimates true inside spread; treat as upper bound.')
if median_bps < 7.0:
    print('  -> < 7 bps RT: Variant E is a clean Phase 1 PASS')
elif median_bps < 10.0:
    print('  -> 7-10 bps RT: MARGINAL, Phase 1 needs W4-recent kill criterion')
else:
    print('  -> > 10 bps RT: KEEP_FOR_REFERENCE / tombstone')
