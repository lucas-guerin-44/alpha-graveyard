"""Pre-FOMC drift event-window profile on SPX500 M5 (Phase 0b).

Tests the Lucca-Moench (2015) pre-FOMC drift: in the 24h before scheduled
FOMC announcements, equity indices historically drift up. Replicate on
SPX500 M5 2018-2026 using `fomc_calendar.csv`.

Baseline window: [T_announce - 24h, T_announce - 30min] = ~23.5 hour hold.
Variants tested: 6h / 12h / 18h / 24h / 48h windows × {5/15/30/60} exit buffer.

Also includes:
- Per-regime breakdown (W1/W2/W3/W4)
- Direction-null placebo (same window on random non-FOMC Wednesdays)
- Cross-product test on NDX100 (should mirror SPX) and GER40 (should NOT
  mirror — ECB, not Fed)

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/macro_drift/_profile_fomc_drift.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
CAL_PATH = os.path.join(_HERE, 'fomc_calendar.csv')
SPX_M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'SPX500_M5.csv')
NDX_M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'NDX100_M5.csv')
GER_M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'GER40_M5.csv')

# Eightcap SPX500 RT cost assumption: ~0.5-1 pt on ~6000 = ~1-2 bp RT
COST_BPS_DEFAULT = 2.0

# Baseline window
WINDOW_HOURS = 24
EXIT_BUFFER_MIN = 30

# Variants for Phase 0f / 0g sweep
WINDOW_HOURS_SWEEP = (6, 12, 18, 24, 48)
EXIT_BUFFER_SWEEP = (5, 15, 30, 60)


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def label_regime(year: int) -> str:
    if year <= 2019:
        return 'W1'
    if year <= 2021:
        return 'W2'
    if year <= 2023:
        return 'W3'
    return 'W4'


def et_is_dst(date: pd.Timestamp) -> bool:
    """Approximate US Eastern Time DST: 2nd Sunday March -> 1st Sunday November."""
    year = date.year
    # 2nd Sunday of March
    march_first = pd.Timestamp(f'{year}-03-01')
    march_2nd_sun = march_first + pd.Timedelta(days=(6 - march_first.dayofweek) % 7 + 7)
    # 1st Sunday of November
    nov_first = pd.Timestamp(f'{year}-11-01')
    nov_1st_sun = nov_first + pd.Timedelta(days=(6 - nov_first.dayofweek) % 7)
    return march_2nd_sun <= pd.Timestamp(date.year, date.month, date.day) < nov_1st_sun


def et_to_utc(local_dt: pd.Timestamp) -> pd.Timestamp:
    """Convert a naive ET datetime to UTC."""
    offset_h = 4 if et_is_dst(local_dt) else 5
    return (local_dt + pd.Timedelta(hours=offset_h)).tz_localize('UTC')


def load_calendar() -> pd.DataFrame:
    df = pd.read_csv(CAL_PATH)
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['is_historical'] == 'yes'].copy()
    # Compute announce_time_utc per row
    rows = []
    for _, r in df.iterrows():
        h, m = map(int, r['announce_time_et'].split(':'))
        et_dt = r['date'] + pd.Timedelta(hours=h, minutes=m)
        utc_dt = et_to_utc(et_dt)
        rows.append({
            'date': r['date'],
            'year': r['date'].year,
            'regime': label_regime(r['date'].year),
            'announce_utc': utc_dt,
            'with_projections': r['with_projections'] == 'yes',
        })
    return pd.DataFrame(rows)


def load_m5(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    return df


def closest_bar_close(df: pd.DataFrame, target_utc: pd.Timestamp,
                      tolerance_min: int = 30) -> float | None:
    """Return the close of the M5 bar nearest target_utc within tolerance."""
    delta = (df['timestamp'] - target_utc).abs()
    idx = delta.idxmin()
    if delta.iloc[idx] > pd.Timedelta(minutes=tolerance_min):
        return None
    return float(df.iloc[idx]['close'])


def compute_event_returns(
    df: pd.DataFrame, cal: pd.DataFrame,
    window_hours: int = WINDOW_HOURS,
    exit_buffer_min: int = EXIT_BUFFER_MIN,
    cost_bps: float = COST_BPS_DEFAULT,
    label: str = 'SPX500',
) -> pd.DataFrame:
    """For each FOMC event, compute long pnl over [T-window, T-buffer]."""
    rows = []
    for _, ev in cal.iterrows():
        announce = ev['announce_utc']
        entry_t = announce - pd.Timedelta(hours=window_hours)
        exit_t = announce - pd.Timedelta(minutes=exit_buffer_min)
        entry_px = closest_bar_close(df, entry_t)
        exit_px = closest_bar_close(df, exit_t)
        if entry_px is None or exit_px is None:
            continue
        gross = (exit_px - entry_px) / entry_px * 100.0
        net = gross - cost_bps / 100.0
        rows.append({
            'date': ev['date'],
            'year': ev['year'],
            'regime': ev['regime'],
            'with_projections': ev['with_projections'],
            'entry_px': entry_px,
            'exit_px': exit_px,
            'gross_pct': gross,
            'net_pct': net,
        })
    return pd.DataFrame(rows)


def stats_block(label: str, trades: pd.DataFrame, cost_bps: float) -> None:
    if trades.empty:
        print(f'  {label}: no trades')
        return
    n = len(trades)
    gross = trades['gross_pct'].to_numpy()
    net = trades['net_pct'].to_numpy()
    mean_gross = gross.mean()
    mean_net = net.mean()
    std_net = net.std(ddof=1)
    se = std_net / np.sqrt(n)
    t = mean_net / se if se > 0 else 0.0
    wr = float((net > 0).mean())
    sh_per_trade = mean_net / std_net if std_net > 0 else 0.0
    sh_annual = sh_per_trade * np.sqrt(8)   # ~8 FOMC events/yr
    print(f'  {label:<32s} n={n:>3d}  gross_mean={mean_gross:>+6.3f}%  '
          f'net_mean={mean_net:>+6.3f}%  std={std_net:>5.3f}%  t={t:>+5.2f}  '
          f'WR={wr * 100:>4.1f}%  Sh(ann)={sh_annual:>+5.2f}')


def regime_table(trades: pd.DataFrame, cost_bps: float, label: str) -> None:
    print(f'  --- {label} per regime ---')
    print(f'  {"regime":<14s} {"n":>4s}  {"mean_net":>10s} {"t":>6s}  {"WR":>6s}')
    for w in ('W1', 'W2', 'W3', 'W4'):
        sub = trades[trades['regime'] == w]
        n = len(sub)
        if n < 3:
            print(f'  {w:<14s} {n:>4d}  (sparse)')
            continue
        net = sub['net_pct'].to_numpy()
        mean = net.mean()
        std = net.std(ddof=1)
        se = std / np.sqrt(n) if n > 1 else np.nan
        t = mean / se if se > 0 else 0.0
        wr = (net > 0).mean()
        marker = ''
        if w == 'W4':
            if mean > 0.05:
                marker = '  <<< deploy-bar pass'
            elif mean < 0:
                marker = '  <<< deploy-bar FAIL'
        print(f'  {w:<14s} {n:>4d}  {mean:>+9.3f}%  {t:>+5.2f}  {wr * 100:>5.1f}%{marker}')


def placebo_check(df: pd.DataFrame, cal: pd.DataFrame, cost_bps: float,
                  seed: int = 42, n_samples: int | None = None) -> None:
    """Direction null: same 24h window on random non-FOMC Wednesdays."""
    fomc_dates = set(cal['date'].dt.date)
    # Build a list of all Wednesdays in the data range that are NOT FOMC dates
    start = df['timestamp'].min().date()
    end = df['timestamp'].max().date()
    all_wed = []
    d = pd.Timestamp(start)
    while d.date() <= end:
        if d.dayofweek == 2 and d.date() not in fomc_dates:   # 2 = Wednesday
            all_wed.append(d)
        d += pd.Timedelta(days=1)
    rng = np.random.default_rng(seed)
    n = n_samples if n_samples is not None else len(cal)
    if len(all_wed) < n:
        print(f'  placebo: not enough non-FOMC Wednesdays ({len(all_wed)})')
        return
    sampled = rng.choice(len(all_wed), size=n, replace=False)
    rows = []
    for idx in sampled:
        wed = all_wed[idx]
        # Synthetic 14:00 ET on this Wednesday
        et_dt = pd.Timestamp(wed.date()) + pd.Timedelta(hours=14)
        utc_dt = et_to_utc(et_dt)
        entry_t = utc_dt - pd.Timedelta(hours=24)
        exit_t = utc_dt - pd.Timedelta(minutes=30)
        e_px = closest_bar_close(df, entry_t)
        x_px = closest_bar_close(df, exit_t)
        if e_px is None or x_px is None:
            continue
        gross = (x_px - e_px) / e_px * 100.0
        net = gross - cost_bps / 100.0
        rows.append({'date': wed, 'gross_pct': gross, 'net_pct': net,
                     'regime': label_regime(wed.year)})
    placebo = pd.DataFrame(rows)
    if placebo.empty:
        print('  placebo: no valid samples')
        return
    n_p = len(placebo)
    net = placebo['net_pct'].to_numpy()
    mean = net.mean()
    std = net.std(ddof=1)
    t = mean / (std / np.sqrt(n_p)) if std > 0 else 0
    print(f'  placebo non-FOMC Wed:  n={n_p}  mean_net={mean:>+6.3f}%  t={t:>+5.2f}  '
          f'(should be ~0 if FOMC effect is real)')


def main() -> int:
    section('Loading FOMC calendar')
    cal = load_calendar()
    print(f'  Historical FOMC events: {len(cal)}')
    print(f'  Per-regime: {cal.groupby("regime").size().to_dict()}')
    print(f'  First: {cal["date"].min().date()}, Last: {cal["date"].max().date()}')

    for sym, path in [('SPX500', SPX_M5_PATH), ('NDX100', NDX_M5_PATH), ('GER40', GER_M5_PATH)]:
        if not os.path.exists(path):
            print(f'\n  {sym}: no data file at {path}')
            continue
        section(f'{sym} — pre-FOMC event-window profile')
        df = load_m5(path)
        print(f'  loaded {len(df):,} M5 bars  {df["timestamp"].min().date()} -> {df["timestamp"].max().date()}')
        trades = compute_event_returns(df, cal, label=sym)
        if trades.empty:
            print(f'  {sym}: no events matched bars')
            continue
        print()
        stats_block(f'{sym} baseline (24h, 30min buffer, {COST_BPS_DEFAULT}bp cost)',
                    trades, COST_BPS_DEFAULT)
        print()
        regime_table(trades, COST_BPS_DEFAULT, sym)
        print()
        placebo_check(df, cal, COST_BPS_DEFAULT)

        # Window/buffer sweeps on SPX only (most-documented effect)
        if sym == 'SPX500':
            section('SPX500 — window-length sweep (buffer 30min, cost 2bp)')
            for wh in WINDOW_HOURS_SWEEP:
                sub = compute_event_returns(df, cal, window_hours=wh)
                stats_block(f'window={wh}h', sub, COST_BPS_DEFAULT)

            section('SPX500 — exit-buffer sweep (window 24h, cost 2bp)')
            for ebm in EXIT_BUFFER_SWEEP:
                sub = compute_event_returns(df, cal, exit_buffer_min=ebm)
                stats_block(f'buffer={ebm}min', sub, COST_BPS_DEFAULT)

            section('SPX500 — with-projections vs without')
            sep = trades[trades['with_projections']]
            nosep = trades[~trades['with_projections']]
            stats_block(f'with SEP ({len(sep)} events, Mar/Jun/Sep/Dec)', sep, COST_BPS_DEFAULT)
            stats_block(f'no SEP  ({len(nosep)} events, other 4)', nosep, COST_BPS_DEFAULT)

    section('Phase 0b verdict gate')
    print('  Look for SPX500:')
    print('    - net_mean > +0.10% per trade at 2bp cost (clears deploy bar)')
    print('    - W4 (2024-2026) net_mean > +0.05% (post-2015 attenuation acceptable)')
    print('    - placebo non-FOMC Wed mean ~0 (FOMC effect is event-specific)')
    print('    - NDX100 same-sign and similar magnitude (cross-product robustness)')
    print('    - GER40 NOT positive on same FOMC dates (US Fed-specific, not generic risk-on)')
    print('  If all four pass, proceed to Phase 1 pre-commit.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
