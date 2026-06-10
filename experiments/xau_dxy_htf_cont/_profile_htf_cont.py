"""DXY-breakout -> XAU inverse-continuation (H1/H4) — Phase 0 profile.

Thesis: experiments/xau_dxy_htf_cont/xau_dxy_htf_cont.md (2026-06-01).

Real USDX vs XAUUSD at H1 and H4. A DXY breakout (k-bar momentum, sign+magnitude)
predicts XAU inverse-continuation: DXY up -> SHORT XAU; DXY down -> LONG XAU.

LOAD-BEARING gate: does the DXY breakout add forward predictive power BEYOND
XAU's own prior-k move? Within terciles of xau_own, split by dxy_mom sign and
measure forward XAU. If the DXY effect vanishes inside the buckets, it's just
gold momentum (gold_trend, REJECT #73).

Sections: 1 corr sanity | 2 event counts | 3 inverse-cont signed fwd |
4 OWN-MOMENTUM GATE | 5 direction null | 6 regime | 7 verdict.
"""
import os, sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))

from data import fetch_ohlc

START_DATE = "2021-06-10"
END_DATE = "2026-06-01"
TF_CFG = {
    'H1': {'native': 'H1', 'resample': None, 'k': [6, 12, 24], 'h': [1, 2, 3, 6, 12]},
    'H4': {'native': 'H1', 'resample': '4h', 'k': [3, 6, 12], 'h': [1, 2, 3, 6]},
}
MAG_PCTILES = [0, 50, 70]   # 0 = no magnitude filter
MIN_CELL = 150


def section(title):
    print(f"\n{'='*80}\n{title}\n{'='*80}")


def t_of(arr):
    arr = arr[np.isfinite(arr)]
    if len(arr) < 5:
        return 0.0, np.nan, 0
    m = arr.mean()
    s = arr.std(ddof=1)
    if s == 0:
        return m, np.nan, len(arr)
    return m, m / (s / np.sqrt(len(arr))), len(arr)


def load_join(native_tf):
    xau = fetch_ohlc("XAUUSD", native_tf, START_DATE, END_DATE)
    usdx = fetch_ohlc("USDX", native_tf, START_DATE, END_DATE)

    def prep(d, name):
        d = d[['timestamp', 'close']].copy()
        d['timestamp'] = pd.to_datetime(d['timestamp'], utc=True)
        return d.rename(columns={'close': name})

    df = prep(xau, 'xau').merge(prep(usdx, 'usdx'), on='timestamp', how='inner').dropna()
    df = df[df['timestamp'] >= pd.Timestamp(START_DATE, tz='UTC')]
    return df.sort_values('timestamp').reset_index(drop=True)


def resample_close(df, rule):
    s = df.set_index('timestamp')
    out = pd.DataFrame({
        'xau': s['xau'].resample(rule, label='left', closed='left').last(),
        'usdx': s['usdx'].resample(rule, label='left', closed='left').last(),
    }).dropna().reset_index()
    return out


def regime_of(y):
    if y < 2022:
        return 'W2'
    if y < 2024:
        return 'W3'
    return 'W4'


print("Loading H1 series (XAUUSD, USDX) ...")
base = load_join('H1')
print(f"H1 aligned bars: {len(base):,} | {base['timestamp'].min()} -> {base['timestamp'].max()}")


# ---------------------------------------------------------------------------
# 1. Correlation sanity (per TF)
# ---------------------------------------------------------------------------
section("1. Correlation sanity (log-return corr, per TF)")
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    rx = np.diff(np.log(df['xau'].values))
    rd = np.diff(np.log(df['usdx'].values))
    print(f"  {tf}: n={len(df):,}  corr={np.corrcoef(rx, rd)[0,1]:+.3f}")


# ---------------------------------------------------------------------------
# core builder
# ---------------------------------------------------------------------------
def build(df, k, h_list):
    log_xau = np.log(df['xau'].values.astype(np.float64))
    log_usdx = np.log(df['usdx'].values.astype(np.float64))
    xau_p = df['xau'].values.astype(np.float64)
    reg = df['timestamp'].dt.year.apply(regime_of).values
    n = len(df)
    dxy_kret = np.full(n, np.nan); dxy_kret[k:] = (log_usdx[k:] - log_usdx[:-k]) * 1e4
    xau_own = np.full(n, np.nan); xau_own[k:] = (log_xau[k:] - log_xau[:-k]) * 1e4
    fwd = {}
    for h in h_list:
        sh = np.concatenate([xau_p[h:], np.full(h, np.nan)])
        fwd[h] = (sh - xau_p) / xau_p * 1e4
    return dxy_kret, xau_own, fwd, reg


