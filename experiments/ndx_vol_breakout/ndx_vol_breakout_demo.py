#!/usr/bin/env python3
"""
NDX100 direction-agnostic vol-breakout — Phase 1/2 + tail-complement + gap-guard.

Thesis: experiments/ndx_vol_breakout/ndx_vol_breakout.md
Purer long-gamma sibling of ndx_trend_day: enter on the OR break (whichever side), hold to close,
vol-gated. Gap-aware fill baked in (lesson #81/#83). Gate = tail-complement, not standalone Sharpe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))
from data import fetch_ohlc  # noqa: E402

SYM, TZ = "NDX100", "US/Eastern"
OR_S, OR_E, CLOSE_M = 9 * 60 + 30, 10 * 60 + 30, 16 * 60
EXP_MULT, LOOKBACK, COST_BPS = 1.0, 20, 0.8
START, END, BPY = "2019-01-01", "2026-05-28", 252
BOOK_CSV = _ROOT / "experiments/_live/portfolio_risk_parity/outputs/daily_pnl_per_strategy.csv"


def section(t): print(f"\n{'=' * 88}\n  {t}\n{'=' * 88}\n")
def regime(y): return "W1" if y <= 2020 else ("W2" if y <= 2022 else "W3")
def ann_sh(r):
    r = r[np.isfinite(r)]
    if len(r) < 2 or r.std(ddof=1) == 0: return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(BPY))
def mdd(r):
    eq = np.cumprod(1 + r); rm = np.maximum.accumulate(eq); return float(((eq - rm) / rm).min())


def load_rth():
    df = fetch_ohlc(SYM, "M5", START, END)
    df = df[["timestamp", "open", "high", "low", "close"]].copy()
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    df = df.set_index("ts").sort_index()
    df = df[df.index.dayofweek < 5]
    mm = df.index.hour * 60 + df.index.minute
    return df[(mm >= OR_S) & (mm < CLOSE_M + 5)]


def simulate(df, fade=False, exp_mult=EXP_MULT, cost_bps=COST_BPS, gap_aware=True):
    """Returns (net, dates, gapfrac). dir=whichever side breaks first; gap-aware entry fill."""
    mins = (df.index.hour * 60 + df.index.minute).to_numpy()
    o = df["open"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    day = df.index.normalize().to_numpy()
    recs = []
    n_gap = 0
    for d in np.unique(day):
        m = day == d
        dm = mins[m]; do = o[m]; dh = h[m]; dl = l[m]; dc = c[m]
        orm = (dm >= OR_S) & (dm < OR_E)
        if orm.sum() < 3: continue
        or_open = do[orm][0]; or_hi = dh[orm].max(); or_lo = dl[orm].min()
        if or_open <= 0: continue
        orpct = (or_hi - or_lo) / or_open
        post = np.where(dm >= OR_E)[0]
        dr, entry, gap = 0, 0.0, False
        for i in post:
            if dh[i] >= or_hi:
                gap = do[i] > or_hi
                entry = do[i] if (gap_aware and gap) else or_hi
                dr = +1; break
            if dl[i] <= or_lo:
                gap = do[i] < or_lo
                entry = do[i] if (gap_aware and gap) else or_lo
                dr = -1; break
        if dr != 0:
            n_gap += int(gap)
        recs.append((pd.Timestamp(d), orpct, dr, entry, dc[-1]))
    rdf = pd.DataFrame(recs, columns=["date", "orpct", "dir", "entry", "exit"])
    med = rdf["orpct"].rolling(LOOKBACK, min_periods=LOOKBACK // 2).median().shift(1)
    sig = rdf[(rdf["orpct"] > exp_mult * med.fillna(np.inf)) & (rdf["dir"] != 0)].copy()
    if sig.empty: return np.array([]), np.array([]), 0.0
    sgn = sig["dir"].to_numpy() * (-1.0 if fade else 1.0)
    net = sgn * (sig["exit"].to_numpy() - sig["entry"].to_numpy()) / sig["entry"].to_numpy() - cost_bps / 1e4
    gapfrac = n_gap / max(len(sig), 1)
    return net, sig["date"].to_numpy(), gapfrac


def main():
    section("NDX100 direction-agnostic vol-breakout")
    df = load_rth()
    print(f"  RTH bars: {len(df):,}  {df.index[0].date()} -> {df.index[-1].date()}")

    net, dates, gapfrac = simulate(df)
    dts = pd.to_datetime(dates)
    if dts.tz is not None: dts = dts.tz_convert("UTC").tz_localize(None)
    yrs = dts.year.to_numpy()
    sh = ann_sh(net)
    section("Baseline (break-continuation, gap-aware, cost 0.8bp)")
    print(f"  n={len(net)}  Sh {sh:+.2f}  mean {net.mean()*1e4:+.2f}bp  MDD {mdd(net)*100:+.1f}%  "
          f"tot {(np.cumprod(1+net)[-1]-1)*100:+.1f}%  gap-fill frac {gapfrac:.2f}")
    allpos = True
    for w in ("W1", "W2", "W3"):
        mm = np.array([regime(y) == w for y in yrs])
        if mm.sum() >= 2:
            print(f"    {w}: n={mm.sum():>3d}  Sh {ann_sh(net[mm]):+.2f}  mean {net[mm].mean()*1e4:+.2f}bp")
            if net[mm].mean() <= 0 and w == "W3": allpos = False

    section("Direction null (break-continuation vs break-FADE, same gated days)")
    net_f, _, _ = simulate(df, fade=True)
    dirgap = sh - ann_sh(net_f)
    print(f"  continuation Sh {sh:+.2f}  fade Sh {ann_sh(net_f):+.2f}  dir-gap {dirgap:+.2f}  ({'PASS' if dirgap > 0.30 else 'FAIL'})")

    section("Gap-through guard (lesson #83): gap-aware vs forced level-fill")
    net_lvl, _, _ = simulate(df, gap_aware=False)
    print(f"  gap-AWARE Sh {sh:+.2f}   level-FILL Sh {ann_sh(net_lvl):+.2f}  "
          f"(level >> aware ⇒ phantom; here Δ={ann_sh(net_lvl)-sh:+.2f}, gap-fill frac {gapfrac:.2f})")

    section("Sweeps (exit always close)")
    for em in (0.8, 1.0, 1.3, 1.6):
        ns, _, _ = simulate(df, exp_mult=em)
        print(f"  EXP_MULT {em:>4.1f}  n={len(ns):>4d}  Sh {ann_sh(ns):+.2f}")
    for cb in (0.5, 0.8, 1.5, 3.0):
        ns, _, _ = simulate(df, cost_bps=cb)
        print(f"  cost {cb:>4.1f}bp  Sh {ann_sh(ns):+.2f}")

    # ---- tail-complement + corr to ndx_trend_day ----
    section("TAIL-COMPLEMENT vs book + corr to ndx_trend_day")
    s = pd.Series(net, index=dts.normalize()).groupby(level=0).sum()
    book = pd.read_csv(BOOK_CSV, index_col=0, parse_dates=True)
    if book.index.tz is not None: book.index = book.index.tz_convert("UTC").tz_localize(None)
    book.index = book.index.normalize()
    book_agg = book.sum(axis=1)
    j = pd.concat([s.rename("strat"), book[["lunch_fade"]], book_agg.rename("book")], axis=1).fillna(0.0)
    j = j.loc[j["strat"] != 0.0]
    corr_lf = float(j["strat"].corr(j["lunch_fade"]))
    corr_bk = float(j["strat"].corr(j["book"]))
    corr_ntd = float("nan")
    if "ndx_trend_day" in book.columns:
        jn = pd.concat([s.rename("strat"), book[["ndx_trend_day"]]], axis=1).fillna(0.0)
        jn = jn.loc[jn["strat"] != 0.0]
        corr_ntd = float(jn["strat"].corr(jn["ndx_trend_day"]))
    thr = book_agg.quantile(0.10)
    worst = book_agg[book_agg <= thr].index
    sw = s.reindex(worst).fillna(0.0)
    print(f"  active {len(j)}  corr→lunch_fade {corr_lf:+.3f}  corr→book {corr_bk:+.3f}  corr→ndx_trend_day {corr_ntd:+.3f}")
    print(f"  book worst-decile days {len(worst)}: strat mean {sw.mean()*1e4:+.2f}bp "
          f"({'POSITIVE — helps tail' if sw.mean() > 0 else 'NEGATIVE'})")

    section("Pre-committed scorecard")
    checks = [
        ("1. Sharpe > +0.30", sh > 0.30, f"{sh:+.2f}"),
        ("2. MDD < 25%", abs(mdd(net)) < 0.25, f"{mdd(net)*100:+.1f}%"),
        ("3. W3 holdout > 0", net[np.array([regime(y)=='W3' for y in yrs])].mean() > 0, ""),
        ("4. trades >= 100", len(net) >= 100, f"{len(net)}"),
        ("5. null dir-gap > +0.30", dirgap > 0.30, f"{dirgap:+.2f}"),
        ("6a. corr lunch_fade <= +0.20", corr_lf <= 0.20, f"{corr_lf:+.3f}"),
        ("6b. worst-decile mean > 0", sw.mean() > 0, f"{sw.mean()*1e4:+.2f}bp"),
        ("7. not redundant w/ ndx_trend_day (corr<0.7)", (np.isnan(corr_ntd) or corr_ntd < 0.7), f"{corr_ntd:+.3f}"),
    ]
    npass = sum(ok for _, ok, _ in checks)
    for name, ok, val in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<46s} {val}")
    standalone = checks[0][1] and checks[1][1] and checks[2][1] and checks[3][1] and checks[4][1]
    complement = checks[5][1] and checks[6][1]
    section("Verdict")
    if standalone and complement:
        v = "PROCEED to Phase 3 — standalone + tail-complement (adds a 2nd long-gamma leg)"
    elif complement and not standalone:
        v = "tail-complement but sub-bar standalone — overlay-only at best"
    elif standalone:
        v = "standalone-positive but not complementary — REJECT for this purpose"
    else:
        v = "REJECT"
    print(f"  {npass}/8. VERDICT: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
