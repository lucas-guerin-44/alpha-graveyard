#!/usr/bin/env python3
"""
Allocation sweep: 3-strategy book under different per-strategy risk weights.

Each scheme specifies (orb_dax, lunch_fade, xau_session) risk multipliers on
top of the baseline 1% per trade. So (1, 2, 2) means lunch_fade and xau get
2% risk per trade, orb_dax stays at 1%.

Backtest: 2018-2026 full sample, $10k start, compounded equity.

Schemes:
  baseline           (1, 1, 1)        current deployed
  half_orb           (0.5, 1, 1)      address the orb_dax drawdown concentration
  no_orb             (0, 1, 1)        sanity: book without orb_dax
  double_lf          (1, 2, 1)        sharpe-leader concentration
  double_xau         (1, 1, 2)        diversifier concentration
  double_both_off    (1, 2, 2)        keep orb at base, lever up the better-MDD pair
  equal_vol_weights  (auto)           inverse trade-stdev (risk parity at trade level)
  max_sharpe_iso     (auto)           concentrated on highest-Sharpe strategy
  min_mdd_weighted   (auto)           weights inversely proportional to historical MDD
  conservative       (0.5, 1.5, 1.5)  halve orb, lift the others
  aggressive         (1.5, 2, 2)      lever everything

For each: Sharpe, CAGR, MDD%, MDD$, Calmar, Worst-day, Worst-trade-day-set,
         total return, final equity from $10k.
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


def section(t: str) -> None:
    print(f"\n{'=' * 100}\n  {t}\n{'=' * 100}")


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


# --- backtest under a scheme ---------------------------------------------

def annual_sharpe(r: np.ndarray, bpy: int = 252) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    return 0.0 if s == 0 else float(r.mean() / s * np.sqrt(bpy))


def run_scheme(all_trades: pd.DataFrame, one_R: dict, weights: dict) -> dict:
    """weights = {strategy: multiplier on BASE_RISK_PCT}"""
    equity = ACCOUNT
    rows = []
    for d, g in all_trades.groupby('exit_dt', sort=True):
        per = {'orb_dax': 0.0, 'lunch_fade': 0.0, 'xau_session': 0.0}
        day_pnl = 0.0
        for _, r in g.iterrows():
            s = r['strategy']
            w = weights.get(s, 1.0)
            R = r['pnl_pct'] / one_R[s]
            pnl = equity * BASE_RISK_PCT * w * R
            per[s] += pnl
            day_pnl += pnl
        equity += day_pnl
        rows.append({'date': d, **per, 'total_pnl': day_pnl, 'equity': equity})
    pnl_df = pd.DataFrame(rows).set_index('date')
    eq = pnl_df['equity']
    daily_ret = pnl_df['total_pnl'] / eq.shift(1).fillna(ACCOUNT)
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd_pct = float(dd.min())
    mdd_dollar = float((eq - peak).min())
    tot_ret = float(eq.iloc[-1] / ACCOUNT - 1)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (1 + tot_ret) ** (1 / max(years, 1e-9)) - 1
    return {
        'final': float(eq.iloc[-1]),
        'total_ret': tot_ret,
        'cagr': cagr,
        'sharpe': annual_sharpe(daily_ret.to_numpy()),
        'mdd_pct': mdd_pct,
        'mdd_dollar': mdd_dollar,
        'calmar': cagr / abs(mdd_pct) if mdd_pct < 0 else float('inf'),
        'worst_day': float(pnl_df['total_pnl'].min()),
        'best_day': float(pnl_df['total_pnl'].max()),
        'contrib': {s: float(pnl_df[s].sum()) for s in per.keys()},
    }


def print_header() -> None:
    print(f"  {'scheme':<24s}  {'orb':>5s} {'lf':>5s} {'xau':>5s}  "
          f"{'Sharpe':>7s} {'CAGR':>7s} {'MDD%':>8s} {'MDD$':>10s} "
          f"{'Calmar':>7s} {'final$':>10s} {'worst$':>9s}")
    print('  ' + '-' * 116)


def print_row(name: str, w: dict, m: dict) -> None:
    print(f"  {name:<24s}  {w['orb_dax']:>5.2f} {w['lunch_fade']:>5.2f} {w['xau_session']:>5.2f}  "
          f"{m['sharpe']:>+7.2f} {m['cagr']*100:>+6.1f}% {m['mdd_pct']*100:>+7.2f}% "
          f"${m['mdd_dollar']:>+9,.0f} {m['calmar']:>7.2f} ${m['final']:>+9,.0f} "
          f"${m['worst_day']:>+8,.0f}")


# --- main -----------------------------------------------------------------

def main() -> int:
    section('Loading trades (deployed configs)')
    t_orb = trades_orb_dax()
    t_lf = trades_lunch_fade()
    t_xau = trades_xau_session()
    all_trades = pd.concat([t_orb, t_lf, t_xau], ignore_index=True) \
        .sort_values('exit_dt').reset_index(drop=True)
    print(f"  Trades: orb_dax={len(t_orb)}  lunch_fade={len(t_lf)}  xau_session={len(t_xau)}")

    one_R = {s: float(g['pnl_pct'].std(ddof=1)) for s, g in all_trades.groupby('strategy')}
    print('\n  1R (full-sample trade-return stdev):')
    for s, r in one_R.items():
        print(f"    {s:12s}  1R = {r*100:.3f}%")

    # Per-strategy historical metrics (used by auto-allocation schemes)
    print('\n  Per-strategy 7-yr stats (at 1% risk-per-trade, solo):')
    solo_stats = {}
    for s in ('orb_dax', 'lunch_fade', 'xau_session'):
        m = run_scheme(all_trades[all_trades['strategy'] == s].reset_index(drop=True),
                       one_R, {'orb_dax': 1, 'lunch_fade': 1, 'xau_session': 1})
        solo_stats[s] = m
        print(f"    {s:12s}  Sh={m['sharpe']:+.2f}  CAGR={m['cagr']*100:+.1f}%  "
              f"MDD={m['mdd_pct']*100:+.1f}%  Calmar={m['calmar']:.2f}")

    # Auto-allocation schemes
    sharpes = {s: solo_stats[s]['sharpe'] for s in solo_stats}
    mdds = {s: abs(solo_stats[s]['mdd_pct']) for s in solo_stats}

    inv_vol = {s: 1 / one_R[s] for s in one_R}
    # Normalize all auto schemes so the avg weight = 1.0 (preserves "1% baseline budget")
    def normalize(d: dict) -> dict:
        m = np.mean(list(d.values()))
        return {k: v / m for k, v in d.items()}

    equal_vol_w = normalize(inv_vol)
    max_sharpe_iso = {s: 1.0 if s == max(sharpes, key=sharpes.get) else 0.0 for s in sharpes}
    # Min-MDD weighted = inverse-MDD, normalized
    min_mdd_w = normalize({s: 1 / mdds[s] for s in mdds})
    # Sharpe-weighted
    sharpe_w = normalize({s: max(sharpes[s], 0.01) for s in sharpes})

    schemes = [
        ('baseline (deployed)',   {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('half_orb',              {'orb_dax': 0.5, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('no_orb',                {'orb_dax': 0.0, 'lunch_fade': 1.0, 'xau_session': 1.0}),
        ('double_lf',             {'orb_dax': 1.0, 'lunch_fade': 2.0, 'xau_session': 1.0}),
        ('double_xau',            {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': 2.0}),
        ('double_both_off_orb',   {'orb_dax': 1.0, 'lunch_fade': 2.0, 'xau_session': 2.0}),
        ('equal_vol (risk-parity)', equal_vol_w),
        ('max_sharpe_iso',        max_sharpe_iso),
        ('inv_mdd_weighted',      min_mdd_w),
        ('sharpe_weighted',       sharpe_w),
        ('conservative',          {'orb_dax': 0.5, 'lunch_fade': 1.5, 'xau_session': 1.5}),
        ('aggressive',            {'orb_dax': 1.5, 'lunch_fade': 2.0, 'xau_session': 2.0}),
        ('half_orb_dbl_xau',      {'orb_dax': 0.5, 'lunch_fade': 1.0, 'xau_session': 2.0}),
        ('half_orb_dbl_both',     {'orb_dax': 0.5, 'lunch_fade': 2.0, 'xau_session': 2.0}),
    ]

    section('Allocation sweep (full 7-year backtest, $10k start)')
    print_header()
    results = []
    for name, w in schemes:
        m = run_scheme(all_trades, one_R, w)
        print_row(name, w, m)
        results.append((name, w, m))

    section('Sorted by Calmar (risk-adjusted CAGR — most decision-useful)')
    print_header()
    for name, w, m in sorted(results, key=lambda x: -x[2]['calmar']):
        print_row(name, w, m)

    section('Sorted by Sharpe')
    print_header()
    for name, w, m in sorted(results, key=lambda x: -x[2]['sharpe']):
        print_row(name, w, m)

    section('Sorted by final equity (raw return)')
    print_header()
    for name, w, m in sorted(results, key=lambda x: -x[2]['final']):
        print_row(name, w, m)

    section('Sorted by best MDD (least painful)')
    print_header()
    for name, w, m in sorted(results, key=lambda x: x[2]['mdd_pct'], reverse=True):
        print_row(name, w, m)

    # Targeted: scan xau weight from 0.0 to 3.0 holding others fixed
    section('Xau-weight scan (orb=1.0, lf=1.0, xau varies)')
    print_header()
    for xw in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        w = {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': xw}
        m = run_scheme(all_trades, one_R, w)
        print_row(f'xau={xw:.1f}x', w, m)

    section('Lunch_fade-weight scan (orb=1.0, lf varies, xau=1.0)')
    print_header()
    for lw in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        w = {'orb_dax': 1.0, 'lunch_fade': lw, 'xau_session': 1.0}
        m = run_scheme(all_trades, one_R, w)
        print_row(f'lf={lw:.1f}x', w, m)

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