# ---------------------------------------------------------------------------
# 2. Event counts
# ---------------------------------------------------------------------------
section("2. DXY-breakout event counts by (TF, k, mag-pctile)")
print(f"  {'TF':>3s} {'k':>3s} {'mag%':>5s} {'n':>7s} {'ev/yr':>7s}")
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    yrs = (df['timestamp'].max() - df['timestamp'].min()) / np.timedelta64(1, 'D') / 365.25
    for k in cfg['k']:
        dxy_kret, xau_own, fwd, reg = build(df, k, cfg['h'])
        for mp in MAG_PCTILES:
            th = 0.0 if mp == 0 else np.nanpercentile(np.abs(dxy_kret), mp)
            ev = np.isfinite(dxy_kret) & (np.abs(dxy_kret) >= th) & (dxy_kret != 0)
            print(f"  {tf:>3s} {k:>3d} {mp:>5d} {int(ev.sum()):>7d} {ev.sum()/yrs:>7.0f}")


# ---------------------------------------------------------------------------
# 3. Inverse-continuation signed forward XAU
# ---------------------------------------------------------------------------
section("3. Inverse-continuation signed fwd XAU (signal=-sign(dxy_kret)), mean/t by h")
best_cells = []
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    print(f"\n  --- {tf} ---")
    print(f"  {'k':>3s} {'mag%':>5s} {'n':>6s}  " +
          "  ".join([f"{'h'+str(h):>12s}" for h in cfg['h']]))
    for k in cfg['k']:
        dxy_kret, xau_own, fwd, reg = build(df, k, cfg['h'])
        for mp in MAG_PCTILES:
            th = 0.0 if mp == 0 else np.nanpercentile(np.abs(dxy_kret), mp)
            ev = np.isfinite(dxy_kret) & (np.abs(dxy_kret) >= th) & (dxy_kret != 0)
            idx = np.where(ev)[0]
            if len(idx) < MIN_CELL:
                continue
            sig = -np.sign(dxy_kret[idx])
            parts = []
            for h in cfg['h']:
                vals = sig * fwd[h][idx]
                m, t, nn = t_of(vals)
                parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
                best_cells.append((tf, k, mp, h, m, t, nn))
            print(f"  {k:>3d} {mp:>5d} {len(idx):>6d}  " +
                  "  ".join([f"{p:>12s}" for p in parts]))


# ---------------------------------------------------------------------------
# 4. OWN-MOMENTUM GATE (load-bearing)
# ---------------------------------------------------------------------------
section("4. OWN-MOMENTUM GATE: within xau_own terciles, DXY-direction fwd-XAU spread")
print("  Spread = mean[fwd XAU | DXY-down] - mean[fwd XAU | DXY-up]  (>0 = inverse-cont survives).")
print("  If the spread lives ONLY in the tercile where gold already moved, DXY adds nothing.")
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    # use middle k and a representative forward horizon
    k = cfg['k'][1]
    h = cfg['h'][2] if len(cfg['h']) > 2 else cfg['h'][-1]
    dxy_kret, xau_own, fwd, reg = build(df, k, cfg['h'])
    valid = np.isfinite(dxy_kret) & np.isfinite(xau_own) & np.isfinite(fwd[h])
    vi = np.where(valid)[0]
    q33, q66 = np.nanpercentile(xau_own[vi], [33, 66])
    print(f"\n  --- {tf} (k={k}, h={h}) ---  xau_own terciles cut at {q33:+.0f}/{q66:+.0f} bps")
    print(f"  {'xau_own bucket':>16s} {'n_dn':>6s} {'fwd|DXYdn':>10s} {'n_up':>6s} {'fwd|DXYup':>10s} {'SPREAD':>9s} {'t':>6s}")
    for lab, lo, hi in [('down (gold fell)', -np.inf, q33),
                        ('flat', q33, q66),
                        ('up (gold rose)', q66, np.inf)]:
        bmask = valid & (xau_own >= lo) & (xau_own < hi)
        dn = bmask & (dxy_kret < 0)   # DXY down
        up = bmask & (dxy_kret > 0)   # DXY up
        a = fwd[h][dn]; a = a[np.isfinite(a)]
        b = fwd[h][up]; b = b[np.isfinite(b)]
        if len(a) < 5 or len(b) < 5:
            print(f"  {lab:>16s} (thin)")
            continue
        spread = a.mean() - b.mean()
        se = np.sqrt(a.var(ddof=1)/len(a) + b.var(ddof=1)/len(b))
        t = spread/se if se > 0 else 0.0
        print(f"  {lab:>16s} {len(a):>6d} {a.mean():>+9.1f} {len(b):>6d} {b.mean():>+9.1f} "
              f"{spread:>+8.1f} {t:>+6.2f}")


