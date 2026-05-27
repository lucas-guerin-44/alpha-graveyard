"""XAUUSD Asia-range level-interaction Phase 0 profile.

Discretionary thesis (user's intuition): the high and low of XAUUSD's price
range during 00:00-08:00 CET tend to act as support/resistance during the
subsequent London/NY hours, with price retesting and bouncing around them.

CET window 00-08 = UTC 23-07 (winter) or UTC 22-06 (summer / CEST). This
profile anchors to UTC 23-07 as the primary 8h range definition, and also
sweeps 6h (01-07 UTC) and 7h (00-07 UTC) for sensitivity.

NO strategy commitment yet. This Phase 0 measures:
  1. Touch frequency on real range levels vs placebo (translated) levels
  2. Post-touch forward returns at 15 / 30 / 60 / 120 / 240 min horizons
  3. Conditional splits: touch_type (high/low), touch_num (1st/2nd+),
     range_size tercile, prior-NY direction, London-open direction,
     time-since-range-close, regime window (W1-W4)
  4. Fade vs continuation winner per cell
  5. High/low symmetry (mechanism should be roughly mirror-symmetric)

If no conditional cell shows |t| >= 2 across W3 AND W4 (the post-2022
regimes), the mechanical version of the thesis is REJECTED at Phase 0.
"""
import os, sys
from collections import defaultdict
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
# experiments/xau_asia_range/_profile_asia_range.py -> repo root is two dirs up
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# ---------- config ----------
RANGE_DEFS = {
    'R8h_23-07': list(range(23, 24)) + list(range(0, 7)),   # primary (CET winter 00-08)
    'R7h_00-07': list(range(0, 7)),                          # CEST summer 02-09 / CET 01-08
    'R6h_01-07': list(range(1, 7)),                          # mid-Asia only
}
PRIMARY = 'R8h_23-07'
RANGE_END_HOUR = 7  # 07:00 UTC = London open = end of all three range defs
TRADE_END_HOUR = 21  # post-range trade window: 07-21 UTC (London + NY)
FWD_BARS = [3, 6, 12, 24, 48]  # M5 bars = 15 / 30 / 60 / 120 / 240 min

# ---------- load ----------
df = pd.read_csv(
    os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_M5.csv'),
    parse_dates=['timestamp'],
)
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)
df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
df = df.reset_index(drop=True)

df['hour'] = df['timestamp'].dt.hour
df['minute'] = df['timestamp'].dt.minute
df['date'] = df['timestamp'].dt.date

# trade_date = the UTC date during which post-range trading happens
# Hour-23 bars belong to the NEXT day's trade_date (their range is shared with tomorrow).
df['trade_date'] = df['date']
mask_evening = df['hour'] == 23
df.loc[mask_evening, 'trade_date'] = (
    df.loc[mask_evening, 'timestamp'] + pd.Timedelta(days=1)
).dt.date


def regime_of(d):
    y = d.year
    if y < 2020: return 'W1'
    if y < 2022: return 'W2'
    if y < 2024: return 'W3'
    return 'W4'


df['regime'] = df['trade_date'].apply(regime_of)

# numpy arrays for the hot loop
ts_arr = df['timestamp'].values
hour_arr = df['hour'].values.astype(np.int32)
trade_date_arr = df['trade_date'].values
high_arr = df['high'].values.astype(np.float64)
low_arr = df['low'].values.astype(np.float64)
open_arr = df['open'].values.astype(np.float64)
close_arr = df['close'].values.astype(np.float64)

day_bars = defaultdict(list)
for i in range(len(df)):
    day_bars[trade_date_arr[i]].append(i)
day_bars = {k: np.array(v, dtype=np.int64) for k, v in day_bars.items()}

print(f"\nLoaded {len(df):,} M5 bars, {len(day_bars):,} candidate trade-dates")
print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")


# ---------- per-day touch extraction ----------

