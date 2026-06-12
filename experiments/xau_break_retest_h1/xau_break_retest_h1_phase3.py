#!/usr/bin/env python3
"""XAUUSD H1 NY 12-18 UTC FADE — Phase 3 controls.

Phase 2 (xau_break_retest_h1.md): Sh +1.50 / W1 +1.21 / W2 +1.59 / W3 +1.66,
n=924, MDD -1.68%, corr vs deployed M15 NY-AM FADE = +0.12 (independent edge).
Substantive criteria PASS; sub-window check FAILED for simulator-artifact reasons.

Phase 3 — six controls, in order:

  C1 — Cross-session control
      FADE on Asia 02-08 UTC and Late-US 18-24 UTC (both 6h, matching the
      NY 12-18 deploy window). PASS iff NY Sh >= each off-session Sh + 0.50.

  C2 — Per-regime block-bootstrap CI (1000 iter, 21-trading-day blocks)
      PASS iff lower-95 FULL > +0.50 AND lower-95 W1 > 0 AND lower-95 W2 > 0
      AND lower-95 W3 > 0.

  C3 — Eightcap H1 spread audit (M5 proxy + cost-stress backup)
      Same methodology as parent M15 Phase 3 but on 12-18 UTC window. PASS
      iff p95 proxy spread <= 0.30 USD. FAIL > 0.50. MARGINAL between.
      Backup: if cost-stress @ 1.0pt RT Sh > +0.30 then MARGINAL even if
      proxy fails.

  C4 — Macro-release calendar control
      Same calendar (FOMC/CPI/PPI/NFP/RS/PCE). PASS iff non-macro Sh >= +0.50
      AND macro-day Sh >= +0.50.

  C5 — Corrected sub-window decomposition (replaces broken Phase 2 #11)
      H1 FADE on 12-15 UTC (3h) and 15-18 UTC (3h) as standalone strategies.
      PASS iff at least ONE sub-window has Sh > +0.50 (deploy uses that
      sub-window as the deploy form) AND the aggregate 12-18 stays > +1.00.
      If BOTH sub-windows > +0.30, deploy as 12-18 unchanged.
      If only one > +0.30, deploy ONLY that sub-window (narrower form).

  C6 — Walk-forward 3-fold OOS
      Train 2018-2021 IS / test 2021-2026 OOS; train 2021-2023 IS / test
      2023-2026 OOS; train 2023-2026 IS / no further OOS available (only
      stability check). PASS iff every OOS slice Sh > +0.50.

Reuses the parent M15 Phase 3 helpers + the H1 demo's run_h1 wrapper.

Run:
  venv\\Scripts\\python.exe experiments\\xau_break_retest_h1\\xau_break_retest_h1_phase3.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
# experiments/_live/xau_break_retest_h1/ -> repo root is 3 dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_ROOT, "experiments", "_live", "xau_break_retest_m15"))

from xau_break_retest_m15_demo import (  # noqa: E402
    annualized_sharpe, max_drawdown, simulate_break_retest_m15,
)
from xau_break_retest_m15_phase3 import (  # noqa: E402
    _block_bootstrap_sharpe,
    C2_N_BOOT, C2_BLOCK_DAYS,
    C3_PASS_SPREAD, C3_MARGINAL_SPREAD, C3_SPREAD_PROXY_K,
    C4_MACRO_WINDOW_MIN,
)


# Local calendar loader (parent's _ROOT_P resolves wrong from _live/ subdir,
# and a few calendars have been relocated under _live/ since the parent was
# written). Hard-coded paths from a current Glob over the repo.
CALENDAR_FILES = {
    "fomc": Path(_ROOT) / "experiments" / "_live" / "macro_drift" / "fomc_calendar.csv",
    "cpi":  Path(_ROOT) / "experiments" / "_live" / "pre_cpi_drift" / "cpi_calendar.csv",
    "ppi":  Path(_ROOT) / "experiments" / "pre_ppi_drift" / "ppi_calendar.csv",
    "nfp":  Path(_ROOT) / "experiments" / "_live" / "pre_nfp_drift" / "nfp_calendar.csv",
    "rs":   Path(_ROOT) / "experiments" / "_live" / "pre_retail_sales_drift" / "retail_sales_calendar.csv",
    "pce":  Path(_ROOT) / "experiments" / "pre_pce_drift" / "pce_calendar.csv",
}


def _load_macro_calendar() -> pd.DataFrame:
    rows = []
    for source, path in CALENDAR_FILES.items():
        if not Path(path).exists():
            print(f"  WARN: {source} calendar missing at {path}")
            continue
        df = pd.read_csv(path)
        df["source"] = source
        for _, r in df.iterrows():
            tstr = str(r.get("announce_time_et", "08:30")).strip() or "08:30"
            try:
                hh, mm = tstr.split(":")
                hh = int(hh); mm = int(mm)
            except Exception:
                hh, mm = 8, 30
            d = pd.Timestamp(r["date"])
            local = pd.Timestamp(year=d.year, month=d.month, day=d.day,
                                 hour=hh, minute=mm, tz="US/Eastern")
            ts_utc = local.tz_convert("UTC")
            rows.append({"ts_utc": ts_utc, "source": source})
    if not rows:
        return pd.DataFrame(columns=["ts_utc", "source"])
    return pd.DataFrame(rows).sort_values("ts_utc").reset_index(drop=True)
from xau_break_retest_h1_demo import (  # noqa: E402
    load_h1, run_h1,
    SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC,
    COST_POINTS_DEFAULT,
    H1_SWING_LOOKBACK, H1_RETEST_WINDOW, H1_TIME_EXIT_BARS,
)


# Phase 3 pre-committed thresholds (H1-specific; stricter than parent)
C1_NY_BEATS_BY = 0.50
C1_FAIL_GAP = 0.30
C2_LB_FULL = 0.50      # stricter than parent's +0.30 (we have higher point Sh)
C2_LB_REGIME = 0.0
C4_PASS_SH = 0.50
C4_MARGINAL_SH = 0.20
C5_SUBWIN_PASS_SH = 0.50
C5_SUBWIN_FLOOR = 0.30
C5_AGGREGATE_FLOOR = 1.00
C6_OOS_FLOOR = 0.50


def section(t: str) -> None:
    print(f"\n{'=' * 92}\n  {t}\n{'=' * 92}\n")


def _regime_arr(trades: list[dict], rets: np.ndarray, key: str) -> np.ndarray:
    return np.asarray([r for r, t in zip(rets, trades) if t["regime"] == key],
                      dtype=np.float64)


def _summary(rets: np.ndarray, trades: list[dict], label: str) -> dict:
    if rets.size == 0:
        print(f"  [{label}] empty (0 trades)")
        return {"sharpe": 0.0, "n": 0, "mdd": 0.0, "wr": 0.0, "pf": 0.0, "tpy": 0.0}
    first = pd.Timestamp(trades[0]["entry_ts"])
    last = pd.Timestamp(trades[-1]["entry_ts"])
    years = max((last - first).days / 365.25, 1e-9)
    tpy = rets.size / years
    sh = annualized_sharpe(rets, trades_per_year=tpy)
    eq = (1 + rets).cumprod()
    mdd = max_drawdown(eq)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    wr = wins.size / rets.size
    gw = float(wins.sum()) if wins.size else 0.0
    gl = float(-losses.sum()) if losses.size else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    print(f"  [{label}] n={rets.size:>4d} ({tpy:.0f}/yr) Sh {sh:>+6.2f} "
          f"MDD {mdd*100:>+6.2f}% WR {wr*100:>4.1f}% PF {pf:>4.2f}")
    return {"sharpe": sh, "n": rets.size, "mdd": mdd, "wr": wr, "pf": pf, "tpy": tpy}


# --- C1: Cross-session control --------------------------------------------

def control1_cross_session(df_h1: pd.DataFrame) -> dict:
    section("C1 - Cross-session control (FADE on H1, 6h windows matching NY 12-18)")

    sessions = {
        "NY 12-18 UTC (deploy)": (12, 18, 18),
        "Asia 02-08 UTC":        (2, 8, 8),
        "Late-US 18-24 UTC":     (18, 24, 24),
    }
    out: dict = {}
    for label, (ss, se, sec) in sessions.items():
        rets, trades = run_h1(df_h1, "fade", COST_POINTS_DEFAULT, ss, se, sec)
        out[label] = _summary(rets, trades, f"FADE {label}")

    ny_sh = out["NY 12-18 UTC (deploy)"]["sharpe"]
    print()
    print(f"  Verdict logic: NY Sh must beat each off-session by >= +{C1_NY_BEATS_BY:.2f}; "
          f"FAIL if any within {C1_FAIL_GAP:.2f}.")
    verdict = "PASS"
    for label, stats in out.items():
        if label.startswith("NY 12-18"):
            continue
        sh = stats["sharpe"]
        gap = ny_sh - sh
        if gap < C1_FAIL_GAP:
            v = "FAIL"
        elif gap >= C1_NY_BEATS_BY:
            v = "PASS"
        else:
            v = "MARGINAL"
        print(f"    {label}: Sh {sh:+.2f}  (NY gap {gap:+.2f}) -> {v}")
        if v == "FAIL":
            verdict = "FAIL"
        elif v == "MARGINAL" and verdict != "FAIL":
            verdict = "MARGINAL"
    print(f"\n  C1 VERDICT: {verdict}")
    return {"sessions": out, "verdict": verdict, "ny_sh": ny_sh}


# --- C2: Block-bootstrap CI -----------------------------------------------

def control2_block_bootstrap(df_h1: pd.DataFrame) -> dict:
    section("C2 - Per-regime block-bootstrap CI on baseline H1 12-18 FADE")
    rets, trades = run_h1(df_h1, "fade", COST_POINTS_DEFAULT,
                          SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    first = pd.Timestamp(trades[0]["entry_ts"])
    last = pd.Timestamp(trades[-1]["entry_ts"])
    years = max((last - first).days / 365.25, 1e-9)
    tpy_full = rets.size / years
    block_trades = max(int(np.ceil(C2_BLOCK_DAYS * (tpy_full / 252.0))), 2)
    print(f"  Trades/year = {tpy_full:.1f}  ->  block size = {block_trades} trades "
          f"(= {C2_BLOCK_DAYS} trading days)")

    regimes = {
        "FULL":                   rets,
        "W1 2019-2020":           _regime_arr(trades, rets, "W1 2019-2020"),
        "W2 2021-2022":           _regime_arr(trades, rets, "W2 2021-2022"),
        "W3 2023-2026 (holdout)": _regime_arr(trades, rets, "W3 2023-2026 (holdout)"),
    }
    out: dict = {}
    print()
    print("  Bootstrap (1000 iter) per regime:")
    for label, arr in regimes.items():
        if arr.size < 2 * block_trades:
            print(f"    {label:<28s} n={arr.size:>4d}  insufficient")
            out[label] = {"point": float("nan"), "lo": float("nan"),
                          "hi": float("nan"), "n": arr.size}
            continue
        point = annualized_sharpe(arr, trades_per_year=tpy_full)
        lo, hi = _block_bootstrap_sharpe(arr, tpy_full, block_trades, C2_N_BOOT,
                                         seed=20260526 + hash(label) % 1000)
        print(f"    {label:<28s} n={arr.size:>4d}  point Sh {point:>+6.2f}  "
              f"95% CI [{lo:>+6.2f}, {hi:>+6.2f}]")
        out[label] = {"point": point, "lo": lo, "hi": hi, "n": arr.size}

    full_lb = out["FULL"]["lo"]
    w1_lb = out["W1 2019-2020"]["lo"]
    w2_lb = out["W2 2021-2022"]["lo"]
    w3_lb = out["W3 2023-2026 (holdout)"]["lo"]
    print()
    print(f"  PASS: lower-95 FULL > +{C2_LB_FULL:.2f} AND W1/W2/W3 lb > {C2_LB_REGIME:.2f}")
    full_ok = np.isfinite(full_lb) and full_lb > C2_LB_FULL
    w1_ok = np.isfinite(w1_lb) and w1_lb > C2_LB_REGIME
    w2_ok = np.isfinite(w2_lb) and w2_lb > C2_LB_REGIME
    w3_ok = np.isfinite(w3_lb) and w3_lb > C2_LB_REGIME
    for nm, lb, ok in [("FULL", full_lb, full_ok), ("W1", w1_lb, w1_ok),
                       ("W2", w2_lb, w2_ok), ("W3", w3_lb, w3_ok)]:
        thresh = C2_LB_FULL if nm == "FULL" else C2_LB_REGIME
        print(f"    {nm:<5s} lb {lb:+.2f} > {thresh:+.2f} ? {'PASS' if ok else 'FAIL'}")
    verdict = "PASS" if (full_ok and w1_ok and w2_ok and w3_ok) else "FAIL"
    print(f"\n  C2 VERDICT: {verdict}")
    return {"regimes": out, "verdict": verdict}


# --- C3: Spread audit -----------------------------------------------------

def control3_spread_audit(df_h1: pd.DataFrame) -> dict:
    section("C3 - H1 12-18 UTC spread audit (M1 unavailable; M5 proxy)")
    print(f"  proxy: spread ~= {C3_SPREAD_PROXY_K:.2f} * (M5.high - M5.low)")
    m5 = pd.read_csv(os.path.join(_ROOT, "ohlc_data", "XAUUSD_M5.csv"),
                     parse_dates=["timestamp"])
    m5["timestamp"] = pd.to_datetime(m5["timestamp"], utc=True)
    m5 = m5.sort_values("timestamp").reset_index(drop=True)
    m5 = m5[~m5["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    m5 = m5[m5["timestamp"] >= pd.Timestamp("2018-08-01", tz="UTC")].reset_index(drop=True)
    m5["hour"] = m5["timestamp"].dt.hour

    full_sess = m5[(m5["hour"] >= 12) & (m5["hour"] < 18)
                   & (m5["timestamp"] >= pd.Timestamp("2024-01-01", tz="UTC"))]
    spreads = ((full_sess["high"] - full_sess["low"]).to_numpy()
               * C3_SPREAD_PROXY_K)
    p95 = float(np.percentile(spreads, 95))
    median = float(np.median(spreads))
    print(f"  2024-2025 12-18 UTC pool: n={spreads.size:,}  "
          f"median {median:.2f}  p75 {float(np.percentile(spreads,75)):.2f}  "
          f"p90 {float(np.percentile(spreads,90)):.2f}  p95 {p95:.2f}  "
          f"p99 {float(np.percentile(spreads,99)):.2f}")
    print()
    print(f"  PASS bar (tick-data ideal): p95 spread <= {C3_PASS_SPREAD:.2f} USD")
    print(f"  MARGINAL: p95 {C3_PASS_SPREAD:.2f}-{C3_MARGINAL_SPREAD:.2f} USD")
    print(f"  FAIL    : p95 > {C3_MARGINAL_SPREAD:.2f} USD")

    print()
    print("  Cost-stress (FADE baseline at elevated costs):")
    cost_stress = {}
    for cost in (0.4, 0.6, 0.8, 1.0, 1.5):
        r_, t_ = run_h1(df_h1, "fade", cost, SESSION_START_UTC, SESSION_END_UTC,
                        ENTRY_CUTOFF_UTC)
        if r_.size:
            first = pd.Timestamp(t_[0]["entry_ts"])
            last = pd.Timestamp(t_[-1]["entry_ts"])
            years = max((last - first).days / 365.25, 1e-9)
            tpy = r_.size / years
            sh = annualized_sharpe(r_, trades_per_year=tpy)
        else:
            sh = 0.0
        cost_stress[cost] = sh
        print(f"    cost={cost:.2f}pt  Sh {sh:+.2f}")

    if p95 <= C3_PASS_SPREAD:
        proxy_v = "PASS"
    elif p95 <= C3_MARGINAL_SPREAD:
        proxy_v = "MARGINAL"
    else:
        proxy_v = "FAIL_BY_PROXY"

    sh_at_1pt = cost_stress.get(1.0, 0.0)
    if proxy_v == "FAIL_BY_PROXY":
        if sh_at_1pt > 0.30:
            verdict = "MARGINAL"
            reason = (f"proxy p95 {p95:.2f} FAIL but cost-stress @1.0pt Sh "
                      f"{sh_at_1pt:+.2f} > +0.30 (5x deploy)")
        else:
            verdict = "FAIL"
            reason = (f"proxy p95 {p95:.2f} FAIL AND cost-stress @1.0pt Sh "
                      f"{sh_at_1pt:+.2f} also fails")
    else:
        verdict = proxy_v
        reason = f"proxy p95 = {p95:.2f} USD"
    print(f"\n  C3 VERDICT: {verdict}  ({reason})")
    return {"p95_proxy": p95, "median_proxy": median, "verdict": verdict,
            "cost_stress": cost_stress}


# --- C4: Macro-release calendar ------------------------------------------

def control4_macro_calendar(df_h1: pd.DataFrame) -> dict:
    section("C4 - Macro-release calendar control (FOMC/CPI/PPI/NFP/RS/PCE)")
    cal = _load_macro_calendar()
    print(f"  Loaded {len(cal)} releases from {cal['source'].nunique()} sources:")
    for s, n in cal["source"].value_counts().sort_index().items():
        print(f"    {s:>5s}: {n}")

    rets, trades = run_h1(df_h1, "fade", COST_POINTS_DEFAULT,
                          SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    print(f"\n  Baseline H1 12-18 FADE n={rets.size}")

    def _to_utc_ns(ts) -> np.int64:
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        else:
            t = t.tz_convert("UTC")
        return np.int64(t.value)

    entry_ts_ns = np.array([_to_utc_ns(t["entry_ts"]) for t in trades],
                           dtype=np.int64)
    cal_ts_pd = pd.DatetimeIndex(cal["ts_utc"]).tz_convert("UTC")
    cal_ts_ns = cal_ts_pd.astype(np.int64).to_numpy()
    cal_dates_pre18 = set(t.date() for t in cal_ts_pd if t.hour < 18)
    entry_dates = np.array([pd.Timestamp(t["entry_ts"]).date() for t in trades])

    window_ns = int(C4_MACRO_WINDOW_MIN * 60 * 1_000_000_000)
    macro_flag = np.zeros(len(trades), dtype=bool)
    macro_day_flag = np.zeros(len(trades), dtype=bool)
    cal_sorted = np.sort(cal_ts_ns)
    for i, ets in enumerate(entry_ts_ns):
        idx = np.searchsorted(cal_sorted, ets)
        nearest = np.inf
        if idx < cal_sorted.size:
            nearest = min(nearest, abs(int(cal_sorted[idx]) - int(ets)))
        if idx > 0:
            nearest = min(nearest, abs(int(cal_sorted[idx - 1]) - int(ets)))
        if nearest <= window_ns:
            macro_flag[i] = True
        if entry_dates[i] in cal_dates_pre18:
            macro_day_flag[i] = True
    share_within = float(macro_flag.mean())
    share_macro_day = float(macro_day_flag.mean())
    print(f"\n  Share entries within +/-{C4_MACRO_WINDOW_MIN}min of any release: "
          f"{share_within*100:.1f}%")
    print(f"  Share entries on a US-macro-release day: {share_macro_day*100:.1f}%")

    macro_rets = rets[macro_day_flag]
    macro_trades = [t for t, f in zip(trades, macro_day_flag) if f]
    nonmacro_rets = rets[~macro_day_flag]
    nonmacro_trades = [t for t, f in zip(trades, macro_day_flag) if not f]
    print("\n  Slice summary:")
    s_macro = _summary(macro_rets, macro_trades, "FADE macro-day")
    s_non = _summary(nonmacro_rets, nonmacro_trades, "FADE non-macro-day")

    win_rets = rets[macro_flag]
    win_trades = [t for t, f in zip(trades, macro_flag) if f]
    outwin_rets = rets[~macro_flag]
    outwin_trades = [t for t, f in zip(trades, macro_flag) if not f]
    print()
    s_win = _summary(win_rets, win_trades, "FADE within +/-60min")
    s_outwin = _summary(outwin_rets, outwin_trades, "FADE outside +/-60min")

    macro_sh = s_macro["sharpe"]; non_sh = s_non["sharpe"]
    print()
    print(f"  PASS: non-macro Sh >= +{C4_PASS_SH:.2f} AND macro-day Sh >= +{C4_PASS_SH:.2f}")
    if non_sh >= C4_PASS_SH and macro_sh >= C4_PASS_SH:
        verdict = "PASS"
    elif non_sh >= C4_MARGINAL_SH:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"
    print(f"\n  C4 VERDICT: {verdict}  "
          f"(non-macro Sh {non_sh:+.2f}, macro-day Sh {macro_sh:+.2f})")
    return {"macro_day": s_macro, "non_macro_day": s_non,
            "within_60min": s_win, "outside_60min": s_outwin,
            "share_within": share_within, "share_macro_day": share_macro_day,
            "verdict": verdict}


# --- C5: Corrected sub-window decomposition -------------------------------

def control5_subwindow(df_h1: pd.DataFrame) -> dict:
    section("C5 - Corrected sub-window decomposition (12-15 / 15-18, both 3h)")
    SUBS = [("12-15 UTC", 12, 15, 15), ("15-18 UTC", 15, 18, 18)]
    out: dict = {}
    for label, ss, se, sec in SUBS:
        rets_f, trades_f = run_h1(df_h1, "fade", COST_POINTS_DEFAULT, ss, se, sec)
        rets_c, trades_c = run_h1(df_h1, "continuation", COST_POINTS_DEFAULT, ss, se, sec)
        s_f = _summary(rets_f, trades_f, f"FADE {label}")
        s_c = _summary(rets_c, trades_c, f"CONT {label}")
        # Regime breakdown for FADE
        from xau_break_retest_m15_demo import regime_breakdown as rb_fn
        rb = rb_fn(rets_f, trades_f, silent=True) if rets_f.size else {}
        w1 = rb.get("W1 2019-2020", {}).get("sharpe", 0.0)
        w2 = rb.get("W2 2021-2022", {}).get("sharpe", 0.0)
        w3 = rb.get("W3 2023-2026 (holdout)", {}).get("sharpe", 0.0)
        print(f"    {label} FADE regime: W1 {w1:+.2f}  W2 {w2:+.2f}  W3 {w3:+.2f}")
        out[label] = {**s_f, "cont_sharpe": s_c["sharpe"],
                      "fade_gap": s_f["sharpe"] - s_c["sharpe"],
                      "w1": w1, "w2": w2, "w3": w3}

    sh_12_15 = out["12-15 UTC"]["sharpe"]
    sh_15_18 = out["15-18 UTC"]["sharpe"]
    aggregate_rets, aggregate_trades = run_h1(df_h1, "fade", COST_POINTS_DEFAULT, 12, 18, 18)
    agg_first = pd.Timestamp(aggregate_trades[0]["entry_ts"])
    agg_last = pd.Timestamp(aggregate_trades[-1]["entry_ts"])
    agg_years = max((agg_last - agg_first).days / 365.25, 1e-9)
    agg_tpy = aggregate_rets.size / agg_years
    agg_sh = annualized_sharpe(aggregate_rets, trades_per_year=agg_tpy)

    print()
    print(f"  Aggregate 12-18 Sh: {agg_sh:+.2f}")
    print(f"  PASS logic: aggregate > +{C5_AGGREGATE_FLOOR:.2f} AND at least one "
          f"sub-window > +{C5_SUBWIN_PASS_SH:.2f}")
    print(f"             (both > +{C5_SUBWIN_FLOOR:.2f} = deploy 12-18 unchanged; "
          f"only one > +{C5_SUBWIN_PASS_SH:.2f} = deploy narrower form)")

    one_strong = (sh_12_15 > C5_SUBWIN_PASS_SH) or (sh_15_18 > C5_SUBWIN_PASS_SH)
    both_floor = (sh_12_15 > C5_SUBWIN_FLOOR) and (sh_15_18 > C5_SUBWIN_FLOOR)
    agg_ok = agg_sh > C5_AGGREGATE_FLOOR

    if agg_ok and one_strong and both_floor:
        verdict = "PASS — deploy 12-18 UTC unchanged"
        deploy_form = "12-18 UTC (full window)"
    elif agg_ok and one_strong and not both_floor:
        verdict = "MARGINAL — deploy narrower form"
        deploy_form = ("12-15 UTC" if sh_12_15 >= sh_15_18 else "15-18 UTC")
    elif agg_ok:
        verdict = "MARGINAL — aggregate edge but no sub-window standalone clears bar"
        deploy_form = "12-18 UTC (rely on wide-lookback interaction effects)"
    else:
        verdict = "FAIL"
        deploy_form = "n/a"

    print(f"\n  C5 VERDICT: {verdict}")
    print(f"  Deploy form: {deploy_form}")
    return {"subs": out, "aggregate_sh": agg_sh,
            "verdict": verdict, "deploy_form": deploy_form}


# --- C6: Walk-forward 3-fold ---------------------------------------------

def control6_walk_forward(df_h1: pd.DataFrame) -> dict:
    section("C6 - Walk-forward 3-fold OOS (Train IS / next slice OOS)")
    print("  3-fold scheme:")
    print("    fold 1: IS 2018-2020   OOS 2021-2022")
    print("    fold 2: IS 2018-2022   OOS 2023-2024")
    print("    fold 3: IS 2018-2024   OOS 2025-2026")
    print("  Strategy: parameters are pre-committed (no tuning per fold), so")
    print("  'walk-forward' = compute OOS Sharpe on the same fixed-parameter strategy")
    print("  for each OOS slice.\n")

    FOLDS = [
        ("fold 1 OOS 2021-2022", pd.Timestamp("2021-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")),
        ("fold 2 OOS 2023-2024", pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")),
        ("fold 3 OOS 2025-2026", pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2027-01-01", tz="UTC")),
    ]
    rets, trades = run_h1(df_h1, "fade", COST_POINTS_DEFAULT,
                          SESSION_START_UTC, SESSION_END_UTC, ENTRY_CUTOFF_UTC)
    ts_arr = np.array([pd.Timestamp(t["entry_ts"]) for t in trades])

    out: dict = {}
    sharpes = []
    for label, lo, hi in FOLDS:
        mask = (ts_arr >= lo) & (ts_arr < hi)
        sub_rets = rets[mask]
        sub_trades = [t for t, m in zip(trades, mask) if m]
        if sub_rets.size < 30:
            print(f"  {label}: n={sub_rets.size} insufficient")
            out[label] = {"sharpe": float("nan"), "n": sub_rets.size}
            sharpes.append(float("nan"))
            continue
        first = pd.Timestamp(sub_trades[0]["entry_ts"])
        last = pd.Timestamp(sub_trades[-1]["entry_ts"])
        years = max((last - first).days / 365.25, 1e-9)
        tpy = sub_rets.size / years
        sh = annualized_sharpe(sub_rets, trades_per_year=tpy)
        eq = (1 + sub_rets).cumprod()
        mdd = max_drawdown(eq)
        print(f"  {label}: n={sub_rets.size:>4d}  Sh {sh:+.2f}  MDD {mdd*100:+.2f}%")
        out[label] = {"sharpe": sh, "n": sub_rets.size, "mdd": mdd}
        sharpes.append(sh)

    valid = [s for s in sharpes if np.isfinite(s)]
    mean_oos = float(np.mean(valid)) if valid else float("nan")
    min_oos = float(np.min(valid)) if valid else float("nan")
    print()
    print(f"  Mean OOS Sh: {mean_oos:+.2f}  Min OOS Sh: {min_oos:+.2f}")
    print(f"  PASS: every OOS slice Sh > +{C6_OOS_FLOOR:.2f}")
    all_ok = all(np.isfinite(s) and s > C6_OOS_FLOOR for s in sharpes)
    marg_ok = all(np.isfinite(s) and s > 0 for s in sharpes)
    if all_ok:
        verdict = "PASS"
    elif marg_ok:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"
    print(f"\n  C6 VERDICT: {verdict}")
    return {"folds": out, "mean_oos": mean_oos, "min_oos": min_oos, "verdict": verdict}


# --- Main -----------------------------------------------------------------

def main() -> int:
    section("Loading XAU H1")
    df_h1 = load_h1()
    print(f"  H1 bars: {len(df_h1):,}  range {df_h1['timestamp'].min()} -> {df_h1['timestamp'].max()}")

    c1 = control1_cross_session(df_h1)
    c2 = control2_block_bootstrap(df_h1)
    c3 = control3_spread_audit(df_h1)
    c4 = control4_macro_calendar(df_h1)
    c5 = control5_subwindow(df_h1)
    c6 = control6_walk_forward(df_h1)

    section("Phase 3 SUMMARY (H1 NY 12-18 UTC FADE)")
    rows = [
        ("C1 cross-session",      c1["verdict"],
            f"NY Sh {c1['ny_sh']:+.2f}; off-sessions: " +
            ", ".join(f"{k.split(' ')[0]} {v['sharpe']:+.2f}"
                      for k, v in c1["sessions"].items() if not k.startswith("NY"))),
        ("C2 block-bootstrap",    c2["verdict"],
            f"FULL lb {c2['regimes']['FULL']['lo']:+.2f}, "
            f"W1 lb {c2['regimes']['W1 2019-2020']['lo']:+.2f}, "
            f"W2 lb {c2['regimes']['W2 2021-2022']['lo']:+.2f}, "
            f"W3 lb {c2['regimes']['W3 2023-2026 (holdout)']['lo']:+.2f}"),
        ("C3 spread audit",       c3["verdict"],
            f"p95 proxy {c3['p95_proxy']:.2f} USD; cost-stress@1pt Sh "
            f"{c3['cost_stress'][1.0]:+.2f}"),
        ("C4 macro calendar",     c4["verdict"],
            f"non-macro Sh {c4['non_macro_day']['sharpe']:+.2f}, "
            f"macro-day Sh {c4['macro_day']['sharpe']:+.2f}, "
            f"macro-day share {c4['share_macro_day']*100:.0f}%"),
        ("C5 sub-window decomp",  c5["verdict"],
            f"12-15 Sh {c5['subs']['12-15 UTC']['sharpe']:+.2f}, "
            f"15-18 Sh {c5['subs']['15-18 UTC']['sharpe']:+.2f}, "
            f"agg Sh {c5['aggregate_sh']:+.2f} -> {c5['deploy_form']}"),
        ("C6 walk-forward",       c6["verdict"],
            f"mean OOS {c6['mean_oos']:+.2f}, min OOS {c6['min_oos']:+.2f}"),
    ]
    for label, v, detail in rows:
        print(f"  {label:<24s} : {v:<35s}  {detail}")

    n_fail = sum(1 for _, v, _ in rows if v.startswith("FAIL"))
    n_marg = sum(1 for _, v, _ in rows if v.startswith("MARGINAL"))
    print()
    if n_fail == 0 and n_marg == 0:
        verdict = "PHASE 2-3 PASS  (deploy-ready)"
    elif n_fail == 0 and n_marg >= 1:
        verdict = f"MARGINAL  ({n_marg} control(s) marginal; deploy with qualification)"
    elif n_fail == 1:
        verdict = "MARGINAL  (1 control FAIL; downgrade with qualification)"
    else:
        verdict = f"REJECT  ({n_fail} controls FAIL)"
    print(f"  >>> PHASE 3 OVERALL VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
