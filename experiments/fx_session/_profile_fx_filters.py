"""FX session Phase 0b — filter × hold-window exploration on EURUSD SHORT.

Phase 0a finding: every USD-major has a strong hour-23 UTC SHORT signal
(EURUSD t=-12.28 on 1944 obs, all 5 majors confirm with t<-3). Mechanism
hypothesis: end-of-day USD bid into NY close + T+2 FX settlement balancing.

Single-hour magnitude (+0.014%) is too thin for retail RT cost (~3 bp).
Same problem as xau_session's single-hour Asia-open hold — fixed by
filter overlay. This script applies the same approach to EURUSD SHORT:
  - 5 hold windows (1h / 2h / 3h / 6h / 10h)
  - 3 filter modes (unconditional / |z|>1.0 / DOWN-med / UP-med)
  - Per-trade gross + Sharpe + W4 amplification

Prior session = 08:00-21:00 UTC trading day BEFORE the SHORT entry at 21:00
or later. ATR normalization: rolling 20-day std of LDN+NY session returns.

Filter mechanisms:
  - Filter A — magnitude: fire only if |prior LDN+NY zscore| > k.
    Hypothesis: bigger intraday move = more positions to unwind = stronger
    end-of-day USD bid.
  - Filter B — direction: sign of prior LDN+NY move.
    UP-prior hypothesis: USD-weak day → reversal stronger.
    DOWN-prior hypothesis: USD-strong day → continuation into close.
  - Combo: prior-direction × prior-magnitude bucket.

Cost reference: Eightcap raw EURUSD ~0.1-0.5 pips RT spread = 0.5-2.5 bps RT
(plus commission ~0.7 bp = ~1.5-3 bp all-in). Use 3 bp realistic, 5 bp stress.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/fx_session/_profile_fx_filters.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
SYMBOL = os.environ.get('FX_SYMBOL', 'EURUSD')
DATA_PATH_CANDIDATES = [
    os.path.join(_ROOT, 'experiments', 'xau_session', 'cross_cache', f'{SYMBOL}_H1.csv'),
    os.path.join(_ROOT, 'ohlc_data', f'{SYMBOL}_H1.csv'),
]

# Hold windows (entry_hour, exit_hour, label). All entries on day D, exits at
# the close of exit_hour bar = (exit_hour+1):00 UTC, possibly crossing midnight.
# Per pandas bar convention: bar h has open at h:00, close at (h+1):00.
# So SHORT 21->23 means: enter at open of bar 21 (=21:00 UTC), exit at close
# of bar 23 (=00:00 UTC next day). 3-hour hold.
HOLD_WINDOWS = [
    ('1h: 23->00',     23, 23),   # enter open of 23-bar, exit close of 23-bar (1 hour)
    ('2h: 22->00',     22, 23),   # 22:00 -> 00:00 UTC
    ('3h: 21->00',     21, 23),
    ('6h: 18->00',     18, 23),
    ('10h: 14->00',    14, 23),
]

# Prior session: 08-21 UTC (LDN + NY) on the entry-day for ATR / zscore.
PRIOR_START_HOUR = 8
PRIOR_END_HOUR = 21    # exclusive — bars starting at 8..20
ATR_DAYS = 20

COST_BPS_DEFAULT = 3.0
COST_BPS_STRESS = 5.0


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


def fmt_pct(x: float, dec: int = 4) -> str:
    return f'{x:+.{dec}f}%'


def load_h1() -> pd.DataFrame:
    for path in DATA_PATH_CANDIDATES:
        if os.path.exists(path):
            df = pd.read_csv(path, parse_dates=['timestamp'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            df = df.sort_values('timestamp').reset_index(drop=True)
            df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
            df['hour'] = df['timestamp'].dt.hour
            df['date'] = df['timestamp'].dt.normalize()
            return df
    raise FileNotFoundError(f'No EURUSD_H1.csv found in {DATA_PATH_CANDIDATES}')


def build_prior_summary(df: pd.DataFrame) -> pd.DataFrame:
    """For each UTC date, compute (open of 08-bar, close of 20-bar) → LDN+NY ret."""
    mask = (df['hour'] >= PRIOR_START_HOUR) & (df['hour'] < PRIOR_END_HOUR)
    sub = df[mask].copy()
    g = sub.groupby('date')
    out = pd.DataFrame({
        'p_open': g['open'].first(),
        'p_close': g['close'].last(),
        'p_n_bars': g.size(),
    })
    out['p_ret_pct'] = (out['p_close'] - out['p_open']) / out['p_open'] * 100.0
    out = out.sort_index()
    out['p_atr_pct'] = (
        out['p_ret_pct']
        .rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1)
        .shift(1)
    )
    return out


def simulate_short(
    df: pd.DataFrame, prior: pd.DataFrame,
    entry_bar_hour: int, exit_bar_hour: int,
    filter_mode: str = 'unconditional',
    cost_bps: float = COST_BPS_DEFAULT,
) -> pd.DataFrame:
    """SHORT direction: profit when price drops between entry_open and exit_close.

    Entry price = open of bar at entry_bar_hour (= entry_bar_hour:00 UTC).
    Exit price  = close of bar at exit_bar_hour (= (exit_bar_hour+1):00 UTC).
    """
    opens = df.set_index(['date', 'hour'])['open']
    closes = df.set_index(['date', 'hour'])['close']

    # Days where exit_bar_hour bar EXISTS
    trade_dates = sorted(df.loc[df['hour'] == exit_bar_hour, 'date'].unique())
    cost_pct = cost_bps / 10000.0
    rows = []
    for d in trade_dates:
        d = pd.Timestamp(d)
        try:
            entry_open = opens.loc[(d, entry_bar_hour)]
            exit_close = closes.loc[(d, exit_bar_hour)]
        except KeyError:
            continue
        if d not in prior.index:
            continue
        atr = prior.loc[d, 'p_atr_pct']
        if pd.isna(atr) or atr == 0:
            continue
        z = prior.loc[d, 'p_ret_pct'] / atr

        if filter_mode == 'mag' and not (abs(z) > 1.0):
            continue
        if filter_mode == 'dnmed' and not (z < 0 and 0.5 < abs(z) < 1.5):
            continue
        if filter_mode == 'upmed' and not (z > 0 and 0.5 < abs(z) < 1.5):
            continue

        gross_long = (exit_close - entry_open) / entry_open
        gross_short = -gross_long
        net_short = gross_short - cost_pct
        rows.append({
            'date': d,
            'gross_pct': gross_short * 100.0,
            'net_pct': net_short * 100.0,
            'prior_z': z,
            'regime': label_regime(d),
            'dow': d.day_name(),
        })
    return pd.DataFrame(rows)


def stats_block(trades: pd.DataFrame, label: str) -> dict:
    if trades.empty:
        print(f'  {label:<40s} empty')
        return {}
    n = len(trades)
    r = trades['net_pct'].to_numpy() / 100.0   # back to fraction for sharpe math
    years = max((trades['date'].max() - trades['date'].min()).days / 365.25, 1e-9)
    tpy = n / years
    sh = annualized_sharpe(r, tpy)
    mean_bp = r.mean() * 1e4
    w4 = trades[trades['regime'] == 'W4']
    w4_mean_bp = float(w4['net_pct'].mean() * 1e2) if len(w4) >= 5 else float('nan')
    w4_sh = float('nan')
    if len(w4) >= 5:
        wy = max((w4['date'].max() - w4['date'].min()).days / 365.25, 1e-9)
        wtpy = len(w4) / wy
        w4_sh = annualized_sharpe(w4['net_pct'].to_numpy() / 100.0, wtpy)
    print(f'  {label:<40s} n={n:>4d}  tpy={tpy:>4.0f}  '
          f'Sh {sh:>+5.2f}  mean {mean_bp:>+5.1f}bp  '
          f'W4 mean {w4_mean_bp:>+5.1f}bp  W4 Sh {w4_sh:>+5.2f}')
    return {'sh': sh, 'mean_bp': mean_bp, 'n': n, 'tpy': tpy,
            'w4_mean_bp': w4_mean_bp, 'w4_sh': w4_sh}


def main() -> int:
    df = load_h1()
    print(f'  {SYMBOL} H1: {len(df):,} bars  '
          f'{df["timestamp"].min().date()} -> {df["timestamp"].max().date()}')
    prior = build_prior_summary(df)
    print(f'  Prior LDN+NY summary rows: {len(prior):,}')

    for hold_label, entry_h, exit_h in HOLD_WINDOWS:
        section(f'Hold window {hold_label}  (cost {COST_BPS_DEFAULT:.0f} bp RT)')
        print(f'  {"variant":<40s} {"n":>4s}  {"tpy":>5s}  {"Sh":>6s}  {"mean":>7s}  '
              f'{"W4 mean":>9s}  {"W4 Sh":>7s}')
        for fmode in ['unconditional', 'mag', 'dnmed', 'upmed']:
            trades = simulate_short(df, prior, entry_h, exit_h, fmode, COST_BPS_DEFAULT)
            stats_block(trades, f'{hold_label} / filter={fmode}')

    # Stress at 5bp
    section(f'Cost stress @ {COST_BPS_STRESS:.0f} bp RT on the 3-hour hold (key candidate)')
    for fmode in ['unconditional', 'mag', 'dnmed', 'upmed']:
        trades = simulate_short(df, prior, 21, 23, fmode, COST_BPS_STRESS)
        stats_block(trades, f'21->00 / {fmode}')

    # Combo grid on the 3-hour hold
    section('Combo grid (3-hour hold 21->00): direction × magnitude bucket')

    def bucket(z: float) -> str:
        if abs(z) < 0.5:
            return 'low'
        if abs(z) < 1.5:
            return 'med'
        return 'high'

    trades_all = simulate_short(df, prior, 21, 23, 'unconditional', COST_BPS_DEFAULT)
    trades_all = trades_all.copy()
    trades_all['mag_bucket'] = trades_all['prior_z'].apply(bucket)
    trades_all['sign'] = np.sign(trades_all['prior_z'])
    print(f'  {"sign":>6s} {"bucket":>7s} {"n":>5s} {"mean":>8s} {"Sh":>6s} {"W4 mean":>9s} {"W4 n":>5s}')
    print('  ' + '-' * 70)
    for sgn, slabel in ((+1, '+'), (-1, '-')):
        for b in ('low', 'med', 'high'):
            sub = trades_all[(trades_all['sign'] == sgn) & (trades_all['mag_bucket'] == b)]
            n = len(sub)
            if n < 5:
                print(f'  {slabel:>6s} {b:>7s} {n:>5d}  (sparse)')
                continue
            years = max((sub['date'].max() - sub['date'].min()).days / 365.25, 1e-9)
            tpy = n / years
            r = sub['net_pct'].to_numpy() / 100.0
            sh = annualized_sharpe(r, tpy)
            w4 = sub[sub['regime'] == 'W4']
            w4_mean_bp = float(w4['net_pct'].mean() * 1e2) if len(w4) >= 5 else float('nan')
            w4_n = len(w4)
            print(f'  {slabel:>6s} {b:>7s} {n:>5d} {r.mean() * 1e4:>+7.1f}bp '
                  f'{sh:>+5.2f} {w4_mean_bp:>+8.1f}bp {w4_n:>5d}')

    # DOW breakdown on the unconditional 3h hold
    section('Day-of-week breakdown (3-hour hold 21->00, unconditional)')
    df_dow = trades_all.copy()
    DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    print(f'  {"DOW":<10s}  {"n":>4s}  {"mean":>8s}  {"t":>6s}  {"Sh":>6s}')
    for day in DAYS:
        sub = df_dow[df_dow['dow'] == day]
        n = len(sub)
        if n < 5:
            continue
        r = sub['net_pct'].to_numpy() / 100.0
        mean_bp = r.mean() * 1e4
        std_bp = r.std(ddof=1) * 1e4
        t = mean_bp / (std_bp / np.sqrt(n)) if (std_bp and n > 1) else 0.0
        years = max((sub['date'].max() - sub['date'].min()).days / 365.25, 1e-9)
        tpy = n / years
        sh = annualized_sharpe(r, tpy)
        marker = '  <<< pos' if t > 2 else ('  <<< neg' if t < -2 else '')
        print(f'  {day:<10s}  {n:>4d}  {mean_bp:>+6.1f}bp  {t:>+5.2f}  {sh:>+5.2f}{marker}')

    section('Phase 0b verdict gate')
    print('  Look for hold × filter combos where:')
    print('    - per-trade net mean > +3bp at realistic 3bp RT cost')
    print('    - Sharpe > +0.40 at realistic cost')
    print('    - Sharpe still > 0 at 5bp stress')
    print('    - W4 mean positive (deploy-relevant regime)')
    print('    - trades/yr >= 50')
    print('  If a combo meets all five, that is the Phase 1 pre-commit candidate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
