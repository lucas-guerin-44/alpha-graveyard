"""XAGUSD hour-of-day profile across 2019-2026. Phase 0a exploration.

Direct analog of xau_session/_profile_xau_hod.py — does silver share the
hour-00 UTC structural drift that gold has? If yes, proceed with Phase 0b;
if no (or signal sign-inverts), tombstone.
"""
import os, sys
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

df = pd.read_csv(
    os.path.join(_ROOT, 'ohlc_data', 'XAGUSD_H1.csv'),
    parse_dates=['timestamp'],
)
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)
df = df[df['timestamp'] >= pd.Timestamp('2019-01-01', tz='UTC')].copy()
df['ret_pct'] = df['close'].pct_change() * 100.0
df['hour'] = df['timestamp'].dt.hour
df = df.dropna(subset=['ret_pct'])


def profile(label, sub):
    g = sub.groupby('hour')['ret_pct']
    rows = []
    for h, ser in g:
        n = len(ser)
        mean = ser.mean()
        std = ser.std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if (se and np.isfinite(se)) else 0.0
        rows.append({'hour': h, 'n': n, 'mean_pct': mean, 'std_pct': std, 't': t})
    out = pd.DataFrame(rows).sort_values('hour')
    print(f'\n  -- {label} --')
    print(f'  {"hour":>4s} {"n":>6s} {"mean%":>9s} {"std%":>7s} {"t-stat":>7s}')
    for _, r in out.iterrows():
        marker = ''
        if r['t'] <= -2.0:
            marker = '  <<< neg'
        elif r['t'] >= 2.0:
            marker = '  <<< pos'
        print(f"  {int(r['hour']):>4d} {int(r['n']):>6d} {r['mean_pct']:>+8.4f}% "
              f"{r['std_pct']:>6.3f}% {r['t']:>+6.2f}{marker}")
    return out


print(f"  XAGUSD H1: {len(df):,} bars  "
      f"{df['timestamp'].min().date()} -> {df['timestamp'].max().date()}")
full_out = profile('FULL 2019-2026', df)

# Regime windows (silver-adjusted: W1 is only 2019 because no 2018 data)
WINDOWS = [
    ('W1 2019',      '2019-01-01', '2019-12-31'),
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

# Side-by-side annualized
print('\n\n  === Per-hour mean return (annualized %) across windows ===')
HOURS_PER_YEAR = 252 * 24
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

# Session aggregates
print('\n\n  === Session aggregate cumulative drift ===')
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

# Direct comparison: hour-00 in each regime — the xau_session benchmark
print('\n\n  === Hour-00 UTC comparison vs xau_session (the deploy-binding hour) ===')
print(f"  XAGUSD hour-00:")
for wname, _, _ in WINDOWS:
    wr = regime_profiles[wname]
    h0 = wr[wr['hour'] == 0]
    if h0.empty:
        continue
    print(f"    {wname:<14s} mean {h0['mean_pct'].values[0]:>+8.4f}%  "
          f"std {h0['std_pct'].values[0]:>6.3f}%  t {h0['t'].values[0]:>+6.2f}  n={int(h0['n'].values[0])}")
print()
print("  Reference (xau_session same hour):")
print("    XAU W1 2018-2019: mean +0.0198%, t +5.12, n=515")
print("    XAU W2 2020-2021: mean +0.0282%, t +3.06, n=516")
print("    XAU W3 2022-2023: mean +0.0169%, t +2.35, n=513")
print("    XAU W4 2024-2026: mean +0.0325%, t +2.46, n=578")
print("    XAU FULL t=+5.26, ratio recent6mo/W4-mean=3.34 (still building)")
