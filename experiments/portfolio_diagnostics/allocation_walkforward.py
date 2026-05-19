#!/usr/bin/env python3
"""
Walk-forward validation of allocation schemes.

Train window:    2019-01-01 -> 2023-12-31  (5 years, pre-covid + covid + recovery + 2022 bear)
Holdout window:  2024-01-01 -> 2026-05-01  (28 months, completely unseen)

Both windows start at $10,000 fresh. 1R is computed from TRAIN trades only
(no look-ahead). The same 1R and the same weights are used on the holdout.

Reports per scheme:
  TRAIN Sharpe / CAGR / MDD / Calmar
  HOLDOUT Sharpe / CAGR / MDD / Calmar
  Degradation: d_Sharpe, d_Calmar (holdout - train; negative = worse OOS)

A scheme is "real" if its holdout metrics survive within sane bounds of train.
A scheme is "curve-fit" if it ranks top on train but cratered on holdout.
"""
from __future__ import annotations

import os
import sys
import importlib

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'orb'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'lunch_fade'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'xau_session'))


ACCOUNT = 10_000.0
BASE_RISK_PCT = 0.01
TRAIN_END = pd.Timestamp('2024-01-01')
HOLDOUT_END = pd.Timestamp('2026-05-01')


def section(t: str) -> None:
    print(f"\n{'=' * 116}\n  {t}\n{'=' * 116}")


# --- trade extraction -----------------------------------------------------

def trades_orb_dax() -> pd.DataFrame:
    os.environ['ORB_SYMBOL'] = 'GER40'
    os.environ['ORB_SESSION'] = 'EU'
    import orb_demo
    importlib.reload(orb_demo)
    bars = orb_demo.load_m5('GER40')
    daily_idx = pd.Index(sorted(set(bars.index.date)))
    bias = pd.Series(1, index=daily_idx, dtype=int)
    _, trades = orb_demo.simulate_orb(
        bars, or_minutes=30, entry_cutoff_min=180, tod_exit_minutes=180,
        trend_filter=bias, cost_points=1.0,
    )
    df = pd.DataFrame(trades)
    df['exit_dt'] = pd.to_datetime(df['exit_ts']).dt.tz_convert('UTC') \
        .dt.tz_localize(None).dt.normalize()
    df['strategy'] = 'orb_dax'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


def trades_lunch_fade() -> pd.DataFrame:
    os.environ['LUNCH_SYMBOL'] = 'NDX100'
    import lunch_fade_demo
    importlib.reload(lunch_fade_demo)
    bars = lunch_fade_demo.load_m5('NDX100')
    _, trades = lunch_fade_demo.simulate_lunch_fade(
        bars, morning_end_min=120, afternoon_end_min=240,
        min_move_atr=0.25, cost_points=1.0,
        direction='fade', long_only=True,
    )
    df = pd.DataFrame(trades)
    df['exit_dt'] = pd.to_datetime(df['exit_ts']).dt.tz_convert('UTC') \
        .dt.tz_localize(None).dt.normalize()
    df['strategy'] = 'lunch_fade'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


def trades_xau_session() -> pd.DataFrame:
    import xau_session_demo as xs
    df_bars = xs.load_h1()
    ny = xs.build_ny_summary(df_bars)
    _, trades = xs.simulate(
        df_bars, ny, filter_mode='dnmed', z_threshold=1.0,
        cost_bps=2.0, direction='long',
    )
    df = pd.DataFrame(trades)
    dates = pd.to_datetime(df['date'])
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)
    df['exit_dt'] = dates.dt.normalize()
    df['pnl_pct'] = df['net_pct']
    df['strategy'] = 'xau_session'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


# --- metrics & backtest --------------------------------------------------

def annual_sharpe(r: np.ndarray, bpy: int = 252) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    return 0.0 if s == 0 else float(r.mean() / s * np.sqrt(bpy))


