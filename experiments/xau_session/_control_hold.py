"""XAU session Phase 2 — control-hold check (W4 bullrun isolation).

User concern: W4 (2024-2026) coincides with the XAUUSD bullrun
(~$2000 to ~$4500, +125%). Variant C (Asia-open hold) shows W4 Sharpe
+0.56 unconditional / +1.23 with DOWN-med filter. How much of that is
"Asian-session structural drift" vs "broad gold-bull-market lift"?

Test: run the IDENTICAL simulator logic (same 9-hour-hold structure, same
DOWN-med filter, same per-day NY-zscore gate) but with the entry/exit
during a DIFFERENT non-Asian window:

  Variant C (deploy): 23:00 -> 08:00 UTC (9h, Asia-open + early Asia)
  Control NY        : 11:00 -> 20:00 UTC (9h, US morning + cash open)
  Control London    : 06:00 -> 15:00 UTC (9h, London open + early NY)
  Control overlap   : 02:00 -> 11:00 UTC (9h, mid-Asia, supposed weakness zone)

If W4 NY-control Sharpe is comparable to W4 Asia (+0.56 / +1.23 dnmed),
the signal is bullrun-driven across all hours.
If W4 NY-control is much lower, Asia window is session-mechanism-specific.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/_control_hold.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv')

NY_START_HOUR = 13
NY_END_HOUR = 21
ATR_DAYS = 20
COST_BPS = 2.0

# (label, entry_hour, exit_hour, entry_is_prior_day)
WINDOWS = [
    ('Variant C  (23->08, Asia overnight)', 23,  8, True),
    ('Control NY (11->20, US morning)',     11, 20, False),
    ('Control LDN(06->15, LDN open)',        6, 15, False),
    ('Control MA (02->11, mid-Asia)',        2, 11, False),
]


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


def max_drawdown(eq: np.ndarray) -> float:
    if len(eq) == 0:
        return 0.0
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min())


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
    ny = df.loc[ny_mask].copy()
    g = ny.groupby('date')
    out = pd.DataFrame({
        'ny_open': g['open'].first(),
        'ny_close': g['close'].last(),
        'ny_n_bars': g.size(),
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


def simulate(
    df: pd.DataFrame,
    ny: pd.DataFrame,
    entry_hour: int,
    exit_hour: int,
    entry_is_prior_day: bool,
    filter_mode: str = 'unconditional',
    cost_bps: float = COST_BPS,
) -> pd.DataFrame:
    closes = df.set_index(['date', 'hour'])['close']
    trade_dates = sorted(df.loc[df['hour'] == exit_hour, 'date'].unique())
    cost_pct = cost_bps / 10000.0
    one_day = pd.Timedelta(days=1)
    rows = []
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
        atr = ny_row['ny_atr_pct']
        if pd.isna(atr) or atr == 0:
            continue
        z = ny_row['ny_ret_pct'] / atr
        if filter_mode == 'mag' and not (abs(z) > 1.0):
            continue
        if filter_mode == 'dnmed' and not (z < 0 and 0.5 < abs(z) < 1.5):
            continue
        gross = (exit_close - entry_close) / entry_close
        net = gross - cost_pct
        rows.append({
            'date': d, 'gross_pct': gross, 'net_pct': net,
            'regime': label_regime(d),
        })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def report(window_label: str, filter_label: str, trades: pd.DataFrame) -> None:
    if trades.empty:
        print(f'  {window_label:<38s} {filter_label:<15s} (no trades)')
        return
    r = trades['net_pct'].to_numpy()
    eq = (1 + r).cumprod()
    n = len(r)
    years = (trades['date'].max() - trades['date'].min()).days / 365.25
    tpy = n / max(years, 1e-9)
    sh = annualized_sharpe(r, tpy)
    mdd = max_drawdown(eq)
    cagr = (float(eq[-1])) ** (1 / max(years, 1e-9)) - 1
    mean = r.mean()
    # Per-regime sharpe
    sub = trades.groupby('regime')
    regime_shs = {}
    for w in ('W1', 'W2', 'W3', 'W4'):
        if w in sub.groups:
            wr = sub.get_group(w)['net_pct'].to_numpy()
            wy = max((sub.get_group(w)['date'].max() -
                      sub.get_group(w)['date'].min()).days / 365.25, 1e-9)
            wtpy = len(wr) / wy
            regime_shs[w] = annualized_sharpe(wr, wtpy)
        else:
            regime_shs[w] = float('nan')
    print(f'  {window_label:<38s} {filter_label:<15s} n={n:>5d}  '
          f'Sh {sh:>+5.2f}  CAGR {cagr * 100:>+5.1f}%  MDD {mdd * 100:>+6.1f}%  '
          f'mean {mean * 100:>+7.4f}%  | W1 {regime_shs["W1"]:>+5.2f}  '
          f'W2 {regime_shs["W2"]:>+5.2f}  W3 {regime_shs["W3"]:>+5.2f}  '
          f'W4 {regime_shs["W4"]:>+5.2f}')


def main() -> int:
    df = load_h1()
    ny = build_ny_summary(df)
    print(f'  Loaded {len(df):,} H1 bars 2018-2026 UTC')

    for filt_label, filt_mode in [
        ('unconditional', 'unconditional'),
        ('|z|>1.0',       'mag'),
        ('DOWN-med',      'dnmed'),
    ]:
        section(f'Control-hold comparison — filter: {filt_label}  cost {COST_BPS}bp RT')
        for w_label, eh, xh, prior in WINDOWS:
            trades = simulate(df, ny, eh, xh, prior, filter_mode=filt_mode)
            report(w_label, filt_label, trades)

    section('Interpretation gate')
    print('  - If W4 Control-NY Sharpe is COMPARABLE to W4 Variant C: signal is')
    print('    W4-bullrun-driven, mechanism is generic gold-bull-lift, not')
    print('    session-specific. Phase 2 verdict needs revisiting.')
    print('  - If W4 Control-NY Sharpe is MUCH LOWER (>0.5 below Variant C):')
    print('    the Asia-overnight window has a session-specific structural edge')
    print('    that survives detrending by other 9-hour windows. Verdict stands.')
    print('  - Control-LDN / Control-MA serve as additional cross-checks: if')
    print('    they show a gradient (Asia >> LDN >> NY), session-effect confirmed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
