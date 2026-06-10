#!/usr/bin/env python3
"""XAUUSD 3-bar FVG — full-history characterization screen (M5, 2005-2026).

Thesis / methodology: experiments/xau_imbalance_screen/xau_imbalance_screen.md

NOT a parameter optimizer. Enumerates EVERY 3-bar FVG across all 24h under a
single FROZEN canonical exit rule, attaches a feature vector to each entered
trade, and measures the forward-edge SURFACE as a function of those features.
One pre-committed config is drawn from the most-stable robust region at the end
and validated once on the untouched 2024-2026 tail.

Frozen canonical rule (NOT swept): retest=6, hold=6, stop=0.5*width past far edge,
entry=next-bar-open, direction=FVG-direction (continuation), geometry-guard ON,
gap-guard (terminate scan if bar-to-bar gap > 10 min).

Cost is NOT baked in: gross + entry_price stored; net@cost computed at analysis.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe \
    experiments/xau_imbalance_screen/xau_imbalance_screen_demo.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)  # for `import data` if ever needed
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_M5.csv')

# ---------------------------------------------------------------------------
# Frozen canonical rule (see thesis — NOT swept during characterization)
# ---------------------------------------------------------------------------
RETEST_WINDOW = 6
HOLD_BARS = 6
STOP_MULT = 0.5
GAP_GUARD_MIN = 10.0          # terminate retest/hold scan if bar gap > 10 min
ATR_WINDOW = 20

# Cost grid — BPS round-trip (NOT fixed USD: gold ran $1160->$5588 within the M5
# window, so a fixed-USD spread is confounded with the secular bull. bps is the
# fair cross-time / forward-deploy cost. Live ref: 0.16 USD @ $4500 = 0.35 bps;
# all-in deploy ~0.5 bps. Sweep brackets the realistic range.)
COSTS = (0.35, 0.50, 0.75, 1.00)
COST_SELECT = 0.50            # forward-deploy realistic cost (bps RT)

# M5 coverage starts 2018 (pre-2018 in the CSV is daily/hourly bars mislabeled
# M5 — NO real intraday gold before 2018). Discovery 2018-2023, holdout 2024-2026.
M5_START_YEAR = 2018
DISCOVERY_END_YEAR = 2023
SUBWINDOWS = [
    ('D1 2018-2020', 2018, 2020),   # range -> covid vol
    ('D2 2021-2022', 2021, 2022),   # vol regime
    ('D3 2023', 2023, 2023),        # early secular bull
]
HOLDOUT = ('H 2024-2026', 2024, 2026)

# Pre-committed robustness gates (DO NOT REVISE AFTER RUN)
G_MIN_N = 300
G_MIN_N_SUB = 60
G_TSTAT = 3.0
G_FADE_GAP = 0.40
HO_SHARPE_BAR = 0.30

# Session buckets (UTC hour -> label)
def session_of(hr: int) -> str:
    if 22 <= hr or hr < 6:
        return 'ASIA'
    if 6 <= hr < 12:
        return 'LDN'
    if 12 <= hr < 16:
        return 'NYAM'
    return 'NYPM'   # 16-21


def section(t: str) -> None:
    print(f'\n{"=" * 100}\n  {t}\n{"=" * 100}')


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def load_m5() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    dow = df['timestamp'].dt.dayofweek
    df = df[dow < 5].copy().reset_index(drop=True)
    df['year'] = df['timestamp'].dt.year
    df = df[df['year'] >= M5_START_YEAR].copy().reset_index(drop=True)  # real M5 only
    df['hour'] = df['timestamp'].dt.hour
    df['dow'] = df['timestamp'].dt.dayofweek
    return df


# ---------------------------------------------------------------------------
# Enumerator: one trade per FVG-that-retests, with feature vector.
# numpy inner loop (CLAUDE.md: prioritize numpy in hot path).
# ---------------------------------------------------------------------------
def enumerate_fvgs(df: pd.DataFrame, fade: bool = False) -> pd.DataFrame:
    o = df['open'].to_numpy(np.float64)
    h = df['high'].to_numpy(np.float64)
    l = df['low'].to_numpy(np.float64)
    c = df['close'].to_numpy(np.float64)
    hr = df['hour'].to_numpy()
    dw = df['dow'].to_numpy()
    yr = df['year'].to_numpy()
    n = len(df)

    # bar-to-bar gap in minutes (gap[k] = ts[k]-ts[k-1])
    tsv = df['timestamp'].values.astype('datetime64[ns]').astype('int64')
    gap_min = np.empty(n, np.float64)
    gap_min[0] = 1e9
    gap_min[1:] = (tsv[1:] - tsv[:-1]) / 6e10

    # ATR20 proxy: rolling std of M5 returns * price (shift 1, no leak) — matches
    # prior xau_imbalance / xau_session 'ny_atr_pct' convention, vectorized once.
    rets = np.zeros(n, np.float64)
    rets[1:] = (c[1:] - c[:-1]) / c[:-1]
    roll_std = pd.Series(rets).rolling(ATR_WINDOW).std(ddof=1).shift(1).to_numpy()
    atr = roll_std * c

    # EMA20 / EMA60 (trend context), vectorized via pandas ewm once.
    ema20 = pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy()
    ema60 = pd.Series(c).ewm(span=60, adjust=False).mean().to_numpy()
    trend_sign = np.sign(ema20 - ema60)

    # Candidate FVG bars (vectorized detection), then loop only candidates.
    bull_mask = np.zeros(n, bool)
    bear_mask = np.zeros(n, bool)
    bull_mask[2:] = h[:-2] < l[2:]
    bear_mask[2:] = l[:-2] > h[2:]
    cand = np.where(bull_mask | bear_mask)[0]

    rows = []
    for i in cand:
        bull = bull_mask[i]
        # FVG zone & width
        if bull:
            fvg_lo, fvg_hi = h[i - 2], l[i]
        else:
            fvg_lo, fvg_hi = h[i], l[i - 2]
        fvg_width = fvg_hi - fvg_lo
        if fvg_width <= 0 or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue

        # Retest scan (i, i+RETEST_WINDOW]; terminate on a time-gap (market closed)
        retest_k = -1
        for k in range(i + 1, min(i + 1 + RETEST_WINDOW, n)):
            if gap_min[k] > GAP_GUARD_MIN:
                break
            if bull and l[k] <= fvg_hi:
                retest_k = k
                break
            if (not bull) and h[k] >= fvg_lo:
                retest_k = k
                break
        if retest_k < 0:
            continue

        ek = retest_k + 1
        if ek >= n or gap_min[ek] > GAP_GUARD_MIN:
            continue
        entry_price = o[ek]

        # Direction actually traded (continuation, or fade for the null pass)
        go_long = bull if not fade else (not bull)
        if go_long:
            stop_level = fvg_lo - STOP_MULT * fvg_width
            if entry_price <= stop_level:   # geometry guard
                continue
        else:
            stop_level = fvg_hi + STOP_MULT * fvg_width
            if entry_price >= stop_level:   # geometry guard
                continue

        # Exit: stop / time / gap, scanning ek .. ek+HOLD_BARS-1
        last_k = min(ek + HOLD_BARS - 1, n - 1)
        exit_price = np.nan
        exit_reason = ''
        for k in range(ek, last_k + 1):
            if k > ek and gap_min[k] > GAP_GUARD_MIN:
                exit_price = c[k - 1]
                exit_reason = 'gap'
                break
            if go_long and l[k] <= stop_level:
                exit_price = stop_level
                exit_reason = 'stop'
                break
            if (not go_long) and h[k] >= stop_level:
                exit_price = stop_level
                exit_reason = 'stop'
                break
        if exit_reason == '':
            exit_price = c[last_k]
            exit_reason = 'time'

        if go_long:
            gross = (exit_price - entry_price) / entry_price
        else:
            gross = (entry_price - exit_price) / entry_price

        rows.append((
            int(yr[i]), int(hr[i]), int(dw[i]),
            1 if bull else 0,
            float(fvg_width / entry_price * 1e4),   # gap_bps
            float(fvg_width / atr[i]),              # gap_atr
            float(atr[i] / c[i] * 1e4),             # atr_bps (vol level)
            int(retest_k - i),                      # retest_age (1..6)
            int(trend_sign[i]),                     # +1 up / -1 down / 0
            float(gross),
            float(entry_price),
            exit_reason,
        ))

    cols = ['year', 'hour', 'dow', 'bull', 'gap_bps', 'gap_atr', 'atr_bps',
            'retest_age', 'trend_sign', 'gross', 'entry_price', 'exit_reason']
    t = pd.DataFrame(rows, columns=cols)
    if len(t) == 0:
        return t
    t['session'] = t['hour'].map(session_of)
    t['macro'] = t['hour'].isin([12, 13, 14, 15])
    t['dir'] = np.where(t['bull'] == 1, 'bull', 'bear')
    t['trend_align'] = np.where(
        (t['trend_sign'] > 0) & (t['bull'] == 1) |
        (t['trend_sign'] < 0) & (t['bull'] == 0), 'aligned',
        np.where(t['trend_sign'] == 0, 'flat', 'counter'))
    # retest age bucket
    t['age_b'] = pd.cut(t['retest_age'], [0, 2, 4, 6],
                        labels=['fast1-2', 'mid3-4', 'slow5-6'])
    return t


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------
def net_at(g: np.ndarray, cost_bps: float) -> np.ndarray:
    return g - cost_bps / 1e4


def cell_stats(sub: pd.DataFrame, cost: float) -> dict:
    if len(sub) == 0:
        return {'n': 0}
    r = net_at(sub['gross'].to_numpy(), cost)
    n = len(r)
    mu = r.mean()
    sd = r.std(ddof=1) if n > 1 else 0.0
    tstat = mu / sd * np.sqrt(n) if sd > 0 else 0.0
    return {'n': n, 'mean_bps': mu * 1e4, 'tstat': tstat, 'sd': sd, 'mu': mu,
            'wr': float((r > 0).mean())}


def ann_sharpe(sub: pd.DataFrame, cost: float, span_days: float) -> float:
    if len(sub) < 2 or span_days <= 0:
        return 0.0
    r = net_at(sub['gross'].to_numpy(), cost)
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0
    tpy = len(r) / (span_days / 365.25)
    return float(r.mean() / sd * np.sqrt(tpy))


def fmt(v, w=7, p=2):
    return f'{v:>+{w}.{p}f}'


# ---------------------------------------------------------------------------
# Marginal surface: one feature at a time, cont vs fade null.
# ---------------------------------------------------------------------------
def marginal(cont: pd.DataFrame, fade: pd.DataFrame, col: str, cost: float):
    print(f'\n  -- marginal: {col}  (gross + net @ {cost:.2f} bps RT) --')
    print(f'    {"bucket":<12s} {"n":>7s} {"gross_bps":>9s} {"net_bps":>9s} '
          f'{"tstat":>7s} {"wr%":>5s} {"fade_gr":>9s} {"dir_edge":>9s}')
    cats = cont[col].dropna().unique()
    try:
        cats = sorted(cats)
    except TypeError:
        cats = list(cats)
    for b in cats:
        cs = cell_stats(cont[cont[col] == b], cost)
        gr = cell_stats(cont[cont[col] == b], 0.0)
        fs = cell_stats(fade[fade[col] == b], 0.0)
        if cs['n'] == 0:
            continue
        # directional edge = gross continuation - gross fade (raw mechanism content)
        dir_edge = gr['mean_bps'] - fs.get('mean_bps', 0.0)
        print(f'    {str(b):<12s} {cs["n"]:>7d} {fmt(gr["mean_bps"],9,3)} '
              f'{fmt(cs["mean_bps"],9,3)} {fmt(cs["tstat"],7,2)} {cs["wr"]*100:>5.1f} '
              f'{fmt(fs.get("mean_bps",0),9,3)} {fmt(dir_edge,9,3)}')


# ---------------------------------------------------------------------------
# Cell selection across a pre-committed grid
# ---------------------------------------------------------------------------
def add_buckets(t: pd.DataFrame, gap_edges, vol_edges) -> pd.DataFrame:
    t = t.copy()
    t['gap_b'] = pd.cut(t['gap_bps'], gap_edges,
                        labels=['tiny', 'small', 'med', 'large'])
    t['vol_b'] = pd.cut(t['atr_bps'], vol_edges,
                        labels=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
    return t


def span_days(sub: pd.DataFrame, df: pd.DataFrame) -> float:
    # approximate span via year range (cheap, good enough for ann factor)
    if len(sub) == 0:
        return 0.0
    return (sub['year'].max() - sub['year'].min() + 1) * 365.25


def evaluate_cell(disc_c, disc_f, mask_fn, label):
    """Return robustness dict for a cell on DISCOVERY. mask_fn(t)->bool Series."""
    c_all = disc_c[mask_fn(disc_c)]
    f_all = disc_f[mask_fn(disc_f)]
    n = len(c_all)
    res = {'label': label, 'n': n, 'robust': False}
    if n < G_MIN_N:
        return res
    # per-subwindow
    sub_ok = True
    sub_sh = []
    for wlab, ya, yb in SUBWINDOWS:
        s = c_all[(c_all['year'] >= ya) & (c_all['year'] <= yb)]
        if len(s) < G_MIN_N_SUB:
            sub_ok = False
            break
        cs = cell_stats(s, COST_SELECT)
        if cs['mean_bps'] <= 0:
            sub_ok = False
            break
        sub_sh.append(ann_sharpe(s, COST_SELECT, (yb - ya + 1) * 365.25))
    res['sub_ok'] = sub_ok
    if not sub_ok:
        return res
    cs = cell_stats(c_all, COST_SELECT)
    fs = cell_stats(f_all, COST_SELECT)
    # pooled fade Sharpe gap
    sh_c = ann_sharpe(c_all, COST_SELECT, span_days(c_all, None))
    sh_f = ann_sharpe(f_all, COST_SELECT, span_days(f_all, None))
    res.update({'tstat': cs['tstat'], 'mean_bps': cs['mean_bps'],
                'sh_c': sh_c, 'sh_f': sh_f, 'fade_gap': sh_c - sh_f,
                'min_sub_sh': min(sub_sh), 'sub_sh': sub_sh, 'wr': cs['wr']})
    res['robust'] = (cs['tstat'] >= G_TSTAT and (sh_c - sh_f) > G_FADE_GAP)
    return res


def main() -> int:
    t0 = time.time()
    section('Load XAUUSD M5')
    df = load_m5()
    print(f'  bars {len(df):,}  range {df["timestamp"].min()} -> {df["timestamp"].max()}')

    section('Enumerate ALL 3-bar FVGs (continuation + fade null), 24h, full history')
    t1 = time.time()
    cont = enumerate_fvgs(df, fade=False)
    fade = enumerate_fvgs(df, fade=True)
    print(f'  continuation trades : {len(cont):,}')
    print(f'  fade(null) trades   : {len(fade):,}')
    print(f'  enumerate time      : {time.time()-t1:.1f}s')
    print(f'  exit-reason mix     : {dict(cont["exit_reason"].value_counts())}')
    print(f'  direction mix       : {dict(cont["dir"].value_counts())}')

    # discovery / holdout split
    disc_c = cont[cont['year'] <= DISCOVERY_END_YEAR].copy()
    disc_f = fade[fade['year'] <= DISCOVERY_END_YEAR].copy()
    ho_c = cont[cont['year'] >= HOLDOUT[1]].copy()
    ho_f = fade[fade['year'] >= HOLDOUT[1]].copy()
    print(f'  discovery trades    : {len(disc_c):,}  holdout trades: {len(ho_c):,}')

    # discovery-derived bucket thresholds (no holdout lookahead)
    gap_q = np.quantile(disc_c['gap_bps'], [0, .25, .5, .75, 1.0])
    gap_q[0] -= 1e-9; gap_q[-1] += 1e-9
    vol_q = np.quantile(disc_c['atr_bps'], [0, .2, .4, .6, .8, 1.0])
    vol_q[0] -= 1e-9; vol_q[-1] += 1e-9
    print(f'  gap_bps quartiles   : {np.round(gap_q,2)}')
    print(f'  atr_bps quintiles   : {np.round(vol_q,2)}')

    disc_c = add_buckets(disc_c, gap_q, vol_q)
    disc_f = add_buckets(disc_f, gap_q, vol_q)
    ho_c = add_buckets(ho_c, gap_q, vol_q)
    ho_f = add_buckets(ho_f, gap_q, vol_q)

    # ----- POOLED baseline (all FVGs, no conditioning) for reference -----
    section('Pooled reference (ALL FVGs, no conditioning) — DISCOVERY')
    grc = cell_stats(disc_c, 0.0)
    grf = cell_stats(disc_f, 0.0)
    print(f'  GROSS  n {grc["n"]:>6d}  cont {fmt(grc["mean_bps"],8,3)}bps  '
          f'fade {fmt(grf["mean_bps"],8,3)}bps  dir_edge {fmt(grc["mean_bps"]-grf["mean_bps"],7,3)}bps  '
          f'(raw mechanism content, pre-cost)')
    for cost in COSTS:
        cs = cell_stats(disc_c, cost)
        sh = ann_sharpe(disc_c, cost, span_days(disc_c, None))
        fs = cell_stats(disc_f, cost)
        print(f'  cost {cost:.2f}  n {cs["n"]:>6d}  mean {fmt(cs["mean_bps"],8,3)}bps  '
              f'tstat {fmt(cs["tstat"],6,2)}  Sh {fmt(sh,6,2)}  wr {cs["wr"]*100:4.1f}%  '
              f'fade_mean {fmt(fs["mean_bps"],8,3)}bps')

    # ----- MARGINAL surfaces (the characterization map) -----
    section(f'Marginal forward-edge surface — DISCOVERY (net @ {COST_SELECT} USD RT)')
    for col in ['session', 'dir', 'age_b', 'gap_b', 'vol_b', 'trend_align', 'macro', 'dow']:
        marginal(disc_c, disc_f, col, COST_SELECT)

    # per-subwindow stability of the two prior-known marginals (gap_b, age_b)
    section('Cross-cycle stability of key marginals (mean_bps @ 0.30) — DISCOVERY')
    for col in ['gap_b', 'age_b', 'session']:
        print(f'\n  -- {col} x sub-window --')
        hdr = '    {:<10s}'.format('bucket') + ''.join(f'{w[0]:>14s}' for w in SUBWINDOWS)
        print(hdr)
        for b in [x for x in disc_c[col].dropna().unique()]:
            line = f'    {str(b):<10s}'
            for wlab, ya, yb in SUBWINDOWS:
                s = disc_c[(disc_c[col] == b) & (disc_c['year'] >= ya) & (disc_c['year'] <= yb)]
                cs = cell_stats(s, COST_SELECT)
                line += f'{cs.get("mean_bps",0):>+10.3f}({cs["n"]:>4d})'.rjust(14)
            print(line)

    # ----- CELL GRID + pre-committed selection -----
    section('Cell grid — pre-committed robustness gates (DISCOVERY)')
    cells = []
    sessions = ['ASIA', 'LDN', 'NYAM', 'NYPM']
    gaps = ['tiny', 'small', 'med', 'large']
    ages = ['fast1-2', 'mid3-4', 'slow5-6']
    vols = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']
    # session x gap
    for s in sessions:
        for g in gaps:
            cells.append((f'{s}|{g}', lambda t, s=s, g=g: (t['session'] == s) & (t['gap_b'] == g)))
    # session x age
    for s in sessions:
        for a in ages:
            cells.append((f'{s}|{a}', lambda t, s=s, a=a: (t['session'] == s) & (t['age_b'] == a)))
    # gap x age
    for g in gaps:
        for a in ages:
            cells.append((f'{g}|{a}', lambda t, g=g, a=a: (t['gap_b'] == g) & (t['age_b'] == a)))
    # session x vol
    for s in sessions:
        for v in vols:
            cells.append((f'{s}|{v}', lambda t, s=s, v=v: (t['session'] == s) & (t['vol_b'] == v)))

    n_trials = len(cells)
    results = [evaluate_cell(disc_c, disc_f, fn, lab) for lab, fn in cells]
    robust = [r for r in results if r.get('robust')]
    print(f'  n_trials (cells tested) : {n_trials}')
    print(f'  cells passing n>=300    : {sum(1 for r in results if r["n"]>=G_MIN_N)}')
    print(f'  cells passing all-4-sub>0: {sum(1 for r in results if r.get("sub_ok"))}')
    print(f'  ROBUST cells            : {len(robust)}')

    # show the survivors (and near-misses that cleared the cross-cycle gate)
    cross = [r for r in results if r.get('sub_ok')]
    cross.sort(key=lambda r: r.get('min_sub_sh', -9), reverse=True)
    print(f'\n  cells clearing the cross-cycle (all-4-windows>0) gate, '
          f'ranked by worst-window Sharpe:')
    print(f'    {"cell":<14s} {"n":>6s} {"tstat":>6s} {"mean_bps":>9s} '
          f'{"shC":>6s} {"shF":>6s} {"fgap":>6s} {"minSub":>7s} robust')
    for r in cross[:25]:
        print(f'    {r["label"]:<14s} {r["n"]:>6d} {fmt(r["tstat"],6,2)} '
              f'{fmt(r["mean_bps"],9,3)} {fmt(r["sh_c"],6,2)} {fmt(r["sh_f"],6,2)} '
              f'{fmt(r["fade_gap"],6,2)} {fmt(r["min_sub_sh"],7,2)} '
              f'{"YES" if r["robust"] else "no"}')

    # ----- SINGLE DRAW + holdout validation -----
    section('Single pre-committed draw -> HOLDOUT 2024-2026 validation')
    if not robust:
        print('  >>> ZERO robust cells. Pre-committed verdict: NEGATIVE.')
        print('  >>> XAU M5 3-bar FVG continuation has no cross-cycle-stable,')
        print('  >>> cost-survivable directional edge in any feature region.')
        print(f'\n  total time {time.time()-t0:.1f}s')
        return 0

    robust.sort(key=lambda r: r['min_sub_sh'], reverse=True)
    pick = robust[0]
    print(f'  SELECTED cell (max worst-window Sharpe): {pick["label"]}')
    print(f'    discovery: n {pick["n"]}  tstat {pick["tstat"]:+.2f}  '
          f'mean {pick["mean_bps"]:+.3f}bps  shC {pick["sh_c"]:+.2f}  '
          f'fade_gap {pick["fade_gap"]:+.2f}  minSub Sh {pick["min_sub_sh"]:+.2f}')

    # rebuild the mask for the picked label
    pick_fn = dict(cells)[pick['label']]
    ho_cell_c = ho_c[pick_fn(ho_c)]
    ho_cell_f = ho_f[pick_fn(ho_f)]
    print(f'\n  HOLDOUT 2024-2026 (untouched):')
    for cost in COSTS:
        cs = cell_stats(ho_cell_c, cost)
        sh = ann_sharpe(ho_cell_c, cost, span_days(ho_cell_c, None))
        flag = '  <- select-cost' if cost == COST_SELECT else ''
        print(f'    cost {cost:.2f}  n {cs["n"]:>5d}  mean {fmt(cs.get("mean_bps",0),8,3)}bps  '
              f'tstat {fmt(cs.get("tstat",0),6,2)}  Sh {fmt(sh,6,2)}  '
              f'wr {cs.get("wr",0)*100:4.1f}%{flag}')
    sh_hc = ann_sharpe(ho_cell_c, COST_SELECT, span_days(ho_cell_c, None))
    sh_hf = ann_sharpe(ho_cell_f, COST_SELECT, span_days(ho_cell_f, None))
    cs_h = cell_stats(ho_cell_c, COST_SELECT)
    ho_pass = (sh_hc > HO_SHARPE_BAR and cs_h.get('mean_bps', 0) > 0 and (sh_hc - sh_hf) > 0)
    print(f'\n  holdout @ {COST_SELECT}: Sh {sh_hc:+.2f} (bar > {HO_SHARPE_BAR})  '
          f'mean {cs_h.get("mean_bps",0):+.3f}bps  fade_gap {sh_hc-sh_hf:+.2f}')
    print(f'  >>> HOLDOUT {"PASS" if ho_pass else "FAIL"}  '
          f'-> verdict {"CANDIDATE (one cell survived OOS)" if ho_pass else "NEGATIVE (no OOS survival)"}')
    print(f'\n  total time {time.time()-t0:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