def run_scheme(trades: pd.DataFrame, one_R: dict, weights: dict,
               start_equity: float = ACCOUNT) -> dict:
    if len(trades) == 0:
        return {'final': start_equity, 'total_ret': 0, 'cagr': 0, 'sharpe': 0,
                'mdd_pct': 0, 'mdd_dollar': 0, 'calmar': 0, 'worst_day': 0,
                'best_day': 0, 'n_trades': 0, 'days': 0}
    equity = start_equity
    rows = []
    for d, g in trades.groupby('exit_dt', sort=True):
        day_pnl = 0.0
        for _, r in g.iterrows():
            s = r['strategy']
            w = weights.get(s, 1.0)
            if w == 0:
                continue
            R = r['pnl_pct'] / one_R[s]
            day_pnl += equity * BASE_RISK_PCT * w * R
        equity += day_pnl
        rows.append({'date': d, 'pnl': day_pnl, 'equity': equity})
    pnl_df = pd.DataFrame(rows).set_index('date')
    eq = pnl_df['equity']
    daily_ret = pnl_df['pnl'] / eq.shift(1).fillna(start_equity)
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd_pct = float(dd.min())
    tot = float(eq.iloc[-1] / start_equity - 1)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (1 + tot) ** (1 / max(years, 1e-9)) - 1
    return {
        'final': float(eq.iloc[-1]),
        'total_ret': tot,
        'cagr': cagr,
        'sharpe': annual_sharpe(daily_ret.to_numpy()),
        'mdd_pct': mdd_pct,
        'mdd_dollar': float((eq - peak).min()),
        'calmar': cagr / abs(mdd_pct) if mdd_pct < 0 else float('inf'),
        'worst_day': float(pnl_df['pnl'].min()),
        'best_day': float(pnl_df['pnl'].max()),
        'n_trades': int(sum(1 for _ in trades.iterrows())),
        'days': int(len(pnl_df)),
    }


# --- main -----------------------------------------------------------------

