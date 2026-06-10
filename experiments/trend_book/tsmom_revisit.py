#!/usr/bin/env python3
"""tsmom revisit — Eightcap-deployable long-only TSMOM, swap-modelled (D1).

Step 2 of experiments/trend_book/trend_book.md. Re-evaluates the 12-1 long-only
time-series-momentum ensemble on the ~30-name Eightcap-tradeable + swap-survivable
universe scoped by _scope_probe.py (live MT5, 2026-05-30). The prior tsmom's only
blocker (+0.69 corr with the now-retired xs_momentum) is moot; this asks the
deployability question: does it clear the bar AFTER real per-instrument swap, beat
EW buy-and-hold (lesson #73 gate), survive the null, and across regimes?

PERFORMANCE: fully VECTORIZED — no per-bar or per-instrument loop in the hot path.
Each instrument's daily strat-return series is computed with matrix ops, stacked
into a dates x instruments frame, equal-weighted. ~30 instruments in <1s.

NO LOOKAHEAD (vectorized-leak discipline):
  - momentum = close.shift(21)/close.shift(252) - 1   (current bar never in signal)
  - vol-target uses lagged rolling std
  - TRADED position = position.shift(1)  (decided EoD t-1, applied to ret_t)
  - cost (turnover) + swap charged on that same lagged position

Run: PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/trend_book/tsmom_revisit.py
"""
from __future__ import annotations
import os
import sys
import time
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from data import fetch_ohlc  # noqa: E402

TIMEFRAME = 'D1'
START, END = '2015-01-01', '2026-12-31'

# Signal params (match prior tsmom base_params)
LOOKBACK, SKIP, VOL_LB, REBAL = 252, 21, 60, 21
VOL_TARGET = 0.15
MAX_LEV = 3.0            # per-instrument vol-target cap
ANN = 252

# Deployable universe (research name -> Eightcap long swap fraction/yr, from probe)
SWAP_ANN_L = {
    'EURUSD': -0.025, 'GBPUSD': -0.005, 'USDJPY': +0.016, 'USDCHF': +0.019,
    'USDCAD': +0.006, 'AUDUSD': +0.001, 'NZDUSD': -0.022,
    'AUDNZD': +0.008, 'NZDCAD': -0.014, 'GBPNZD': +0.003, 'AUDCAD': +0.014,
    'CADJPY': +0.006, 'NZDJPY': +0.006, 'EURGBP': -0.028, 'EURNOK': -0.038,
    'USDZAR': -0.073,
    'SPX500': -0.051, 'NDX100': -0.060, 'GER40': -0.042, 'UK100': -0.060,
    'FRA40': +0.022, 'JPN225': -0.028, 'HK50': -0.034,
    'XAUUSD': -0.065, 'XAGUSD': -0.085, 'XPDUSD': -0.078, 'XPTUSD': -0.102,
    'COCOA': -0.001, 'COFFEE': +0.001, 'SUGAR': -0.003, 'WHEAT': -0.116,
    'EWZ': -0.068,
}
# Eightcap SHORT-side financing fraction/yr (probe annS%). Pos = credit to a short.
SWAP_ANN_S = {
    'EURUSD': +0.010, 'GBPUSD': -0.009, 'USDJPY': -0.046, 'USDCHF': -0.052,
    'USDCAD': -0.030, 'AUDUSD': -0.014, 'NZDUSD': +0.003,
    'AUDNZD': -0.033, 'NZDCAD': -0.016, 'GBPNZD': -0.024, 'AUDCAD': -0.035,
    'CADJPY': -0.027, 'NZDJPY': -0.033, 'EURGBP': +0.010, 'EURNOK': +0.011,
    'USDZAR': +0.014,
    'SPX500': +0.007, 'NDX100': +0.016, 'GER40': -0.001, 'UK100': +0.016,
    'FRA40': -0.065, 'JPN225': -0.013, 'HK50': -0.008,
    'XAUUSD': +0.027, 'XAGUSD': +0.017, 'XPDUSD': -0.004, 'XPTUSD': +0.001,
    'COCOA': +0.001, 'COFFEE': -0.002, 'SUGAR': -0.003, 'WHEAT': +0.065,
    'EWZ': +0.018,
}
# RT cost (commission+slippage bps) per class
COST_BPS = {
    'XAUUSD': 8, 'XAGUSD': 9, 'XPDUSD': 10, 'XPTUSD': 11,
    'SPX500': 4, 'NDX100': 4, 'GER40': 5, 'UK100': 5, 'FRA40': 5, 'JPN225': 5, 'HK50': 6,
    'COCOA': 13, 'COFFEE': 13, 'SUGAR': 13, 'WHEAT': 13, 'EWZ': 8,
}
DEFAULT_COST_BPS = 4   # FX majors; exotics get 6 below
FX_EXOTIC = {'AUDNZD','NZDCAD','GBPNZD','AUDCAD','CADJPY','NZDJPY','EURGBP','EURNOK','USDZAR'}

