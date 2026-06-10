#!/usr/bin/env python3
"""XAUUSD intraday mean-reversion — regime-gated high-cadence screen (M5, 2018-26).

Thesis / methodology: experiments/xau_intraday_mr/xau_intraday_mr.md

Question: does fading intraday price EXTENSION on XAU M5 clear cost (~0.5 bps RT),
at high cadence, when GATED by an intraday trend/range regime (Kaufman efficiency
ratio)? The graveyard says unconditional XAU fades get run over by trend/LBMA
flow; the gate is the new ingredient.

Gross-first characterization (no exit params): enumerate fresh |z|>=THR crossings,
fade at t+1 open, measure forward fade-return at horizons {1,3,6,12} bars. Surface
vs (THR x efficiency-ratio bucket x session). Pre-committed gates + holdout +
SPX/NDX cross-instrument confirm.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe \
    experiments/xau_intraday_mr/xau_intraday_mr_demo.py
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

def data_path(sym: str) -> str:
    return os.path.join(_ROOT, 'ohlc_data', f'{sym}_M5.csv')

# ---------------------------------------------------------------------------
# Frozen screen params
# ---------------------------------------------------------------------------
LOOKBACK = 24                 # 2h rolling window for z / efficiency-ratio / atr
THRESHOLDS = (1.0, 1.5, 2.0, 2.5)
HORIZONS = (1, 3, 6, 12)      # bars; primary = 6 (30 min)
PRIMARY_H = 6
GAP_GUARD_MIN = 10.0

# bps RT cost per instrument (live refs: XAU 0.16USD@4500=0.35; SPX ~0.5; NDX ~1.4)
COST = {'XAUUSD': 0.50, 'SPX500': 0.50, 'NDX100': 1.40}
COSTS_SWEEP = (0.35, 0.50, 0.75, 1.00)
COST_SELECT = 0.50

M5_START_YEAR = 2018
DISCOVERY_END_YEAR = 2023
SUBWINDOWS = [('D1 2018-2020', 2018, 2020), ('D2 2021-2022', 2021, 2022),
              ('D3 2023', 2023, 2023)]
HOLDOUT = (2024, 2026)

# gates
G_MIN_N = 300
G_MIN_N_SUB = 60
G_MIN_CADENCE = 150           # events/yr
G_TSTAT = 3.0
HO_SHARPE_BAR = 0.30


def section(t: str) -> None:
    print(f'\n{"=" * 100}\n  {t}\n{"=" * 100}')


def session_of(hr: int) -> str:
    if 22 <= hr or hr < 6:
        return 'ASIA'
    if 6 <= hr < 12:
        return 'LDN'
    if 12 <= hr < 16:
        return 'NYAM'
    return 'NYPM'


def fmt(v, w=7, p=2):
    return f'{v:>+{w}.{p}f}'


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_m5(sym: str) -> pd.DataFrame:
    df = pd.read_csv(data_path(sym), parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'].dt.dayofweek < 5].copy().reset_index(drop=True)
    df['year'] = df['timestamp'].dt.year
    df = df[df['year'] >= M5_START_YEAR].copy().reset_index(drop=True)
    df['hour'] = df['timestamp'].dt.hour
    return df


# ---------------------------------------------------------------------------
# Enumerate extension events with forward fade-returns + regime features.
# numpy inner loop.
# ---------------------------------------------------------------------------
def enumerate_events(df: pd.DataFrame) -> pd.DataFrame:
    o = df['open'].to_numpy(np.float64)
    c = df['close'].to_numpy(np.float64)
    hr = df['hour'].to_numpy()
    yr = df['year'].to_numpy()
    n = len(df)

    tsv = df['timestamp'].values.astype('datetime64[ns]').astype('int64')
    gap_min = np.empty(n, np.float64)
    gap_min[0] = 1e9
    gap_min[1:] = (tsv[1:] - tsv[:-1]) / 6e10

    cs = pd.Series(c)
    mean = cs.rolling(LOOKBACK).mean().to_numpy()
    std = cs.rolling(LOOKBACK).std(ddof=1).to_numpy()
    z = (c - mean) / std

    # Kaufman efficiency ratio (24-bar): |net change| / sum(|bar change|)
    dc = np.abs(np.diff(c, prepend=c[0]))
    vol_sum = pd.Series(dc).rolling(LOOKBACK).sum().to_numpy()
    net_chg = np.abs(c - np.concatenate([np.full(LOOKBACK, np.nan), c[:-LOOKBACK]]))
    er = net_chg / vol_sum

    rets = np.zeros(n)
    rets[1:] = (c[1:] - c[:-1]) / c[:-1]
    atr_bps = pd.Series(rets).rolling(LOOKBACK).std(ddof=1).to_numpy() * 1e4

    az = np.abs(z)
    rows = []
    maxh = max(HORIZONS)
    for thr in THRESHOLDS:
        # fresh crossings: |z|>=thr and prev <thr
        cross = np.zeros(n, bool)
        cross[1:] = (az[1:] >= thr) & (az[:-1] < thr) & np.isfinite(az[1:]) & np.isfinite(az[:-1])
        idx = np.where(cross)[0]
        for t in idx:
            ek = t + 1
            if ek + maxh >= n or not np.isfinite(er[t]):
                continue
            if gap_min[ek] > GAP_GUARD_MIN:
                continue
            entry = o[ek]
            sgn = np.sign(z[t])  # +1 stretched up -> fade short
            # forward fade returns, gap-guarded
            fr = {}
            ok = True
            for h in HORIZONS:
                # ensure contiguous to t+h
                if np.any(gap_min[ek + 1:ek + h + 1] > GAP_GUARD_MIN):
                    ok = False
                    break
                fr[h] = float(-sgn * (c[ek + h] - entry) / entry)
            if not ok:
                continue
            rows.append((thr, int(yr[t]), int(hr[t]), float(az[t]), float(er[t]),
                         float(atr_bps[t]), fr[1], fr[3], fr[6], fr[12]))
    cols = ['thr', 'year', 'hour', 'absz', 'er', 'atr_bps',
            'fr1', 'fr3', 'fr6', 'fr12']
    t = pd.DataFrame(rows, columns=cols)
    if len(t):
        t['session'] = t['hour'].map(session_of)
    return t


# ---------------------------------------------------------------------------
# Stats (cost in bps; forward return is gross fraction)
# ---------------------------------------------------------------------------
def cstat(sub: pd.DataFrame, cost_bps: float, hcol=f'fr{PRIMARY_H}') -> dict:
    if len(sub) == 0:
        return {'n': 0}
    r = sub[hcol].to_numpy() - cost_bps / 1e4
    nn = len(r)
    mu = r.mean()
    sd = r.std(ddof=1) if nn > 1 else 0.0
    t = mu / sd * np.sqrt(nn) if sd > 0 else 0.0
    return {'n': nn, 'mean_bps': mu * 1e4, 'tstat': t, 'wr': float((r > 0).mean()),
            'sd': sd, 'mu': mu}


def ann_sh(sub: pd.DataFrame, cost_bps: float, hcol=f'fr{PRIMARY_H}') -> float:
    if len(sub) < 2:
        return 0.0
    r = sub[hcol].to_numpy() - cost_bps / 1e4
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0
    span = (sub['year'].max() - sub['year'].min() + 1)
    tpy = len(r) / max(span, 1)
    return float(r.mean() / sd * np.sqrt(tpy))


def cadence(sub: pd.DataFrame) -> float:
    if len(sub) == 0:
        return 0.0
    span = sub['year'].max() - sub['year'].min() + 1
    return len(sub) / max(span, 1)


def add_buckets(t, z_edges, er_edges, vol_edges):
    t = t.copy()
    t['z_b'] = pd.cut(t['absz'], z_edges, labels=['z1', 'z2', 'z3', 'z4'])
    t['er_b'] = pd.cut(t['er'], er_edges, labels=['ER1', 'ER2', 'ER3', 'ER4', 'ER5'])
    t['vol_b'] = pd.cut(t['atr_bps'], vol_edges, labels=['V1', 'V2', 'V3', 'V4', 'V5'])
    return t


def horizon_table(disc, cost):
    print(f'\n  -- forward fade-return by horizon (THR pooled, net @ {cost} bps) --')
    print(f'    {"horizon":<8s} {"n":>7s} {"gross_bps":>9s} {"net_bps":>9s} {"tstat":>7s} {"wr%":>5s}')
    for h in HORIZONS:
        g = cstat(disc, 0.0, f'fr{h}'); nb = cstat(disc, cost, f'fr{h}')
        print(f'    h={h:<6d} {g["n"]:>7d} {fmt(g["mean_bps"],9,3)} {fmt(nb["mean_bps"],9,3)} '
              f'{fmt(nb["tstat"],7,2)} {nb["wr"]*100:>5.1f}')


def marginal(disc, col, cost):
    print(f'\n  -- {col} (net @ {cost} bps, h={PRIMARY_H}) --')
    print(f'    {"bucket":<8s} {"n":>7s} {"cad/yr":>7s} {"gross":>8s} {"net":>8s} {"tstat":>7s} {"wr%":>5s}')
    for b in [x for x in disc[col].dropna().unique()]:
        s = disc[disc[col] == b]
        g = cstat(s, 0.0); nb = cstat(s, cost)
        if g['n'] == 0:
            continue
        print(f'    {str(b):<8s} {g["n"]:>7d} {cadence(s):>7.0f} {fmt(g["mean_bps"],8,3)} '
              f'{fmt(nb["mean_bps"],8,3)} {fmt(nb["tstat"],7,2)} {nb["wr"]*100:>5.1f}')


def main() -> int:
    t0 = time.time()
    sym = 'XAUUSD'
    section(f'Load + enumerate extension events — {sym} M5')
    df = load_m5(sym)
    print(f'  bars {len(df):,}  {df["timestamp"].min()} -> {df["timestamp"].max()}')
    ev = enumerate_events(df)
    print(f'  events (all THR): {len(ev):,}')
    print(f'  per-THR counts  : {dict(ev["thr"].value_counts().sort_index())}')

    disc = ev[ev['year'] <= DISCOVERY_END_YEAR].copy()
    ho = ev[ev['year'] >= HOLDOUT[0]].copy()
    print(f'  discovery {len(disc):,}  holdout {len(ho):,}')

    z_q = np.quantile(disc['absz'], [0, .25, .5, .75, 1]); z_q[0]-=1e-9; z_q[-1]+=1e-9
    er_q = np.quantile(disc['er'].dropna(), [0,.2,.4,.6,.8,1]); er_q[0]-=1e-9; er_q[-1]+=1e-9
    v_q = np.quantile(disc['atr_bps'].dropna(), [0,.2,.4,.6,.8,1]); v_q[0]-=1e-9; v_q[-1]+=1e-9
    print(f'  |z| quartiles   : {np.round(z_q,2)}')
    print(f'  ER quintiles    : {np.round(er_q,3)}  (low=ranging, high=trending)')
    disc = add_buckets(disc, z_q, er_q, v_q)
    ho = add_buckets(ho, z_q, er_q, v_q)

    cost = COST[sym]
    section(f'Pooled reversion edge — {sym} DISCOVERY (cost {cost} bps)')
    horizon_table(disc, cost)
    g = cstat(disc, 0.0); print(f'\n  pooled h={PRIMARY_H} GROSS {g["mean_bps"]:+.3f}bps  '
                                f'net@{cost} {cstat(disc,cost)["mean_bps"]:+.3f}bps  '
                                f'cadence {cadence(disc):.0f}/yr')

    section(f'Marginal surface — DISCOVERY (h={PRIMARY_H}, net @ {cost} bps)')
    for col in ['er_b', 'z_b', 'session', 'vol_b', 'thr']:
        marginal(disc, col, cost)

    # The KEY mechanism table: ER x z (does fade work in low-ER, fail in high-ER?)
    section('Trend-gate surface: efficiency-ratio x |z|  (net mean_bps @ cost)')
    print(f'    {"":<6s}' + ''.join(f'{z:>11s}' for z in ['z1','z2','z3','z4']))
    for erb in ['ER1','ER2','ER3','ER4','ER5']:
        line = f'    {erb:<6s}'
        for zb in ['z1','z2','z3','z4']:
            s = disc[(disc['er_b']==erb)&(disc['z_b']==zb)]
            line += f'{cstat(s,cost).get("mean_bps",0):>+8.2f}({len(s)//1000}k)'.rjust(11)
        print(line)

    # ---- Cell grid: THR x er_b x session, pre-committed gates ----
    section('Cell grid — pre-committed robustness gates (DISCOVERY)')
    cells = []
    for thr in THRESHOLDS:
        for erb in ['ER1','ER2','ER3','ER4','ER5']:
            cells.append((f'thr{thr}|{erb}', lambda t,thr=thr,erb=erb:(t['thr']==thr)&(t['er_b']==erb)))
    for thr in THRESHOLDS:
        for s in ['ASIA','LDN','NYAM','NYPM']:
            cells.append((f'thr{thr}|{s}', lambda t,thr=thr,s=s:(t['thr']==thr)&(t['session']==s)))
    for erb in ['ER1','ER2','ER3','ER4','ER5']:
        for s in ['ASIA','LDN','NYAM','NYPM']:
            cells.append((f'{erb}|{s}', lambda t,erb=erb,s=s:(t['er_b']==erb)&(t['session']==s)))

    results = []
    for lab, fn in cells:
        d = disc[fn(disc)]
        n = len(d)
        if n < G_MIN_N or cadence(d) < G_MIN_CADENCE:
            results.append({'label':lab,'n':n,'robust':False}); continue
        sub_ok = True; sub_sh = []
        for wl,ya,yb in SUBWINDOWS:
            s = d[(d['year']>=ya)&(d['year']<=yb)]
            if len(s) < G_MIN_N_SUB or cstat(s,COST_SELECT)['mean_bps'] <= 0:
                sub_ok=False; break
            sub_sh.append(ann_sh(s,COST_SELECT))
        cs = cstat(d, COST_SELECT)
        r = {'label':lab,'n':n,'cad':cadence(d),'tstat':cs['tstat'],
             'mean_bps':cs['mean_bps'],'wr':cs['wr'],'sub_ok':sub_ok,
             'sh':ann_sh(d,COST_SELECT),'min_sub':min(sub_sh) if sub_sh else -9,
             'robust': sub_ok and cs['tstat']>=G_TSTAT}
        results.append(r)
    robust = [r for r in results if r.get('robust')]
    crossw = [r for r in results if r.get('sub_ok')]
    crossw.sort(key=lambda r:r.get('min_sub',-9), reverse=True)
    print(f'  n_trials {len(cells)}  | n>=300 & cad>=150: {sum(1 for r in results if r.get("cad",0)>=G_MIN_CADENCE and r["n"]>=G_MIN_N)}'
          f'  | all-sub>0: {len(crossw)}  | ROBUST: {len(robust)}')
    print(f'\n  cells clearing cross-window gate (ranked worst-window Sharpe):')
    print(f'    {"cell":<16s} {"n":>6s} {"cad":>5s} {"tstat":>6s} {"net_bps":>8s} {"Sh":>6s} {"minSub":>7s} robust')
    for r in crossw[:25]:
        print(f'    {r["label"]:<16s} {r["n"]:>6d} {r["cad"]:>5.0f} {fmt(r["tstat"],6,2)} '
              f'{fmt(r["mean_bps"],8,3)} {fmt(r["sh"],6,2)} {fmt(r["min_sub"],7,2)} '
              f'{"YES" if r["robust"] else "no"}')

    # ---- Single draw + holdout ----
    section('Single pre-committed draw -> HOLDOUT 2024-2026')
    if not robust:
        print('  >>> ZERO robust cells. Pre-committed verdict: NEGATIVE.')
        print('  >>> High-cadence XAU intraday MR has no cost-survivable, cross-regime')
        print('  >>> edge even under a trend gate. Closes the frequent-XAU question.')
        # still report the best cross-window near-miss on holdout for the writeup
        if crossw:
            r = crossw[0]; fn = dict(cells)[r['label']]
            h = ho[fn(ho)]
            print(f'\n  (info) best near-miss {r["label"]} on HOLDOUT: '
                  f'n {len(h)} net@{COST_SELECT} {cstat(h,COST_SELECT).get("mean_bps",0):+.3f}bps '
                  f'Sh {ann_sh(h,COST_SELECT):+.2f} tstat {cstat(h,COST_SELECT).get("tstat",0):+.2f}')
        print(f'\n  total {time.time()-t0:.1f}s')
        return 0

    robust.sort(key=lambda r:r['min_sub'], reverse=True)
    pick = robust[0]; fn = dict(cells)[pick['label']]
    print(f'  SELECTED {pick["label"]}: DISC n {pick["n"]} cad {pick["cad"]:.0f}/yr '
          f'tstat {pick["tstat"]:+.2f} net {pick["mean_bps"]:+.3f}bps Sh {pick["sh"]:+.2f}')
    h = ho[fn(ho)]
    print(f'\n  HOLDOUT:')
    for cb in COSTS_SWEEP:
        cs = cstat(h, cb)
        print(f'    cost {cb:.2f}  n {cs.get("n",0):>5d}  net {fmt(cs.get("mean_bps",0),8,3)}bps  '
              f'tstat {fmt(cs.get("tstat",0),6,2)}  Sh {fmt(ann_sh(h,cb),6,2)}')
    sh_h = ann_sh(h, COST_SELECT); m_h = cstat(h, COST_SELECT).get('mean_bps',0)
    ho_pass = sh_h > HO_SHARPE_BAR and m_h > 0
    print(f'  >>> HOLDOUT {"PASS" if ho_pass else "FAIL"} (Sh {sh_h:+.2f} bar>{HO_SHARPE_BAR}, net {m_h:+.3f})')

    # ---- Cross-instrument confirm ----
    section('Cross-instrument confirm — SPX500 / NDX100 (selected ER/session/THR regime)')
    for xsym in ['SPX500', 'NDX100']:
        try:
            xdf = load_m5(xsym); xev = enumerate_events(xdf)
            xev = add_buckets(xev, z_q, er_q, v_q)  # z/er unit-free; vol approximate
            xc = xev[fn(xev)]
            cc = COST[xsym]
            print(f'  {xsym}: n {len(xc)}  net@{cc} {cstat(xc,cc).get("mean_bps",0):+.3f}bps  '
                  f'tstat {cstat(xc,cc).get("tstat",0):+.2f}  Sh {ann_sh(xc,cc):+.2f}  '
                  f'cad {cadence(xc):.0f}/yr')
        except Exception as e:
            print(f'  {xsym}: error {e}')
    print(f'\n  total {time.time()-t0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