def main() -> int:
    section('Loading trades + train/holdout split')
    all_trades = pd.concat([trades_orb_dax(), trades_lunch_fade(), trades_xau_session()],
                            ignore_index=True).sort_values('exit_dt').reset_index(drop=True)
    train = all_trades.loc[all_trades['exit_dt'] < TRAIN_END].reset_index(drop=True)
    holdout = all_trades.loc[(all_trades['exit_dt'] >= TRAIN_END)
                              & (all_trades['exit_dt'] < HOLDOUT_END)].reset_index(drop=True)
    print(f"  TRAIN  : {train['exit_dt'].min().date()} -> {train['exit_dt'].max().date()}"
          f"  ({len(train)} trades)")
    print(f"  HOLDOUT: {holdout['exit_dt'].min().date()} -> {holdout['exit_dt'].max().date()}"
          f"  ({len(holdout)} trades)")

    for w, name in [(train, 'TRAIN'), (holdout, 'HOLDOUT')]:
        print(f"\n  {name} per-strategy:")
        for s in ('orb_dax', 'lunch_fade', 'xau_session'):
            g = w[w['strategy'] == s]
            wins = (g['pnl_pct'] > 0).sum()
            print(f"    {s:12s}  n={len(g):>4d}  WR={wins/max(len(g),1)*100:.1f}%  "
                  f"avg_pnl={g['pnl_pct'].mean()*100:+.3f}%  "
                  f"std={g['pnl_pct'].std(ddof=1)*100:.3f}%")

    # 1R computed on TRAIN only
    one_R = {s: float(g['pnl_pct'].std(ddof=1))
             for s, g in train.groupby('strategy')}
    print('\n  1R (train-only, no-lookahead):')
    for s, r in one_R.items():
        print(f"    {s:12s}  1R = {r*100:.3f}%")

    # Auto-allocation schemes (computed on TRAIN per-strategy stats)
    train_solo = {}
    for s in ('orb_dax', 'lunch_fade', 'xau_session'):
        sub = train[train['strategy'] == s].reset_index(drop=True)
        train_solo[s] = run_scheme(sub, one_R,
                                    {'orb_dax': 1, 'lunch_fade': 1, 'xau_session': 1})
    print('\n  TRAIN solo Sharpe per strategy (used for auto allocation):')
    for s in ('orb_dax', 'lunch_fade', 'xau_session'):
        print(f"    {s:12s}  Sh={train_solo[s]['sharpe']:+.2f}  "
              f"MDD={train_solo[s]['mdd_pct']*100:+.1f}%")

    def normalize(d: dict) -> dict:
        m = np.mean(list(d.values()))
        return {k: v / m for k, v in d.items()}

    inv_vol = {s: 1 / one_R[s] for s in one_R}
    inv_mdd = {s: 1 / max(abs(train_solo[s]['mdd_pct']), 0.001) for s in train_solo}
    sharpe_w = {s: max(train_solo[s]['sharpe'], 0.01) for s in train_solo}

    schemes = [
        ('baseline (1,1,1)',          {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('half_orb (0.5,1,1)',        {'orb_dax': 0.5, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('conservative (0.5,1.5,1.5)',{'orb_dax': 0.5, 'lunch_fade': 1.5, 'xau_session': 1.5}),
        ('double_lf (1,2,1)',         {'orb_dax': 1.0, 'lunch_fade': 2.0, 'xau_session': 1.0}),
        ('double_xau (1,1,2)',        {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': 2.0}),
        ('double_both_off (1,2,2)',   {'orb_dax': 1.0, 'lunch_fade': 2.0, 'xau_session': 2.0}),
        ('aggressive (1.5,2,2)',      {'orb_dax': 1.5, 'lunch_fade': 2.0, 'xau_session': 2.0}),
        ('half_orb_dbl_lf (0.5,2,1)', {'orb_dax': 0.5, 'lunch_fade': 2.0, 'xau_session': 1.0}),
        ('no_orb (0,1,1)',            {'orb_dax': 0.0, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('equal_vol',                 normalize(inv_vol)),
        ('inv_mdd_weighted',          normalize(inv_mdd)),
        ('sharpe_weighted',           normalize(sharpe_w)),
    ]

    section('Walk-forward results')
    hdr = (f"  {'scheme':<28s}  {'orb':>5s} {'lf':>5s} {'xau':>5s} | "
           f"{'TRAIN Sh':>9s} {'CAGR':>7s} {'MDD%':>7s} {'Calmar':>7s} {'$end':>9s} | "
           f"{'HOLD Sh':>9s} {'CAGR':>7s} {'MDD%':>7s} {'Calmar':>7s} {'$end':>9s} | "
           f"{'dSh':>6s} {'dCalmar':>8s}")
    print(hdr)
    print('  ' + '-' * 162)

    rows = []
    for name, w in schemes:
        m_tr = run_scheme(train, one_R, w)
        m_ho = run_scheme(holdout, one_R, w)
        d_sh = m_ho['sharpe'] - m_tr['sharpe']
        d_cal = m_ho['calmar'] - m_tr['calmar']
        print(f"  {name:<28s}  {w['orb_dax']:>5.2f} {w['lunch_fade']:>5.2f} {w['xau_session']:>5.2f} | "
              f"{m_tr['sharpe']:>+9.2f} {m_tr['cagr']*100:>+6.1f}% {m_tr['mdd_pct']*100:>+6.2f}% "
              f"{m_tr['calmar']:>7.2f} ${m_tr['final']:>+8,.0f} | "
              f"{m_ho['sharpe']:>+9.2f} {m_ho['cagr']*100:>+6.1f}% {m_ho['mdd_pct']*100:>+6.2f}% "
              f"{m_ho['calmar']:>7.2f} ${m_ho['final']:>+8,.0f} | "
              f"{d_sh:>+6.2f} {d_cal:>+8.2f}")
        rows.append({'name': name, 'train': m_tr, 'holdout': m_ho, 'w': w})

    # The honest tests
    section('Honest test 1: top-3 schemes on TRAIN -- did they survive on HOLDOUT?')
    by_train_calmar = sorted(rows, key=lambda x: -x['train']['calmar'])[:3]
    for r in by_train_calmar:
        m_tr, m_ho = r['train'], r['holdout']
        delta_calmar = m_ho['calmar'] - m_tr['calmar']
        verdict = 'SURVIVED' if m_ho['calmar'] > m_tr['calmar'] * 0.5 else 'BROKE'
        print(f"  {r['name']:<28s}  train Calmar {m_tr['calmar']:.2f} -> holdout {m_ho['calmar']:.2f}  "
              f"(d {delta_calmar:+.2f})  ==> {verdict}")

    section('Honest test 2: top-3 schemes by HOLDOUT Calmar (what would have actually worked)')
    by_holdout_calmar = sorted(rows, key=lambda x: -x['holdout']['calmar'])[:3]
    for r in by_holdout_calmar:
        m_tr, m_ho = r['train'], r['holdout']
        print(f"  {r['name']:<28s}  train Calmar {m_tr['calmar']:.2f}  holdout {m_ho['calmar']:.2f}  "
              f"(train rank by Calmar = "
              f"{sorted(rows, key=lambda x: -x['train']['calmar']).index(r) + 1})")

    section('Honest test 3: rank-correlation between train and holdout')
    train_ranks = {r['name']: i for i, r in enumerate(sorted(rows, key=lambda x: -x['train']['calmar']))}
    hold_ranks = {r['name']: i for i, r in enumerate(sorted(rows, key=lambda x: -x['holdout']['calmar']))}
    names = [r['name'] for r in rows]
    tr_r = np.array([train_ranks[n] for n in names])
    ho_r = np.array([hold_ranks[n] for n in names])
    spearman = np.corrcoef(tr_r, ho_r)[0, 1]
    print(f"  Spearman rank correlation (train Calmar -> holdout Calmar): {spearman:+.3f}")
    print(f"    +1.0 = train ranks perfectly predict holdout ranks")
    print(f"     0.0 = no predictive value (overfit)")
    print(f"    -1.0 = inverted (worst case)")

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