# ---------------------------------------------------------------------------
# 5. Direction null-check
# ---------------------------------------------------------------------------
section("5. Direction null-check: inverse-CONTINUATION vs inverse-REVERSAL (per TF, mid k, mag70)")
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    k = cfg['k'][1]
    dxy_kret, xau_own, fwd, reg = build(df, k, cfg['h'])
    th = np.nanpercentile(np.abs(dxy_kret), 70)
    ev = np.isfinite(dxy_kret) & (np.abs(dxy_kret) >= th)
    idx = np.where(ev)[0]
    h = cfg['h'][2] if len(cfg['h']) > 2 else cfg['h'][-1]
    cont = (-np.sign(dxy_kret[idx])) * fwd[h][idx]
    rev = (+np.sign(dxy_kret[idx])) * fwd[h][idx]
    mc, tc, _ = t_of(cont)
    mr, tr, _ = t_of(rev)
    print(f"  {tf} k={k} h={h} n={len(idx)}: CONT {mc:+.1f}/{tc:+.2f}  "
          f"REV {mr:+.1f}/{tr:+.2f}  gap(cont-rev) {mc-mr:+.1f}")


# ---------------------------------------------------------------------------
# 6. Regime decomposition
# ---------------------------------------------------------------------------
section("6. Regime decomposition (per TF, mid k, mag70, inverse-cont signed) — W4 binding")
for tf, cfg in TF_CFG.items():
    df = base if cfg['resample'] is None else resample_close(base, cfg['resample'])
    k = cfg['k'][1]
    dxy_kret, xau_own, fwd, reg = build(df, k, cfg['h'])
    th = np.nanpercentile(np.abs(dxy_kret), 70)
    ev = np.isfinite(dxy_kret) & (np.abs(dxy_kret) >= th)
    print(f"\n  --- {tf} (k={k}, mag70) ---")
    print(f"  {'reg':>4s} {'n':>5s}  " + "  ".join([f"{'h'+str(h):>12s}" for h in cfg['h']]))
    for rg in ['W2', 'W3', 'W4']:
        idx = np.where(ev & (reg == rg))[0]
        if len(idx) < 20:
            print(f"  {rg:>4s} {len(idx):>5d}  (thin)")
            continue
        sig = -np.sign(dxy_kret[idx])
        parts = []
        for h in cfg['h']:
            m, t, _ = t_of(sig * fwd[h][idx])
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
        print(f"  {rg:>4s} {len(idx):>5d}  " + "  ".join([f"{p:>12s}" for p in parts]))


# ---------------------------------------------------------------------------
# 7. Verdict
# ---------------------------------------------------------------------------
section("7. Phase 0 pass criteria (pre-committed)")
print("""
PASS (-> Phase 1) requires ALL:
  - >=1 (TF,k,mag,h) cell: signed mean >= +5 bps AND t >= +2.0 AND n >= 150  [Sec 3]
  - OWN-MOMENTUM GATE: DXY-direction spread >= +3 bps & t >= +1.8 in ALL 3
    xau_own terciles (DXY adds beyond gold's own momentum)                   [Sec 4]
  - inverse-CONTINUATION beats inverse-REVERSAL (gap > 0)                    [Sec 5]
  - persists W3 AND W4                                                       [Sec 6]

Best signed cells (mean>=+5, t>=+2.0, n>=150):""")
good = [c for c in best_cells if c[4] >= 5.0 and c[5] >= 2.0 and c[6] >= 150]
if good:
    for (tf, k, mp, h, m, t, nn) in sorted(good, key=lambda x: -x[4]):
        print(f"    {tf} k={k} mag{mp} h={h}: mean={m:+.1f}bp t={t:+.2f} n={nn}")
else:
    print("    NONE — no cell clears mean>=+5 & t>=+2.0 & n>=150.")
