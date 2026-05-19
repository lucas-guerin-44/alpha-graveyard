"""XAU session Phase 0 follow-up — confirmation-filter exploration.

Tests four conditional filters on the hour-00-UTC Asia-open long signal:
  Filter A: prior-NY-session magnitude (|prior NY move| > k * ATR20)
  Filter B: prior-NY-session direction (sign(prior NY move))
  Filter C: day-of-week slice (Mon/Tue/.../Fri/Sun)
  Combo A+B: 2x3 grid (sign x magnitude bucket)
Plus W4-internal-trajectory rolling Sharpe (is the W4 effect peaking or building).

Run with no args:
  venv/Scripts/python.exe experiments/xau_session/_profile_xau_filters.py

Output is printed to stdout; success-criteria flags highlight the most
promising filter combinations.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv')

# Asia-open signal: hour 0 UTC bar (00:00-01:00 UTC = 09:00 Tokyo/HK/SGP)
SIGNAL_HOUR = 0

# Prior NY session: previous calendar day's 13:00-21:00 UTC window.
# (NY cash typically 13:30-21:00 UTC summer / 14:30-22:00 winter — using
# the broad 13-21 window catches most of both.)
NY_START_HOUR = 13
NY_END_HOUR = 21   # inclusive of bars STARTING at 13..20

ATR_DAYS = 20      # rolling window for prior-NY magnitude normalization

# Per-trade success bar (annualized via daily-cadence sqrt(252) heuristic)
GROSS_PER_TRADE_BAR_PCT = 0.10   # filtered per-trade gross > +0.10%
TRADES_PER_YR_BAR = 50           # need >= 50 trades/yr filtered
PERSISTENT_REGIMES = ('W3', 'W4')  # filter must work post-2022, not just W2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 88}\n  {t}\n{"=" * 88}\n')


def annualized_sharpe(r: np.ndarray, trades_per_year: float = 252.0) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(trades_per_year))


def label_regime(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2019:
        return 'W1'
    if y <= 2021:
        return 'W2'
    if y <= 2023:
        return 'W3'
    return 'W4'


def fmt_pct(x: float, width: int = 7, decimals: int = 4) -> str:
    return f'{x * 100:>+{width}.{decimals}f}%'


# ---------------------------------------------------------------------------
# Load + build prior-NY-session-aware Asia-open table
# ---------------------------------------------------------------------------

def load_h1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    df['hour'] = df['timestamp'].dt.hour
    df['date'] = df['timestamp'].dt.normalize()  # UTC midnight stamp
    df['dow'] = df['timestamp'].dt.day_name()
    return df


def build_asia_with_prior_ny(df: pd.DataFrame) -> pd.DataFrame:
    """Return one row per Asia-open H1 bar with prior NY session columns."""
    # H1 returns for Asia bars
    df = df.copy()
    df['ret_pct'] = df['close'].pct_change() * 100.0

    # Aggregate NY session per UTC date: open at first bar in [13,21), close
    # at last bar in [13,21). NY-session return = (close_NY - open_NY) / open_NY
    ny_mask = (df['hour'] >= NY_START_HOUR) & (df['hour'] < NY_END_HOUR)
    ny = df[ny_mask].copy()
    ny_grp = ny.groupby('date')
    ny_summary = pd.DataFrame({
        'ny_open': ny_grp['open'].first(),
        'ny_close': ny_grp['close'].last(),
        'ny_n_bars': ny_grp.size(),
    })
    ny_summary['ny_ret_pct'] = (
        (ny_summary['ny_close'] - ny_summary['ny_open']) / ny_summary['ny_open'] * 100.0
    )
    # ATR-style normalizer: rolling std of NY returns over last ATR_DAYS sessions
    ny_summary = ny_summary.sort_index()
    ny_summary['ny_atr_pct'] = (
        ny_summary['ny_ret_pct'].rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1)
        .shift(1)  # use only PRIOR sessions in the window
    )

    # Extract Asia hour-00 bars (the trade entry)
    asia = df[df['hour'] == SIGNAL_HOUR].copy()
    asia = asia.dropna(subset=['ret_pct'])
    asia['asia_date'] = asia['date']
    asia['prior_date'] = asia['date'] - pd.Timedelta(days=1)

    # Merge prior-NY session summary onto the prior_date key
    asia = asia.merge(
        ny_summary.reset_index().rename(columns={'date': 'prior_date'}),
        on='prior_date', how='left',
    )
    asia['prior_ny_ret_pct'] = asia['ny_ret_pct']
    asia['prior_ny_atr_pct'] = asia['ny_atr_pct']
    asia['prior_ny_zscore'] = asia['prior_ny_ret_pct'] / asia['prior_ny_atr_pct']
    asia['prior_ny_sign'] = np.sign(asia['prior_ny_ret_pct'])
    asia['regime'] = asia['timestamp'].apply(label_regime)
    asia = asia.dropna(subset=['prior_ny_zscore'])
    return asia


# ---------------------------------------------------------------------------
# Filter A: prior-NY magnitude
# ---------------------------------------------------------------------------

def filter_a_magnitude(asia: pd.DataFrame) -> None:
    section('Filter A -- prior-NY magnitude (|prior NY zscore| > k)')
    print(f'  Hour-00 UTC Asia-open long return, conditional on |prior NY zscore|.')
    print(f'  k=1.0/1.5/2.0 thresholds. Reports per-regime mean and Sharpe.\n')
    for k in (1.0, 1.5, 2.0):
        mask = asia['prior_ny_zscore'].abs() > k
        sub = asia[mask]
        n = len(sub)
        if n < 10:
            print(f'  k={k}: only {n} trades — too sparse')
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        full_mean = sub['ret_pct'].mean()
        full_std = sub['ret_pct'].std(ddof=1)
        full_sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        print(f'  k={k:.1f}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(full_mean / 100)}, '
              f'std={fmt_pct(full_std / 100, decimals=3)}, Sharpe={full_sh:+.2f}')
        # Per-regime breakdown
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            wn = len(wsub)
            if wn < 5:
                continue
            wm = wsub['ret_pct'].mean()
            print(f'         {w}: n={wn:>3d}, mean={fmt_pct(wm / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter B: prior-NY direction
# ---------------------------------------------------------------------------

def filter_b_direction(asia: pd.DataFrame) -> None:
    section('Filter B -- prior-NY direction (sign of prior NY move)')
    for sgn, lbl in ((+1, 'PRIOR NY UP'), (-1, 'PRIOR NY DOWN')):
        sub = asia[asia['prior_ny_sign'] == sgn]
        n = len(sub)
        if n < 10:
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        full_mean = sub['ret_pct'].mean()
        full_sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        print(f'  {lbl}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(full_mean / 100)}, '
              f'Sharpe={full_sh:+.2f}')
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            wn = len(wsub)
            if wn < 5:
                continue
            wm = wsub['ret_pct'].mean()
            print(f'         {w}: n={wn:>3d}, mean={fmt_pct(wm / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter C: day-of-week
# ---------------------------------------------------------------------------

def filter_c_dow(asia: pd.DataFrame) -> None:
    section('Filter C -- day-of-week slice of Asia-open hour')
    DAY_ORDER = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    print('  Asia-open H1 hour-00 UTC return, grouped by weekday of the Asia bar.')
    print('  Note: XAUUSD typically pauses Sat→Sun evening; Sunday bars may be sparse.\n')
    for day in DAY_ORDER:
        sub = asia[asia['dow'] == day]
        n = len(sub)
        if n < 5:
            print(f'  {day:<10s}: n={n} (too sparse)')
            continue
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if se and np.isfinite(se) else 0.0
        marker = ''
        if t >= 2.0:
            marker = '  <<< pos'
        elif t <= -2.0:
            marker = '  <<< neg'
        print(f'  {day:<10s}: n={n:>4d}, mean={fmt_pct(mean / 100)}, t={t:>+5.2f}{marker}')

    # Per-regime DOW grid (compact)
    print('\n  Per-regime mean by DOW (annualized H1 return × 252):')
    rows = []
    for day in DAY_ORDER:
        for w in ('W1', 'W2', 'W3', 'W4'):
            sub = asia[(asia['dow'] == day) & (asia['regime'] == w)]
            n = len(sub)
            if n < 5:
                rows.append({'dow': day, 'regime': w, 'mean_ann': np.nan, 'n': n})
            else:
                rows.append({
                    'dow': day, 'regime': w,
                    'mean_ann': sub['ret_pct'].mean() * 252,
                    'n': n,
                })
    grid = pd.DataFrame(rows)
    pivot = grid.pivot(index='dow', columns='regime', values='mean_ann')
    print(pivot.reindex(DAY_ORDER).to_string(float_format=lambda x: f'{x:+.2f}%' if pd.notnull(x) else '   --'))


# ---------------------------------------------------------------------------
# Combo: A x B grid (magnitude bucket x direction)
# ---------------------------------------------------------------------------

def combo_ab(asia: pd.DataFrame) -> None:
    section('Combo A+B -- prior-NY magnitude bucket × direction grid')
    print('  Bucket prior-NY zscore into {abs < 0.5, 0.5-1.5, > 1.5} × sign {+, -}.')
    print('  Shows where the Asia-open drift is strongest.\n')

    def bucket(z: float) -> str:
        if abs(z) < 0.5:
            return 'low'
        if abs(z) < 1.5:
            return 'med'
        return 'high'

    asia = asia.copy()
    asia['mag_bucket'] = asia['prior_ny_zscore'].apply(bucket)
    print(f'  {"sign":>6s} {"bucket":>7s} {"n":>5s} {"mean":>10s} {"Sharpe":>8s} '
          f'{"W4 mean":>10s} {"W4 n":>5s}')
    print('  ' + '-' * 70)
    for sgn, slabel in ((+1, '+'), (-1, '-')):
        for b in ('low', 'med', 'high'):
            sub = asia[(asia['prior_ny_sign'] == sgn) & (asia['mag_bucket'] == b)]
            n = len(sub)
            if n < 5:
                print(f'  {slabel:>6s} {b:>7s} {n:>5d}  (sparse)')
                continue
            years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
            tpy = n / max(years, 1e-9)
            mean = sub['ret_pct'].mean()
            sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
            w4 = sub[sub['regime'] == 'W4']
            w4_mean = w4['ret_pct'].mean() if len(w4) >= 5 else np.nan
            w4_n = len(w4)
            print(f'  {slabel:>6s} {b:>7s} {n:>5d} {fmt_pct(mean / 100):>10s} '
                  f'{sh:>+7.2f} '
                  f'{fmt_pct(w4_mean / 100) if pd.notnull(w4_mean) else "    --":>10s} '
                  f'{w4_n:>5d}')


# ---------------------------------------------------------------------------
# W4-internal trajectory: is the effect peaking or still building
# ---------------------------------------------------------------------------

def w4_trajectory(asia: pd.DataFrame) -> None:
    section('W4 internal trajectory -- rolling 3-month Sharpe within 2024-2026')
    w4 = asia[asia['regime'] == 'W4'].copy().sort_values('timestamp').reset_index(drop=True)
    if len(w4) < 90:
        print(f'  Only {len(w4)} W4 bars — too few for rolling trajectory.')
        return
    # Quarter-by-quarter (or 3-month rolling) Sharpe
    w4['quarter'] = w4['timestamp'].dt.to_period('Q')
    print(f'  {"quarter":<10s} {"n":>4s} {"mean":>10s} {"std":>9s} {"Sharpe":>8s}')
    for q, sub in w4.groupby('quarter'):
        n = len(sub)
        if n < 5:
            continue
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=252)
        print(f'  {str(q):<10s} {n:>4d} {fmt_pct(mean / 100):>10s} '
              f'{fmt_pct(std / 100, decimals=3):>9s} {sh:>+7.2f}')

    # Compare recent 6 months vs W4 average
    if len(w4) >= 60:
        recent_cutoff = w4['timestamp'].max() - pd.Timedelta(days=183)
        recent = w4[w4['timestamp'] > recent_cutoff]
        full_w4 = w4
        recent_mean = recent['ret_pct'].mean()
        full_mean = full_w4['ret_pct'].mean()
        ratio = recent_mean / full_mean if full_mean != 0 else np.nan
        print(f'\n  Recent 6 months mean: {fmt_pct(recent_mean / 100)}  (n={len(recent)})')
        print(f'  Full W4 mean        : {fmt_pct(full_mean / 100)}  (n={len(full_w4)})')
        print(f'  Ratio recent / full : {ratio:.2f}')
        if not np.isnan(ratio):
            if ratio < 0.5:
                print('  → PEAKING. Pre-commit thresholds should reflect decay expectation.')
            elif ratio < 1.0:
                print('  → STABLE-DECAYING. Mechanism intact but lower-conviction.')
            elif ratio < 1.5:
                print('  → STABLE. Mechanism intact, deploy expectation matches W4 mean.')
            else:
                print('  → STILL BUILDING. Forward-looking expectation is W4-or-better.')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    df = load_h1()
    print(f'  Loaded {len(df):,} H1 bars  '
          f'{df["timestamp"].min().date()} → {df["timestamp"].max().date()}')

    asia = build_asia_with_prior_ny(df)
    print(f'  Asia-open hour-00 rows with prior-NY coverage: {len(asia):,}')
    print(f'  Regime breakdown:')
    print(asia['regime'].value_counts().sort_index().to_string())

    filter_a_magnitude(asia)
    filter_b_direction(asia)
    filter_c_dow(asia)
    combo_ab(asia)
    w4_trajectory(asia)

    section('Next steps')
    print('  Look for filter buckets where ALL of the following are true:')
    print(f'    - per-trade mean > {GROSS_PER_TRADE_BAR_PCT}%')
    print(f'    - filtered trade count ≥ {TRADES_PER_YR_BAR}/yr')
    print(f'    - W3 AND W4 per-regime mean both positive')
    print(f'    - DOW concentration < 50% in any single weekday')
    print('  If a bucket meets all four, that is the Phase 1 pre-commit candidate.')
    print('  If none do, the signal is too thin for retail-CFD deploy — tombstone xau_session.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
