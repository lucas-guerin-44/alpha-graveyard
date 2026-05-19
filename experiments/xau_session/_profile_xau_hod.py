"""XAUUSD hour-of-day profile across 2018-2026. Phase 0 exploration.

Goal: identify whether there's an Asian-session-vs-other asymmetry in
XAUUSD H1 returns, similar to the discovery process that surfaced
NDX100 lunch_fade.

Output: per-hour mean return, std, t-stat across full window and per regime.
"""
import os, sys
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

df = pd.read_csv(
    os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv'),
    parse_dates=['timestamp'],
)
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)

# Cut to real H1 (raw) era — 2018+
df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()

# Hourly return: close-to-close on consecutive H1 bars
df['ret_pct'] = df['close'].pct_change() * 100.0
df['hour'] = df['timestamp'].dt.hour  # UTC hour
df['date'] = df['timestamp'].dt.date
df['dow'] = df['timestamp'].dt.day_name()
df = df.dropna(subset=['ret_pct'])

# Helper
def profile(label, sub):
    g = sub.groupby('hour')['ret_pct']
    rows = []
    for h, ser in g:
        n = len(ser)
        mean = ser.mean()
        std = ser.std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if se and np.isfinite(se) else 0.0
        rows.append({
            'hour': h, 'n': n, 'mean_pct': mean,
            'std_pct': std, 't': t,
        })
    out = pd.DataFrame(rows).sort_values('hour')
    print(f'\n  -- {label} --')
    print(f'  {"hour":>4s} {"n":>6s} {"mean%":>8s} {"std%":>7s} {"t-stat":>7s}')
    for _, r in out.iterrows():
        marker = ''
        if r['t'] <= -2.0:
            marker = '  <<< neg'
        elif r['t'] >= 2.0:
            marker = '  <<< pos'
        print(f"  {int(r['hour']):>4d} {int(r['n']):>6d} {r['mean_pct']:>+7.4f}% "
              f"{r['std_pct']:>6.3f}% {r['t']:>+6.2f}{marker}")
    # Cumulative-mean during continuous-trading hours (skip data gaps)
    return out


# Annotate timezone landmarks
print(f"  XAUUSD H1: {len(df):,} bars  "
      f"{df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")
print(f"  Total hourly returns: {len(df.dropna(subset=['ret_pct']))}")

# Full period
full_out = profile('FULL 2018-2026', df)

# Regime windows (matching btc framework)
WINDOWS = [
    ('W1 2018-2019', '2018-01-01', '2019-12-31'),
    ('W2 2020-2021', '2020-01-01', '2021-12-31'),
    ('W3 2022-2023', '2022-01-01', '2023-12-31'),
    ('W4 2024-2026', '2024-01-01', '2026-04-30'),
]
regime_profiles = {}
for wname, ws, we in WINDOWS:
    ws_ts = pd.Timestamp(ws, tz='UTC')
    we_ts = pd.Timestamp(we, tz='UTC')
    sub = df[(df['timestamp'] >= ws_ts) & (df['timestamp'] <= we_ts)]
    regime_profiles[wname] = profile(wname, sub)

# Side-by-side compare full vs each window
print('\n\n  === Per-hour mean return (annualized %) across windows ===')
HOURS_PER_YEAR = 252 * 24  # rough
print(f"  {'hour':>4s} {'FULL':>8s} {'W1':>8s} {'W2':>8s} {'W3':>8s} {'W4':>8s}")
for h in range(24):
    fr = full_out[full_out['hour'] == h]
    if fr.empty:
        continue
    full_ann = fr['mean_pct'].values[0] * HOURS_PER_YEAR
    row_vals = [full_ann]
    for wname, _, _ in WINDOWS:
        wr = regime_profiles[wname]
        sub = wr[wr['hour'] == h]
        if sub.empty:
            row_vals.append(np.nan)
        else:
            row_vals.append(sub['mean_pct'].values[0] * HOURS_PER_YEAR)
    print(f"  {h:>4d} " + " ".join(f"{v:>+7.2f}%" for v in row_vals))

# Asian session aggregate (01:00-07:00 UTC) vs European (08:00-14:00) vs US (14:00-21:00)
print('\n\n  === Session aggregate cumulative drift (sum of mean H1 returns) ===')
print(f"  {'session':<24s} {'full':>10s} {'W1':>10s} {'W2':>10s} {'W3':>10s} {'W4':>10s}")
SESSIONS = [
    ('Asia 01-07 UTC',    range(1, 8)),
    ('London 08-13 UTC',  range(8, 14)),
    ('NY 14-20 UTC',      range(14, 21)),
    ('Late 21-23 UTC',    range(21, 24)),
]
for sname, hr_range in SESSIONS:
    full_sum = full_out[full_out['hour'].isin(hr_range)]['mean_pct'].sum()
    row = [full_sum]
    for wname, _, _ in WINDOWS:
        wr = regime_profiles[wname]
        row.append(wr[wr['hour'].isin(hr_range)]['mean_pct'].sum())
    print(f"  {sname:<24s} " + " ".join(f"{v:>+9.4f}%" for v in row))
