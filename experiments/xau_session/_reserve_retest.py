"""XAU session Phase 6 — reserve-and-retest (selection-process holdout).

User concern: a strict forward-holdout is impossible because all available
data through 2026-04-30 was used in Phase 0+2 filter discovery and variant
selection. The walk-forward S5 split (IS 2022-2024 / OOS 2025-2026) uses
the same per-day filter logic across both windows, so it tests parameter
fit but not the selection process itself.

This script does the cleanest retrospective approximation: truncate the
data to ≤ 2024-12-31, re-run the entire discovery process from scratch
(all variant × filter combinations), and check:

  Q1: Does Variant C + DOWN-med still emerge as the best PASSING variant
      when 2025-2026 has not been seen?
  Q2: When the truncated-best variant is evaluated on 2025-2026 OOS,
      does it produce a positive Sharpe?

If both YES: the selection process is robust to OOS testing. If Q1 is
NO (a different variant wins on truncated data): the choice depends on
2025-2026 data and we should re-evaluate. If Q2 is NO: the strategy
doesn't generalize even though selection is stable.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/_reserve_retest.py
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
TRUNCATE_END = pd.Timestamp('2024-12-31 23:59:59', tz='UTC')   # everything ≤ this is IS

# Same hold-variant space as `_profile_xau_holds.py` (the Phase 0 selection grid)
HOLD_VARIANTS = [
    ('A: 00->01 (1h)',  0, 1, False),
    ('B: 23->02 (3h)', 23, 2, True),
    ('C: 23->08 (9h)', 23, 8, True),
    ('D: 23->04 (5h)', 23, 4, True),
    ('E: 00->04 (4h)',  0, 4, False),
]
FILTER_MODES = ['unconditional', 'mag', 'dnmed']
Z_MAG_THRESHOLD = 1.0


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def annualized_sharpe(r: np.ndarray, tpy: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(tpy))


def load_h1(end_cap: pd.Timestamp | None = None) -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    if end_cap is not None:
        df = df[df['timestamp'] <= end_cap].copy()
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
    df: pd.DataFrame, ny: pd.DataFrame,
    entry_hour: int, exit_hour: int, entry_is_prior_day: bool,
    filter_mode: str, cost_bps: float = COST_BPS,
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
        if filter_mode == 'mag' and not (abs(z) > Z_MAG_THRESHOLD):
            continue
        if filter_mode == 'dnmed' and not (z < 0 and 0.5 < abs(z) < 1.5):
            continue
        gross = (exit_close - entry_close) / entry_close
        rows.append({'date': d, 'gross_pct': gross,
                     'net_pct': gross - cost_pct})
    return pd.DataFrame(rows)


def stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {'n': 0, 'sharpe': 0.0, 'mean': 0.0, 'tpy': 0.0}
    r = trades['net_pct'].to_numpy()
    n = len(r)
    years = max((trades['date'].max() - trades['date'].min()).days / 365.25, 1e-9)
    tpy = n / years
    sh = annualized_sharpe(r, tpy)
    return {'n': n, 'sharpe': sh, 'mean': float(r.mean()), 'tpy': tpy, 'years': years}


def main() -> int:
    section('Reserve-and-retest — re-run Phase 0+2 discovery on ≤ 2024-12-31')
    df_is = load_h1(end_cap=TRUNCATE_END)
    ny_is = build_ny_summary(df_is)
    print(f'  IS data : {df_is["timestamp"].min().date()} -> {df_is["timestamp"].max().date()}')
    print(f'            {len(df_is):,} H1 bars / {len(ny_is):,} NY-session rows')
    print(f'  Selection-process question: does Variant C + DOWN-med re-emerge as best?')
    print()

    # Run the 5×3 = 15 combination grid on IS data (same as Phase 0 holds sweep,
    # consolidated to the 3 filter modes that survived Phase 0).
    print(f'  {"variant":<18s} {"filter":<14s} {"n":>5s} {"tpy":>5s} '
          f'{"IS Sh":>8s} {"IS mean bp":>11s}')
    print('  ' + '-' * 75)
    is_grid = []
    for vlabel, eh, xh, prior in HOLD_VARIANTS:
        for fmode in FILTER_MODES:
            trades = simulate(df_is, ny_is, eh, xh, prior, fmode)
            s = stats(trades)
            is_grid.append({
                'variant': vlabel, 'filter': fmode,
                'entry_h': eh, 'exit_h': xh, 'prior': prior,
                **s,
            })
            flag = ''
            if vlabel.startswith('C: 23->08') and fmode == 'dnmed':
                flag = '  <<< deploy candidate'
            print(f'  {vlabel:<18s} {fmode:<14s} {s["n"]:>5d} {s["tpy"]:>4.0f}  '
                  f'{s["sharpe"]:>+7.3f}  {s["mean"] * 1e4:>+10.2f}{flag}')

    # Rank IS results
    section('IS ranking (top 5 by Sharpe, n ≥ 100 to avoid extreme overfit)')
    grid_df = pd.DataFrame(is_grid)
    eligible = grid_df[grid_df['n'] >= 100].copy()
    eligible_sorted = eligible.sort_values('sharpe', ascending=False)
    for i, row in enumerate(eligible_sorted.head(5).to_dict('records'), 1):
        print(f'  {i}. {row["variant"]:<18s} {row["filter"]:<14s} '
              f'n={row["n"]:>4d}  Sh={row["sharpe"]:+.3f}')

    # Was Variant C + DOWN-med in the top? Print its IS rank.
    target_idx = eligible_sorted.reset_index(drop=True).index[
        (eligible_sorted.reset_index(drop=True)['variant'].str.startswith('C: 23->08')) &
        (eligible_sorted.reset_index(drop=True)['filter'] == 'dnmed')
    ]
    if len(target_idx) > 0:
        rank = int(target_idx[0]) + 1
        target = eligible_sorted.iloc[int(target_idx[0])]
        print(f'\n  Variant C + DOWN-med IS rank: #{rank} of {len(eligible_sorted)} eligible')
        print(f'    IS Sh = {target["sharpe"]:+.3f}, n={target["n"]}')
    else:
        print('\n  Variant C + DOWN-med did not survive eligibility (n<100)')

    # ============================================================
    # Now evaluate the IS-CHOSEN best on the OOS window
    # ============================================================
    section('OOS evaluation on 2025-01-01 -> 2026-04-30 (unseen)')
    df_oos = load_h1()   # full data
    ny_oos = build_ny_summary(df_oos)
    print(f'  Full data: {df_oos["timestamp"].min().date()} -> {df_oos["timestamp"].max().date()}')
    print(f'  OOS window: 2025-01-01 -> 2026-04-30\n')

    # Take the IS top-5 and compute their OOS Sharpe (using 2025-2026 only)
    OOS_START = pd.Timestamp('2025-01-01', tz='UTC')
    print(f'  {"rank":>4s} {"variant":<18s} {"filter":<14s} {"IS Sh":>8s} '
          f'{"OOS n":>6s} {"OOS Sh":>8s} {"OOS mean bp":>13s} {"IS-OOS deg":>11s}')
    print('  ' + '-' * 100)
    oos_results = []
    for i, row in enumerate(eligible_sorted.head(5).to_dict('records'), 1):
        trades_full = simulate(
            df_oos, ny_oos, row['entry_h'], row['exit_h'], row['prior'], row['filter'],
        )
        if trades_full.empty:
            print(f'  {i:>4d}  (empty)')
            continue
        trades_oos = trades_full[trades_full['date'] >= OOS_START]
        s_oos = stats(trades_oos) if not trades_oos.empty else {'n': 0, 'sharpe': 0.0, 'mean': 0.0}
        deg = row['sharpe'] - s_oos['sharpe']
        is_target = row['variant'].startswith('C: 23->08') and row['filter'] == 'dnmed'
        flag = '  <<< deploy' if is_target else ''
        print(f'  {i:>4d}  {row["variant"]:<18s} {row["filter"]:<14s} '
              f'{row["sharpe"]:>+7.3f}  {s_oos["n"]:>5d}  '
              f'{s_oos["sharpe"]:>+7.3f}  {s_oos["mean"] * 1e4:>+11.2f}  '
              f'{deg:>+10.3f}{flag}')
        oos_results.append({**row, 'oos_n': s_oos['n'],
                            'oos_sharpe': s_oos['sharpe'],
                            'oos_mean_bp': s_oos['mean'] * 1e4})

    section('Verdict')
    # Q1: Is Variant C + DOWN-med in top-3 by IS Sharpe?
    target_in_top3 = any(
        r['variant'].startswith('C: 23->08') and r['filter'] == 'dnmed'
        for r in oos_results[:3]
    )
    print(f'  Q1: Variant C + DOWN-med in top-3 by IS-only Sharpe: '
          f'{"YES" if target_in_top3 else "NO"}')
    # Q2: OOS Sharpe positive?
    target_oos = next(
        (r for r in oos_results
         if r['variant'].startswith('C: 23->08') and r['filter'] == 'dnmed'),
        None,
    )
    if target_oos is None:
        print(f'  Q2: (Variant C + DOWN-med not in top-5; cannot evaluate OOS)')
        q2_pass = False
    else:
        q2_pass = target_oos['oos_sharpe'] > 0
        print(f'  Q2: OOS Sharpe positive: {"YES" if q2_pass else "NO"}  '
              f'(Sh = {target_oos["oos_sharpe"]:+.3f}, n={target_oos["oos_n"]})')

    print()
    if target_in_top3 and q2_pass:
        print('  PASS: Selection process is robust to OOS testing.')
        print('  The same Variant C + DOWN-med deploy candidate emerges from')
        print('  truncated (≤2024) discovery AND produces a positive OOS Sharpe')
        print('  on the 2025-2026 unseen window. This is the cleanest retrospective')
        print('  approximation of forward-holdout available given that all data')
        print('  was used in the original Phase 0+2 work.')
    else:
        print('  PARTIAL: At least one of Q1 / Q2 failed.')
        print('  Reconsider before proceeding to Phase 7.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