WINDOWS = [('2015-2018',2015,2018),('2019-2020',2019,2020),
           ('2021-2022',2021,2022),('2023-2026',2023,2026)]
HOLDOUT = (2023, 2026)


def section(t): print(f'\n{"="*92}\n  {t}\n{"="*92}')
def cost_of(sym): return COST_BPS.get(sym, 6 if sym in FX_EXOTIC else DEFAULT_COST_BPS)


def strat_series(close: pd.Series, sym: str, mode: str = 'long',
                 invert: bool = False) -> pd.DataFrame:
    """Vectorized TSMOM daily net-return series for one instrument.
    mode 'long' -> long-only (sig in {0,1}); 'ls' -> long/short (sig in {-1,+1}).
    invert flips the signal (anti-trend null). Two-sided swap (long & short legs).
    Returns net + bnh daily fractions, indexed by date.
    """
    c = close.astype(float)
    ret = c.pct_change()
    mom = c.shift(SKIP) / c.shift(LOOKBACK) - 1.0           # 12-1, no current bar
    if mode == 'ls':
        sig = np.sign(mom)
        if invert:
            sig = -sig
    else:
        sig = (mom < 0).astype(float) if invert else (mom > 0).astype(float)
    sig = pd.Series(sig, index=c.index)
    vol = ret.rolling(VOL_LB).std() * np.sqrt(ANN)          # lagged realized vol
    scalar = (VOL_TARGET / vol).clip(upper=MAX_LEV).fillna(0.0)
    raw_pos = sig * scalar                                  # desired position EoD t

    # monthly rebalance: hold position between rebalance days
    n = len(c)
    reb = np.zeros(n, bool); reb[::REBAL] = True
    pos = raw_pos.where(pd.Series(reb, index=c.index)).ffill().fillna(0.0)

    traded = pos.shift(1).fillna(0.0)                       # decided t-1, applied t  (no leak)
    turn = (traded - traded.shift(1).fillna(0.0)).abs()
    cost = turn * (cost_of(sym) / 1e4)
    # two-sided swap: long leg pays swap_long, short leg pays swap_short (signed)
    swap = (traded.clip(lower=0) * (SWAP_ANN_L.get(sym, 0.0) / 365.0)
            + (-traded).clip(lower=0) * (SWAP_ANN_S.get(sym, 0.0) / 365.0))
    net = traded * ret - cost + swap
    net = net.where(mom.notna())          # exclude pre-warmup (NaN, not 0) from EW
    return pd.DataFrame({'net': net, 'bnh': ret})


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 20:
        return {'n': len(r)}
    sd = r.std(ddof=1)
    sh = r.mean() / sd * np.sqrt(ANN) if sd > 0 else 0.0
    eq = (1 + r).cumprod()
    yrs = len(r) / ANN
    cagr = eq.iloc[-1] ** (1 / max(yrs, 1e-9)) - 1
    dd = (eq / eq.cummax() - 1).min()
    return {'n': len(r), 'sharpe': sh, 'cagr': cagr, 'mdd': dd}


def report(name, r):
    m = metrics(r)
    if m.get('n',0) < 20: print(f'  {name:<22s} insufficient (n={m.get("n",0)})'); return m
    print(f'  {name:<22s} Sh {m["sharpe"]:>+6.2f}  CAGR {m["cagr"]*100:>+6.2f}%  '
          f'MDD {m["mdd"]*100:>+7.2f}%  n {m["n"]}')
    return m