def extract_touches(range_hours_set, label):
    """Walk every trade_date, build {range_high, range_low} from range bars,
    then scan the trade window for first-crossing touch events. Return a
    flat DataFrame of touch records.
    """
    records = []
    days_summary = []
    for d, idxs in day_bars.items():
        hours = hour_arr[idxs]
        range_mask = np.isin(hours, list(range_hours_set))
        trade_mask = (hours >= RANGE_END_HOUR) & (hours < TRADE_END_HOUR)
        range_idxs = idxs[range_mask]
        trade_idxs = idxs[trade_mask]
        if len(range_idxs) < 12 or len(trade_idxs) < 24:
            continue  # incomplete: weekend / holiday / data gap
        r_high = float(high_arr[range_idxs].max())
        r_low = float(low_arr[range_idxs].min())
        r_size = r_high - r_low
        if r_size <= 0:
            continue
        r_mid = (r_high + r_low) / 2.0
        r_size_bps = r_size / r_mid * 10000.0

        # prior-NY direction (yesterday's 13-20 UTC open-to-close)
        yesterday = (pd.Timestamp(d) - pd.Timedelta(days=1)).date()
        prior_ny_ret = np.nan
        if yesterday in day_bars:
            y_idxs = day_bars[yesterday]
            y_hours = hour_arr[y_idxs]
            ny_mask = (y_hours >= 13) & (y_hours < 21)
            ny_idxs = y_idxs[ny_mask]
            if len(ny_idxs) >= 24:
                ny_open = float(open_arr[ny_idxs[0]])
                ny_close = float(close_arr[ny_idxs[-1]])
                prior_ny_ret = (ny_close - ny_open) / ny_open * 100.0

        # London-open impulse: 07:00-07:25 UTC = first 6 M5 bars of trade window
        lon_open_ret = np.nan
        lon_first = trade_idxs[hour_arr[trade_idxs] == RANGE_END_HOUR]
        if len(lon_first) >= 6:
            l_open = float(open_arr[lon_first[0]])
            l_close = float(close_arr[lon_first[5]])
            lon_open_ret = (l_close - l_open) / l_open * 100.0

        prior_ny_sign = (
            'UP' if (np.isfinite(prior_ny_ret) and prior_ny_ret > 0)
            else 'DOWN' if (np.isfinite(prior_ny_ret) and prior_ny_ret < 0)
            else 'NA'
        )
        lon_open_sign = (
            'UP' if (np.isfinite(lon_open_ret) and lon_open_ret > 0)
            else 'DOWN' if (np.isfinite(lon_open_ret) and lon_open_ret < 0)
            else 'NA'
        )
        reg = regime_of(d)

        # ----- touch detection (vectorized) -----
        t_high = high_arr[trade_idxs]
        t_low = low_arr[trade_idxs]
        t_close = close_arr[trade_idxs]
        t_hours = hour_arr[trade_idxs]

        # Real levels
        above_high = t_high >= r_high
        below_low = t_low <= r_low

        # First-crossing only: bar B counts if at(B) and not at(B-1).
        # Treat B==0 as a touch if at(0) (gap into range extreme on London open).
        high_touch_mask = above_high.copy()
        if len(high_touch_mask) > 1:
            high_touch_mask[1:] = above_high[1:] & (~above_high[:-1])
        low_touch_mask = below_low.copy()
        if len(low_touch_mask) > 1:
            low_touch_mask[1:] = below_low[1:] & (~below_low[:-1])

        high_idxs = np.where(high_touch_mask)[0]
        low_idxs = np.where(low_touch_mask)[0]

        # Placebo levels: translate the range by +1*size (upper placebo) and -1*size (lower placebo).
        # Same width, no special meaning - tests whether the level coordinates carry info.
        plac_upper_high = r_high + r_size
        plac_upper_low = r_low + r_size
        plac_lower_high = r_high - r_size
        plac_lower_low = r_low - r_size

        for plac_high_lvl, plac_low_lvl, plac_tag in [
            (plac_upper_high, plac_upper_low, 'plac_up'),
            (plac_lower_high, plac_lower_low, 'plac_dn'),
        ]:
            ph = t_high >= plac_high_lvl
            pl = t_low <= plac_low_lvl
            phm = ph.copy()
            plm = pl.copy()
            if len(phm) > 1:
                phm[1:] = ph[1:] & (~ph[:-1])
                plm[1:] = pl[1:] & (~pl[:-1])
            for li in np.where(phm)[0]:
                rec = _make_rec(
                    d, reg, 'high', None, li, t_hours, t_close,
                    r_size_bps, prior_ny_ret, prior_ny_sign,
                    lon_open_ret, lon_open_sign, plac_tag,
                )
                records.append(rec)
            for li in np.where(plm)[0]:
                rec = _make_rec(
                    d, reg, 'low', None, li, t_hours, t_close,
                    r_size_bps, prior_ny_ret, prior_ny_sign,
                    lon_open_ret, lon_open_sign, plac_tag,
                )
                records.append(rec)

        for tnum, li in enumerate(high_idxs, start=1):
            rec = _make_rec(
                d, reg, 'high', tnum, li, t_hours, t_close,
                r_size_bps, prior_ny_ret, prior_ny_sign,
                lon_open_ret, lon_open_sign, 'real',
            )
            records.append(rec)
        for tnum, li in enumerate(low_idxs, start=1):
            rec = _make_rec(
                d, reg, 'low', tnum, li, t_hours, t_close,
                r_size_bps, prior_ny_ret, prior_ny_sign,
                lon_open_ret, lon_open_sign, 'real',
            )
            records.append(rec)

        days_summary.append({
            'trade_date': d, 'regime': reg, 'r_size_bps': r_size_bps,
            'n_high': len(high_idxs), 'n_low': len(low_idxs),
        })

    rec_df = pd.DataFrame(records)
    day_df = pd.DataFrame(days_summary)
    return rec_df, day_df


