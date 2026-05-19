#!/usr/bin/env python3
"""
Book integration test: deployed 3-strategy book + USD-hedge sleeve.

Tests whether adding USD-long-in-stress (V1 trigger, short EURUSD/GBPUSD
during SPX drawdown > 5%) to the deployed book improves the overall Calmar.

If it does, that's the deployment argument — even though USD-hedge alone is
MARGINAL on standalone metrics, it can earn its keep if it correlates
correctly with the book.
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
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'fx_safe_haven'))


ACCOUNT = 10_000.0
BASE_RISK_PCT = 0.01


def section(t: str) -> None:
    print(f'\n{"=" * 100}\n  {t}\n{"=" * 100}')


# --- existing book trades (same as allocation_sweep.py) ------------------

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


# --- USD hedge daily returns (V1 trigger, short EURUSD + GBPUSD) ---------

def usd_hedge_daily_returns() -> pd.Series:
    from fx_safe_haven_demo import load_pair_d1, build_spx_regime, simulate_fx_safe
    spx = load_pair_d1('SPX500')
    reg = build_spx_regime(spx)
    trigger = reg['V1_drawdown']  # the cleanest single-trigger from the sweep

    eur = load_pair_d1('EURUSD')
    gbp = load_pair_d1('GBPUSD')

    ret_eur, _ = simulate_fx_safe(eur, trigger, direction=-1)
    ret_gbp, _ = simulate_fx_safe(gbp, trigger, direction=-1)
    # Equal-weight portfolio of the two USD-pair shorts
    hedge = pd.concat([ret_eur.rename('eur'), ret_gbp.rename('gbp')],
                     axis=1).fillna(0.0).mean(axis=1)
    return hedge


# --- main: simulate book with hedge at varying weights -------------------

def run_book(all_trades: pd.DataFrame, hedge_daily: pd.Series,
             one_R: dict, hedge_weight: float,
             book_weights: dict = None) -> dict:
    book_weights = book_weights or {'orb_dax': 1.0, 'lunch_fade': 1.0, 'xau_session': 1.0}
    equity = ACCOUNT
    rows = []
    trade_dates = sorted(all_trades['exit_dt'].unique())
    hedge_dates = hedge_daily.index

    # Build a unified per-day flow
    all_dates = sorted(set(list(trade_dates) + list(hedge_dates)))
    trade_by_date = {d: g for d, g in all_trades.groupby('exit_dt')}

    for d in all_dates:
        if isinstance(d, np.datetime64):
            d = pd.Timestamp(d)
        day_pnl = 0.0
        per = {'orb_dax': 0.0, 'lunch_fade': 0.0, 'xau_session': 0.0, 'usd_hedge': 0.0}

        # Trades
        if d in trade_by_date:
            for _, r in trade_by_date[d].iterrows():
                s = r['strategy']
                w = book_weights.get(s, 1.0)
                R = r['pnl_pct'] / one_R[s]
                pnl = equity * BASE_RISK_PCT * w * R
                per[s] += pnl
                day_pnl += pnl

        # Hedge (continuous daily return, scaled by hedge_weight)
        if d in hedge_dates:
            hr = float(hedge_daily.loc[d])
            # Hedge is already vol-targeted to 10% inside simulate_fx_safe;
            # treat the daily ret as a %-of-equity contribution scaled by hedge_weight
            pnl = equity * hedge_weight * hr
            per['usd_hedge'] += pnl
            day_pnl += pnl

        equity += day_pnl
        rows.append({'date': d, **per, 'total_pnl': day_pnl, 'equity': equity})

    pnl_df = pd.DataFrame(rows).set_index('date')
    eq = pnl_df['equity']
    daily_ret = pnl_df['total_pnl'] / eq.shift(1).fillna(ACCOUNT)
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd_pct = float(dd.min())
    tot = float(eq.iloc[-1] / ACCOUNT - 1)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (1 + tot) ** (1 / max(years, 1e-9)) - 1
    r = daily_ret.to_numpy()
    r = r[np.isfinite(r)]
    sh = 0.0 if (r.size < 2 or r.std(ddof=1) == 0) else float(r.mean() / r.std(ddof=1) * np.sqrt(252))
    return {
        'final': float(eq.iloc[-1]),
        'total_ret': tot,
        'cagr': cagr,
        'sharpe': sh,
        'mdd_pct': mdd_pct,
        'mdd_dollar': float((eq - peak).min()),
        'calmar': cagr / abs(mdd_pct) if mdd_pct < 0 else float('inf'),
        'worst_day': float(pnl_df['total_pnl'].min()),
        'best_day': float(pnl_df['total_pnl'].max()),
        'hedge_contrib': float(pnl_df['usd_hedge'].sum()),
        'pnl_df': pnl_df,
    }


def main() -> int:
    section('Loading trades + USD hedge daily returns')
    all_trades = pd.concat([trades_orb_dax(), trades_lunch_fade(), trades_xau_session()],
                            ignore_index=True).sort_values('exit_dt').reset_index(drop=True)
    print(f'  Book trades: {len(all_trades)}')

    one_R = {s: float(g['pnl_pct'].std(ddof=1)) for s, g in all_trades.groupby('strategy')}
    for s, r in one_R.items():
        print(f'  1R[{s}] = {r*100:.3f}%')

    hedge_daily = usd_hedge_daily_returns()
    hedge_daily.index = pd.to_datetime(hedge_daily.index).normalize()
    print(f'  USD hedge daily returns: {len(hedge_daily)} days, '
          f'{hedge_daily.index.min().date()} -> {hedge_daily.index.max().date()}')

    section('Book + USD hedge: hedge-weight sweep')
    print(f'  {"hedge_w":>9s} {"Sharpe":>8s} {"CAGR":>7s} {"MDD%":>8s} {"MDD$":>10s} '
          f'{"Calmar":>7s} {"$end":>10s} {"hedge_$":>10s} {"worst_day":>11s}')
    print('  ' + '-' * 95)
    results = {}
    for hw in (0.00, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00):
        m = run_book(all_trades, hedge_daily, one_R, hw)
        results[hw] = m
        print(f'  {hw:>9.2f} {m["sharpe"]:>+7.2f} {m["cagr"]*100:>+6.1f}% '
              f'{m["mdd_pct"]*100:>+7.2f}% ${m["mdd_dollar"]:>+9,.0f} '
              f'{m["calmar"]:>7.2f} ${m["final"]:>+9,.0f} ${m["hedge_contrib"]:>+9,.0f} '
              f'${m["worst_day"]:>+10,.0f}')

    section('Comparison: baseline vs hedge_w=0.50 in stress windows')
    base_df = results[0.0]['pnl_df']
    hedged_df = results[0.5]['pnl_df']
    for window_name, start, end in [
        ('2020-Q1 COVID', '2020-02-19', '2020-04-30'),
        ('2022 bear', '2022-01-01', '2022-12-31'),
        ('2024-2026 calm', '2024-01-01', '2026-04-22'),
    ]:
        b = base_df.loc[start:end]
        h = hedged_df.loc[start:end]
        bpnl = b['total_pnl'].sum() if len(b) else 0
        hpnl = h['total_pnl'].sum() if len(h) else 0
        b_mdd = float(((b['equity'] - b['equity'].cummax()) / b['equity'].cummax()).min()) if len(b) else 0
        h_mdd = float(((h['equity'] - h['equity'].cummax()) / h['equity'].cummax()).min()) if len(h) else 0
        print(f'\n  {window_name}:')
        print(f'    baseline:  $pnl={bpnl:+,.0f}  in-window MDD={b_mdd*100:+.2f}%')
        print(f'    hedge=0.5: $pnl={hpnl:+,.0f}  in-window MDD={h_mdd*100:+.2f}%')
        print(f'    delta:     $pnl={hpnl - bpnl:+,.0f}  MDD-change={(h_mdd - b_mdd)*100:+.2f}pp')

    section('Hedge correlation to book in stress vs calm')
    for window_name, start, end in [
        ('2020-Q1 stress', '2020-02-19', '2020-04-30'),
        ('2022 stress', '2022-01-01', '2022-12-31'),
        ('Calm (2017-2019, 2024-2026)', '2024-01-01', '2026-04-22'),
    ]:
        sub = base_df.loc[start:end]
        # Compute book-only daily PnL (sum of strategy cols, not total which includes hedge=0)
        book_pnl = sub[['orb_dax', 'lunch_fade', 'xau_session']].sum(axis=1)
        # Hedge daily $-PnL at hedge_w=1.0 (= equity * 1 * hedge_daily)
        ah = hedge_daily.reindex(sub.index).fillna(0.0)
        hedge_pnl = sub['equity'].shift(1).fillna(ACCOUNT) * ah  # approximate
        if len(book_pnl) < 5 or book_pnl.std() == 0 or hedge_pnl.std() == 0:
            print(f'  {window_name:<30s}: insufficient data')
            continue
        c = book_pnl.corr(hedge_pnl)
        print(f'  {window_name:<30s}: corr={c:+.3f}  '
              f'(book_total=${book_pnl.sum():+,.0f}  hedge_total=${hedge_pnl.sum():+,.0f})')

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
