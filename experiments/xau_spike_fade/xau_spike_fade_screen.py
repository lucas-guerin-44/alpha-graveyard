#!/usr/bin/env python3
"""
XAUUSD M5 spike-resolution characterization — Phase 0 screen.

Thesis: experiments/xau_spike_fade/xau_spike_fade.md

User question: of M5 bars that move >= X*ATR(14) in one bar, what % retrace?
And is that retrace rate above the chance base rate, with a tradeable fade edge
net of the XAU spread?

Sections:
  1. Spike resolution table       -- P(retrace >= F*size within K bars), up/down, by X/K/F
  2. Base-rate null               -- same on "normal" candles (0.5-1.0 ATR moves); EDGE = spike - normal
  3. Net signed reversion         -- mean forward return AGAINST spike dir over K bars, with t-stat
  4. Continuation-first problem   -- median favorable excursion before the retrace (stop-out risk)
  5. Fade-expectancy sketch       -- mechanical fade, target/stop/time-stop, cost sweep
  6. Breakdown                    -- by session bucket and by regime window
  7. 3-bar burst variant          -- same machinery on cumulative 3-bar displacement

Pure-numpy inner scan (loop over spike indices only; forward scan <=48 bars).
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

from data import fetch_ohlc  # noqa: E402

# =============================================================================
# Config
# =============================================================================
SYMBOL = "XAUUSD"
TIMEFRAME = "M5"
START_DATE = "2018-06-08"   # true M5 intraday start (daily-mislabelled bars before)
END_DATE = "2026-06-01"

ATR_PERIOD = 14
XS = (1.5, 2.0, 3.0, 4.0)            # spike threshold in ATR multiples
KS = (3, 6, 12, 24, 48)              # forward horizons in M5 bars (15m,30m,1h,2h,4h)
FS = (0.5, 1.0)                      # retrace fractions of the spike size
KMAX = max(KS)

# fade-expectancy sketch
FADE_X = 2.0                         # which spike threshold to trade
FADE_TARGET_F = 0.5                  # take profit at 50% retrace of the spike
FADE_STOP_BUF_ATR = 0.5             # stop = spike extreme +/- this*ATR beyond
FADE_TIME_STOP_K = 12               # exit at close[t+K] if neither hit
COST_SWEEP = (0.0, 0.20, 0.30, 0.40, 0.60, 1.00)   # round-trip spread in price units ($)


def section(t: str) -> None:
    print(f"\n{'=' * 92}\n  {t}\n{'=' * 92}\n")


# =============================================================================
# Load
# =============================================================================
def load() -> pd.DataFrame:
    raw = fetch_ohlc(SYMBOL, TIMEFRAME, START_DATE, END_DATE)
    if raw is None or raw.empty:
        raise RuntimeError(f"No bars for {SYMBOL} {TIMEFRAME}")
    df = raw[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df[df.index.dayofweek < 5]   # drop weekends
    return df


def wilder_atr(high, low, close, period=14):
    prev_close = np.empty_like(close)
    prev_close[0] = close[0]
    prev_close[1:] = close[:-1]
    tr = np.maximum.reduce([
        high - low,
        np.abs(high - prev_close),
        np.abs(low - prev_close),
    ])
    atr = np.full_like(tr, np.nan)
    if len(tr) <= period:
        return atr
    atr[period] = tr[1:period + 1].mean()
    a = 1.0 / period
    for i in range(period + 1, len(tr)):
        atr[i] = atr[i - 1] + a * (tr[i] - atr[i - 1])
    return atr


# =============================================================================
# Forward resolution scan (per candidate bar)
# =============================================================================
def scan(idxs, dirs, sizes, anchor, high, low, close, contig):
    """For each candidate bar i: forward-scan up to KMAX *contiguous* bars.
    anchor = price to measure retrace from (close[i]).
    Returns dict of arrays, one row per candidate, columns per K:
      reached[K]  -- window had >=K contiguous fwd bars
      revfrac[K]  -- max reversion excursion / size achieved within K (back toward pre-spike)
      contfrac[K] -- max continuation excursion / size within K (further in spike dir)
      fwdret[K]   -- signed return AGAINST spike at exactly horizon K (>0 == reverted)
    """
    n = len(idxs)
    nk = len(KS)
    reached = np.zeros((n, nk), dtype=bool)
    revfrac = np.zeros((n, nk))
    contfrac = np.zeros((n, nk))
    fwdret = np.full((n, nk), np.nan)
    kset = {k: j for j, k in enumerate(KS)}

    N = len(close)
    for r in range(n):
        i = idxs[r]
        d = dirs[r]
        sz = sizes[r]
        a = anchor[r]
        run_rev = 0.0   # max favorable (toward pre-spike) excursion so far
        run_cont = 0.0  # max adverse (further extension) excursion so far
        steps = 0
        for k in range(1, KMAX + 1):
            j = i + k
            if j >= N or not contig[j]:   # gap or end -> stop accumulating
                break
            steps = k
            # reversion excursion = how far price pulled back toward pre-spike anchor
            if d > 0:   # up-spike: retrace = anchor - low
                rev = a - low[j]
                cont = high[j] - a
            else:       # down-spike: retrace = high - anchor
                rev = high[j] - a
                cont = a - low[j]
            if rev > run_rev:
                run_rev = rev
            if cont > run_cont:
                run_cont = cont
            if k in kset:
                col = kset[k]
                reached[r, col] = True
                revfrac[r, col] = run_rev / sz
                contfrac[r, col] = run_cont / sz
                # signed close-to-close return against spike at exactly horizon k
                fwdret[r, col] = -d * (close[j] - a)
        # horizons beyond the contiguous run stay reached=False (censored)
        _ = steps
    return dict(reached=reached, revfrac=revfrac, contfrac=contfrac, fwdret=fwdret)


def res_table(tag, res, sizes_atr=None):
    """Print resolution % per (K, F), counting only windows that reached K."""
    reached = res["reached"]
    revfrac = res["revfrac"]
    print(f"  {tag}")
    hdr = "    K(bars)  " + "".join(f"{k:>8}" for k in KS)
    print(hdr)
    for F in FS:
        row = []
        for col, k in enumerate(KS):
            m = reached[:, col]
            if m.sum() == 0:
                row.append("   n/a")
                continue
            p = (revfrac[m, col] >= F).mean() * 100
            row.append(f"{p:7.1f}")
        print(f"    F>={F:<4}  " + "".join(f"{x:>8}" for x in row))
    # net signed reversion at each K
    row_mu, row_t = [], []
    for col, k in enumerate(KS):
        m = reached[:, col]
        x = res["fwdret"][m, col]
        x = x[np.isfinite(x)]
        if len(x) < 3:
            row_mu.append("   n/a"); row_t.append("   n/a"); continue
        mu = x.mean(); t = mu / (x.std(ddof=1) / np.sqrt(len(x))) if x.std() else 0
        row_mu.append(f"{mu:7.2f}"); row_t.append(f"{t:7.1f}")
    print(f"    netRev$ " + "".join(f"{x:>8}" for x in row_mu) + "   (>0 = reverted, price units)")
    print(f"    t-stat  " + "".join(f"{x:>8}" for x in row_t))
    # continuation-first: median further-extension before retrace (in size units)
    row_c = []
    for col, k in enumerate(KS):
        m = reached[:, col]
        if m.sum() == 0:
            row_c.append("   n/a"); continue
        row_c.append(f"{np.median(res['contfrac'][m, col]):7.2f}")
    print(f"    medCont " + "".join(f"{x:>8}" for x in row_c) + "   (median further-extension / spike size)")


# =============================================================================
# Fade expectancy
# =============================================================================
def fade_expectancy(idxs, dirs, sizes, anchor, extreme, atr_at, high, low, close, contig, tag):
    """Mechanical fade: enter at close[t] against spike, TP at FADE_TARGET_F retrace,
    SL beyond spike extreme by FADE_STOP_BUF_ATR*ATR, time-stop at FADE_TIME_STOP_K.
    Returns gross per-trade P&L in price units (cost applied later)."""
    N = len(close)
    pnl = []
    for r in range(len(idxs)):
        i = idxs[r]; d = dirs[r]; sz = sizes[r]; a = anchor[r]
        ext = extreme[r]; atr = atr_at[r]
        if d > 0:   # short the up-spike
            tp = a - FADE_TARGET_F * sz
            sl = ext + FADE_STOP_BUF_ATR * atr
        else:       # long the down-spike
            tp = a + FADE_TARGET_F * sz
            sl = ext - FADE_STOP_BUF_ATR * atr
        exit_px = None
        for k in range(1, FADE_TIME_STOP_K + 1):
            j = i + k
            if j >= N or not contig[j]:
                exit_px = close[i + k - 1] if k > 1 else a
                break
            if d > 0:
                if high[j] >= sl:   # stop first (conservative: check stop before target)
                    exit_px = sl; break
                if low[j] <= tp:
                    exit_px = tp; break
            else:
                if low[j] <= sl:
                    exit_px = sl; break
                if high[j] >= tp:
                    exit_px = tp; break
            if k == FADE_TIME_STOP_K:
                exit_px = close[j]
        if exit_px is None:
            continue
        # short up-spike profits when price falls: pnl = (a - exit)*... ; generalize by dir
        pnl.append(d * (a - exit_px) if d > 0 else d * (a - exit_px))
    pnl = np.array(pnl)
    # NB: for d>0 short, profit = a-exit; for d<0 long, profit = exit-a = -(a-exit) -> d*(a-exit) with d=-1 gives exit-a. correct.
    print(f"\n  {tag}: {len(pnl)} fade trades, gross avg ${pnl.mean():.3f}")
    print(f"    {'costRT$':>8}{'avg$':>9}{'WR%':>7}{'PF':>7}{'expR':>7}{'tot$':>9}")
    for c in COST_SWEEP:
        net = pnl - c
        wr = (net > 0).mean() * 100
        gains = net[net > 0].sum(); losses = -net[net < 0].sum()
        pf = gains / losses if losses > 0 else float('inf')
        expR = net.mean() / net.std(ddof=1) if net.std() else 0
        print(f"    {c:>8.2f}{net.mean():>9.3f}{wr:>7.1f}{pf:>7.2f}{expR:>7.3f}{net.sum():>9.0f}")
    return pnl


# =============================================================================
# Main
# =============================================================================
def main():
    section(f"XAU SPIKE-FADE SCREEN — {SYMBOL} {TIMEFRAME} {START_DATE}..{END_DATE}")
    df = load()
    ts = df.index
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    N = len(c)
    print(f"  bars: {N:,}  span: {ts[0]} .. {ts[-1]}")

    # contiguity: bar j is contiguous with j-1 if exactly 5 min apart
    dt_min = np.empty(N); dt_min[0] = 0
    dt_min[1:] = (ts[1:] - ts[:-1]).total_seconds() / 60.0  # resolution-agnostic
    contig = np.abs(dt_min - 5.0) < 1e-6   # contig[j] True => bar j is 5m after j-1

    atr = wilder_atr(h, l, c, ATR_PERIOD)
    move = np.empty(N); move[0] = 0.0
    move[1:] = c[1:] - c[:-1]
    prev_atr = np.empty(N); prev_atr[0] = np.nan
    prev_atr[1:] = atr[:-1]

    valid = np.isfinite(prev_atr) & (prev_atr > 0) & contig & (np.arange(N) > ATR_PERIOD + 2)

    # ------------------------------------------------------------------ #
    section("1-2. SPIKE RESOLUTION + BASE-RATE NULL")
    print("  Read: 'resolve' = price retraced >= F*(spike size) within K bars.")
    print("  EDGE only exists if spike-resolve% >> normal-candle-resolve% AND netRev$ t-stat is real.\n")

    # base-rate reference set: 'normal' directional candles 0.5-1.0 ATR
    base_norm = {}
    for sign_tag, sgn in (("UP", 1), ("DOWN", -1)):
        m = valid & (np.sign(move) == sgn) & (np.abs(move) >= 0.5 * prev_atr) & (np.abs(move) < 1.0 * prev_atr)
        idxs = np.where(m)[0]
        sizes = np.abs(move[idxs])
        res = scan(idxs, np.full(len(idxs), sgn), sizes, c[idxs], h, l, c, contig)
        base_norm[sign_tag] = res

    summary_edge = {}
    for X in XS:
        section(f"  X = {X} ATR")
        for sign_tag, sgn in (("UP-spike", 1), ("DOWN-spike", -1)):
            m = valid & (np.sign(move) == sgn) & (np.abs(move) >= X * prev_atr)
            idxs = np.where(m)[0]
            if len(idxs) == 0:
                print(f"    {sign_tag}: 0 spikes"); continue
            sizes = np.abs(move[idxs])
            res = scan(idxs, np.full(len(idxs), sgn), sizes, c[idxs], h, l, c, contig)
            freq = len(idxs) / N * 100
            res_table(f"{sign_tag}  (n={len(idxs):,}, {freq:.2f}% of bars)", res)
            # edge vs base rate at headline K=12, F=0.5
            base = base_norm["UP" if sgn > 0 else "DOWN"]
            col = KS.index(12)
            mb = base["reached"][:, col]; ms = res["reached"][:, col]
            if mb.sum() and ms.sum():
                pe = (res["revfrac"][ms, col] >= 0.5).mean() * 100
                pb = (base["revfrac"][mb, col] >= 0.5).mean() * 100
                print(f"    --> EDGE vs normal candle (K=12,F=0.5): spike {pe:.1f}% - normal {pb:.1f}% = {pe-pb:+.1f}pp")
                summary_edge[(X, sign_tag)] = pe - pb
            print()

    # ------------------------------------------------------------------ #
    section(f"5. FADE EXPECTANCY SKETCH  (X={FADE_X}, TP={FADE_TARGET_F} retrace, "
            f"SL=extreme+{FADE_STOP_BUF_ATR}ATR, time-stop {FADE_TIME_STOP_K} bars)")
    all_pnl = []
    for sign_tag, sgn in (("UP-spike (short)", 1), ("DOWN-spike (long)", -1)):
        m = valid & (np.sign(move) == sgn) & (np.abs(move) >= FADE_X * prev_atr)
        idxs = np.where(m)[0]
        sizes = np.abs(move[idxs])
        extreme = np.where(sgn > 0, h[idxs], l[idxs])
        pnl = fade_expectancy(idxs, np.full(len(idxs), sgn), sizes, c[idxs], extreme,
                              prev_atr[idxs], h, l, c, contig, sign_tag)
        all_pnl.append(pnl)

    # ------------------------------------------------------------------ #
    section("6. BREAKDOWN — session bucket & regime window (X=2, K=12, F=0.5, both dirs)")
    hour = ts.hour.to_numpy()
    year = ts.year.to_numpy()
    # session buckets (UTC): Asia 0-7, EU 7-12, US 12-21, late 21-24
    def sess_bucket(hh):
        b = np.full(len(hh), "late ", dtype="<U5")
        b[(hh >= 0) & (hh < 7)] = "Asia "
        b[(hh >= 7) & (hh < 12)] = "EU   "
        b[(hh >= 12) & (hh < 21)] = "US   "
        return b
    def regime(yy):
        r = np.full(len(yy), "23-26", dtype="<U5")
        r[yy <= 2020] = "18-20"
        r[(yy >= 2021) & (yy <= 2022)] = "21-22"
        return r

    m = valid & (np.abs(move) >= 2.0 * prev_atr)
    idxs = np.where(m)[0]
    sgn = np.sign(move[idxs]).astype(int)
    sizes = np.abs(move[idxs])
    res = scan(idxs, sgn, sizes, c[idxs], h, l, c, contig)
    col = KS.index(12)
    rch = res["reached"][:, col]
    resolved = res["revfrac"][:, col] >= 0.5
    netrev = res["fwdret"][:, col]
    sb = sess_bucket(hour[idxs]); rg = regime(year[idxs])

    def grp_report(labels, key):
        print(f"  by {key}:")
        print(f"    {'grp':>6}{'n':>8}{'resolve%':>10}{'netRev$':>10}{'t':>7}")
        for g in sorted(set(labels)):
            mm = (labels == g) & rch
            if mm.sum() < 10:
                continue
            pr = resolved[mm].mean() * 100
            x = netrev[mm]; x = x[np.isfinite(x)]
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() else 0
            print(f"    {g:>6}{mm.sum():>8}{pr:>10.1f}{x.mean():>10.2f}{t:>7.1f}")
    grp_report(sb, "session")
    grp_report(rg, "regime")

    # ------------------------------------------------------------------ #
    section("7. 3-BAR BURST VARIANT (cumulative 3-bar displacement >= X*ATR)")
    burst = np.full(N, np.nan)
    burst[3:] = c[3:] - c[:-3]
    contig3 = np.empty(N, dtype=bool); contig3[:3] = False
    contig3[3:] = contig[3:] & contig[2:-1] & contig[1:-2]   # all of last 3 steps contiguous
    for X in (2.0, 3.0):
        section(f"  burst X = {X} ATR")
        for sign_tag, sgn in (("UP-burst", 1), ("DOWN-burst", -1)):
            m = valid & contig3 & (np.sign(burst) == sgn) & (np.abs(burst) >= X * prev_atr)
            idxs = np.where(m)[0]
            if len(idxs) == 0:
                print(f"    {sign_tag}: 0"); continue
            sizes = np.abs(burst[idxs])
            res = scan(idxs, np.full(len(idxs), sgn), sizes, c[idxs], h, l, c, contig)
            res_table(f"{sign_tag} (n={len(idxs):,})", res)
            print()

    section("SUMMARY — edge vs base rate (K=12, F=0.5)")
    for (X, st), e in sorted(summary_edge.items()):
        verdict = "EDGE" if e >= 8 else ("weak" if e >= 3 else "NONE (noise)")
        print(f"    X={X} {st:<11} {e:+6.1f}pp  -> {verdict}")
    print("\n  Promote to Phase-2 strategy only if EDGE>=+8pp AND fade expectancy>0 at 0.30 RT")
    print("  AND netRev$ t-stat real AND holds in 23-26 + both directions (see md pre-commit).\n")


if __name__ == "__main__":
    main()