def _make_rec(d, reg, touch_type, touch_num, local_i, t_hours, t_close,
              r_size_bps, prior_ny_ret, prior_ny_sign,
              lon_open_ret, lon_open_sign, level_kind):
    entry_close = float(t_close[local_i])
    hours_after = int(t_hours[local_i] - RANGE_END_HOUR)
    rec = {
        'trade_date': d, 'regime': reg, 'touch_type': touch_type,
        'touch_num': touch_num, 'hours_after': hours_after,
        'range_size_bps': r_size_bps,
        'prior_ny_ret': prior_ny_ret, 'prior_ny_sign': prior_ny_sign,
        'lon_open_ret': lon_open_ret, 'lon_open_sign': lon_open_sign,
        'level_kind': level_kind, 'entry_close': entry_close,
    }
    for fb in FWD_BARS:
        target = local_i + fb
        if target < len(t_close):
            rec[f'fwd_{fb*5}m_bps'] = (float(t_close[target]) - entry_close) / entry_close * 10000.0
        else:
            rec[f'fwd_{fb*5}m_bps'] = np.nan
    return rec


# ---------- run primary 8h definition ----------
print(f"\n=== Primary range definition: {PRIMARY} (UTC) ===")
rec_df, day_df = extract_touches(set(RANGE_DEFS[PRIMARY]), PRIMARY)
real_df = rec_df[rec_df['level_kind'] == 'real'].copy()
plac_df = rec_df[rec_df['level_kind'].isin(['plac_up', 'plac_dn'])].copy()

print(f"\nTrading days analyzed: {len(day_df):,}")
print(f"Touch events: real={len(real_df):,}  placebo={len(plac_df):,}")
print(f"  real high-touches: {(real_df['touch_type']=='high').sum():,}")
print(f"  real  low-touches: {(real_df['touch_type']=='low').sum():,}")