def main():
    t0 = time.time()
    section('Load deployable universe (D1)')
    closes = {}
    for sym in SWAP_ANN_L:
        try:
            df = fetch_ohlc(sym, TIMEFRAME, START, END)
        except Exception as e:
            print(f'  {sym:<8s} FAIL ({type(e).__name__})'); continue
        if df is None or df.empty or len(df) < 400:
            print(f'  {sym:<8s} skip ({0 if df is None else len(df)} bars)'); continue
        # normalize to DATE so daily bars align across instruments regardless of
        # their intraday D1 stamp (00:00 vs 21:00 vs 22:00 UTC).
        idx = pd.to_datetime(df['timestamp'], utc=True).dt.normalize()
        s = pd.Series(df['close'].to_numpy(float), index=idx).sort_index()
        s = s[~s.index.duplicated(keep='last')]
        closes[sym] = s
    print(f'  loaded {len(closes)}/{len(SWAP_ANN_L)}: {", ".join(sorted(closes))}')
    print(f'  load time {time.time()-t0:.1f}s')

    def build(mode: str):
        """Build EW portfolio (port, bnh, null, eff_n) for a signal mode."""
        nets, bnhs, nulls = {}, {}, {}
        for sym, s in closes.items():
            nets[sym] = strat_series(s, sym, mode=mode)['net']
            bnhs[sym] = strat_series(s, sym, mode=mode)['bnh']
            nulls[sym] = strat_series(s, sym, mode=mode, invert=True)['net']
        NET = pd.DataFrame(nets).sort_index()
        BNH = pd.DataFrame(bnhs).sort_index()
        NULL = pd.DataFrame(nulls).sort_index()
        active = NET.notna()
        eff = active.sum(axis=1)
        keep = eff >= 5
        return (NET[keep].mean(axis=1), BNH.where(active)[keep].mean(axis=1),
                NULL[keep].mean(axis=1), eff[keep], NET.shape)

    t1 = time.time()
    port, port_bnh, port_null, eff_n, shape = build('long')
    port_ls, _, port_ls_null, _, _ = build('ls')
    print(f'  compute time {time.time()-t1:.2f}s  (matrix {shape[0]}x{shape[1]}, both modes)')
    print(f'  effective N: {eff_n.min()}..{eff_n.max()} instruments')

    def gates(name, p, pnull, pbnh=None):
        section(f'{name}')
        report(f'{name} (full)', p)
        report('NULL (anti-trend)', pnull)
        ng = metrics(p).get('sharpe',0) - metrics(pnull).get('sharpe',0)
        print(f'  null-gap (trend - anti-trend Sharpe): {ng:+.2f}   (directional content)')
        if pbnh is not None:
            report('EW buy-and-hold', pbnh)
            bg = metrics(p).get('sharpe',0) - metrics(pbnh).get('sharpe',0)
            print(f'  B&H-gap (trend - EW B&H Sharpe)     : {bg:+.2f}   (lesson #73 gate: > 0)')
        yrs = p.index.year
        print('  regime:')
        for lab, ya, yb in WINDOWS:
            report('    ' + lab, p[(yrs>=ya)&(yrs<=yb)])

    gates('LONG-ONLY TSMOM (swap-modelled)', port, port_null, port_bnh)
    gates('LONG/SHORT TSMOM (swap-modelled, both legs)', port_ls, port_ls_null)

    section('Swap impact (swap OFF vs ON)')
    for mode, p in [('long', port), ('ls', port_ls)]:
        ns = {}
        for sym, s in closes.items():
            sl, ss = SWAP_ANN_L.get(sym,0.0), SWAP_ANN_S.get(sym,0.0)
            SWAP_ANN_L[sym] = SWAP_ANN_S[sym] = 0.0
            ns[sym] = strat_series(s, sym, mode=mode)['net']
            SWAP_ANN_L[sym], SWAP_ANN_S[sym] = sl, ss
        p_off = pd.DataFrame(ns).sort_index().mean(axis=1).reindex(p.index)
        print(f'  [{mode}] swap OFF Sh {metrics(p_off).get("sharpe",0):+.2f}  '
              f'-> ON Sh {metrics(p).get("sharpe",0):+.2f}  '
              f'(haircut {metrics(p_off).get("sharpe",0)-metrics(p).get("sharpe",0):+.2f})')

    out = os.path.join(_HERE, 'tsmom_revisit_daily.csv')
    pd.DataFrame({'tsmom_long': port, 'tsmom_ls': port_ls}).to_csv(out)
    print(f'\n  saved daily returns -> {out}')
    print(f'  total {time.time()-t0:.1f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
