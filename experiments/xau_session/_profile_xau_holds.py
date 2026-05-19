"""XAU session Phase 0 — multi-hour hold variants with filter overlay.

Phase 0 follow-up to _profile_xau_filters.py. The single-hour Asia-open
hold (Variant A) produces per-trade gross ~+0.035% even with Filter A k=1.0,
which is under retail-CFD RT cost (~6 bps). Multi-hour holds amortize cost
across more drift.

Variants tested:
  A: 00:00 UTC -> 01:00 UTC (1-hour, baseline)
  B: 23:00 UTC (prev day) -> 02:00 UTC (3-hour)
  C: 23:00 UTC (prev day) -> 08:00 UTC (9-hour, London open)
  D: 23:00 UTC (prev day) -> 04:00 UTC (5-hour, mid-Asia)
  E: 00:00 UTC -> 04:00 UTC (4-hour, post-open)

Each variant tested:
  - Unconditional
  - With Filter A k=1.0 (prior-NY |zscore| > 1.0)
Both sliced by FULL and W4.

Cost sensitivity: net = gross - cost_bps; we report gross, then net at
3 / 6 / 10 bps RT.

Run with no args:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/_profile_xau_holds.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv')

# Variant definitions: (label, entry_hour, exit_hour, entry_is_prior_day)
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

# Pre-committed bars
GROSS_BAR_PCT = 0.10          # per-trade gross > +0.10%
NET_BAR_PCT_AT_6BP = 0.04     # per-trade net at 6 bps RT cost > +0.04%
TRADES_PER_YR_BAR = 50

COSTS_BPS = (0, 3, 6, 10)


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


def annualized_sharpe(r: np.ndarray, trades_per_year: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(trades_per_year))


def fmt_pct(x: float, decimals: int = 4) -> str:
    return f'{x:+.{decimals}f}%'


def load_h1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
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
    df: pd.DataFrame,
    ny: pd.DataFrame,
    entry_hour: int,
    exit_hour: int,
    entry_is_prior_day: bool,
) -> pd.DataFrame:
    """Build a one-row-per-trade table for a hold variant.

    Each Asia 'trade date' D anchors:
      - entry close from bar at hour=entry_hour, date=D or D-1
      - exit close from bar at hour=exit_hour, date=D
      - prior_NY summary keyed on D-1
    """
    # Index by (date, hour) for fast lookup
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
            'date': d,
            'ret_pct': ret_pct,
            'prior_ny_z': z,
            'regime': label_regime(d),
        })
    return pd.DataFrame(rows)


def report_variant(label: str, trades: pd.DataFrame) -> dict:
    if trades.empty:
        print(f'  {label}: no trades')
        return {}
    years = (trades['date'].max() - trades['date'].min()).days / 365.25
    n = len(trades)
    tpy = n / max(years, 1e-9)
    r = trades['ret_pct'].to_numpy()
    mean = r.mean()
    sh = annualized_sharpe(r, trades_per_year=tpy)
    w4 = trades[trades['regime'] == 'W4']
    w4_mean = w4['ret_pct'].mean() if len(w4) >= 5 else np.nan
    w4_n = len(w4)
    w4_years = (w4['date'].max() - w4['date'].min()).days / 365.25 if w4_n >= 2 else 1.0
    w4_tpy = w4_n / max(w4_years, 1e-9)
    w4_sh = annualized_sharpe(w4['ret_pct'].to_numpy(), trades_per_year=w4_tpy) if w4_n >= 5 else np.nan

    # Cost sensitivity: gross - cost_bps/100 per trade (one RT cost per trade)
    net_lines = []
    for cb in COSTS_BPS:
        net = mean - cb / 100.0
        # Pass/fail flag
        flag = ' (deploy)' if (cb == 6 and net > NET_BAR_PCT_AT_6BP) else ''
        net_lines.append(f'{cb}bp:{fmt_pct(net)}{flag}')
    print(f'  {label:<32s} n={n:>4d} ({tpy:>4.0f}/yr)  '
          f'gross={fmt_pct(mean)}  Sh={sh:>+5.2f}  '
          f'W4(n={w4_n})={fmt_pct(w4_mean) if pd.notnull(w4_mean) else "  --"}  '
          f'Sh4={w4_sh:>+5.2f}')
    print(f'      net@cost: ' + '  '.join(net_lines))
    return {
        'label': label, 'n': n, 'tpy': tpy, 'mean': mean, 'sharpe': sh,
        'w4_mean': w4_mean, 'w4_n': w4_n, 'w4_sharpe': w4_sh,
    }


def main() -> int:
    df = load_h1()
    print(f'  Loaded {len(df):,} H1 bars  {df["timestamp"].min().date()} - {df["timestamp"].max().date()}')
    ny = build_ny_summary(df)

    summary = []
    for vlabel, eh, xh, prior in VARIANTS:
        section(f'Variant {vlabel}')
        trades = build_variant_trades(df, ny, eh, xh, prior)
        if trades.empty:
            print('  (no trades built)')
            continue

        print('  --- Unconditional ---')
        u_stats = report_variant(f'{vlabel} unconditional', trades)
        summary.append({'variant': vlabel, 'filter': 'unc', **u_stats})

        for k in (1.0, 1.5):
            filt = trades[trades['prior_ny_z'].abs() > k]
            label = f'{vlabel} |z|>{k}'
            f_stats = report_variant(label, filt)
            summary.append({'variant': vlabel, 'filter': f'|z|>{k}', **f_stats})

        # Direction-conditioned filter (DOWN-priors only — the W4-best bucket from filters)
        filt_down = trades[(trades['prior_ny_z'] < 0) & (trades['prior_ny_z'].abs() > 0.5)
                           & (trades['prior_ny_z'].abs() < 1.5)]
        label_d = f'{vlabel} DOWN med'
        d_stats = report_variant(label_d, filt_down)
        summary.append({'variant': vlabel, 'filter': 'DOWN-med', **d_stats})

    section('Summary: per-trade gross vs deploy bars')
    print(f'  Bar: gross > {GROSS_BAR_PCT}% OR net at 6bp > {NET_BAR_PCT_AT_6BP}%, AND >= {TRADES_PER_YR_BAR}/yr')
    print(f'\n  {"variant":<18s} {"filter":<10s} {"n":>5s} {"tpy":>6s} {"gross":>9s} {"net@6bp":>10s} '
          f'{"Sharpe":>8s} {"W4 gross":>10s} {"W4 Sh":>8s} {"verdict"}')
    print('  ' + '-' * 110)
    candidates = []
    for s in summary:
        if not s:
            continue
        net6 = s['mean'] - 6 / 100.0
        deploy = (
            (s['mean'] > GROSS_BAR_PCT or net6 > NET_BAR_PCT_AT_6BP)
            and s['tpy'] >= TRADES_PER_YR_BAR
            and pd.notnull(s.get('w4_mean'))
            and s['w4_mean'] > 0
        )
        flag = '  <<< CANDIDATE' if deploy else ''
        if deploy:
            candidates.append(s)
        w4_str = fmt_pct(s['w4_mean']) if pd.notnull(s.get('w4_mean')) else '  --'
        w4_sh_str = f'{s["w4_sharpe"]:+.2f}' if pd.notnull(s.get('w4_sharpe')) else '  --'
        print(f'  {s["variant"]:<18s} {s["filter"]:<10s} {s["n"]:>5d} {s["tpy"]:>5.0f} '
              f'{fmt_pct(s["mean"]):>9s} {fmt_pct(net6):>10s} {s["sharpe"]:>+7.2f} '
              f'{w4_str:>10s} {w4_sh_str:>8s}{flag}')

    section('Deploy-candidate buckets')
    if not candidates:
        print('  NONE pass the (gross>0.10% OR net@6bp>0.04%) AND tpy>=50 AND W4>0 bar.')
        print('  Single-hour and multi-hour Asia-open holds are too thin at retail CFD cost.')
    else:
        for c in candidates:
            print(f'  - {c["variant"]} / {c["filter"]}: gross {fmt_pct(c["mean"])}, '
                  f'net@6bp {fmt_pct(c["mean"] - 0.06)}, Sharpe {c["sharpe"]:+.2f}, '
                  f'W4 gross {fmt_pct(c["w4_mean"])}, W4 Sharpe {c["w4_sharpe"]:+.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
