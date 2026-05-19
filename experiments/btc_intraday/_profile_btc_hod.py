"""BTCUSD hour-of-day profile across 2018-2026. Phase 0 exploration.

Mirrors experiments/xau_session/_profile_xau_hod.py.

Aggregates M5 -> H1 in-process (UTC). Profiles:
  1. Hour-of-day mean H1 return, FULL + W1-W4 regimes
  2. Day-of-week slice (BTC trades 24/7 -> Sat/Sun are structural)
  3. Session aggregate cumulative drift (Asia/EU/US/Late)
"""
import os
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# --- Load M5, aggregate to H1 ---
m5 = pd.read_csv(
    os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M5.csv'),
    parse_dates=['timestamp'],
)
m5['timestamp'] = pd.to_datetime(m5['timestamp'], utc=True)
m5 = m5.sort_values('timestamp').reset_index(drop=True)

# Restrict to 2018+ (matches BTC framework)
m5 = m5[m5['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()

# Floor to H1 bucket, aggregate OHLC
m5['h1_bucket'] = m5['timestamp'].dt.floor('1h')
h1 = (
    m5.groupby('h1_bucket', as_index=False)
      .agg(open=('open', 'first'),
           high=('high', 'max'),
           low=('low', 'min'),
           close=('close', 'last'),
           bars=('close', 'size'))
      .rename(columns={'h1_bucket': 'timestamp'})
)
h1 = h1.sort_values('timestamp').reset_index(drop=True)

# Hourly return: close-to-close on consecutive H1 bars
h1['ret_pct'] = h1['close'].pct_change() * 100.0
h1['hour'] = h1['timestamp'].dt.hour       # UTC hour
h1['date'] = h1['timestamp'].dt.date
h1['dow_idx'] = h1['timestamp'].dt.weekday  # 0=Mon ... 6=Sun
h1['dow'] = h1['timestamp'].dt.day_name()
h1 = h1.dropna(subset=['ret_pct']).reset_index(drop=True)

# Drop the first bar of any obvious gap: if previous bar is > 2h earlier,
# the close-to-close return is contaminated by the gap. Mark and drop.
h1['gap_h'] = h1['timestamp'].diff().dt.total_seconds() / 3600.0
h1['gap_flag'] = h1['gap_h'] > 1.5
gapped = int(h1['gap_flag'].sum())
h1 = h1[~h1['gap_flag']].copy()


# --- Profile helper ---
def profile(label, sub):
    g = sub.groupby('hour')['ret_pct']
    rows = []
    for h_, ser in g:
        n = len(ser)
        mean = ser.mean()
        std = ser.std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if se and np.isfinite(se) else 0.0
        rows.append({
            'hour': h_, 'n': n, 'mean_pct': mean,
            'std_pct': std, 't': t,
        })
    out = pd.DataFrame(rows).sort_values('hour')
    print(f'\n  -- {label} --')
    print(f'  {"hr":>3s} {"n":>6s} {"mean%":>8s} {"std%":>7s} {"t":>6s}')
    for _, r in out.iterrows():
        marker = ''
        if r['t'] <= -2.0:
            marker = '  <<< neg'
        elif r['t'] >= 2.0:
            marker = '  <<< pos'
        print(f"  {int(r['hour']):>3d} {int(r['n']):>6d} {r['mean_pct']:>+7.4f}% "
              f"{r['std_pct']:>6.3f}% {r['t']:>+6.2f}{marker}")
    return out


print(f"  M5 rows loaded: {len(m5):,}")
print(f"  H1 bars derived: {len(h1):,}  "
      f"{h1['timestamp'].min().date()} -> {h1['timestamp'].max().date()}")
print(f"  Bars dropped on gap > 1.5h: {gapped}")

# --- 1. FULL period hour-of-day ---
full_out = profile('FULL 2018-2026', h1)

# --- 2. Regime windows ---
WINDOWS = [
    ('W1 2018-2019', '2018-01-01', '2019-12-31'),
    ('W2 2020-2021', '2020-01-01', '2021-12-31'),
    ('W3 2022-2023', '2022-01-01', '2023-12-31'),
    ('W4 2024-2026', '2024-01-01', '2026-05-15'),
]
regime_profiles = {}
for wname, ws, we in WINDOWS:
    ws_ts = pd.Timestamp(ws, tz='UTC')
    we_ts = pd.Timestamp(we, tz='UTC')
    sub = h1[(h1['timestamp'] >= ws_ts) & (h1['timestamp'] <= we_ts)]
    regime_profiles[wname] = profile(wname, sub)

# --- 3. Per-hour mean return across windows (annualized %) ---
print('\n\n  === Per-hour mean H1 return (annualized %, 24*365 hrs) across windows ===')
HOURS_PER_YEAR = 24 * 365
print(f"  {'hr':>3s} {'FULL':>8s} {'W1':>8s} {'W2':>8s} {'W3':>8s} {'W4':>8s}")
for h_ in range(24):
    fr = full_out[full_out['hour'] == h_]
    if fr.empty:
        continue
    full_ann = fr['mean_pct'].values[0] * HOURS_PER_YEAR
    row_vals = [full_ann]
    for wname, _, _ in WINDOWS:
        wr = regime_profiles[wname]
        sub = wr[wr['hour'] == h_]
        if sub.empty:
            row_vals.append(np.nan)
        else:
            row_vals.append(sub['mean_pct'].values[0] * HOURS_PER_YEAR)
    print(f"  {h_:>3d} " + " ".join(f"{v:>+7.2f}%" for v in row_vals))

# --- 4. Session aggregates ---
print('\n\n  === Session aggregate cumulative drift (sum of mean H1 returns within session) ===')
SESSIONS = [
    ('Asia 00-07 UTC',    range(0, 8)),
    ('Europe 08-13 UTC',  range(8, 14)),
    ('US 14-20 UTC',      range(14, 21)),
    ('Late 21-23 UTC',    range(21, 24)),
]
print(f"  {'session':<22s} {'FULL':>10s} {'W1':>10s} {'W2':>10s} {'W3':>10s} {'W4':>10s}")
for sname, hr_range in SESSIONS:
    hrs = list(hr_range)
    full_sum = full_out[full_out['hour'].isin(hrs)]['mean_pct'].sum()
    row = [full_sum]
    for wname, _, _ in WINDOWS:
        wr = regime_profiles[wname]
        row.append(wr[wr['hour'].isin(hrs)]['mean_pct'].sum())
    print(f"  {sname:<22s} " + " ".join(f"{v:>+9.4f}%" for v in row))


# --- 5. Day-of-week slice (FULL period) ---
print('\n\n  === Per-hour mean (bps) by DOW (FULL 2018-2026) ===')
dow_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
piv = (h1.groupby(['hour', 'dow'])['ret_pct'].mean() * 100.0).unstack('dow')  # ret_pct->bps
piv = piv[dow_order]
print(f"  {'hr':>3s} " + " ".join(f"{d[:3]:>6s}" for d in dow_order))
for h_ in range(24):
    if h_ not in piv.index:
        continue
    row = piv.loc[h_]
    print(f"  {h_:>3d} " + " ".join(f"{row[d]:>+6.2f}" for d in dow_order))

# --- 6. DOW-level totals (mean H1 return across all 24 hours of each DOW) ---
print('\n\n  === DOW-level mean H1 return (annualized %) ===')
HOURS_PER_DAY = 24
dow_means = h1.groupby('dow')['ret_pct'].mean() * HOURS_PER_DAY * 365.0 / 7.0  # roughly per-DOW annual
print(f"  (using mean_H1_ret * 24h * (365/7 weeks of this DOW) = annualised contribution)")
for d in dow_order:
    if d in dow_means.index:
        print(f"  {d:<10s} {dow_means[d]:>+7.2f}%")

# --- 7. DOW slice of session aggregates (Asia/EU/US/Late by DOW) ---
print('\n\n  === Session-of-day x DOW (mean H1 return in bps, FULL period) ===')
print(f"  {'session':<22s} " + " ".join(f"{d[:3]:>6s}" for d in dow_order))
for sname, hr_range in SESSIONS:
    hrs = list(hr_range)
    sess_mask = h1['hour'].isin(hrs)
    sub = h1[sess_mask]
    bps_by_dow = sub.groupby('dow')['ret_pct'].mean() * 100.0
    row_str = []
    for d in dow_order:
        v = bps_by_dow.get(d, np.nan)
        row_str.append(f"{v:>+6.2f}" if pd.notna(v) else f"{'  nan':>6s}")
    print(f"  {sname:<22s} " + " ".join(row_str))

# --- 8. Phase-0 gating-criteria check ---
print('\n\n  === Phase 0 -> Phase 1 gating-criteria check ===')

# Criterion 1: W4 hour-of-day t-stat > +2 or < -2 on at least one hour
w4 = regime_profiles['W4 2024-2026']
w4_hot = w4[(w4['t'] >= 2.0) | (w4['t'] <= -2.0)].copy()
if w4_hot.empty:
    print('  [1] W4 t > |2| on any hour: NO HOT HOUR -> FAIL')
    crit1 = False
else:
    print(f'  [1] W4 t > |2| on at least 1 hour: PASS')
    print('      W4 hot hours:')
    for _, r in w4_hot.iterrows():
        print(f"        hr {int(r['hour']):>2d}  mean +{r['mean_pct']:+7.4f}%  t {r['t']:+6.2f}")
    crit1 = True

# Criterion 2 + 3 evaluated for each W4 hot hour
if crit1:
    print('\n  [2/3] For each W4 hot hour, check DOW concentration + sign consistency...')
    for _, r in w4_hot.iterrows():
        h_ = int(r['hour'])
        # DOW concentration: how much of the W4 hot-hour signal comes from
        # one weekday? sum of |mean_pct| across DOW; share of the max.
        w4_ts_s = pd.Timestamp('2024-01-01', tz='UTC')
        w4_ts_e = pd.Timestamp('2026-05-15', tz='UTC')
        w4_sub = h1[(h1['timestamp'] >= w4_ts_s) & (h1['timestamp'] <= w4_ts_e)
                     & (h1['hour'] == h_)].copy()
        dow_signal = w4_sub.groupby('dow')['ret_pct'].mean() * 100.0  # bps
        total_abs = dow_signal.abs().sum()
        if total_abs > 0:
            max_share = dow_signal.abs().max() / total_abs
        else:
            max_share = 1.0
        pass_dow = max_share < 0.70

        # Sign consistency across regimes for this hour
        signs = {}
        for wname in ['W2 2020-2021', 'W3 2022-2023', 'W4 2024-2026']:
            wr = regime_profiles[wname]
            sub2 = wr[wr['hour'] == h_]
            if not sub2.empty:
                signs[wname] = np.sign(sub2['mean_pct'].values[0])
        w4_sign = signs.get('W4 2024-2026', 0)
        n_same = sum(1 for k, v in signs.items() if k != 'W4 2024-2026' and v == w4_sign)
        pass_sign = n_same >= 1

        v1 = 'PASS' if pass_dow else 'FAIL'
        v2 = 'PASS' if pass_sign else 'FAIL'
        print(f"    hr {h_:>2d}: DOW max-share {max_share:.2f} (<0.70 {v1}); "
              f"sign-consistent W2/W3/W4 {n_same}/2 same-sign-as-W4 ({v2})")
