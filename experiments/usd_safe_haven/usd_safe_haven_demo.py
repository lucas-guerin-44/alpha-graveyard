#!/usr/bin/env python3
"""
USD safe-haven: short EURUSD/GBPUSD/AUDUSD/NZDUSD during equity stress.

Thesis: experiments/usd_safe_haven/usd_safe_haven.md

Identical framework to fx_safe_haven but on USD pairs (short pair = long USD).
The deployed book has negative USD-up beta (lf: -2521, xau: -7697), so
short-USD-pair-in-stress should be a genuine hedge if USD rallies in stress.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))

# Reuse helpers from fx_safe_haven
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'fx_safe_haven'))
from fx_safe_haven_demo import (  # noqa: E402
    load_pair_d1, build_spx_regime, simulate_fx_safe,
    annual_sharpe, max_drawdown, report_run, regime_breakdown,
    DAYS_PER_YEAR,
)

PAIRS = ['EURUSD', 'GBPUSD', 'AUDUSD', 'NZDUSD']


def section(t: str) -> None:
    print(f'\n{"=" * 88}\n  {t}\n{"=" * 88}')


def main() -> int:
    section('Loading data')
    spx = load_pair_d1('SPX500')
    print(f'  SPX500     {len(spx)} bars  {spx.index.min().date()} -> {spx.index.max().date()}')

    pairs_data = {}
    for sym in PAIRS:
        try:
            prefer_h1 = sym in ('AUDUSD', 'NZDUSD')  # short D1 coverage on these
            bars = load_pair_d1(sym, prefer_h1=prefer_h1)
            pairs_data[sym] = bars
            print(f'  {sym:8s}  {len(bars)} bars  '
                  f'{bars.index.min().date()} -> {bars.index.max().date()}')
        except Exception as e:
            print(f'  {sym}: SKIP -- {e}')

    if not pairs_data:
        print('No pairs loaded.')
        return 1

    section('SPX regime signals')
    reg = build_spx_regime(spx)
    for col in reg.columns:
        print(f'  {col:<20s}  active {reg[col].mean()*100:.1f}% of days')

    section('Baseline -- V4 trigger, short USD-pair (= long USD)')
    baseline = {}
    for sym, bars in pairs_data.items():
        ret, tr = simulate_fx_safe(bars, reg['V4_union_V1_V2'], direction=-1)
        baseline[sym] = report_run(f'{sym} V4 short', ret, tr)

    section('Portfolio (equal-weight) -- V4 baseline')
    portfolio = pd.concat([baseline[s]['series'].rename(s) for s in baseline],
                          axis=1).fillna(0.0).mean(axis=1)
    p_metrics = report_run('PORTFOLIO V4 short_pair (long USD)', portfolio, [])
    regime_breakdown(portfolio, 'PORTFOLIO USD-long-in-stress')

    section('Variant sweep -- trigger choice')
    variant_metrics = {}
    for variant in ('V1_drawdown', 'V2_rvol_spike', 'V3_below_sma', 'V4_union_V1_V2'):
        series_list = []
        all_trades = []
        for sym, bars in pairs_data.items():
            ret, tr = simulate_fx_safe(bars, reg[variant], direction=-1)
            series_list.append(ret)
            all_trades.extend(tr)
        port_ret = pd.concat([s.rename(i) for i, s in enumerate(series_list)],
                              axis=1).fillna(0.0).mean(axis=1)
        m = report_run(f'{variant:<22s}', port_ret, all_trades)
        variant_metrics[variant] = (m, port_ret)

    section('Null check -- V4 trigger, LONG USD-pair (short USD)')
    null_series = []
    for sym, bars in pairs_data.items():
        ret, tr = simulate_fx_safe(bars, reg['V4_union_V1_V2'], direction=+1)
        null_series.append(ret)
    null_port = pd.concat([s.rename(i) for i, s in enumerate(null_series)],
                          axis=1).fillna(0.0).mean(axis=1)
    n_metrics = report_run('PORTFOLIO V4 long_pair (null check)', null_port, [])
    base_sh = variant_metrics['V4_union_V1_V2'][0]['sharpe']
    dir_gap = base_sh - n_metrics['sharpe']
    print(f'\n  direction-gap (short_pair - long_pair) = {dir_gap:+.2f}')
    print(f'    PASS bar: > +0.30')

    section('Cost sensitivity')
    for c in (0.0, 0.5, 1.0, 2.0, 5.0):
        series_list = []
        for sym, bars in pairs_data.items():
            ret, _ = simulate_fx_safe(bars, reg['V4_union_V1_V2'],
                                       direction=-1, cost_bps_rt=c)
            series_list.append(ret)
        port_ret = pd.concat([s.rename(i) for i, s in enumerate(series_list)],
                              axis=1).fillna(0.0).mean(axis=1)
        sh = annual_sharpe(port_ret.to_numpy())
        mdd = max_drawdown((1 + port_ret).cumprod().to_numpy())
        print(f'    cost={c:.1f}bp RT  Sharpe={sh:+.2f}  MDD={mdd*100:+.2f}%')

    section('Kill-criteria check (hedge-asset framework + 2022-binding)')
    p_metrics, port_ret = variant_metrics['V4_union_V1_V2']
    sub_2020 = port_ret.loc['2020-02-19':'2020-04-30']
    sub_2022 = port_ret.loc['2022-01-01':'2022-12-31']
    sub_24_26 = port_ret.loc['2024-01-01':]
    sh_2020 = annual_sharpe(sub_2020.to_numpy())
    sh_2022 = annual_sharpe(sub_2022.to_numpy())
    sh_24_26 = annual_sharpe(sub_24_26.to_numpy())

    def check(name, val, op, bar, weight=''):
        ok = (val > bar) if op == '>' else (val < bar)
        print(f'    {"PASS" if ok else "FAIL"}  {name:<54s}  {val:+.2f}  {op}  {bar:+.2f}  {weight}')

    check('Full-sample Sharpe > -0.50', p_metrics['sharpe'], '>', -0.50)
    check('MDD > -40%', p_metrics['mdd'], '>', -0.40)
    check('Trades >= 30', float(p_metrics['trades']), '>', 29.0)
    check('2020-Q1 stress Sharpe > +1.5  [LOAD-BEARING]', sh_2020, '>', 1.5, 'LB')
    check('2022 stress Sharpe > +0.5  [LOAD-BEARING, the binding test]', sh_2022, '>', 0.5, 'LB')
    check('Direction null-gap > +0.30  [LOAD-BEARING]', dir_gap, '>', 0.30, 'LB')
    check('2024-2026 drag Sharpe > -0.50', sh_24_26, '>', -0.50)

    print('\n  2020-Q1 robustness across triggers:')
    for v, (m, pr) in variant_metrics.items():
        sub = pr.loc['2020-02-19':'2020-04-30']
        sh = annual_sharpe(sub.to_numpy())
        print(f'    {v:<22s}  2020-Q1 Sh={sh:+.2f}')
    print('\n  2022 robustness across triggers:')
    for v, (m, pr) in variant_metrics.items():
        sub = pr.loc['2022-01-01':'2022-12-31']
        sh = annual_sharpe(sub.to_numpy())
        print(f'    {v:<22s}  2022    Sh={sh:+.2f}')

    section('Done -- see thesis doc for verdict')
    return 0


if __name__ == '__main__':
    sys.exit(main())
