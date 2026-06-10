#!/usr/bin/env python3
"""Cointegrated-pair spread mean-reversion — the one Eightcap-native non-structural
family left untested (market-neutral; orthogonal to the all-directional live book).

Why not already in the graveyard: equity_pairs tested single STOCKS (decayed);
cross_asset_lead_lag tested TIMING (HFT-arbed); eth_btc_ratio was crypto re-rating.
Cointegrated liquid INDEX/METAL pairs (β-hedged spread reversion over days) is
genuinely untested. Honest prior: low (legs may be too correlated for tradeable
spread vol after 2-leg cost, or the spread trends instead of reverting).

Method (no-leak): spread = logA - β·logB, β = rolling OLS over W_BETA (lagged);
z = rolling z of spread over W_Z (lagged). Enter -sign(z) when |z|>=Z_IN, hold to
|z|<=Z_OUT. Daily P&L = pos_{t-1}·(retA_t - β_{t-1}·retB_t). Cost = both legs.
Half-life from AR(1) of the spread = cointegration/MR proxy (dependency-free).

Run: PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/index_pairs_mr/index_pairs_mr_demo.py
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)
from data import fetch_ohlc  # noqa: E402

START, END = '2018-01-01', '2026-12-31'
W_BETA, W_Z = 120, 60
Z_IN, Z_OUT = 2.0, 0.5
ANN = 252
# RT cost per leg (bps) — index CFDs tight, XAG wider
COST_LEG = {'SPX500':1.5,'NDX100':1.5,'GER40':1.5,'FRA40':2.0,'EUSTX50':2.0,
            'UK100':2.0,'XAUUSD':0.5,'XAGUSD':2.0,'JPN225':2.0}
PAIRS = [('GER40','EUSTX50'),('SPX500','NDX100'),('GER40','FRA40'),
         ('EUSTX50','FRA40'),('XAUUSD','XAGUSD'),('UK100','EUSTX50'),
         ('SPX500','GER40'),('NDX100','GER40')]
WINDOWS = [('2018-2020',2018,2020),('2021-2022',2021,2022),
           ('2023-2024',2023,2024),('2025-2026',2025,2026)]
HOLDOUT = (2025, 2026)


def section(t): print(f'\n{"="*92}\n  {t}\n{"="*92}')


def load_close(sym):
    try:
        df = fetch_ohlc(sym, 'D1', START, END)
    except Exception:
        return None
    if df is None or df.empty or len(df) < 400:
        return None
    idx = pd.to_datetime(df['timestamp'], utc=True).dt.normalize()
    s = pd.Series(df['close'].to_numpy(float), index=idx).sort_index()
    return s[~s.index.duplicated(keep='last')]


def half_life(spread: np.ndarray) -> float:
    s = spread[np.isfinite(spread)]
    if len(s) < 50:
        return np.nan
    ds = s[1:] - s[:-1]
    lag = s[:-1]
    A = np.vstack([np.ones_like(lag), lag]).T
    coef, *_ = np.linalg.lstsq(A, ds, rcond=None)
    phi = coef[1]  # ds = a + phi*lag  -> AR(1) coef = 1+phi
    if phi >= 0:
        return np.inf
    return float(-np.log(2) / np.log(1 + phi))


def ann_sh(r):
    r = r[np.isfinite(r)]
    if len(r) < 20 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(ANN))


def simulate(a: pd.Series, b: pd.Series, ca: float, cb: float, fade=False):
    df = pd.concat([a.rename('a'), b.rename('b')], axis=1).dropna()
    if len(df) < W_BETA + W_Z + 50:
        return None
    la = np.log(df['a'].to_numpy()); lb = np.log(df['b'].to_numpy())
    yrs = df.index.year.to_numpy()
    n = len(la)
    # rolling beta (cov/var) over W_BETA, value at t uses [t-W_BETA, t-1]
    beta = np.full(n, np.nan)
    for t in range(W_BETA, n):
        x = lb[t-W_BETA:t]; y = la[t-W_BETA:t]
        v = x.var()
        if v > 0:
            beta[t] = np.cov(x, y, ddof=1)[0,1] / v
    spread = la - beta*lb
    sp = pd.Series(spread)
    smean = sp.rolling(W_Z).mean().to_numpy()
    sstd = sp.rolling(W_Z).std(ddof=1).to_numpy()
    z = (spread - smean) / sstd
    # daily spread return (log) using lagged beta
    ret_a = np.diff(la, prepend=la[0]); ret_b = np.diff(lb, prepend=lb[0])
    bl = np.concatenate([[np.nan], beta[:-1]])  # beta_{t-1}
    spread_ret = ret_a - bl*ret_b

    # state machine on z_{t-1}
    pos = np.zeros(n)
    cur = 0.0
    for t in range(1, n):
        zt = z[t-1]
        if not np.isfinite(zt):
            cur = 0.0
        elif cur == 0.0:
            if zt >= Z_IN: cur = -1.0
            elif zt <= -Z_IN: cur = 1.0
        else:
            if abs(zt) <= Z_OUT: cur = 0.0
        pos[t] = cur
    if fade:
        pos = -pos
    dpos = np.abs(np.diff(pos, prepend=0.0))
    cost = dpos * ((ca + cb) / 2.0) / 1e4
    strat = pos * spread_ret - cost
    strat = strat[np.isfinite(strat)]
    yrs2 = yrs[np.isfinite(pos*spread_ret)] if len(yrs)==len(strat) else yrs[-len(strat):]
    n_trades = int((np.diff(pos) != 0).sum())
    return {'strat': strat, 'years': yrs[-len(strat):], 'spread': spread,
            'n_trades': n_trades, 'hl': half_life(spread)}


def main():
    section('Cointegrated index/metal pair spread-MR')
    print(f'  W_beta={W_BETA} W_z={W_Z} Z_in={Z_IN} Z_out={Z_OUT} | cost=both legs')
    closes = {}
    for s in {x for p in PAIRS for x in p}:
        c = load_close(s)
        if c is not None:
            closes[s] = c
    print(f'  loaded: {sorted(closes)}')

    print(f'\n  {"pair":<18s} {"half-life":>9s} {"trades":>6s} {"Sh full":>8s} '
          f'{"null Sh":>8s} {"gap":>6s} {"HO Sh":>7s} verdict')
    print('  '+'-'*86)
    rows = []
    for A, B in PAIRS:
        if A not in closes or B not in closes:
            print(f'  {A}/{B:<10s} missing data'); continue
        r = simulate(closes[A], closes[B], COST_LEG.get(A,2), COST_LEG.get(B,2))
        rn = simulate(closes[A], closes[B], COST_LEG.get(A,2), COST_LEG.get(B,2), fade=True)
        if r is None:
            print(f'  {A}/{B:<10s} insufficient'); continue
        sh = ann_sh(r['strat']); shn = ann_sh(rn['strat']) if rn else 0
        yrs = r['years']; ho = (yrs>=HOLDOUT[0])
        sh_ho = ann_sh(r['strat'][ho[-len(r['strat']):]] if len(ho)>=len(r['strat']) else r['strat'])
        gap = sh - shn
        hl = r['hl']
        verd = 'PASS' if (sh>0.30 and sh_ho>0 and gap>0.3 and r['n_trades']>=30) else 'fail'
        print(f'  {A+"/"+B:<18s} {hl:>9.1f} {r["n_trades"]:>6d} {sh:>+8.2f} '
              f'{shn:>+8.2f} {gap:>+6.2f} {sh_ho:>+7.2f} {verd}')
        rows.append((A,B,r,sh,shn,gap,sh_ho))

    # regime breakdown for any pair with full Sh>0.2
    section('Regime breakdown (pairs with full Sh > +0.20)')
    for A,B,r,sh,shn,gap,sh_ho in rows:
        if sh <= 0.20: continue
        print(f'\n  {A}/{B}  (half-life {r["hl"]:.0f}d, {r["n_trades"]} trades)')
        yrs = r['years']; strat = r['strat']
        for lab,ya,yb in WINDOWS:
            m = (yrs>=ya)&(yrs<=yb)
            if m.sum()<20: print(f'    {lab:<12s} n={m.sum()}'); continue
            print(f'    {lab:<12s} Sh {ann_sh(strat[m]):>+6.2f}  n {m.sum()}')

    section('Verdict')
    passing = [x for x in rows if x[3]>0.30 and x[6]>0 and x[4]<x[3]-0.3 and x[2]['n_trades']>=30]
    if not passing:
        print('  >>> NO pair clears (Sh>+0.30, HO>0, null-gap>+0.3, trades>=30).')
        print('  >>> Cointegration spread-MR REJECT on Eightcap index/metal pairs.')
    else:
        print(f'  >>> {len(passing)} pair(s) clear — candidates for Phase 2:')
        for A,B,r,sh,shn,gap,sh_ho in passing:
            print(f'      {A}/{B}: Sh {sh:+.2f} HO {sh_ho:+.2f} gap {gap:+.2f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
