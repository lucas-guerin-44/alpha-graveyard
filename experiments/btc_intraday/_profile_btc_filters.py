"""BTC intraday Phase 0b -- confirmation-filter exploration.

Tests four conditional filters on the hour-00-UTC Asia-open long signal:
  Filter A: prior-24h magnitude (|prior 24h return| > k * ATR20)
  Filter B: prior-NY-session direction (sign of 13-21 UTC return)
  Filter C: day-of-week slice (all 7 days; BTC trades 24/7)
  Combo A+B: 2x3 grid (sign x magnitude bucket)
Plus W4-internal-trajectory and a cost-clearing summary.

Run:
  venv/Scripts/python.exe experiments/btc_intraday/_profile_btc_filters.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M5.csv')

SIGNAL_HOUR = 0           # Asia open (00:00-01:00 UTC = 09:00 Tokyo)
NY_START_HOUR = 13        # prior-NY session window: 13-21 UTC
NY_END_HOUR = 21          # exclusive
ATR_DAYS = 20             # rolling window for prior-24h magnitude normalisation

# Cost-clearing assumption: 10 bps round-trip BTCUSD CFD spread is the
# typical retail Eightcap range. Per-trade gross must exceed this.
COST_RT_PCT = 0.10
GROSS_PER_TRADE_BAR_PCT = 0.10   # filtered per-trade gross > +0.10% (=cost-clearing)
TRADES_PER_YR_BAR = 50           # need >= 50 trades/yr after filter


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
# Load M5 -> aggregate to H1, build Asia-open table with prior-NY context
# ---------------------------------------------------------------------------

def load_h1() -> pd.DataFrame:
    m5 = pd.read_csv(M5_PATH, parse_dates=['timestamp'])
    m5['timestamp'] = pd.to_datetime(m5['timestamp'], utc=True, format='mixed')
    m5 = m5.sort_values('timestamp').reset_index(drop=True)
    m5 = m5[m5['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()

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
    h1['hour'] = h1['timestamp'].dt.hour
    h1['date'] = h1['timestamp'].dt.normalize()
    h1['dow'] = h1['timestamp'].dt.day_name()
    return h1


def build_asia_with_prior_ny(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # H1 return is close-to-close on consecutive bars; drop gap-bars
    df['ret_pct'] = df['close'].pct_change() * 100.0
    df['gap_h'] = df['timestamp'].diff().dt.total_seconds() / 3600.0
    df.loc[df['gap_h'] > 1.5, 'ret_pct'] = np.nan

    # Prior-day NY session return (13-21 UTC window)
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
    ny_summary = ny_summary.sort_index()
    ny_summary['ny_atr_pct'] = (
        ny_summary['ny_ret_pct'].rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1).shift(1)
    )

    # Prior-24h-return as a second magnitude proxy (alternative to NY-only)
    # Use the close 24 H1 bars before the Asia bar as the reference
    df_close = df.set_index('timestamp')['close'].sort_index()

    asia = df[df['hour'] == SIGNAL_HOUR].copy()
    asia = asia.dropna(subset=['ret_pct'])
    asia['asia_date'] = asia['date']
    asia['prior_date'] = asia['date'] - pd.Timedelta(days=1)

    # Merge prior-day NY session summary
    asia = asia.merge(
        ny_summary.reset_index().rename(columns={'date': 'prior_date'}),
        on='prior_date', how='left',
    )
    asia['prior_ny_ret_pct'] = asia['ny_ret_pct']
    asia['prior_ny_atr_pct'] = asia['ny_atr_pct']
    asia['prior_ny_zscore'] = asia['prior_ny_ret_pct'] / asia['prior_ny_atr_pct']
    asia['prior_ny_sign'] = np.sign(asia['prior_ny_ret_pct'])

    # Compute prior 24h return: close at (asia_ts - 24h) -> close at (asia_ts - 1h)
    # i.e. the close just BEFORE the Asia entry bar opens.
    prior_24h_ret = []
    for ts_pd in asia['timestamp'].to_list():
        try:
            c_now = df_close.asof(ts_pd - pd.Timedelta(hours=1))
            c_24h = df_close.asof(ts_pd - pd.Timedelta(hours=25))
            if pd.isna(c_now) or pd.isna(c_24h) or c_24h == 0:
                prior_24h_ret.append(np.nan)
            else:
                prior_24h_ret.append((c_now - c_24h) / c_24h * 100.0)
        except (KeyError, TypeError):
            prior_24h_ret.append(np.nan)
    asia['prior_24h_ret_pct'] = prior_24h_ret

    # ATR-style normaliser for prior-24h return: rolling std of prior_24h_ret_pct
    # across the last ATR_DAYS observations
    asia = asia.sort_values('timestamp').reset_index(drop=True)
    asia['prior_24h_atr_pct'] = (
        asia['prior_24h_ret_pct'].rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1).shift(1)
    )
    asia['prior_24h_zscore'] = asia['prior_24h_ret_pct'] / asia['prior_24h_atr_pct']
    asia['prior_24h_sign'] = np.sign(asia['prior_24h_ret_pct'])

    asia['regime'] = asia['timestamp'].apply(label_regime)
    return asia


# ---------------------------------------------------------------------------
# Filter A: prior-24h magnitude
# ---------------------------------------------------------------------------

def filter_a_magnitude(asia: pd.DataFrame) -> None:
    section('Filter A -- prior-24h magnitude (|prior 24h zscore| > k)')
    print('  Hour-00 UTC long, conditional on prior-24h move magnitude.\n')
    for k in (0.5, 1.0, 1.5, 2.0):
        sub = asia[asia['prior_24h_zscore'].abs() > k].dropna(subset=['prior_24h_zscore'])
        n = len(sub)
        if n < 10:
            print(f'  k={k:.1f}: only {n} trades — sparse')
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        net = mean - COST_RT_PCT
        flag = '  <CLEARS COST>' if net > 0 else ''
        print(f'  k={k:.1f}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(mean / 100)}, '
              f'std={fmt_pct(std / 100, decimals=3)}, Sh={sh:+.2f}, net={fmt_pct(net / 100)}{flag}')
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            if len(wsub) < 5:
                continue
            print(f'         {w}: n={len(wsub):>3d}, mean={fmt_pct(wsub["ret_pct"].mean() / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter A2: prior-NY magnitude
# ---------------------------------------------------------------------------

def filter_a2_ny_magnitude(asia: pd.DataFrame) -> None:
    section('Filter A2 -- prior-NY magnitude (|prior NY zscore| > k)')
    print('  Hour-00 UTC long, conditional on prior NY-session (13-21 UTC) magnitude.\n')
    for k in (0.5, 1.0, 1.5, 2.0):
        sub = asia[asia['prior_ny_zscore'].abs() > k].dropna(subset=['prior_ny_zscore'])
        n = len(sub)
        if n < 10:
            print(f'  k={k:.1f}: only {n} trades — sparse')
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        net = mean - COST_RT_PCT
        flag = '  <CLEARS COST>' if net > 0 else ''
        print(f'  k={k:.1f}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(mean / 100)}, '
              f'std={fmt_pct(std / 100, decimals=3)}, Sh={sh:+.2f}, net={fmt_pct(net / 100)}{flag}')
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            if len(wsub) < 5:
                continue
            print(f'         {w}: n={len(wsub):>3d}, mean={fmt_pct(wsub["ret_pct"].mean() / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter B: prior-NY direction
# ---------------------------------------------------------------------------

def filter_b_direction(asia: pd.DataFrame) -> None:
    section('Filter B -- prior-NY direction (sign of prior NY 13-21 UTC move)')
    for sgn, lbl in ((+1, 'PRIOR NY UP'), (-1, 'PRIOR NY DOWN')):
        sub = asia[asia['prior_ny_sign'] == sgn].dropna(subset=['prior_ny_sign'])
        n = len(sub)
        if n < 10:
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        mean = sub['ret_pct'].mean()
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        net = mean - COST_RT_PCT
        flag = '  <CLEARS COST>' if net > 0 else ''
        print(f'  {lbl}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(mean / 100)}, '
              f'Sh={sh:+.2f}, net={fmt_pct(net / 100)}{flag}')
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            if len(wsub) < 5:
                continue
            print(f'         {w}: n={len(wsub):>3d}, mean={fmt_pct(wsub["ret_pct"].mean() / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter B2: prior-24h direction
# ---------------------------------------------------------------------------

def filter_b2_24h_direction(asia: pd.DataFrame) -> None:
    section('Filter B2 -- prior-24h direction (sign of last 24h return)')
    for sgn, lbl in ((+1, 'PRIOR 24H UP'), (-1, 'PRIOR 24H DOWN')):
        sub = asia[asia['prior_24h_sign'] == sgn].dropna(subset=['prior_24h_sign'])
        n = len(sub)
        if n < 10:
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        mean = sub['ret_pct'].mean()
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        net = mean - COST_RT_PCT
        flag = '  <CLEARS COST>' if net > 0 else ''
        print(f'  {lbl}: trades={n} ({tpy:.0f}/yr), mean={fmt_pct(mean / 100)}, '
              f'Sh={sh:+.2f}, net={fmt_pct(net / 100)}{flag}')
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            if len(wsub) < 5:
                continue
            print(f'         {w}: n={len(wsub):>3d}, mean={fmt_pct(wsub["ret_pct"].mean() / 100)}')
        print()


# ---------------------------------------------------------------------------
# Filter C: day-of-week
# ---------------------------------------------------------------------------

def filter_c_dow(asia: pd.DataFrame) -> None:
    section('Filter C -- day-of-week slice of Asia-open hour')
    DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    print('  Asia-open H1 hour-00 UTC return, grouped by weekday of the Asia bar.\n')
    for day in DAY_ORDER:
        sub = asia[asia['dow'] == day]
        n = len(sub)
        if n < 5:
            continue
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if se and np.isfinite(se) else 0.0
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=52.0)
        marker = ''
        if t >= 2.0:
            marker = '  <<< pos'
        elif t <= -2.0:
            marker = '  <<< neg'
        net = mean - COST_RT_PCT
        flag = '  <CLEARS COST>' if net > 0 else ''
        print(f'  {day:<10s}: n={n:>4d}, mean={fmt_pct(mean / 100)}, '
              f't={t:>+5.2f}, Sh={sh:+.2f}, net={fmt_pct(net / 100)}{marker}{flag}')

    print('\n  Per-regime mean by DOW (H1 mean %):')
    rows = []
    for day in DAY_ORDER:
        for w in ('W1', 'W2', 'W3', 'W4'):
            sub = asia[(asia['dow'] == day) & (asia['regime'] == w)]
            n = len(sub)
            if n < 5:
                rows.append({'dow': day, 'regime': w, 'mean': np.nan})
            else:
                rows.append({
                    'dow': day, 'regime': w,
                    'mean': sub['ret_pct'].mean(),
                })
    grid = pd.DataFrame(rows)
    pivot = grid.pivot(index='dow', columns='regime', values='mean')
    print(pivot.reindex(DAY_ORDER).to_string(
        float_format=lambda x: f'{x:+.4f}%' if pd.notnull(x) else '    --'))


# ---------------------------------------------------------------------------
# Combo A+B grid
# ---------------------------------------------------------------------------

def combo_ab(asia: pd.DataFrame) -> None:
    section('Combo A+B -- prior-NY magnitude bucket x direction grid')
    print('  Bucket prior-NY zscore into {abs<0.5, 0.5-1.5, >1.5} x sign {+, -}.\n')

    def bucket(z: float) -> str:
        if abs(z) < 0.5:
            return 'low'
        if abs(z) < 1.5:
            return 'med'
        return 'high'

    asia = asia.copy().dropna(subset=['prior_ny_zscore'])
    asia['mag_bucket'] = asia['prior_ny_zscore'].apply(bucket)
    print(f'  {"sign":>5s} {"bucket":>7s} {"n":>5s} {"mean":>10s} {"Sh":>7s} '
          f'{"W4 mean":>10s} {"W4 n":>5s} {"net":>10s}')
    print('  ' + '-' * 75)
    for sgn, slabel in ((+1, '+'), (-1, '-')):
        for b in ('low', 'med', 'high'):
            sub = asia[(asia['prior_ny_sign'] == sgn) & (asia['mag_bucket'] == b)]
            n = len(sub)
            if n < 5:
                print(f'  {slabel:>5s} {b:>7s} {n:>5d}  (sparse)')
                continue
            years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
            tpy = n / max(years, 1e-9)
            mean = sub['ret_pct'].mean()
            sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
            w4 = sub[sub['regime'] == 'W4']
            w4_mean = w4['ret_pct'].mean() if len(w4) >= 5 else np.nan
            w4_n = len(w4)
            net = mean - COST_RT_PCT
            flag = ' <CLEAR>' if net > 0 else ''
            print(f'  {slabel:>5s} {b:>7s} {n:>5d} {fmt_pct(mean / 100):>10s} '
                  f'{sh:>+6.2f} '
                  f'{fmt_pct(w4_mean / 100) if pd.notnull(w4_mean) else "    --":>10s} '
                  f'{w4_n:>5d} {fmt_pct(net / 100):>10s}{flag}')


# ---------------------------------------------------------------------------
# Combo A+B2 grid (prior-24h magnitude x direction)
# ---------------------------------------------------------------------------

def combo_ab_24h(asia: pd.DataFrame) -> None:
    section('Combo A+B2 -- prior-24h magnitude bucket x direction grid')
    print('  Bucket prior-24h zscore into {abs<0.5, 0.5-1.5, >1.5} x sign {+, -}.\n')

    def bucket(z: float) -> str:
        if abs(z) < 0.5:
            return 'low'
        if abs(z) < 1.5:
            return 'med'
        return 'high'

    asia = asia.copy().dropna(subset=['prior_24h_zscore'])
    asia['mag_bucket'] = asia['prior_24h_zscore'].apply(bucket)
    print(f'  {"sign":>5s} {"bucket":>7s} {"n":>5s} {"mean":>10s} {"Sh":>7s} '
          f'{"W4 mean":>10s} {"W4 n":>5s} {"net":>10s}')
    print('  ' + '-' * 75)
    for sgn, slabel in ((+1, '+'), (-1, '-')):
        for b in ('low', 'med', 'high'):
            sub = asia[(asia['prior_24h_sign'] == sgn) & (asia['mag_bucket'] == b)]
            n = len(sub)
            if n < 5:
                print(f'  {slabel:>5s} {b:>7s} {n:>5d}  (sparse)')
                continue
            years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
            tpy = n / max(years, 1e-9)
            mean = sub['ret_pct'].mean()
            sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
            w4 = sub[sub['regime'] == 'W4']
            w4_mean = w4['ret_pct'].mean() if len(w4) >= 5 else np.nan
            w4_n = len(w4)
            net = mean - COST_RT_PCT
            flag = ' <CLEAR>' if net > 0 else ''
            print(f'  {slabel:>5s} {b:>7s} {n:>5d} {fmt_pct(mean / 100):>10s} '
                  f'{sh:>+6.2f} '
                  f'{fmt_pct(w4_mean / 100) if pd.notnull(w4_mean) else "    --":>10s} '
                  f'{w4_n:>5d} {fmt_pct(net / 100):>10s}{flag}')


# ---------------------------------------------------------------------------
# Hold-window sweep: how does Sharpe change if we hold 1, 2, 3, 5, 7 hours?
# ---------------------------------------------------------------------------

def hold_window_sweep(h1: pd.DataFrame) -> None:
    section('Hold-window sweep -- entry at 00:00 UTC, exit at 00:00 + N hours')
    print('  Sums log-returns over the next N H1 bars after the 00:00 UTC entry.\n')
    h1 = h1.copy().sort_values('timestamp').reset_index(drop=True)
    h1['ret_pct'] = h1['close'].pct_change() * 100.0
    h1['gap_h'] = h1['timestamp'].diff().dt.total_seconds() / 3600.0
    h1.loc[h1['gap_h'] > 1.5, 'ret_pct'] = np.nan

    # Rebuild close series for lookup
    close_series = h1.set_index('timestamp')['close'].sort_index()

    entries = h1[h1['hour'] == SIGNAL_HOUR].copy()
    print(f'  {"hold":>5s} {"n":>5s} {"mean":>10s} {"std":>9s} {"Sh":>7s} '
          f'{"W4 mean":>10s} {"net":>10s}')
    print('  ' + '-' * 75)
    for hold in (1, 2, 3, 5, 7, 9, 12):
        trade_rets = []
        regimes = []
        for _, r in entries.iterrows():
            entry_ts = r['timestamp']
            exit_ts = entry_ts + pd.Timedelta(hours=hold)
            try:
                p_in = close_series.asof(entry_ts - pd.Timedelta(hours=1))
                p_out = close_series.asof(exit_ts - pd.Timedelta(hours=1))
                if pd.isna(p_in) or pd.isna(p_out) or p_in == 0:
                    continue
                trade_rets.append((p_out - p_in) / p_in * 100.0)
                regimes.append(label_regime(entry_ts))
            except Exception:
                continue
        trade_rets = np.array(trade_rets)
        regimes = np.array(regimes)
        if len(trade_rets) < 10:
            continue
        mean = trade_rets.mean()
        std = trade_rets.std(ddof=1)
        sh = mean / std * np.sqrt(365.25) if std > 0 else 0.0  # daily-cadence
        w4_mask = regimes == 'W4'
        w4_mean = trade_rets[w4_mask].mean() if w4_mask.sum() >= 5 else np.nan
        net = mean - COST_RT_PCT
        flag = ' <CLEAR>' if net > 0 else ''
        print(f'  {hold:>3d}h  {len(trade_rets):>5d} {fmt_pct(mean / 100):>10s} '
              f'{fmt_pct(std / 100, decimals=3):>9s} {sh:>+6.2f} '
              f'{fmt_pct(w4_mean / 100) if pd.notnull(w4_mean) else "    --":>10s} '
              f'{fmt_pct(net / 100):>10s}{flag}')


# ---------------------------------------------------------------------------
# W4 internal trajectory
# ---------------------------------------------------------------------------

def w4_trajectory(asia: pd.DataFrame) -> None:
    section('W4 internal trajectory -- quarterly Sharpe within 2024-2026')
    w4 = asia[asia['regime'] == 'W4'].copy().sort_values('timestamp').reset_index(drop=True)
    if len(w4) < 90:
        print(f'  Only {len(w4)} W4 bars — too few')
        return
    w4['quarter'] = w4['timestamp'].dt.to_period('Q')
    print(f'  {"quarter":<10s} {"n":>4s} {"mean":>10s} {"std":>9s} {"Sh":>7s}')
    for q, sub in w4.groupby('quarter'):
        n = len(sub)
        if n < 5:
            continue
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=365.25)
        print(f'  {str(q):<10s} {n:>4d} {fmt_pct(mean / 100):>10s} '
              f'{fmt_pct(std / 100, decimals=3):>9s} {sh:>+6.2f}')

    if len(w4) >= 60:
        recent_cutoff = w4['timestamp'].max() - pd.Timedelta(days=183)
        recent = w4[w4['timestamp'] > recent_cutoff]
        recent_mean = recent['ret_pct'].mean()
        full_mean = w4['ret_pct'].mean()
        ratio = recent_mean / full_mean if full_mean != 0 else np.nan
        print(f'\n  Recent 6 months mean: {fmt_pct(recent_mean / 100)}  (n={len(recent)})')
        print(f'  Full W4 mean        : {fmt_pct(full_mean / 100)}  (n={len(w4)})')
        print(f'  Ratio recent/full   : {ratio:.2f}')
        if not np.isnan(ratio):
            if ratio < 0.5:
                print('  -> PEAKING (recent < 50% of W4 average).')
            elif ratio < 1.0:
                print('  -> STABLE-DECAYING (mechanism intact, lower-conviction).')
            elif ratio < 1.5:
                print('  -> STABLE.')
            else:
                print('  -> STILL BUILDING.')


# ---------------------------------------------------------------------------
# Best combo: DOW gate {Tue/Thu/Fri} x magnitude gate
# ---------------------------------------------------------------------------

def best_combo(asia: pd.DataFrame) -> None:
    section('Best combo -- DOW in {Tue,Thu,Fri} x prior-24h |z| > k')
    print('  The strongest DOWs (Filter C: Tue +2.46, Thu +2.26, Fri +2.81) plus\n'
          '  a magnitude gate. This is the natural "Phase 1 candidate" filter.\n')
    gate_dows = {'Tuesday', 'Thursday', 'Friday'}
    base = asia[asia['dow'].isin(gate_dows)].copy().dropna(subset=['prior_24h_zscore'])
    print(f'  Universe after DOW gate: {len(base)} trades')
    print(f'  {"k":>5s} {"n":>5s} {"tpy":>5s} {"mean":>10s} {"Sh":>6s} '
          f'{"W4 mean":>10s} {"W4 n":>5s} {"net":>10s}')
    print('  ' + '-' * 75)
    for k in (0.0, 0.5, 1.0, 1.5, 2.0):
        sub = base[base['prior_24h_zscore'].abs() > k]
        n = len(sub)
        if n < 10:
            continue
        years = (sub['timestamp'].max() - sub['timestamp'].min()).days / 365.25
        tpy = n / max(years, 1e-9)
        mean = sub['ret_pct'].mean()
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=tpy)
        w4 = sub[sub['regime'] == 'W4']
        w4_mean = w4['ret_pct'].mean() if len(w4) >= 5 else np.nan
        net = mean - COST_RT_PCT
        flag = ' <CLEAR>' if net > 0 else ''
        print(f'  {k:>4.1f}  {n:>5d} {tpy:>5.0f} {fmt_pct(mean / 100):>10s} '
              f'{sh:>+5.2f} '
              f'{fmt_pct(w4_mean / 100) if pd.notnull(w4_mean) else "    --":>10s} '
              f'{len(w4):>5d} {fmt_pct(net / 100):>10s}{flag}')
        # Per-regime breakdown for the W3 sign check
        regime_means = {}
        for w in ('W1', 'W2', 'W3', 'W4'):
            wsub = sub[sub['regime'] == w]
            regime_means[w] = wsub['ret_pct'].mean() if len(wsub) >= 5 else np.nan
        rs = ' '.join(f'{w}={fmt_pct(regime_means[w] / 100, decimals=3)}'
                      if pd.notnull(regime_means[w]) else f'{w}=  --'
                      for w in ('W1', 'W2', 'W3', 'W4'))
        print(f'         {rs}')


# ---------------------------------------------------------------------------
# W4-recent floor check: is the mechanism alive in 2025-2026, or arbed?
# ---------------------------------------------------------------------------

def w4_recent_floor_check(asia: pd.DataFrame) -> None:
    section('W4-recent floor check -- is the mechanism alive in 2025+ vs 2024?')
    print('  Splits W4 into 2024 (year 1 of W4) vs 2025-2026 (year 2-3).\n'
          '  If 2025+ slice is near zero or negative, the institutionalization\n'
          '  activation has been arbed away; the full-W4 mean is paid for by\n'
          '  the 2024 strong quarters, not forward-looking.\n')
    w4 = asia[asia['regime'] == 'W4'].copy()
    cut_2025 = pd.Timestamp('2025-01-01', tz='UTC')
    y2024 = w4[w4['timestamp'] < cut_2025]
    y2526 = w4[w4['timestamp'] >= cut_2025]

    for label, sub in (('2024 only', y2024), ('2025-2026 only', y2526), ('FULL W4', w4)):
        n = len(sub)
        if n < 5:
            continue
        mean = sub['ret_pct'].mean()
        std = sub['ret_pct'].std(ddof=1)
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=365.25)
        net = mean - COST_RT_PCT
        flag = ' <CLEAR>' if net > 0 else ''
        print(f'  {label:<15s}: n={n:>4d}, mean={fmt_pct(mean / 100)}, '
              f'std={fmt_pct(std / 100, decimals=3)}, Sh={sh:+.2f}, '
              f'net={fmt_pct(net / 100)}{flag}')

    # Same split but with the strongest filter (prior-24h |z|>1.0 + DOW in {Tue,Thu,Fri})
    print('\n  With Phase-0b best filter (DOW in {Tue,Thu,Fri} AND |prior-24h z| > 1.0):')
    asia_f = asia[
        asia['dow'].isin({'Tuesday', 'Thursday', 'Friday'})
        & (asia['prior_24h_zscore'].abs() > 1.0)
    ].copy()
    for label, ts_filter in (('2024 only', y2024.index.intersection(asia_f.index)),
                              ('2025-2026 only', y2526.index.intersection(asia_f.index)),
                              ('FULL W4', w4.index.intersection(asia_f.index))):
        sub = asia_f.loc[ts_filter]
        n = len(sub)
        if n < 5:
            continue
        mean = sub['ret_pct'].mean()
        sh = annualized_sharpe(sub['ret_pct'].to_numpy(), trades_per_year=180.0)
        net = mean - COST_RT_PCT
        flag = ' <CLEAR>' if net > 0 else ''
        print(f'  {label:<15s}: n={n:>4d}, mean={fmt_pct(mean / 100)}, '
              f'Sh={sh:+.2f}, net={fmt_pct(net / 100)}{flag}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    h1 = load_h1()
    print(f'  Loaded {len(h1):,} H1 bars (M5-aggregated)  '
          f'{h1["timestamp"].min().date()} -> {h1["timestamp"].max().date()}')

    asia = build_asia_with_prior_ny(h1)
    print(f'  Asia-open hour-00 rows with prior-NY + prior-24h coverage: {len(asia):,}')
    print(f'  Regime breakdown: {asia["regime"].value_counts().sort_index().to_dict()}')

    filter_a_magnitude(asia)
    filter_a2_ny_magnitude(asia)
    filter_b_direction(asia)
    filter_b2_24h_direction(asia)
    filter_c_dow(asia)
    combo_ab(asia)
    combo_ab_24h(asia)
    hold_window_sweep(h1)
    w4_trajectory(asia)
    best_combo(asia)
    w4_recent_floor_check(asia)

    section('Decision rule')
    print('  A bucket is a Phase 1 candidate if ALL of:')
    print(f'    (a) per-trade mean > {GROSS_PER_TRADE_BAR_PCT}% (clears {COST_RT_PCT}% cost RT)')
    print(f'    (b) filtered trades >= {TRADES_PER_YR_BAR}/yr')
    print('    (c) W3 AND W4 per-regime mean both positive')
    print('    (d) DOW concentration < 50% in any single weekday')
    return 0


if __name__ == '__main__':
    sys.exit(main())
