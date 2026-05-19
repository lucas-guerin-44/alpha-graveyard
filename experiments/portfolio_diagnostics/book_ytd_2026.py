#!/usr/bin/env python3
"""
2026 YTD simulation: 3 deployed strategies running together, $10k start,
1% risk per trade, vol-targeted sizing.

1R per strategy is computed from PRE-2026 trades only (no look-ahead): this
is the risk unit a trader would have had on Jan 1 2026, calibrated from
their existing live/research history.

Strategies (deployed config, no overlays):
  orb_dax       GER40 M5 EU ORB=30 T+180 LONG-only
  lunch_fade    NDX100 M5 thr=0.25 LONG-only fade
  xau_session   XAUUSD H1 23->08 UTC dnmed-filter
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
RISK_PCT = 0.01
START = pd.Timestamp('2026-01-01')
END = pd.Timestamp('2026-05-01')


def section(t: str) -> None:
    print(f"\n{'=' * 88}\n  {t}\n{'=' * 88}")


# --- per-strategy trade extraction (same as book_drawdown_w4.py) -----------

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


# --- 2026 sim --------------------------------------------------------------

def simulate_book() -> None:
    section('Loading trades from all 3 strategies (no overlay)')
    parts = [trades_orb_dax(), trades_lunch_fade(), trades_xau_session()]
    all_trades = pd.concat(parts, ignore_index=True).sort_values('exit_dt')
    print(f"  Total trades all-time: {len(all_trades)}")

    # 1R = stdev of pre-2026 trade returns (no lookahead)
    pre2026 = all_trades.loc[all_trades['exit_dt'] < START]
    one_R = {}
    for s, g in pre2026.groupby('strategy'):
        one_R[s] = float(g['pnl_pct'].std(ddof=1))

    print('\n  1R per strategy (calibrated on pre-2026 trades only):')
    for s, r in one_R.items():
        n_pre = int((pre2026['strategy'] == s).sum())
        print(f"    {s:12s}  1R = {r*100:.3f}%  (from {n_pre} trades)")

    # Filter to 2026 Jan 1 -> May 1
    book = all_trades.loc[(all_trades['exit_dt'] >= START) & (all_trades['exit_dt'] < END)] \
        .sort_values('exit_dt').reset_index(drop=True)

    section(f'2026 YTD trades: {START.date()} -> {END.date()}')
    print(f"  Total trades in window: {len(book)}")
    for s in ('orb_dax', 'lunch_fade', 'xau_session'):
        sub = book[book['strategy'] == s]
        wins = (sub['pnl_pct'] > 0).sum()
        losers = (sub['pnl_pct'] < 0).sum()
        wr = wins / max(len(sub), 1) * 100
        print(f"    {s:12s}  n={len(sub):>3d}  W/L={wins}/{losers}  "
              f"WR={wr:>4.1f}%  best={sub['pnl_pct'].max()*100:+.2f}%  "
              f"worst={sub['pnl_pct'].min()*100:+.2f}%")

    # Walk forward sized PnL, compounded
    equity = ACCOUNT
    rows = []
    for d, g in book.groupby('exit_dt', sort=True):
        per_strat = {'orb_dax': 0.0, 'lunch_fade': 0.0, 'xau_session': 0.0}
        day_pnl = 0.0
        for _, r in g.iterrows():
            R = r['pnl_pct'] / one_R[r['strategy']]
            pnl = equity * RISK_PCT * R
            per_strat[r['strategy']] += pnl
            day_pnl += pnl
        equity += day_pnl
        rows.append({'date': d, **per_strat, 'total_pnl': day_pnl, 'equity': equity})
    pnl_df = pd.DataFrame(rows).set_index('date')

    section(f'2026 YTD book performance ($10k start, 1% risk/trade)')
    eq = pnl_df['equity']
    peak = eq.cummax()
    dd = (eq - peak) / peak
    final = float(eq.iloc[-1])
    total_ret_pct = (final - ACCOUNT) / ACCOUNT * 100
    max_dd_pct = float(dd.min() * 100)
    max_dd_dollar = float((eq - peak).min())
    worst_day = float(pnl_df['total_pnl'].min())
    best_day = float(pnl_df['total_pnl'].max())

    print(f"  Starting equity:      ${ACCOUNT:>10,.2f}")
    print(f"  Final equity:         ${final:>10,.2f}")
    print(f"  Total P&L:            ${final - ACCOUNT:>+10,.2f}")
    print(f"  Total return:         {total_ret_pct:>+10.2f}%")
    print(f"  Peak drawdown:        {max_dd_pct:>+10.2f}%  (${max_dd_dollar:>+10,.2f})")
    print(f"  Best single day:      ${best_day:>+10,.2f}")
    print(f"  Worst single day:     ${worst_day:>+10,.2f}")
    print(f"  Trading days w/PnL:   {len(pnl_df)}")

    section('Per-strategy contribution (YTD)')
    for s in ('orb_dax', 'lunch_fade', 'xau_session'):
        total = pnl_df[s].sum()
        n_days = (pnl_df[s] != 0).sum()
        avg = pnl_df.loc[pnl_df[s] != 0, s].mean() if n_days > 0 else 0
        print(f"    {s:12s}  total=${total:>+9,.2f}  active_days={n_days:>3d}  "
              f"mean_active_day=${avg:>+8,.2f}")

    section('Drawdown episodes')
    in_dd = dd < -0.005
    episodes = []
    st = None
    for t, f in in_dd.items():
        if f and st is None:
            st = t
        elif not f and st is not None:
            sub = dd.loc[st:t]
            episodes.append((sub.min(), st, sub.idxmin(), t, (t - st).days))
            st = None
    if st is not None:
        sub = dd.loc[st:]
        episodes.append((sub.min(), st, sub.idxmin(), None, (eq.index[-1] - st).days))
    episodes = sorted(episodes, key=lambda x: x[0])
    if episodes:
        print(f"  {'start':<12} {'trough':<12} {'recover':<12} {'depth%':>8} {'days':>6}")
        for depth, s, tr, rec, days in episodes:
            rec_s = str(rec.date()) if rec is not None else 'open'
            print(f"  {str(s.date()):<12} {str(tr.date()):<12} {rec_s:<12} "
                  f"{depth*100:>8.2f} {days:>6}")
    else:
        print('  No drawdown > 0.5% in window.')

    section('Daily equity tail (last 15 days)')
    show = pnl_df.tail(15)[['orb_dax', 'lunch_fade', 'xau_session', 'total_pnl', 'equity']]
    print(show.round(2).to_string())

    section('Done')


if __name__ == '__main__':
    simulate_book()
