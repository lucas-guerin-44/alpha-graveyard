#!/usr/bin/env python3
"""
Safe-haven risk-off tail-hedge — Phase 1/2.

Thesis: experiments/safe_haven_riskoff/safe_haven_riskoff.md
NDX down-vol-expansion morning (risk-off trigger) -> long safe-haven (XAU / short USDJPY / short USDCHF)
10:30->16:00 ET. Cross-asset tail-hedge; gate = worst-day-profit (lesson #88), not standalone Sharpe.
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

TZ = "US/Eastern"
OR_S, OR_E, CLOSE_M = 9 * 60 + 30, 10 * 60 + 30, 16 * 60
LOOKBACK, EXP_MULT = 20, 1.0
START, END, BPY = "2019-01-01", "2026-05-28", 252
VESSELS = {"XAUUSD": (+1, 2.0), "USDJPY": (-1, 1.0), "USDCHF": (-1, 1.2)}  # dir, cost_bps
BOOK_CSV = _ROOT / "experiments/_live/portfolio_risk_parity/outputs/daily_pnl_per_strategy.csv"


def section(t): print(f"\n{'=' * 88}\n  {t}\n{'=' * 88}\n")
def regime(y): return "W1" if y <= 2020 else ("W2" if y <= 2022 else "W3")
def ann_sh(r):
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    if len(r) < 2 or r.std(ddof=1) == 0: return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(BPY))
def mdd(r):
    eq = np.cumprod(1 + r); rm = np.maximum.accumulate(eq); return float(((eq - rm) / rm).min())


def load_et(sym):
    df = fetch_ohlc(sym, "M5", START, END)
    df = df[["timestamp", "open", "high", "low", "close"]].copy()
    df["ts"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(TZ)
    df = df.set_index("ts").sort_index()
    df = df[df.index.dayofweek < 5]
    return df


def ndx_riskoff_dates():
    """Return DataFrame[date, riskoff(bool)] from NDX down-vol-expansion morning."""
    df = load_et("NDX100")
    mm = (df.index.hour * 60 + df.index.minute).to_numpy()
    df = df[(mm >= OR_S) & (mm < CLOSE_M)]
    mm = (df.index.hour * 60 + df.index.minute).to_numpy()
    o = df["open"].to_numpy(); h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    day = df.index.normalize().to_numpy()
    recs = []
    for d in np.unique(day):
        m = day == d
        dm = mm[m]; do = o[m]; dh = h[m]; dl = l[m]; dc = c[m]
        orm = (dm >= OR_S) & (dm < OR_E)
        if orm.sum() < 3: continue
        oo = do[orm][0]; hi = dh[orm].max(); lo = dl[orm].min(); cl = dc[orm][-1]
        if oo <= 0: continue
        recs.append((pd.Timestamp(d), (hi - lo) / oo, np.sign(cl - oo)))
    r = pd.DataFrame(recs, columns=["date", "orpct", "thrust"])
    med = r["orpct"].rolling(LOOKBACK, min_periods=LOOKBACK // 2).median().shift(1)
    r["riskoff"] = (r["orpct"] > EXP_MULT * med.fillna(np.inf)) & (r["thrust"] < 0)
    return r.set_index("date")


def sh_window_prices(sym):
    """Per-date (entry@first>=10:30, exit@last<16:00) ET."""
    df = load_et(sym)
    mm = (df.index.hour * 60 + df.index.minute).to_numpy()
    df = df[(mm >= OR_E) & (mm <= CLOSE_M)]
    out = {}
    for d, g in df.groupby(df.index.normalize()):
        if len(g) < 2: continue
        out[pd.Timestamp(d)] = (float(g["open"].iloc[0]), float(g["close"].iloc[-1]))
    return out


def main():
    section("Safe-haven risk-off tail-hedge (NDX down-vol-expansion trigger)")
    ndx = ndx_riskoff_dates()
    trig = ndx.index[ndx["riskoff"].fillna(False)]
    nontrig = ndx.index[~ndx["riskoff"].fillna(False)]
    print(f"  NDX days: {len(ndx)}  risk-off triggered: {len(trig)} ({len(trig)/max(len(ndx),1)*100:.0f}%)")

    book = pd.read_csv(BOOK_CSV, index_col=0, parse_dates=True)
    if book.index.tz is not None: book.index = book.index.tz_convert("UTC").tz_localize(None)
    book.index = book.index.normalize()
    book_agg = book.sum(axis=1)
    thr = book_agg.quantile(0.10); worst = set(book_agg[book_agg <= thr].index)

    for sym, (dr, cost) in VESSELS.items():
        section(f"Vessel: {sym}  (dir {dr:+d}, cost {cost}bp)")
        px = sh_window_prices(sym)
        # returns on triggered + (placebo) non-triggered days
        def rets(dates):
            out = []
            for d in dates:
                if d in px:
                    e, x = px[d]
                    if e > 0: out.append((d, dr * (x - e) / e - cost / 1e4))
            return out
        tr = rets(trig); ntr = rets(nontrig)
        if len(tr) < 10:
            print("  insufficient triggered days"); continue
        td = pd.to_datetime([d for d, _ in tr]); tn = np.array([r for _, r in tr])
        nn = np.array([r for _, r in ntr])
        sh = ann_sh(tn)
        print(f"  triggered n={len(tn)}  Sh {sh:+.2f}  mean {tn.mean()*1e4:+.2f}bp  MDD {mdd(tn)*100:+.1f}%")
        yrs = td.year.to_numpy()
        for w in ("W1", "W2", "W3"):
            mw = np.array([regime(y) == w for y in yrs])
            if mw.sum() >= 2:
                print(f"    {w}: n={mw.sum():>3d}  Sh {ann_sh(tn[mw]):+.2f}  mean {tn[mw].mean()*1e4:+.2f}bp")
        # placebo: triggered vs non-triggered mean (gross, dir-applied, no cost)
        grT = np.array([dr * (px[d][1] - px[d][0]) / px[d][0] for d, _ in tr if px[d][0] > 0])
        grN = np.array([dr * (px[d][1] - px[d][0]) / px[d][0] for d, _ in ntr if px[d][0] > 0])
        placebo = grT.mean() - grN.mean()
        print(f"  placebo: risk-off mean {grT.mean()*1e4:+.2f}bp vs non-trig {grN.mean()*1e4:+.2f}bp  gap {placebo*1e4:+.2f}bp ({'PASS' if placebo > 0 else 'FAIL'})")
        # tail-complement
        tdn = td.tz_convert("UTC").tz_localize(None) if td.tz is not None else td
        s = pd.Series(tn, index=tdn.normalize()).groupby(level=0).sum()
        j = pd.concat([s.rename("strat"), book_agg.rename("book")], axis=1).fillna(0.0)
        j = j.loc[j["strat"] != 0.0]
        corr_bk = float(j["strat"].corr(j["book"])) if len(j) > 5 else float("nan")
        sw = s.reindex(sorted(worst)).fillna(0.0)
        on_worst = (s.index.isin(worst)).sum()
        mean_worst = float(sw.mean())
        corr_xs = float("nan")
        if sym == "XAUUSD" and "xau_session" in book.columns:
            jx = pd.concat([s.rename("strat"), book[["xau_session"]]], axis=1).fillna(0.0); jx = jx.loc[jx["strat"] != 0.0]
            corr_xs = float(jx["strat"].corr(jx["xau_session"]))
        print(f"  corr→book {corr_bk:+.3f}  | strat mean on book worst-decile {mean_worst*1e4:+.2f}bp "
              f"(active {on_worst}) ({'POSITIVE — hedges' if mean_worst > 0 else 'NEGATIVE'})"
              + (f"  | corr→xau_session {corr_xs:+.3f}" if sym == "XAUUSD" else ""))
        # verdict
        standalone = sh > 0.30 and abs(mdd(tn)) < 0.25 and len(tn) >= 80 and placebo > 0
        complement = (corr_bk <= 0.10) and (mean_worst > 0)
        v = ("PROCEED" if standalone and complement else
             "tail-only (sub-bar standalone)" if complement else
             "standalone-only (not complementary) — REJECT for purpose" if standalone else "REJECT")
        print(f"  -> {sym}: standalone={standalone} complement={complement}  VERDICT: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
