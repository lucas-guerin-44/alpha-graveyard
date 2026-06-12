#!/usr/bin/env python3
"""XAUUSD H1 NY 12-18 UTC FADE — Break of Structure + Retest.

Thesis: experiments/xau_break_retest_h1/xau_break_retest_h1.md

Origin: external agent reported Sh +1.78 / W1 +1.46 / W2 +1.99 / W3 +1.98
on H1 12-18 UTC FADE at 0.44 bps cost. Numbers are too clean — running an
adversarial Phase 2 with three additional skepticism checks baked in:
  (#10) Corr vs deployed M15 NY-AM FADE < +0.70 (redundancy tombstone)
  (#11) All three sub-windows individually positive
  (#12) Excl-NY-AM (12-13 + 15-18 only) Sharpe still > +0.30

Run:
  venv\\Scripts\\python.exe experiments\\xau_break_retest_h1\\xau_break_retest_h1_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
# experiments/_live/xau_break_retest_h1/ -> repo root is 3 dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "experiments", "_live", "xau_break_retest_m15"))

from xau_break_retest_m15_demo import (  # type: ignore
    simulate_break_retest_m15,
    annualized_sharpe,
    max_drawdown,
    deflated_sharpe,
    compute_atr_adx,
    report_run,
    regime_breakdown,
    section,
    label_regime,
)


# ---------------------------------------------------------------------------
# H1-specific config
# ---------------------------------------------------------------------------

DATA_PATH = os.path.join(_ROOT, "ohlc_data", "XAUUSD_M5.csv")

SESSION_START_UTC = 12
SESSION_END_UTC = 18
ENTRY_CUTOFF_UTC = 18

# H1 bar-count params (rescaled from M15 to preserve temporal scope)
H1_SWING_LOOKBACK = 4        # 4 H1 = 4h   (M15 was 16 bars = 4h)
H1_RETEST_WINDOW = 1         # 1 H1 = 60min (M15 was 3 bars = 45min)
H1_RETEST_TOL_ATR = 0.30
H1_STOP_ATR_MULT = 1.20
H1_TIME_EXIT_BARS = 2        # 2 H1 = 120min (M15 was 6 bars = 90min)

COST_POINTS_DEFAULT = 0.20
COST_POINTS_SWEEP = (0.10, 0.20, 0.40, 0.80)

# Parent deployed M15 NY-AM (for corr diagnostic)
NYAM_M15_START = 13
NYAM_M15_END = 15
NYAM_M15_ENTRY_CUTOFF = 15
NYAM_M15_SWING = 16
NYAM_M15_RETEST = 3
NYAM_M15_TIME_EXIT = 6

# Pre-committed kill criteria (stricter than parent — see thesis §)
KC_SHARPE_FULL = 0.80
KC_SHARPE_W1 = 0.40
KC_SHARPE_W2 = 0.40
KC_SHARPE_W3 = 0.30
KC_MDD = 0.10
KC_TRADES_MIN = 200
KC_FADE_GAP = 0.30
KC_COST_STRESS_PT = 0.40
KC_COST_STRESS_SH = 0.20
KC_DEFLATED_SH = 0.40
KC_CORR_VS_NYAM = 0.70
KC_SUBWINDOW_FLOOR = 0.0
KC_EXCL_NYAM_SH = 0.30
N_VARIANTS_PRECOMMITTED = 5


# ---------------------------------------------------------------------------
# H1 loader
# ---------------------------------------------------------------------------

def load_h1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[~df["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    df = df[df["timestamp"] >= pd.Timestamp("2018-08-01", tz="UTC")].reset_index(drop=True)
    df = df.set_index("timestamp")
    h1 = df.resample("1h", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna(how="any").reset_index()
    h1["hour"] = h1["timestamp"].dt.hour
    h1["minute"] = h1["timestamp"].dt.minute
    h1["date"] = h1["timestamp"].dt.date
    h1["dow"] = h1["timestamp"].dt.dayofweek
    return h1


def load_m15() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[~df["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    df = df[df["timestamp"] >= pd.Timestamp("2018-08-01", tz="UTC")].reset_index(drop=True)
    df = df.set_index("timestamp")
    m15 = df.resample("15min", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
    }).dropna(how="any").reset_index()
    m15["hour"] = m15["timestamp"].dt.hour
    m15["minute"] = m15["timestamp"].dt.minute
    m15["date"] = m15["timestamp"].dt.date
    m15["dow"] = m15["timestamp"].dt.dayofweek
    return m15


# ---------------------------------------------------------------------------
# Per-day pnl aggregation + correlation
# ---------------------------------------------------------------------------

def per_day_pnl(rets: np.ndarray, trades: list[dict]) -> pd.Series:
    if rets.size == 0:
        return pd.Series(dtype=np.float64)
    rows = []
    for r, t in zip(rets, trades):
        d = pd.Timestamp(t["entry_ts"]).normalize()
        rows.append((d, r))
    s = pd.DataFrame(rows, columns=["date", "ret"]).groupby("date")["ret"].sum()
    return s


def trade_corr(rets_a: np.ndarray, trades_a: list[dict],
               rets_b: np.ndarray, trades_b: list[dict]) -> tuple[float, int]:
    if rets_a.size == 0 or rets_b.size == 0:
        return float("nan"), 0
    s_a = per_day_pnl(rets_a, trades_a)
    s_b = per_day_pnl(rets_b, trades_b)
    lo = max(s_a.index.min(), s_b.index.min())
    hi = min(s_a.index.max(), s_b.index.max())
    s_a = s_a[(s_a.index >= lo) & (s_a.index <= hi)]
    s_b = s_b[(s_b.index >= lo) & (s_b.index <= hi)]
    all_dates = s_a.index.union(s_b.index)
    a = s_a.reindex(all_dates, fill_value=0.0).to_numpy()
    b = s_b.reindex(all_dates, fill_value=0.0).to_numpy()
    if a.std() == 0 or b.std() == 0:
        return float("nan"), len(all_dates)
    return float(np.corrcoef(a, b)[0, 1]), len(all_dates)


# ---------------------------------------------------------------------------
# H1 run wrapper (passes H1 bar-count params)
# ---------------------------------------------------------------------------

def run_h1(df_h1: pd.DataFrame, direction: str, cost_points: float,
           session_start: int, session_end: int, entry_cutoff: int,
           swing_lookback: int = H1_SWING_LOOKBACK,
           retest_window: int = H1_RETEST_WINDOW,
           time_exit_bars: int = H1_TIME_EXIT_BARS,
           atr_floor_usd: float = 0.0, adx_thresh: float = 0.0,
           ) -> tuple[np.ndarray, list[dict]]:
    return simulate_break_retest_m15(
        df_h1, direction=direction,
        swing_lookback=swing_lookback,
        retest_window=retest_window,
        retest_tol_atr=H1_RETEST_TOL_ATR,
        stop_atr_mult=H1_STOP_ATR_MULT,
        session_start_utc=session_start,
        session_end_utc=session_end,
        entry_cutoff_utc=entry_cutoff,
        time_exit_bars=time_exit_bars,
        cost_points=cost_points,
        atr_floor_usd=atr_floor_usd,
        adx_thresh=adx_thresh,
    )


def summarise(rets: np.ndarray, trades: list[dict]) -> dict:
    if rets.size == 0:
        return {"sharpe": 0.0, "mdd": 0.0, "n": 0, "wr": 0.0, "pf": 0.0,
                "mean": 0.0, "tpy": 0.0}
    first = pd.Timestamp(trades[0]["entry_ts"])
    last = pd.Timestamp(trades[-1]["entry_ts"])
    years = max((last - first).days / 365.25, 1e-9)
    tpy = len(rets) / years
    sh = annualized_sharpe(rets, trades_per_year=tpy)
    eq = (1.0 + rets).cumprod()
    mdd = max_drawdown(eq)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    wr = len(wins) / len(rets)
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    return {"sharpe": sh, "mdd": mdd, "n": len(rets), "wr": wr, "pf": pf,
            "mean": float(rets.mean()), "tpy": tpy}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section("Loading XAU M5 -> resample to H1 and M15")
    df_h1 = load_h1()
    df_m15 = load_m15()
    print(f"  H1 bars : {len(df_h1):,}  range {df_h1['timestamp'].min().date()} -> {df_h1['timestamp'].max().date()}")
    print(f"  M15 bars: {len(df_m15):,}")

    in_sess_h1 = df_h1[(df_h1["hour"] >= SESSION_START_UTC) & (df_h1["hour"] < SESSION_END_UTC)]
    print(f"  H1 in-session 12-18 UTC: {len(in_sess_h1):,} bars across {in_sess_h1['date'].nunique()} days")

    # ---- (A) Baseline H1 12-18 UTC, BOTH directions ----
    section("(A) H1 NY 12-18 UTC baseline - BOTH directions at deploy cost 0.20pt")
    rets_f, trades_f = run_h1(df_h1, "fade", COST_POINTS_DEFAULT,
                              SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    stats_f = report_run("H1 12-18 FADE", rets_f, trades_f)
    print()
    print("  Regime breakdown - H1 12-18 FADE:")
    rb_f = regime_breakdown(rets_f, trades_f)

    print()
    rets_c, trades_c = run_h1(df_h1, "continuation", COST_POINTS_DEFAULT,
                              SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    stats_c = report_run("H1 12-18 CONT", rets_c, trades_c)
    print()
    print("  Regime breakdown - H1 12-18 CONT:")
    rb_c = regime_breakdown(rets_c, trades_c)

    # ---- (B) Cost sweep on baseline FADE ----
    section("(B) Cost sweep on H1 12-18 FADE")
    print(f"  {'cost (pt)':<10s} {'cost (bp@$2900)':<16s} {'Sh':>7s} {'MDD':>8s} {'n':>5s}")
    for cp in (0.0, 0.05, 0.10, 0.13, 0.20, 0.30, 0.40, 0.80):
        r_, t_ = run_h1(df_h1, "fade", cp, SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
        s_ = summarise(r_, t_)
        bp = cp / 2900 * 10000
        flag = ""
        if cp == COST_POINTS_DEFAULT:
            flag = "  (deploy)"
        elif abs(cp - 0.13) < 1e-6:
            flag = "  (ext-agent's 0.44bp)"
        elif cp == KC_COST_STRESS_PT:
            flag = "  (stress)"
        print(f"  {cp:<10.2f} {bp:<16.2f} {s_['sharpe']:>+6.2f} "
              f"{s_['mdd']*100:>+7.2f}% {s_['n']:>5d}{flag}")

    # ---- (C) Sub-window decomposition ----
    section("(C) Sub-window decomposition - which slice carries the Sharpe?")
    SUBWINDOWS = [
        ("12-13 UTC (pre-cash)", 12, 13, 13),
        ("13-15 UTC (NY-AM, same as deployed M15)", 13, 15, 15),
        ("15-18 UTC (NY-PM)", 15, 18, 18),
    ]
    sub_results = {}
    for sname, ss, se, sec in SUBWINDOWS:
        sub_results[sname] = {}
        for dirn in ("fade", "continuation"):
            r_, t_ = run_h1(df_h1, dirn, COST_POINTS_DEFAULT, ss, se, sec)
            s_ = summarise(r_, t_)
            rb_ = regime_breakdown(r_, t_, silent=True) if r_.size else {}
            w1 = rb_.get("W1 2019-2020", {}).get("sharpe", 0.0)
            w2 = rb_.get("W2 2021-2022", {}).get("sharpe", 0.0)
            w3 = rb_.get("W3 2023-2026 (holdout)", {}).get("sharpe", 0.0)
            sub_results[sname][dirn] = {**s_, "w1": w1, "w2": w2, "w3": w3,
                                        "rets": r_, "trades": t_}
            print(f"  {sname:<42s} {dirn.upper():<5s} "
                  f"Sh {s_['sharpe']:>+6.2f}  n={s_['n']:>4d}  "
                  f"W1 {w1:>+5.2f} W2 {w2:>+5.2f} W3 {w3:>+5.2f}  "
                  f"MDD {s_['mdd']*100:>+6.2f}%")

    # ---- (D) Excl-NY-AM check: 12-13 + 15-18 only ----
    section("(D) Excl-NY-AM check - H1 FADE on 12-13 + 15-18 UTC ONLY (skip deployed window)")
    # Simulate over BOTH sub-windows separately, concatenate trades, recompute Sharpe.
    excl_rets_parts = []
    excl_trades_parts = []
    for sname, ss, se, sec in [("12-13", 12, 13, 13), ("15-18", 15, 18, 18)]:
        r_, t_ = run_h1(df_h1, "fade", COST_POINTS_DEFAULT, ss, se, sec)
        excl_rets_parts.append(r_)
        excl_trades_parts.extend(t_)
    excl_rets = np.concatenate(excl_rets_parts) if excl_rets_parts else np.array([])
    excl_trades = excl_trades_parts
    # Re-sort by entry_ts to make per-day correlation sane
    if excl_trades:
        order = np.argsort([pd.Timestamp(t["entry_ts"]) for t in excl_trades])
        excl_rets = excl_rets[order]
        excl_trades = [excl_trades[i] for i in order]
    excl_stats = report_run("H1 EXCL-NY-AM FADE (12-13 + 15-18)", excl_rets, excl_trades)
    print()
    print("  Regime breakdown - H1 EXCL-NY-AM FADE:")
    rb_excl = regime_breakdown(excl_rets, excl_trades)

    # ---- (E) Corr vs deployed M15 NY-AM FADE ----
    section("(E) Corr vs deployed M15 NY-AM FADE (per-day net-ret)")
    m15_rets, m15_trades = simulate_break_retest_m15(
        df_m15, direction="fade",
        swing_lookback=NYAM_M15_SWING,
        retest_window=NYAM_M15_RETEST,
        retest_tol_atr=0.30, stop_atr_mult=1.20,
        session_start_utc=NYAM_M15_START,
        session_end_utc=NYAM_M15_END,
        entry_cutoff_utc=NYAM_M15_ENTRY_CUTOFF,
        time_exit_bars=NYAM_M15_TIME_EXIT,
        cost_points=COST_POINTS_DEFAULT,
    )
    m15_stats = summarise(m15_rets, m15_trades)
    print(f"  Deployed M15 NY-AM FADE: Sh {m15_stats['sharpe']:+.2f}  n={m15_stats['n']}  "
          f"(sanity vs published +1.49)")

    corr_full, corr_n = trade_corr(rets_f, trades_f, m15_rets, m15_trades)
    print(f"  Corr (H1 12-18 FADE vs deployed M15 NY-AM FADE) per-day net-ret: "
          f"{corr_full:+.3f}  (n_days={corr_n})")

    # Corr for the excl-NY-AM version (this is what matters for the
    # redundancy tombstone: even if H1 12-18 corr is high, excl-NY-AM corr
    # tells us if there's INDEPENDENT edge in 12-13 + 15-18).
    corr_excl, corr_excl_n = trade_corr(excl_rets, excl_trades, m15_rets, m15_trades)
    print(f"  Corr (H1 EXCL-NY-AM FADE vs deployed M15 NY-AM FADE) per-day net-ret: "
          f"{corr_excl:+.3f}  (n_days={corr_excl_n})")

    # ---- (F) Direction null + cost-stress for headline numbers ----
    fg_f = stats_f["sharpe"] - stats_c["sharpe"]
    rets_f_cs, _ = run_h1(df_h1, "fade", KC_COST_STRESS_PT,
                          SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    stats_f_cs = summarise(rets_f_cs, _)
    dsh_f = deflated_sharpe(stats_f["sharpe"], rets_f, n_trials=N_VARIANTS_PRECOMMITTED)

    # ---- KILL CRITERIA ----
    section("Phase 2 kill criteria - H1 NY 12-18 UTC FADE")
    w1_sh = rb_f.get("W1 2019-2020", {}).get("sharpe", 0.0)
    w2_sh = rb_f.get("W2 2021-2022", {}).get("sharpe", 0.0)
    w3_sh = rb_f.get("W3 2023-2026 (holdout)", {}).get("sharpe", 0.0)

    # Sub-window all-positive check (Sharpe)
    subwins_sh = []
    for sname, _, _, _ in SUBWINDOWS:
        subwins_sh.append((sname, sub_results[sname]["fade"]["sharpe"]))
    subwin_all_pos = all(sh > KC_SUBWINDOW_FLOOR for _, sh in subwins_sh)

    checks = [
        (f"FULL Sharpe        > {KC_SHARPE_FULL:.2f}", stats_f["sharpe"] > KC_SHARPE_FULL,
            f"{stats_f['sharpe']:+.2f}"),
        (f"W1 Sharpe          > {KC_SHARPE_W1:.2f}", w1_sh > KC_SHARPE_W1, f"{w1_sh:+.2f}"),
        (f"W2 Sharpe          > {KC_SHARPE_W2:.2f}", w2_sh > KC_SHARPE_W2, f"{w2_sh:+.2f}"),
        (f"W3 Sharpe          > {KC_SHARPE_W3:.2f}", w3_sh > KC_SHARPE_W3, f"{w3_sh:+.2f}"),
        (f"MDD                < {KC_MDD*100:.0f}%", abs(stats_f["mdd"]) < KC_MDD,
            f"{stats_f['mdd']*100:+.2f}%"),
        (f"Trades            >= {KC_TRADES_MIN}", stats_f["n"] >= KC_TRADES_MIN,
            f"{stats_f['n']}"),
        (f"Fade-gap           > {KC_FADE_GAP:.2f}", fg_f > KC_FADE_GAP, f"{fg_f:+.2f}"),
        (f"Cost-stress Sh@{KC_COST_STRESS_PT:.2f}pt > {KC_COST_STRESS_SH:.2f}",
            stats_f_cs["sharpe"] > KC_COST_STRESS_SH, f"{stats_f_cs['sharpe']:+.2f}"),
        (f"Deflated Sh        > {KC_DEFLATED_SH:.2f}", dsh_f > KC_DEFLATED_SH, f"{dsh_f:+.2f}"),
        (f"Corr vs M15 NY-AM  < {KC_CORR_VS_NYAM:.2f}",
            (corr_full < KC_CORR_VS_NYAM), f"{corr_full:+.2f}"),
        (f"All 3 subwins Sh   > {KC_SUBWINDOW_FLOOR:.2f}", subwin_all_pos,
            "  ".join(f"{n.split(' ')[0]}:{sh:+.2f}" for n, sh in subwins_sh)),
        (f"Excl-NY-AM Sh      > {KC_EXCL_NYAM_SH:.2f}",
            excl_stats["sharpe"] > KC_EXCL_NYAM_SH, f"{excl_stats['sharpe']:+.2f}"),
    ]
    all_pass = True
    insufficient = stats_f["n"] < KC_TRADES_MIN
    for desc, ok, val in checks:
        print(f"  {desc:<40s} : {'PASS' if ok else 'FAIL'}  ({val})")
        if not ok:
            all_pass = False
    if insufficient:
        verdict = "INSUFFICIENT_N"
    elif all_pass:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    print(f"\n  -> {verdict} on Phase 2 kill criteria")

    # ---- Summary ----
    section("Summary")
    print(f"  H1 12-18 FADE: Sh {stats_f['sharpe']:+.2f}  n={stats_f['n']}  "
          f"W1 {w1_sh:+.2f} W2 {w2_sh:+.2f} W3 {w3_sh:+.2f}  "
          f"MDD {stats_f['mdd']*100:+.2f}%")
    print(f"  External-agent claim: Sh +1.78 / W1 +1.46 / W2 +1.99 / W3 +1.98 / "
          f"n=1045 / MDD -1.97% / cost 0.44 bps")
    print(f"  Replication delta: Sh {stats_f['sharpe'] - 1.78:+.2f}  "
          f"W1 {w1_sh - 1.46:+.2f}  W2 {w2_sh - 1.99:+.2f}  W3 {w3_sh - 1.98:+.2f}")
    print(f"  Deployed M15 NY-AM (this run for sanity): Sh {m15_stats['sharpe']:+.2f}  "
          f"(published +1.49)")
    print()
    print(f"  Excl-NY-AM Sh: {excl_stats['sharpe']:+.2f}  -- independent edge in 12-13 + 15-18?")
    print(f"  Corr vs M15 NY-AM: {corr_full:+.2f}  -- redundancy with deployed strategy?")
    print(f"  Corr (excl-NY-AM) vs M15 NY-AM: {corr_excl:+.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