# ---------- helper: t-stat table ----------
def stats_table(sub, group_col=None, label=''):
    """For each forward horizon, compute mean (bps), std, n, t. Optionally group_col."""
    horizons = [f'fwd_{fb*5}m_bps' for fb in FWD_BARS]
    if group_col is None:
        groups = [('ALL', sub)]
    else:
        groups = [(g, sub[sub[group_col] == g]) for g in sorted(sub[group_col].dropna().unique())]
    print(f"\n  -- {label} --")
    print(f"  {'group':>16s} {'n':>6s}  " + "  ".join([f"{'mean/t '+h.split('_')[1]:>14s}" for h in horizons]))
    for gname, gsub in groups:
        if len(gsub) < 5:
            continue
        n = len(gsub)
        parts = []
        for h in horizons:
            vals = gsub[h].dropna().values
            if len(vals) < 5:
                parts.append(f"{'-':>14s}")
                continue
            m = vals.mean()
            s = vals.std(ddof=1)
            t = m / (s / np.sqrt(len(vals))) if s > 0 else 0.0
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
        print(f"  {str(gname):>16s} {n:>6d}  " + "  ".join([f"{p:>14s}" for p in parts]))


def section(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------- 1. Day-level summary ----------
section("1. Range and touch-rate summary, by regime")
print(day_df.groupby('regime').agg(
    n_days=('trade_date', 'count'),
    median_size_bps=('r_size_bps', 'median'),
    p25_size=('r_size_bps', lambda x: x.quantile(0.25)),
    p75_size=('r_size_bps', lambda x: x.quantile(0.75)),
    mean_high_touch=('n_high', 'mean'),
    mean_low_touch=('n_low', 'mean'),
    pct_no_touch=('n_high', lambda x: (x == 0).mean() * 100),
).round(2))


# ---------- 2. Real-level forward returns by touch_type, all regimes ----------
section("2. REAL-LEVEL post-touch forward returns (bps), by touch_type (FULL)")
# Note: post-touch forward return measured from touch-bar close.
# Negative after high-touch = price reverted down = fade works.
# Positive after high-touch = price kept going up = continuation works.
stats_table(real_df, 'touch_type', 'FULL by touch_type')

section("3. REAL-LEVEL post-touch forward returns, by regime x touch_type")
for reg in ['W1', 'W2', 'W3', 'W4']:
    stats_table(real_df[real_df['regime'] == reg], 'touch_type', f'regime={reg}')


# ---------- 4. Placebo comparison ----------
section("4. PLACEBO-LEVEL post-touch forward returns (translated +/- 1*range)")
stats_table(plac_df, 'touch_type', 'FULL placebo by touch_type')


# ---------- 5. Touch number split ----------
section("5. REAL post-touch returns by touch_num (1=first-of-day, 2=second, etc.)")
real_df['touch_num_b'] = real_df['touch_num'].apply(
    lambda x: '1st' if x == 1 else '2nd' if x == 2 else '3rd+' if x >= 3 else 'NA'
)
for tt in ['high', 'low']:
    stats_table(
        real_df[real_df['touch_type'] == tt],
        'touch_num_b',
        f'touch_type={tt}, by touch_num',
    )


# ---------- 6. Range-size tercile split ----------
section("6. REAL post-touch returns by range_size tercile (bps RT in range)")
if len(real_df):
    qs = real_df['range_size_bps'].quantile([0.333, 0.667]).values
    def size_bucket(x):
        if x <= qs[0]: return f'S (<={qs[0]:.0f}bp)'
        if x <= qs[1]: return f'M (<={qs[1]:.0f}bp)'
        return f'L (>{qs[1]:.0f}bp)'
    real_df['size_b'] = real_df['range_size_bps'].apply(size_bucket)
    for tt in ['high', 'low']:
        stats_table(
            real_df[real_df['touch_type'] == tt],
            'size_b',
            f'touch_type={tt}, by range_size',
        )


# ---------- 7. Prior-NY direction x touch_type ----------
section("7. REAL post-touch returns by prior_NY direction x touch_type")
for tt in ['high', 'low']:
    stats_table(
        real_df[(real_df['touch_type'] == tt) & (real_df['prior_ny_sign'] != 'NA')],
        'prior_ny_sign',
        f'touch_type={tt}, by prior_NY_sign',
    )


# ---------- 8. London-open impulse direction x touch_type ----------
section("8. REAL post-touch returns by London-open impulse direction x touch_type")
for tt in ['high', 'low']:
    stats_table(
        real_df[(real_df['touch_type'] == tt) & (real_df['lon_open_sign'] != 'NA')],
        'lon_open_sign',
        f'touch_type={tt}, by London-open sign',
    )


# ---------- 9. Hours-after-range bucket ----------
section("9. REAL post-touch returns by hours-after-range (0=07-08 UTC, 13=20 UTC)")
real_df['hr_bucket'] = real_df['hours_after'].apply(
    lambda h: 'A 0-2h (Lon open)' if h < 2
    else 'B 2-6h (Lon body)' if h < 6
    else 'C 6-10h (NY morn)' if h < 10
    else 'D 10-13h (NY aft)'
)
for tt in ['high', 'low']:
    stats_table(
        real_df[real_df['touch_type'] == tt],
        'hr_bucket',
        f'touch_type={tt}, by hours_after',
    )


# ---------- 10. Combined regime filter: best W3+W4 cells ----------
section("10. W3+W4 only: best regime x split cells (search for surviving edges)")
recent = real_df[real_df['regime'].isin(['W3', 'W4'])]
print("\n  -- W3+W4 by touch_type x London-open sign x touch_num --")
for tt in ['high', 'low']:
    for lon_s in ['UP', 'DOWN']:
        for tn in ['1st', '2nd', '3rd+']:
            sub = recent[
                (recent['touch_type'] == tt)
                & (recent['lon_open_sign'] == lon_s)
                & (recent['touch_num_b'] == tn)
            ]
            if len(sub) < 30:
                continue
            for h in [60, 120, 240]:
                vals = sub[f'fwd_{h}m_bps'].dropna().values
                if len(vals) < 20:
                    continue
                m = vals.mean()
                t = m / (vals.std(ddof=1) / np.sqrt(len(vals))) if vals.std(ddof=1) > 0 else 0.0
                if abs(t) >= 1.8:
                    print(f"    {tt:>4s}-touch lon={lon_s} {tn:>4s} fwd={h:>3d}m  "
                          f"n={len(vals):>4d} mean={m:>+6.1f}bp  t={t:>+5.2f}")


# ---------- 11. Range-definition sensitivity ----------
section("11. Range-definition sensitivity (6h / 7h / 8h)")
for tag, hrs in RANGE_DEFS.items():
    if tag == PRIMARY:
        continue
    rdf, _ = extract_touches(set(hrs), tag)
    rrdf = rdf[rdf['level_kind'] == 'real']
    print(f"\n  -- {tag} --")
    stats_table(rrdf, 'touch_type', f'{tag} FULL')


# ---------- 12. Headline verdict ----------
section("12. Verdict")
print("""
Read for fade: high-touch should have NEGATIVE fwd return (price reverts down),
               low-touch should have POSITIVE fwd return.
Read for continuation/break-retest: opposite signs (high-touch +, low-touch -).
Symmetry: should be roughly mirror, otherwise asymmetric flow.
Placebo: if placebo shows same magnitude as real, level is NOT doing work.

Pass-criteria for proceeding to Phase 1:
  - FULL high-touch and low-touch at >=1 horizon show |t| >= 2 in the
    SAME mechanism direction (both fade OR both continuation).
  - W3 and W4 both confirm the sign.
  - Placebo at same horizon has |t| << real (real beats by >=2x in mean magnitude).
  - At least one conditional split produces a tradeable bucket (n >= 50/yr equiv).
""")
