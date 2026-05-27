#!/usr/bin/env python3
"""xau_fix_drift Phase 2 simulator.

Thesis: experiments/xau_fix_drift/xau_fix_drift.md

Pre-fix drift continuation on XAUUSD M1 around the LBMA Gold Price auction
prints (10:30 / 15:00 London local, DST-aware).

Per-fix logic:
  drift_bps = (close[fix - 5min] - close[fix - 30min]) / close[fix - 30min] * 1e4
  if |drift_bps| < MIN_PRE_DRIFT_BPS: skip
  CONTINUATION: enter at fix-5 min in sign(drift), exit at fix+5 min
  FADE        : enter at fix-5 min in -sign(drift), exit at fix+5 min

Variants scored:
  AM-CONT, AM-FADE, PM-CONT, PM-FADE, COMBINED-CONT, COMBINED-FADE

Phases:
  (1) Per-variant headline (FULL, 0.20pt RT cost, MIN_PRE_DRIFT_BPS=3)
  (2) Regime breakdown: W1 2018-2020 / W2 2021-2022 / W3 2023-2026 (holdout)
  (3) Cost sweep:   0.10 / 0.15 / 0.20 / 0.30 / 0.50 pt RT
  (4) Pre-drift threshold sweep:  1 / 2 / 3 / 5 / 8 bps
  (5) Phase 0c cheap pre-check: raw drift signal vs deployed xau_session daily PnL
  (6) Phase 2 correlation tombstone: trade-by-trade daily PnL corr vs
      deployed XAU book (xau_session + xau_br_m15 + xau_br_h1)
  (7) Kill-criteria check vs 11 pre-committed binding criteria.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_fix_drift/xau_fix_drift_demo.py
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "xau_session"))
sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "xau_break_retest_m15"))
sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "xau_break_retest_h1"))

from _build_fix_calendar import build_fix_calendar  # type: ignore


# ---------------------------------------------------------------------------
# Config (mirrors thesis doc signal-math block)
# ---------------------------------------------------------------------------

DATA_PATH = _ROOT / "ohlc_data" / "XAUUSD_M1.csv"

PRE_FIX_LOOKBACK_MIN = 25       # measure drift from fix-30 to fix-5
ENTRY_OFFSET_MIN = 5            # enter at fix - 5 min
EXIT_OFFSET_MIN = 5             # exit at fix + 5 min  (10-min hold)
TOLERANCE_MIN = 3               # max gap when snapping fix offsets to M1 bars

MIN_PRE_DRIFT_BPS_DEFAULT = 3.0
PRE_DRIFT_SWEEP = (1.0, 2.0, 3.0, 5.0, 8.0)

COST_POINTS_RT_DEFAULT = 0.20
COST_SWEEP = (0.10, 0.15, 0.20, 0.30, 0.50)
COST_STRESS = 0.30              # criterion #8 stress level

# Regime windows (per thesis doc — note W1 starts 2018 to use full lake)
REGIMES = (
    ("W1 2018-2020", 2018, 2020),
    ("W2 2021-2022", 2021, 2022),
    ("W3 2023-2026 (holdout)", 2023, 2026),
)

# Pre-committed kill criteria
KC_SHARPE_FULL = 0.40
KC_W1_SH = 0.10
KC_W2_SH = 0.10
KC_W3_SH = 0.20
KC_MDD = 0.10
KC_TRADES = 400
KC_DIRGAP = 0.40
KC_COST_STRESS_SH = 0.0
KC_SINGLE_WINDOW_SH = 0.20
KC_DEFLATED_SH = 0.20
KC_CORR_VS_DEPLOYED = 0.40
N_VARIANTS_PRECOMMITTED = 8     # 2 windows x 4 cost levels reported


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def label_regime(year: int) -> str:
    for lab, ys, ye in REGIMES:
        if ys <= year <= ye:
            return lab
    return "?"


def annualized_sharpe_per_trade(r: np.ndarray, events_per_year: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(events_per_year))


def max_drawdown(eq: np.ndarray) -> float:
    if len(eq) == 0:
        return 0.0
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min())


def deflated_sharpe(observed_sh: float, returns: np.ndarray, n_trials: int) -> float:
    """Bailey/Lopez-de-Prado deflated Sharpe (simplified, n_trials based)."""
    n = returns.size
    if n < 10 or n_trials < 2:
        return observed_sh
    skew = float(((returns - returns.mean()) ** 3).mean() / (returns.std(ddof=1) ** 3 + 1e-12))
    kurt = float(((returns - returns.mean()) ** 4).mean() / (returns.std(ddof=1) ** 4 + 1e-12))
    # Expected max Sharpe of n_trials draws from a standard normal:
    emc = 0.5772156649
    exp_max = (1 - emc) * np.sqrt(2 * np.log(n_trials)) + emc * np.sqrt(2 * np.log(n_trials)) / (2 * np.log(n_trials))
    sh_per_event = observed_sh / np.sqrt(max(n - 1, 1))
    var = (1 - skew * sh_per_event + (kurt - 1) / 4 * sh_per_event ** 2) / max(n - 1, 1)
    if var <= 0:
        return observed_sh
    dsh = (observed_sh - exp_max * np.sqrt(var)) / np.sqrt(var * (1 - skew * sh_per_event + (kurt - 1) / 4 * sh_per_event ** 2))
    return float(dsh)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_m1() -> tuple[np.ndarray, np.ndarray]:
    """Return (timestamps ns naive UTC, close prices) sorted ascending."""
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[~df["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    ts = df["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).values.astype("datetime64[ns]")
    close = df["close"].to_numpy(dtype=np.float64)
    return ts, close


# ---------------------------------------------------------------------------
# Core simulator (numpy inner loop)
# ---------------------------------------------------------------------------

def snap_close(ts: np.ndarray, close: np.ndarray, target_ns: np.int64,
               tol_min: int = TOLERANCE_MIN) -> float:
    """Return close at the bar with timestamp closest to target_ns within tol.
    NaN if no bar within tolerance. Uses searchsorted -> O(log n)."""
    idx = np.searchsorted(ts.view("i8"), target_ns)
    n = ts.size
    best_d = np.iinfo(np.int64).max
    best_v = np.nan
    for c in (idx - 1, idx):
        if 0 <= c < n:
            d = abs(int(ts[c].view("i8")) - int(target_ns))
            if d < best_d:
                best_d = d
                best_v = close[c]
    if best_d > tol_min * 60 * 1_000_000_000:
        return np.nan
    return float(best_v)


def simulate_fix_events(
    ts: np.ndarray,
    close: np.ndarray,
    cal: pd.DataFrame,
    session_filter: str = "BOTH",   # "AM", "PM", "BOTH"
    direction: str = "cont",        # "cont" or "fade"
    min_pre_drift_bps: float = MIN_PRE_DRIFT_BPS_DEFAULT,
    cost_points_rt: float = COST_POINTS_RT_DEFAULT,
) -> tuple[np.ndarray, list[dict]]:
    """Returns (per-trade net-return array, per-trade record list)."""
    if session_filter != "BOTH":
        cal = cal[cal["session"] == session_filter]
    fix_utc = pd.to_datetime(cal["fix_utc"], utc=True)
    fix_naive = fix_utc.dt.tz_convert("UTC").dt.tz_localize(None)
    fix_ns = fix_naive.values.astype("datetime64[ns]").view("i8")

    ts_i = ts.view("i8")

    pre_window_offset_ns = (PRE_FIX_LOOKBACK_MIN + ENTRY_OFFSET_MIN) * 60 * 1_000_000_000  # 30 min
    entry_offset_ns = ENTRY_OFFSET_MIN * 60 * 1_000_000_000                                  # 5 min
    exit_offset_ns = EXIT_OFFSET_MIN * 60 * 1_000_000_000                                    # 5 min

    rets = []
    rows = []
    sessions = cal["session"].values
    dates = pd.to_datetime(cal["date"]).values
    for i in range(len(fix_ns)):
        f_ns = int(fix_ns[i])
        c_t30 = snap_close(ts, close, np.int64(f_ns - pre_window_offset_ns))
        c_t5 = snap_close(ts, close, np.int64(f_ns - entry_offset_ns))
        c_p5 = snap_close(ts, close, np.int64(f_ns + exit_offset_ns))
        if not (np.isfinite(c_t30) and np.isfinite(c_t5) and np.isfinite(c_p5)):
            continue
        drift_bps = (c_t5 - c_t30) / c_t30 * 1e4
        if abs(drift_bps) < min_pre_drift_bps:
            continue
        sign = 1.0 if drift_bps > 0 else -1.0
        if direction == "fade":
            sign = -sign
        gross = sign * (c_p5 - c_t5) / c_t5
        cost = cost_points_rt / c_t5    # fractional
        net = gross - cost
        d = pd.Timestamp(dates[i]).normalize()
        rets.append(net)
        rows.append({
            "date": d,
            "session": sessions[i],
            "fix_utc": pd.Timestamp(f_ns, tz="UTC"),
            "drift_bps": drift_bps,
            "entry_px": c_t5,
            "exit_px": c_p5,
            "gross_pct": gross * 100,
            "net_pct": net * 100,
            "regime": label_regime(d.year),
        })
    return np.array(rets, dtype=np.float64), rows


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def variant_metrics(rets: np.ndarray, trades: list[dict]) -> dict:
    if rets.size == 0:
        return {"n": 0, "sh": 0.0, "mdd": 0.0, "wr": 0.0, "pf": 0.0,
                "mean_bps": 0.0, "median_bps": 0.0, "t": 0.0,
                "events_per_yr": 0.0, "total_pct": 0.0}
    n = rets.size
    dates = pd.to_datetime([t["date"] for t in trades])
    span_years = max((dates.max() - dates.min()).days / 365.25, 1e-9)
    epy = n / span_years
    mean = rets.mean()
    std = rets.std(ddof=1)
    se = std / np.sqrt(n) if n > 0 else 0.0
    t_stat = mean / se if se > 0 else 0.0
    sh = annualized_sharpe_per_trade(rets, epy)
    eq = (1.0 + rets).cumprod()
    mdd = max_drawdown(eq)
    wr = float((rets > 0).mean())
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    gw = float(wins.sum()) if wins.size else 0.0
    gl = float(-losses.sum()) if losses.size else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    return {"n": n, "sh": sh, "mdd": mdd, "wr": wr, "pf": pf,
            "mean_bps": mean * 1e4, "median_bps": float(np.median(rets)) * 1e4,
            "t": t_stat, "events_per_yr": epy,
            "total_pct": float(eq[-1] - 1) * 100}


def regime_split(rets: np.ndarray, trades: list[dict]) -> dict:
    out = {}
    if rets.size == 0:
        return out
    years = np.array([pd.Timestamp(t["date"]).year for t in trades])
    for lab, ys, ye in REGIMES:
        mask = (years >= ys) & (years <= ye)
        sub_rets = rets[mask]
        sub_trades = [trades[i] for i, m in enumerate(mask) if m]
        if sub_rets.size < 10:
            out[lab] = {"n": int(sub_rets.size), "sh": 0.0, "mean_bps": 0.0, "mdd": 0.0}
            continue
        out[lab] = variant_metrics(sub_rets, sub_trades)
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_variant(label: str, rets: np.ndarray, trades: list[dict]) -> dict:
    m = variant_metrics(rets, trades)
    if m["n"] == 0:
        print(f"  [{label:<20s}]  EMPTY"); return m
    print(f"  [{label:<20s}]  "
          f"n={m['n']:>5d}  mean {m['mean_bps']:>+7.3f}bp  t {m['t']:>+5.2f}  "
          f"Sh {m['sh']:>+6.2f}  MDD {m['mdd']*100:>+6.2f}%  "
          f"WR {m['wr']*100:>4.1f}%  PF {m['pf']:>4.2f}  "
          f"epy {m['events_per_yr']:>5.0f}  tot {m['total_pct']:>+6.2f}%")
    return m


def print_regime_table(label: str, regimes: dict) -> None:
    print(f"  Regime breakdown — {label}:")
    print(f"    {'window':<26s} {'n':>5s} {'mean(bp)':>10s} {'Sh':>7s} {'MDD':>9s}")
    for lab, _, _ in REGIMES:
        r = regimes.get(lab, {})
        if r.get("n", 0) < 10:
            print(f"    {lab:<26s} {r.get('n', 0):>5d}  (sparse)")
            continue
        print(f"    {lab:<26s} {r['n']:>5d} {r['mean_bps']:>+9.3f}  {r['sh']:>+6.2f}  {r['mdd']*100:>+7.2f}%")


# ---------------------------------------------------------------------------
# Correlation tombstone
# ---------------------------------------------------------------------------

def per_day_pnl(rets: np.ndarray, trades: list[dict], name: str) -> pd.Series:
    if rets.size == 0:
        return pd.Series(dtype=float, name=name)
    df = pd.DataFrame({"date": [t["date"] for t in trades], "ret": rets})
    s = df.groupby("date")["ret"].sum()
    s.name = name
    return s


def compute_corr(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    if len(a) == 0 or len(b) == 0:
        return float("nan"), 0
    lo = max(a.index.min(), b.index.min())
    hi = min(a.index.max(), b.index.max())
    a = a[(a.index >= lo) & (a.index <= hi)]
    b = b[(b.index >= lo) & (b.index <= hi)]
    union = a.index.union(b.index)
    av = a.reindex(union, fill_value=0.0).to_numpy()
    bv = b.reindex(union, fill_value=0.0).to_numpy()
    if av.std() == 0 or bv.std() == 0:
        return float("nan"), len(union)
    return float(np.corrcoef(av, bv)[0, 1]), len(union)


def run_deployed_xau_book() -> pd.Series:
    """Returns per-day combined PnL of the deployed XAU book.
    Re-runs each deployed strategy via its existing portfolio_risk_parity wrappers."""
    sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "portfolio_risk_parity"))
    sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "macro_drift"))
    import portfolio_risk_parity_demo as prp  # type: ignore
    importlib.reload(prp)

    print("    running xau_session ...")
    xs = prp.run_xau_session()
    print(f"      n={len(xs)}, sum={xs.sum()*100:+.2f}%")
    print("    running xau_br_m15 ...")
    xm = prp.run_xau_br_m15()
    print(f"      n={len(xm)}, sum={xm.sum()*100:+.2f}%")
    print("    running xau_br_h1 ...")
    xh = prp.run_xau_br_h1()
    print(f"      n={len(xh)}, sum={xh.sum()*100:+.2f}%")
    union = xs.index.union(xm.index).union(xh.index)
    combined = (xs.reindex(union, fill_value=0.0)
                + xm.reindex(union, fill_value=0.0)
                + xh.reindex(union, fill_value=0.0))
    combined.name = "deployed_xau_book"
    return combined


# ---------------------------------------------------------------------------
# Phase 0c — cheap raw-signal vs deployed-xau_session correlation pre-check
# ---------------------------------------------------------------------------

def phase_0c_raw_corr(ts: np.ndarray, close: np.ndarray, cal: pd.DataFrame) -> float:
    """Per-day mean of |pre-fix drift| at fix times vs daily XAUUSD close-to-close ret.
    A positive correlation here is informational, not the binding tombstone — that
    requires the trade-by-trade per-day correlation vs the deployed book."""
    fix_utc = pd.to_datetime(cal["fix_utc"], utc=True)
    fix_naive = fix_utc.dt.tz_convert("UTC").dt.tz_localize(None)
    fix_ns = fix_naive.values.astype("datetime64[ns]").view("i8")
    pre_off = (PRE_FIX_LOOKBACK_MIN + ENTRY_OFFSET_MIN) * 60 * 1_000_000_000
    entry_off = ENTRY_OFFSET_MIN * 60 * 1_000_000_000

    rows = []
    for i in range(len(fix_ns)):
        f = int(fix_ns[i])
        c30 = snap_close(ts, close, np.int64(f - pre_off))
        c5 = snap_close(ts, close, np.int64(f - entry_off))
        if not (np.isfinite(c30) and np.isfinite(c5)):
            continue
        drift = (c5 - c30) / c30 * 1e4
        d = pd.Timestamp(cal["date"].iloc[i]).normalize()
        rows.append({"date": d, "drift_bps": drift, "sign_drift": np.sign(drift)})
    df = pd.DataFrame(rows)
    if df.empty:
        return float("nan")
    daily_sign = df.groupby("date")["sign_drift"].mean()  # -1..+1 by day across AM+PM

    # Daily close-to-close return on XAUUSD: use last bar per UTC date as proxy
    df_ts = pd.Series(close, index=pd.DatetimeIndex(ts).normalize())
    daily_close = df_ts.groupby(df_ts.index).last()
    daily_ret = daily_close.pct_change().dropna()

    union = daily_sign.index.intersection(daily_ret.index)
    if len(union) < 30:
        return float("nan")
    return float(np.corrcoef(daily_sign.reindex(union).fillna(0).values,
                             daily_ret.reindex(union).fillna(0).values)[0, 1])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section("xau_fix_drift Phase 2 — pre-fix drift continuation, M1, AM + PM Fix")

    # ----- Phase 0a: data -----
    section("Phase 0a — XAUUSD M1 load")
    ts, close = load_m1()
    print(f"  bars   : {len(ts):,}")
    print(f"  range  : {pd.Timestamp(ts[0])} -> {pd.Timestamp(ts[-1])} (UTC, naive)")

    # ----- Phase 0b: fix calendar -----
    section("Phase 0b — LBMA fix calendar (DST-aware Europe/London)")
    cal = build_fix_calendar(start="2018-01-01", end=pd.Timestamp(ts[-1]).strftime("%Y-%m-%d"))
    cal = cal[(cal["fix_utc"] >= pd.Timestamp(ts[0], tz="UTC")) &
              (cal["fix_utc"] <= pd.Timestamp(ts[-1], tz="UTC"))].reset_index(drop=True)
    print(f"  fix events in data range: {len(cal):,}  ({cal['date'].nunique():,} weekdays)")
    print(f"  range  : {cal['fix_utc'].min()} -> {cal['fix_utc'].max()}")
    print(f"  AM events: {(cal['session']=='AM').sum():,}    PM events: {(cal['session']=='PM').sum():,}")

    # ----- Phase 0c: cheap raw-signal corr pre-check -----
    section("Phase 0c — cheap raw-signal pre-tombstone")
    raw_corr = phase_0c_raw_corr(ts, close, cal)
    print(f"  raw daily-sign(drift_bps) vs daily XAUUSD return  corr: {raw_corr:+.3f}")
    if abs(raw_corr) > 0.5:
        print("  WARN: raw signal carries >0.5 daily-direction load — Phase 2 corr-tombstone (#11) at risk")
    else:
        print("  raw daily-direction load benign (< 0.5)")

    # ----- Phase 1+2 BASELINE: AM-CONT, AM-FADE, PM-CONT, PM-FADE, COMBINED -----
    section("Phase 1+2 — BASELINE variants  (MIN_PRE_DRIFT=3bp, cost=0.20pt RT)")
    variants = []
    for session in ("AM", "PM", "BOTH"):
        for dirn in ("cont", "fade"):
            label = f"{session}-{dirn.upper()}"
            rets, tr = simulate_fix_events(ts, close, cal, session_filter=session, direction=dirn)
            m = report_variant(label, rets, tr)
            variants.append((label, session, dirn, rets, tr, m))

    # Direction-gap per window
    section("Direction-gaps (CONT Sharpe - FADE Sharpe, by window)")
    by_lookup = {(s, d): (r, t, m) for lab, s, d, r, t, m in variants}
    dirgaps = {}
    for sess in ("AM", "PM", "BOTH"):
        gap = by_lookup[(sess, "cont")][2]["sh"] - by_lookup[(sess, "fade")][2]["sh"]
        dirgaps[sess] = gap
        verdict = "PASS" if gap > KC_DIRGAP else "FAIL"
        print(f"  {sess:<6s}  dir-gap {gap:>+6.2f}  (bar > {KC_DIRGAP:+.2f}: {verdict})")

    # ----- Regime breakdown for all CONT variants -----
    section("Regime breakdown — CONTINUATION variants")
    regime_cache = {}
    for sess in ("AM", "PM", "BOTH"):
        r, t, _ = by_lookup[(sess, "cont")]
        regs = regime_split(r, t)
        regime_cache[sess] = regs
        print_regime_table(f"{sess}-CONT", regs)
        print()

    section("Regime breakdown — FADE variants (null reference)")
    for sess in ("AM", "PM", "BOTH"):
        r, t, _ = by_lookup[(sess, "fade")]
        regs = regime_split(r, t)
        print_regime_table(f"{sess}-FADE", regs)
        print()

    # ----- Cost sweep on BOTH-CONT -----
    section("Cost sweep — COMBINED-CONT (MIN_PRE_DRIFT=3bp)")
    print(f"  {'cost (pt RT)':<14s} {'n':>5s} {'mean(bp)':>10s} {'Sh':>7s} {'MDD':>8s}")
    cost_stress_sh = 0.0
    for cp in COST_SWEEP:
        r_, t_ = simulate_fix_events(ts, close, cal, session_filter="BOTH",
                                     direction="cont", cost_points_rt=cp)
        m_ = variant_metrics(r_, t_)
        flag = "  (deploy)" if cp == COST_POINTS_RT_DEFAULT else (
               "  (stress)" if cp == COST_STRESS else "")
        print(f"  {cp:<14.2f} {m_['n']:>5d} {m_['mean_bps']:>+9.3f}  "
              f"{m_['sh']:>+6.2f}  {m_['mdd']*100:>+7.2f}%{flag}")
        if cp == COST_STRESS:
            cost_stress_sh = m_["sh"]

    # ----- Pre-drift threshold sweep on BOTH-CONT -----
    section("Pre-drift threshold sweep — COMBINED-CONT (cost 0.20pt)")
    print(f"  {'min_drift (bp)':<16s} {'n':>5s} {'mean(bp)':>10s} {'Sh':>7s} {'W3 Sh':>8s}")
    for thr in PRE_DRIFT_SWEEP:
        r_, t_ = simulate_fix_events(ts, close, cal, session_filter="BOTH",
                                     direction="cont", min_pre_drift_bps=thr)
        m_ = variant_metrics(r_, t_)
        reg = regime_split(r_, t_)
        w3 = reg.get("W3 2023-2026 (holdout)", {}).get("sh", 0.0)
        flag = "  (pre-commit)" if thr == MIN_PRE_DRIFT_BPS_DEFAULT else ""
        print(f"  {thr:<16.1f} {m_['n']:>5d} {m_['mean_bps']:>+9.3f}  "
              f"{m_['sh']:>+6.2f}  {w3:>+7.2f}{flag}")

    # ----- Correlation tombstone (criterion #11) -----
    section("Phase 2 correlation tombstone — trade-by-trade per-day PnL vs deployed XAU book")
    print("  computing deployed XAU book (xau_session + xau_br_m15 + xau_br_h1) ...")
    try:
        deployed = run_deployed_xau_book()
        print(f"  deployed book: n_days={len(deployed)}  sum={deployed.sum()*100:+.2f}%")
    except Exception as e:
        print(f"  ERROR running deployed book: {e}")
        deployed = pd.Series(dtype=float)

    corrs = {}
    if not deployed.empty:
        for sess in ("AM", "PM", "BOTH"):
            r, t, _ = by_lookup[(sess, "cont")]
            s_ = per_day_pnl(r, t, f"fix_{sess.lower()}_cont")
            corr, n_overlap = compute_corr(s_, deployed)
            verdict = "PASS" if abs(corr) < KC_CORR_VS_DEPLOYED else "FAIL"
            corrs[sess] = corr
            print(f"  {sess:<6s}-CONT vs deployed-XAU-book  corr {corr:>+.3f}  "
                  f"(n_overlap={n_overlap:>4d})  bar |corr|<{KC_CORR_VS_DEPLOYED:.2f}: {verdict}")

    # ----- Deflated Sharpe for the combined-CONT primary variant -----
    section("Deflated Sharpe — COMBINED-CONT (n_trials=8: 2 windows x 4 cost levels)")
    cb_r, cb_t, cb_m = by_lookup[("BOTH", "cont")]
    dsh = deflated_sharpe(cb_m["sh"], cb_r, n_trials=N_VARIANTS_PRECOMMITTED)
    print(f"  observed Sharpe {cb_m['sh']:+.2f}  ->  deflated {dsh:+.2f}  (bar > {KC_DEFLATED_SH:.2f})")

    # ----- Kill-criteria scorecard (11 binding criteria) -----
    section("Phase 2 kill-criteria scorecard (11 binding criteria)")
    full = cb_m
    am = by_lookup[("AM", "cont")][2]
    pm = by_lookup[("PM", "cont")][2]
    reg_cb = regime_cache["BOTH"]
    w1_sh = reg_cb.get("W1 2018-2020", {}).get("sh", 0.0)
    w2_sh = reg_cb.get("W2 2021-2022", {}).get("sh", 0.0)
    w3_sh = reg_cb.get("W3 2023-2026 (holdout)", {}).get("sh", 0.0)
    dgap_combined = dirgaps["BOTH"]
    corr_combined = corrs.get("BOTH", float("nan"))
    single_window_ok = (am["sh"] > KC_SINGLE_WINDOW_SH) or (pm["sh"] > KC_SINGLE_WINDOW_SH)

    checks = [
        (f"#1  FULL Sharpe (COMBINED-CONT)   > {KC_SHARPE_FULL:.2f}",
            full["sh"] > KC_SHARPE_FULL, f"{full['sh']:+.2f}"),
        (f"#2  W1 2018-2020 CONT Sharpe      > {KC_W1_SH:.2f}",
            w1_sh > KC_W1_SH, f"{w1_sh:+.2f}"),
        (f"#3  W2 2021-2022 CONT Sharpe      > {KC_W2_SH:.2f}",
            w2_sh > KC_W2_SH, f"{w2_sh:+.2f}"),
        (f"#4  W3 2023-2026 HOLDOUT Sharpe   > {KC_W3_SH:.2f}",
            w3_sh > KC_W3_SH, f"{w3_sh:+.2f}"),
        (f"#5  Max DD                        < {KC_MDD*100:.0f}%",
            abs(full["mdd"]) < KC_MDD, f"{full['mdd']*100:+.2f}%"),
        (f"#6  Trade count                  >= {KC_TRADES}",
            full["n"] >= KC_TRADES, f"{full['n']}"),
        (f"#7  Direction-gap COMBINED        > {KC_DIRGAP:.2f}",
            dgap_combined > KC_DIRGAP, f"{dgap_combined:+.2f}"),
        (f"#8  Cost-stress Sh @ 0.30pt       > {KC_COST_STRESS_SH:.2f}",
            cost_stress_sh > KC_COST_STRESS_SH, f"{cost_stress_sh:+.2f}"),
        (f"#9  AM or PM individual Sh        > {KC_SINGLE_WINDOW_SH:.2f}",
            single_window_ok, f"AM {am['sh']:+.2f} / PM {pm['sh']:+.2f}"),
        (f"#10 Deflated Sharpe               > {KC_DEFLATED_SH:.2f}",
            dsh > KC_DEFLATED_SH, f"{dsh:+.2f}"),
        (f"#11 |Corr vs deployed XAU book|   < {KC_CORR_VS_DEPLOYED:.2f}",
            (np.isfinite(corr_combined) and abs(corr_combined) < KC_CORR_VS_DEPLOYED),
            f"{corr_combined:+.2f}"),
    ]
    all_pass = True
    for desc, ok, val in checks:
        print(f"  {desc:<46s} : {'PASS' if ok else 'FAIL'}  ({val})")
        if not ok:
            all_pass = False

    section("VERDICT")
    if full["n"] < KC_TRADES:
        verdict = "INSUFFICIENT_N"
    elif dgap_combined <= KC_DIRGAP:
        verdict = "REJECT (direction-ambiguous)"
    elif np.isfinite(corr_combined) and abs(corr_combined) >= KC_CORR_VS_DEPLOYED:
        verdict = "REJECT-by-redundancy (criterion #11 tombstone)"
    elif not all_pass:
        verdict = "REJECT (failed binding criteria)"
    else:
        verdict = "PASS"
    print(f"  Phase 2 verdict: {verdict}")

    print(f"\n  Headlines (COMBINED-CONT, 0.20pt RT, MIN_PRE_DRIFT=3bp):")
    print(f"    Sh {full['sh']:+.2f}  W1 {w1_sh:+.2f}  W2 {w2_sh:+.2f}  W3 {w3_sh:+.2f}  "
          f"MDD {full['mdd']*100:+.2f}%  n={full['n']}")
    print(f"    direction-gap {dgap_combined:+.2f}  cost-stress@0.30pt Sh {cost_stress_sh:+.2f}  "
          f"deflated {dsh:+.2f}  corr {corr_combined:+.2f}")
    print(f"    AM-CONT Sh {am['sh']:+.2f}  /  PM-CONT Sh {pm['sh']:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
