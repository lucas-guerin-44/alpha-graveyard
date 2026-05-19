#!/usr/bin/env python3
"""
USD safe-haven walk-forward + scaling-rule validation.

Two questions:
  Q1: Is hedge_w=0.5 the result of overfitting on the 2022 sample, or does
      the improvement survive on data the hedge weight wasn't tuned on?
  Q2: Does dynamically scaling the hedge weight by regime add anything over
      a fixed-weight rebalance?

Method:
  TRAIN:   2018-01 -> 2022-12-31 (5 years incl. COVID + 2022 bear)
  HOLDOUT: 2023-01-01 -> 2026-05-01 (28 months, never touched for tuning)

  Pick hedge_w that maximises TRAIN Calmar.
  Apply that weight to HOLDOUT.
  Compare: book-only-OOS vs book+hedge-OOS at TRAIN-optimal weight.

  Parameter neighborhood:
    Test hedge_w in {0, 0.25, 0.5, 0.75, 1.0, 1.5} on TRAIN and HOLDOUT.
    If neighbors of TRAIN-optimal-w all degrade on holdout the same way,
    the result is robust. If only the TRAIN-optimal-w looks good OOS,
    it's overfit.

  Dynamic scaling rules tested:
    R1: hedge_w = 0.5 if SPX 60d_dd < -3% else 0          (binary off/on)
    R2: hedge_w = clip(-SPX_60d_dd / 0.10 * 0.75, 0, 1.0) (proportional)
    R3: hedge_w fixed = 0.5                                (baseline)
    Compare each on TRAIN and HOLDOUT.
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
TRAIN_END = pd.Timestamp('2023-01-01')
HOLDOUT_END = pd.Timestamp('2026-05-01')


def section(t: str) -> None:
    print(f'\n{"=" * 104}\n  {t}\n{"=" * 104}')


# --- existing book trades --------------------------------------------------

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


# --- USD hedge daily series, and regime drawdown series -------------------

def hedge_daily_and_regime():
    from fx_safe_haven_demo import load_pair_d1, build_spx_regime, simulate_fx_safe
    spx = load_pair_d1('SPX500')
    reg = build_spx_regime(spx)
    trigger = reg['V1_drawdown']

    eur = load_pair_d1('EURUSD')
    gbp = load_pair_d1('GBPUSD')

    ret_eur, _ = simulate_fx_safe(eur, trigger, direction=-1)
    ret_gbp, _ = simulate_fx_safe(gbp, trigger, direction=-1)
    hedge = pd.concat([ret_eur.rename('eur'), ret_gbp.rename('gbp')],
                      axis=1).fillna(0.0).mean(axis=1)

    spx_dd_60 = spx['close'] / spx['close'].rolling(60).max() - 1.0
    return hedge, spx_dd_60


# --- book simulator -------------------------------------------------------

def run_book_window(all_trades, hedge_daily, spx_dd_60, one_R,
                    hedge_weight_fn, start, end):
    """Simulate book + hedge between start and end with a (date -> hedge_w) callable."""
    sub = all_trades[(all_trades['exit_dt'] >= start) & (all_trades['exit_dt'] < end)]
    trade_by_date = {d: g for d, g in sub.groupby('exit_dt')}

    hedge_window = hedge_daily.loc[start:end]
    all_dates = sorted(set(list(sub['exit_dt']) + list(hedge_window.index)))
    if not all_dates:
        return None

    equity = ACCOUNT
    rows = []
    for d in all_dates:
        d = pd.Timestamp(d)
        day_pnl = 0.0
        per = {'orb_dax': 0.0, 'lunch_fade': 0.0, 'xau_session': 0.0, 'usd_hedge': 0.0}

        if d in trade_by_date:
            for _, r in trade_by_date[d].iterrows():
                s = r['strategy']
                R = r['pnl_pct'] / one_R[s]
                pnl = equity * BASE_RISK_PCT * R
                per[s] += pnl
                day_pnl += pnl

        if d in hedge_window.index:
            hw = float(hedge_weight_fn(d, spx_dd_60))
            hr = float(hedge_window.loc[d])
            pnl = equity * hw * hr
            per['usd_hedge'] += pnl
            day_pnl += pnl

        equity += day_pnl
        rows.append({'date': d, **per, 'total_pnl': day_pnl, 'equity': equity})

    pnl_df = pd.DataFrame(rows).set_index('date')
    eq = pnl_df['equity']
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd_pct = float(dd.min())
    tot = float(eq.iloc[-1] / ACCOUNT - 1)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (1 + tot) ** (1 / max(years, 1e-9)) - 1
    daily = pnl_df['total_pnl'] / eq.shift(1).fillna(ACCOUNT)
    r = daily.to_numpy()
    r = r[np.isfinite(r)]
    sh = 0.0 if r.size < 2 or r.std(ddof=1) == 0 else float(r.mean() / r.std(ddof=1) * np.sqrt(252))
    return {
        'final': float(eq.iloc[-1]),
        'total_ret': tot,
        'cagr': cagr,
        'sharpe': sh,
        'mdd_pct': mdd_pct,
        'mdd_dollar': float((eq - peak).min()),
        'calmar': cagr / abs(mdd_pct) if mdd_pct < 0 else float('inf'),
        'hedge_contrib': float(pnl_df['usd_hedge'].sum()),
        'worst_day': float(pnl_df['total_pnl'].min()),
    }


# --- main -----------------------------------------------------------------

def main() -> int:
    section('Loading data')
    all_trades = pd.concat([trades_orb_dax(), trades_lunch_fade(), trades_xau_session()],
                            ignore_index=True).sort_values('exit_dt').reset_index(drop=True)
    print(f'  Total book trades: {len(all_trades)}')

    one_R = {s: float(g['pnl_pct'].std(ddof=1)) for s, g in all_trades.groupby('strategy')}
    print('  1R per strategy (full-sample, used uniformly across train+holdout):')
    for s, r in one_R.items():
        print(f'    {s:12s}  1R={r*100:.3f}%')

    hedge_daily, spx_dd_60 = hedge_daily_and_regime()
    spx_dd_60.index = pd.to_datetime(spx_dd_60.index).normalize()
    hedge_daily.index = pd.to_datetime(hedge_daily.index).normalize()

    print(f'  Hedge daily series: {len(hedge_daily)} days, '
          f'{hedge_daily.index.min().date()} -> {hedge_daily.index.max().date()}')
    print(f'  Train: 2018 -> 2022-12 | Holdout: 2023 -> 2026-04')

    # Q1: parameter robustness across hedge_w on TRAIN and HOLDOUT
    section('Q1 - Walk-forward + parameter robustness (fixed weight)')
    print(f'  {"hedge_w":>9s}  {"TRAIN Sh":>9s} {"CAGR":>7s} {"MDD%":>8s} {"Calmar":>7s} {"$end":>9s} | '
          f'{"HOLD Sh":>9s} {"CAGR":>7s} {"MDD%":>8s} {"Calmar":>7s} {"$end":>9s} | '
          f'{"d_Calmar":>9s}')
    print('  ' + '-' * 122)

    results_train = {}
    results_hold = {}
    for hw in (0.00, 0.25, 0.50, 0.75, 1.00, 1.50):
        fn = lambda d, dd, w=hw: w
        m_tr = run_book_window(all_trades, hedge_daily, spx_dd_60, one_R, fn,
                                pd.Timestamp('2018-01-01'), TRAIN_END)
        m_ho = run_book_window(all_trades, hedge_daily, spx_dd_60, one_R, fn,
                                TRAIN_END, HOLDOUT_END)
        results_train[hw] = m_tr
        results_hold[hw] = m_ho
        d_cal = m_ho['calmar'] - m_tr['calmar']
        print(f'  {hw:>9.2f}  {m_tr["sharpe"]:>+8.2f} {m_tr["cagr"]*100:>+6.1f}% '
              f'{m_tr["mdd_pct"]*100:>+7.2f}% {m_tr["calmar"]:>7.2f} ${m_tr["final"]:>+8,.0f} | '
              f'{m_ho["sharpe"]:>+8.2f} {m_ho["cagr"]*100:>+6.1f}% {m_ho["mdd_pct"]*100:>+7.2f}% '
              f'{m_ho["calmar"]:>7.2f} ${m_ho["final"]:>+8,.0f} | {d_cal:>+8.2f}')

    # Train-optimal hedge weight
    train_best_w = max(results_train.keys(), key=lambda w: results_train[w]['calmar'])
    print(f'\n  Train-optimal hedge_w = {train_best_w:.2f} '
          f'(TRAIN Calmar {results_train[train_best_w]["calmar"]:.2f})')
    print(f'  At that weight, HOLDOUT Calmar = {results_hold[train_best_w]["calmar"]:.2f}')
    print(f'  HOLDOUT Calmar with hedge_w=0 (book only): {results_hold[0.0]["calmar"]:.2f}')

    if results_hold[train_best_w]['calmar'] > results_hold[0.0]['calmar']:
        print(f'  ==> Holdout Calmar IMPROVES with hedge: not pure overfit')
    else:
        print(f'  ==> Holdout Calmar WORSE with hedge: overfit warning')

    section('Q1b - Parameter robustness check (do neighbors of train-optimal also pass OOS?)')
    print('  If 0.25 / 0.5 / 0.75 all improve holdout Calmar, the result is robust.')
    print('  If only the train-optimal value improves, it is curve-fit.')
    print()
    base_hold_calmar = results_hold[0.0]['calmar']
    for hw in (0.25, 0.50, 0.75):
        m = results_hold[hw]
        delta = m['calmar'] - base_hold_calmar
        verdict = 'IMPROVES' if delta > 0 else 'DEGRADES'
        print(f'  hedge_w={hw:.2f}: HOLDOUT Calmar {m["calmar"]:.2f} vs book-only {base_hold_calmar:.2f}  '
              f'(d {delta:+.2f})  {verdict}')

    # Q2: dynamic scaling
    section('Q2 - Dynamic vs fixed hedge weight (when to scale?)')
    print('  Three rules tested on full sample (train+holdout):')

    rules = {
        'R0_fixed_0.0 (book only)':
            lambda d, dd_series: 0.0,
        'R1_binary (off / 0.5 if dd<-3%)':
            lambda d, dd_series: 0.5 if (d in dd_series.index and dd_series.loc[d] < -0.03) else 0.0,
        'R2_proportional (clip(-dd/0.10*0.75))':
            lambda d, dd_series: float(np.clip(-dd_series.loc[d] / 0.10 * 0.75, 0, 1.0))
                if d in dd_series.index and pd.notna(dd_series.loc[d]) else 0.0,
        'R3_fixed_0.5':
            lambda d, dd_series: 0.5,
        'R4_fixed_0.25':
            lambda d, dd_series: 0.25,
    }

    print(f'\n  {"rule":<40s}  {"TRAIN Sh":>9s} {"Calmar":>7s} {"$end":>9s} | '
          f'{"HOLD Sh":>9s} {"Calmar":>7s} {"$end":>9s}')
    print('  ' + '-' * 100)
    for name, fn in rules.items():
        bound_fn = lambda d, dd, _fn=fn: _fn(d, dd)
        m_tr = run_book_window(all_trades, hedge_daily, spx_dd_60, one_R, bound_fn,
                                pd.Timestamp('2018-01-01'), TRAIN_END)
        m_ho = run_book_window(all_trades, hedge_daily, spx_dd_60, one_R, bound_fn,
                                TRAIN_END, HOLDOUT_END)
        print(f'  {name:<40s}  {m_tr["sharpe"]:>+8.2f} {m_tr["calmar"]:>7.2f} '
              f'${m_tr["final"]:>+8,.0f} | {m_ho["sharpe"]:>+8.2f} {m_ho["calmar"]:>7.2f} '
              f'${m_ho["final"]:>+8,.0f}')

    section('Q2 - honest framework')
    print('  Two ways to interpret "when to scale":')
    print('    (a) Time-varying weight on the HEDGE based on regime signal')
    print('        Tested above as R1 (binary) and R2 (proportional). Compare to R3/R4 fixed.')
    print('    (b) Time-varying weights on the BOOK strategies (orb/lf/xau)')
    print('        Per allocation_walkforward results: fixed train-period-optimal weights work better')
    print('        than dynamic re-weighting (Spearman 0.50 train->hold ranks, modest).')
    print()
    print('  The CTA / TAA literature consensus: simple rebalanced fixed weights beat')
    print('  most "dynamic regime" rules because the regime detection signal is itself noisy')
    print('  and the alpha decay from being wrong-footed exceeds the gain from being right.')
    print('  Notable exceptions: vol-targeting (already used per-strategy) and trend-filter')
    print('  on the underlying (SMA-200, tested earlier, robust on walk-forward).')

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
