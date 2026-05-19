"""XAG session Phase 0b — multi-hour hold variants with filter overlay.

Direct analog of xau_session/_profile_xau_holds.py adapted for silver.
Silver has 4-6x XAU's per-bar vol; cost model uses 8 bp default (Eightcap
raw realistic ~1.5-3 pip = 4-10 bp RT on XAG) with stress at 15 bp.

Variants tested:
  A: 00->01 (1h)   B: 23->02 (3h)   C: 23->08 (9h)   D: 23->04 (5h)   E: 00->04 (4h)

Filter modes:
  unconditional, |z|>1.0 (prior-NY magnitude), DOWN-med (analog of xau_session deploy)

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xag_session/_profile_xag_holds.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAGUSD_H1.csv')

VARIANTS = [
    ('A: 00->01 (1h)',  0, 1, False),
    ('B: 23->02 (3h)', 23, 2, True),
    ('C: 23->08 (9h)', 23, 8, True),
    ('D: 23->04 (5h)', 23, 4, True),
    ('E: 00->04 (4h)',  0, 4, False),
]

NY_START_HOUR = 13
NY_END_HOUR = 21
ATR_DAYS = 20
COSTS_BPS = (0, 5, 8, 12, 20)


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def label_regime(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2019:
        return 'W1'
    if y <= 2021:
        return 'W2'
    if y <= 2023:
        return 'W3'
    return 'W4'


def annualized_sharpe(r: np.ndarray, tpy: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(tpy))


def fmt_pct(x: float, decimals: int = 4) -> str:
    return f'{x:+.{decimals}f}%'


def load_h1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2019-01-01', tz='UTC')].copy()
    df['hour'] = df['timestamp'].dt.hour
    df['date'] = df['timestamp'].dt.normalize()
    return df


def build_ny_summary(df: pd.DataFrame) -> pd.DataFrame:
    ny_mask = (df['hour'] >= NY_START_HOUR) & (df['hour'] < NY_END_HOUR)
    ny = df[ny_mask].copy()
    ny_grp = ny.groupby('date')
    out = pd.DataFrame({
        'ny_open': ny_grp['open'].first(),
        'ny_close': ny_grp['close'].last(),
        'ny_n_bars': ny_grp.size(),
    })
    out['ny_ret_pct'] = (out['ny_close'] - out['ny_open']) / out['ny_open'] * 100.0
    out = out.sort_index()
    out['ny_atr_pct'] = (
        out['ny_ret_pct']
        .rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1)
        .shift(1)
    )
    return out


def build_variant_trades(
    df: pd.DataFrame, ny: pd.DataFrame,
    entry_hour: int, exit_hour: int, entry_is_prior_day: bool,
) -> pd.DataFrame:
    df2 = df.set_index(['date', 'hour'])
    closes = df2['close']
    trade_dates = sorted(df.loc[df['hour'] == exit_hour, 'date'].unique())
    rows = []
    one_day = pd.Timedelta(days=1)
    for d in trade_dates:
        d = pd.Timestamp(d)
        entry_date = d - one_day if entry_is_prior_day else d
        prior_date = d - one_day
        try:
            entry_close = closes.loc[(entry_date, entry_hour)]
            exit_close = closes.loc[(d, exit_hour)]
        except KeyError:
            continue
        if prior_date not in ny.index:
            continue
        ny_row = ny.loc[prior_date]
        if pd.isna(ny_row['ny_atr_pct']) or ny_row['ny_atr_pct'] == 0:
            continue
        z = ny_row['ny_ret_pct'] / ny_row['ny_atr_pct']
        ret_pct = (exit_close - entry_close) / entry_close * 100.0
        rows.append({
            'date': d, 'ret_pct': ret_pct, 'prior_ny_z': z,
            'regime': label_regime(d),
        })
    return pd.DataFrame(rows)


def report_variant(label: str, trades: pd.DataFrame, cost_bps: float = 8) -> dict:
    if trades.empty:
        print(f'  {label}: no trades')
        return {}
    cost_pct = cost_bps / 100.0   # ret_pct is in %; cost_bps -> % directly: 1 bp = 0.01%
    years = (trades['date'].max() - trades['date'].min()).days / 365.25
    n = len(trades)
    tpy = n / max(years, 1e-9)
    r = trades['ret_pct'].to_numpy() - cost_pct
    mean = r.mean()
    sh = annualized_sharpe(r, tpy)
    w4 = trades[trades['regime'] == 'W4']
    w4_mean = (w4['ret_pct'].mean() - cost_pct) if len(w4) >= 5 else np.nan
    w4_n = len(w4)
    w4_years = (w4['date'].max() - w4['date'].min()).days / 365.25 if w4_n >= 2 else 1.0
    w4_tpy = w4_n / max(w4_years, 1e-9)
    w4_r = w4['ret_pct'].to_numpy() - cost_pct
    w4_sh = annualized_sharpe(w4_r, w4_tpy) if w4_n >= 5 else np.nan
    print(f'  {label:<32s} n={n:>4d} ({tpy:>4.0f}/yr)  '
          f'gross={fmt_pct(trades["ret_pct"].mean())}  net@{cost_bps:.0f}bp={fmt_pct(mean)}  '
          f'Sh={sh:>+5.2f}  '
          f'W4(n={w4_n})={fmt_pct(w4_mean) if pd.notnull(w4_mean) else "  --"}  '
          f'Sh4={w4_sh:>+5.2f}')
    return {
        'label': label, 'n': n, 'tpy': tpy, 'mean': mean, 'sharpe': sh,
        'w4_mean': w4_mean, 'w4_n': w4_n, 'w4_sharpe': w4_sh,
    }


def main() -> int:
    df = load_h1()
    print(f'  Loaded {len(df):,} H1 bars  '
          f'{df["timestamp"].min().date()} - {df["timestamp"].max().date()}')
    ny = build_ny_summary(df)

    summary = []
    for vlabel, eh, xh, prior in VARIANTS:
        section(f'Variant {vlabel}')
        trades = build_variant_trades(df, ny, eh, xh, prior)
        if trades.empty:
            print('  (no trades built)')
            continue

        print('  --- Unconditional @ 8bp ---')
        u_stats = report_variant(f'{vlabel} unconditional', trades, cost_bps=8)
        summary.append({'variant': vlabel, 'filter': 'unc', **u_stats})

        for k in (1.0,):
            filt = trades[trades['prior_ny_z'].abs() > k]
            label = f'{vlabel} |z|>{k}'
            f_stats = report_variant(label, filt, cost_bps=8)
            summary.append({'variant': vlabel, 'filter': f'|z|>{k}', **f_stats})

        filt_down = trades[(trades['prior_ny_z'] < 0)
                           & (trades['prior_ny_z'].abs() > 0.5)
                           & (trades['prior_ny_z'].abs() < 1.5)]
        d_stats = report_variant(f'{vlabel} DOWN med', filt_down, cost_bps=8)
        summary.append({'variant': vlabel, 'filter': 'DOWN-med', **d_stats})

    section('Cost sweep on Variant C (23-08 9h hold, the deploy candidate)')
    trades_c = build_variant_trades(df, ny, 23, 8, True)
    trades_c_dm = trades_c[(trades_c['prior_ny_z'] < 0) &
                           (trades_c['prior_ny_z'].abs() > 0.5) &
                           (trades_c['prior_ny_z'].abs() < 1.5)]
    print(f'  {"filter":<14s} {"cost bp":>8s} {"Sh":>7s} {"net mean":>10s} {"W4 Sh":>7s} {"W4 net":>10s}')
    print('  ' + '-' * 65)
    for cb in COSTS_BPS:
        # Unconditional
        years = (trades_c['date'].max() - trades_c['date'].min()).days / 365.25
        tpy = len(trades_c) / max(years, 1e-9)
        r = trades_c['ret_pct'].to_numpy() - cb / 100.0
        sh = annualized_sharpe(r, tpy)
        w4 = trades_c[trades_c['regime'] == 'W4']
        wy = (w4['date'].max() - w4['date'].min()).days / 365.25 if len(w4) >= 2 else 1
        wtpy = len(w4) / max(wy, 1e-9)
        w4r = w4['ret_pct'].to_numpy() - cb / 100.0
        wsh = annualized_sharpe(w4r, wtpy)
        print(f'  {"unconditional":<14s} {cb:>7.0f}  {sh:>+6.2f}  {fmt_pct(r.mean()):>10s}  '
              f'{wsh:>+6.2f}  {fmt_pct(w4r.mean()):>10s}')

    for cb in COSTS_BPS:
        # DOWN-med
        years = (trades_c_dm['date'].max() - trades_c_dm['date'].min()).days / 365.25
        tpy = len(trades_c_dm) / max(years, 1e-9)
        r = trades_c_dm['ret_pct'].to_numpy() - cb / 100.0
        sh = annualized_sharpe(r, tpy)
        w4 = trades_c_dm[trades_c_dm['regime'] == 'W4']
        wy = (w4['date'].max() - w4['date'].min()).days / 365.25 if len(w4) >= 2 else 1
        wtpy = len(w4) / max(wy, 1e-9)
        w4r = w4['ret_pct'].to_numpy() - cb / 100.0
        wsh = annualized_sharpe(w4r, wtpy) if len(w4) >= 5 else float('nan')
        print(f'  {"DOWN-med":<14s} {cb:>7.0f}  {sh:>+6.2f}  {fmt_pct(r.mean()):>10s}  '
              f'{wsh:>+6.2f}  {fmt_pct(w4r.mean()) if len(w4)>=5 else "  --":>10s}')

    section('Summary @ 8bp realistic cost (key: which combos pass deploy bars)')
    print(f'  Bar: W4 Sh > +0.50, FULL Sh > +0.30, n >= 100')
    print(f'\n  {"variant":<18s} {"filter":<10s} {"n":>5s} {"tpy":>5s} {"Sh":>7s} {"W4 Sh":>7s} verdict')
    print('  ' + '-' * 85)
    for s in summary:
        if not s:
            continue
        deploy = (
            s.get('sharpe', 0) > 0.30 and
            pd.notnull(s.get('w4_sharpe')) and
            s.get('w4_sharpe') > 0.50 and
            s['n'] >= 100
        )
        flag = '  <<< CANDIDATE' if deploy else ''
        w4_sh_str = f'{s["w4_sharpe"]:+.2f}' if pd.notnull(s.get('w4_sharpe')) else '  --'
        print(f'  {s["variant"]:<18s} {s["filter"]:<10s} {s["n"]:>5d} {s["tpy"]:>4.0f}  '
              f'{s["sharpe"]:>+6.2f}  {w4_sh_str:>7s}{flag}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
