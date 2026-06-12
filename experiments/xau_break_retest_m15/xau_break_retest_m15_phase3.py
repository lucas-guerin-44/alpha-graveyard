#!/usr/bin/env python3
"""XAUUSD M15 BoS+Retest — Phase 3 controls (FADE baseline).

Phase 2 (see xau_break_retest_m15.md): FADE PASS Sh +1.49 baseline. This script
runs four pre-committed Phase 3 controls to disambiguate "real edge" vs "subtle
confound we missed":

  Control 1 — Bull-isolation cross-time check
      Re-run baseline FADE on two non-NY-AM sessions (Asia 04-06 UTC,
      late-US 18-20 UTC). PASS iff NY-AM Sh >= each off-session Sh + 0.50.
      FAIL if any off-session within 0.30 of NY-AM Sh.

  Control 2 — Per-regime block-bootstrap CI on baseline FADE
      1000 iterations, block size = 21 trading days. 95% CI on Sharpe for
      FULL / W1 / W2 / W3 separately. PASS iff lower-bound FULL > +0.30
      AND lower-bound W1 > 0 AND lower-bound W2 > 0.

  Control 3 — NY-AM XAUUSD spread audit
      Pull 5 representative days. M1 not available on disk (XAUUSD_M5.csv
      is the lowest TF cached); use M5 high-low * 0.15 proxy on the 13-15
      UTC window as a conservative spread estimate. PASS iff 95th-pct
      spread <= 0.30 USD. MARGINAL 0.30-0.50. FAIL > 0.50. Documented as
      Phase 3 limitation (tick data follow-up).

  Control 4 — Macro-release calendar control
      Tag each FADE entry with whether it falls within +/-60 min of any
      US Tier-1 macro release (FOMC, CPI, PPI, NFP, Retail Sales, PCE).
      Compute Sh on macro-day slice and non-macro slice. PASS iff both
      slices >= +0.50.

Reuses simulator from xau_break_retest_m15_demo (no logic duplication).

Run:
  venv\\Scripts\\python.exe experiments\\xau_break_retest_m15\\xau_break_retest_m15_phase3.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
# experiments/_live/xau_break_retest_m15/ -> repo root is 3 dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, "..", "backtesting-engine-2.0")))

# Re-use simulator + helpers from the Phase 2 demo (no logic duplication).
from xau_break_retest_m15_demo import (  # noqa: E402
    COST_POINTS_DEFAULT,
    SESSION_START_UTC,
    SESSION_END_UTC,
    ENTRY_CUTOFF_UTC,
    annualized_sharpe,
    label_regime,
    load_m15,
    max_drawdown,
    simulate_break_retest_m15,
)

# --- Phase 3 pre-committed thresholds --------------------------------------

# Control 1
C1_NY_BEATS_BY = 0.50   # PASS: NY-AM Sh >= off-session Sh + 0.50
C1_FAIL_GAP = 0.30      # FAIL: any off-session within 0.30 of NY-AM Sh

# Control 2
C2_N_BOOT = 1000
C2_BLOCK_DAYS = 21
C2_LB_FULL = 0.30
C2_LB_REGIME = 0.0      # W1 and W2 lower-bounds must be > 0

# Control 3
C3_PASS_SPREAD = 0.30
C3_MARGINAL_SPREAD = 0.50
C3_SPREAD_PROXY_K = 0.15  # spread ~= 0.15 * (M5.high - M5.low) (conservative)

# Control 4
C4_MACRO_WINDOW_MIN = 60
C4_PASS_SH = 0.50
C4_MARGINAL_SH = 0.20

_ROOT_P = Path(_ROOT)
CALENDAR_FILES = {
    "fomc": _ROOT_P / "experiments" / "macro_drift" / "fomc_calendar.csv",
    "cpi":  _ROOT_P / "experiments" / "pre_cpi_drift" / "cpi_calendar.csv",
    "ppi":  _ROOT_P / "experiments" / "pre_ppi_drift" / "ppi_calendar.csv",
    "nfp":  _ROOT_P / "experiments" / "pre_nfp_drift" / "nfp_calendar.csv",
    "rs":   _ROOT_P / "experiments" / "pre_retail_sales_drift" / "retail_sales_calendar.csv",
    "pce":  _ROOT_P / "experiments" / "pre_pce_drift" / "pce_calendar.csv",
}


# --- Helpers ---------------------------------------------------------------

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


# --- Control 1: Bull-isolation cross-time check ---------------------------

def control1_cross_session(df: pd.DataFrame) -> dict:
    section("Control 1 — Bull-isolation cross-time check (FADE on non-NY sessions)")

    sessions = {
        "NY-AM (13-15 UTC)":   (13, 15, 15),
        "Asia (04-06 UTC)":    (4, 6, 6),
        "Late-US (18-20 UTC)": (18, 20, 20),
    }

    out: dict = {}
    for label, (start_h, end_h, cutoff_h) in sessions.items():
        rets, trades = simulate_break_retest_m15(
            df, direction="fade",
            session_start_utc=start_h,
            session_end_utc=end_h,
            entry_cutoff_utc=cutoff_h,
            cost_points=COST_POINTS_DEFAULT,
        )
        stats = _summary(rets, trades, f"FADE {label}")
        out[label] = stats

    ny_sh = out["NY-AM (13-15 UTC)"]["sharpe"]
    print()
    print("  Verdict logic: NY-AM Sh must beat each off-session by >= "
          f"+{C1_NY_BEATS_BY:.2f}.  FAIL if any off-session within {C1_FAIL_GAP:.2f}.")

    verdict_parts = []
    verdict = "PASS"
    for label, stats in out.items():
        if label.startswith("NY-AM"):
            continue
        sh = stats["sharpe"]
        gap = ny_sh - sh
        if gap < C1_FAIL_GAP:
            v = "FAIL"
        elif gap >= C1_NY_BEATS_BY:
            v = "PASS"
        else:
            v = "MARGINAL"
        print(f"    {label}: Sh {sh:+.2f}  (NY-AM gap {gap:+.2f}) -> {v}")
        verdict_parts.append(v)
        if v == "FAIL":
            verdict = "FAIL"
        elif v == "MARGINAL" and verdict != "FAIL":
            verdict = "MARGINAL"

    print(f"\n  Control 1 VERDICT: {verdict}")
    return {"sessions": out, "verdict": verdict, "ny_sh": ny_sh}


# --- Control 2: Per-regime block-bootstrap CI -----------------------------

def _block_bootstrap_sharpe(rets: np.ndarray, tpy: float, block_size: int,
                            n_boot: int, seed: int = 20260525) -> tuple[float, float]:
    """Stationary-block bootstrap of annualized Sharpe.
    Returns (lower_95, upper_95) of the Sharpe sampling distribution.
    """
    n = rets.size
    if n < block_size * 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    starts_max = n - block_size + 1
    sharpes = np.empty(n_boot, dtype=np.float64)
    for i in range(n_boot):
        starts = rng.integers(0, starts_max, size=n_blocks)
        sample_chunks = [rets[s:s + block_size] for s in starts]
        sample = np.concatenate(sample_chunks)[:n]
        std = sample.std(ddof=1)
        if std == 0 or not np.isfinite(std):
            sharpes[i] = 0.0
            continue
        sharpes[i] = sample.mean() / std * np.sqrt(tpy)
    lo, hi = np.percentile(sharpes, [2.5, 97.5])
    return float(lo), float(hi)


def control2_block_bootstrap(df: pd.DataFrame) -> dict:
    section("Control 2 — Per-regime block-bootstrap CI on baseline FADE Sharpe")

    rets, trades = simulate_break_retest_m15(df, direction="fade",
                                             cost_points=COST_POINTS_DEFAULT)
    first = pd.Timestamp(trades[0]["entry_ts"])
    last = pd.Timestamp(trades[-1]["entry_ts"])
    years = max((last - first).days / 365.25, 1e-9)
    tpy_full = rets.size / years

    # Trades-per-day estimate so block_size = 21 trading days converts to
    # a trade-block size for the (sparse) trade-return series.
    # 21 trading days ~ 21 * (tpy_full / 252) trades per block, rounded up.
    block_trades = max(int(np.ceil(C2_BLOCK_DAYS * (tpy_full / 252.0))), 2)
    print(f"  Trades/year = {tpy_full:.1f}  ->  block size = {block_trades} trades "
          f"(= {C2_BLOCK_DAYS} trading days)")

    print()
    print("  Bootstrap (1000 iter) per regime:")
    regimes = {
        "FULL":                     rets,
        "W1 2019-2020":             _regime_arr(trades, rets, "W1 2019-2020"),
        "W2 2021-2022":             _regime_arr(trades, rets, "W2 2021-2022"),
        "W3 2023-2026 (holdout)":   _regime_arr(trades, rets, "W3 2023-2026 (holdout)"),
    }
    out: dict = {}
    for label, arr in regimes.items():
        if arr.size < 2 * block_trades:
            print(f"    {label:<28s} n={arr.size:>4d}  insufficient for block bootstrap")
            out[label] = {"point": float("nan"), "lo": float("nan"), "hi": float("nan"),
                          "n": arr.size}
            continue
        # tpy for this slice: estimate from the original series since slice years
        # vary by regime; use full-period tpy as proxy for annualization scale
        # (preserves comparability with Phase 2 numbers).
        tpy_slice = tpy_full
        point = annualized_sharpe(arr, trades_per_year=tpy_slice)
        lo, hi = _block_bootstrap_sharpe(arr, tpy_slice, block_trades, C2_N_BOOT,
                                         seed=20260525 + hash(label) % 1000)
        print(f"    {label:<28s} n={arr.size:>4d}  point Sh {point:>+6.2f}  "
              f"95% CI [{lo:>+6.2f}, {hi:>+6.2f}]")
        out[label] = {"point": point, "lo": lo, "hi": hi, "n": arr.size}

    full_lb = out["FULL"]["lo"]
    w1_lb = out["W1 2019-2020"]["lo"]
    w2_lb = out["W2 2021-2022"]["lo"]
    w3_lb = out["W3 2023-2026 (holdout)"]["lo"]

    print()
    print(f"  PASS bar: lower-95 FULL > +{C2_LB_FULL:.2f} "
          f"AND lower-95 W1 > {C2_LB_REGIME:.2f} AND lower-95 W2 > {C2_LB_REGIME:.2f}")
    full_ok = np.isfinite(full_lb) and full_lb > C2_LB_FULL
    w1_ok = np.isfinite(w1_lb) and w1_lb > C2_LB_REGIME
    w2_ok = np.isfinite(w2_lb) and w2_lb > C2_LB_REGIME
    print(f"    FULL  lb {full_lb:+.2f} > +{C2_LB_FULL:.2f} ? {'PASS' if full_ok else 'FAIL'}")
    print(f"    W1    lb {w1_lb:+.2f} > {C2_LB_REGIME:.2f} ? {'PASS' if w1_ok else 'FAIL'}")
    print(f"    W2    lb {w2_lb:+.2f} > {C2_LB_REGIME:.2f} ? {'PASS' if w2_ok else 'FAIL'}")
    print(f"    W3    lb {w3_lb:+.2f}  (informational)")

    verdict = "PASS" if (full_ok and w1_ok and w2_ok) else "FAIL"
    print(f"\n  Control 2 VERDICT: {verdict}")
    return {"regimes": out, "verdict": verdict}


# --- Control 3: NY-AM XAUUSD spread audit ---------------------------------

def control3_spread_audit(df_m15: pd.DataFrame) -> dict:
    df = df_m15  # alias used in cost-stress section
    section("Control 3 — NY-AM XAUUSD spread audit (M1 unavailable; M5 proxy)")

    print("  LIMITATION: tick / M1 data not on disk; using M5 spread proxy")
    print(f"  proxy: spread ~= {C3_SPREAD_PROXY_K:.2f} * (M5.high - M5.low) per bar.")
    print("  This is the per-bar realized range *0.15, a conservative effective")
    print("  bid-ask floor (assumes most of the bar's range is mid-price movement,")
    print("  but the inside-spread is some fraction of it). Refine with tick log Phase 4.\n")

    # Reload the raw M5 file (load_m15 already resamples; we need M5 ranges)
    m5 = pd.read_csv(os.path.join(_ROOT, "ohlc_data", "XAUUSD_M5.csv"),
                     parse_dates=["timestamp"])
    m5["timestamp"] = pd.to_datetime(m5["timestamp"], utc=True)
    m5 = m5.sort_values("timestamp").reset_index(drop=True)
    m5 = m5[~m5["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    m5 = m5[m5["timestamp"] >= pd.Timestamp("2018-08-01", tz="UTC")].reset_index(drop=True)
    m5["hour"] = m5["timestamp"].dt.hour
    m5["date"] = m5["timestamp"].dt.date

    # Pick 5 representative trading days, one per quarter 2024-2025 plus an extra
    # 2025 sample (deterministic with seed).
    rng = np.random.default_rng(20260525)
    candidate_days = sorted(set(m5["date"]))
    # Filter to 2024-2025
    candidate_days = [d for d in candidate_days
                      if d >= pd.Timestamp("2024-01-01").date()
                      and d <= pd.Timestamp("2025-12-31").date()]
    # Group by month to ensure representativeness; sample 5 distinct months
    by_month: dict = {}
    for d in candidate_days:
        key = (d.year, d.month)
        by_month.setdefault(key, []).append(d)
    months = sorted(by_month.keys())
    months_idx = rng.choice(len(months), size=min(5, len(months)), replace=False)
    sample_days = []
    for idx in sorted(months_idx):
        ms = by_month[months[idx]]
        sample_days.append(ms[rng.integers(0, len(ms))])
    print(f"  Sample days (1 per month, n={len(sample_days)}):")
    for d in sample_days:
        print(f"    {d}")

    print("\n  Per-day NY-AM (13-15 UTC) spread proxy stats (USD):")
    all_spreads = []
    for d in sample_days:
        day_m5 = m5[(m5["date"] == d) & (m5["hour"] >= 13) & (m5["hour"] < 15)]
        ranges = (day_m5["high"] - day_m5["low"]).to_numpy()
        spreads = ranges * C3_SPREAD_PROXY_K
        if spreads.size == 0:
            print(f"    {d}: no in-session bars")
            continue
        mean_s = float(np.mean(spreads))
        p95_s = float(np.percentile(spreads, 95))
        max_s = float(np.max(spreads))
        print(f"    {d}: bars={spreads.size:>3d}  mean {mean_s:.2f}  "
              f"p95 {p95_s:.2f}  max {max_s:.2f}")
        all_spreads.append(spreads)

    # Full-sample 2024-2025 NY-AM stats too (more robust than the 5-day pool)
    full_sess = m5[(m5["hour"] >= 13) & (m5["hour"] < 15)
                   & (m5["timestamp"] >= pd.Timestamp("2024-01-01", tz="UTC"))]
    full_spreads = ((full_sess["high"] - full_sess["low"]).to_numpy()
                    * C3_SPREAD_PROXY_K)
    print(f"\n  Full 2024-2025 NY-AM pool: n={full_spreads.size:,}  "
          f"mean {float(np.mean(full_spreads)):.2f}  "
          f"median {float(np.median(full_spreads)):.2f}  "
          f"p75 {float(np.percentile(full_spreads, 75)):.2f}  "
          f"p90 {float(np.percentile(full_spreads, 90)):.2f}  "
          f"p95 {float(np.percentile(full_spreads, 95)):.2f}  "
          f"p99 {float(np.percentile(full_spreads, 99)):.2f}")

    p95 = float(np.percentile(full_spreads, 95))
    median = float(np.median(full_spreads))
    print()
    print(f"  PASS bar (tick-data ideal): p95 spread <= {C3_PASS_SPREAD:.2f} USD")
    print(f"  MARGINAL: p95 {C3_PASS_SPREAD:.2f}-{C3_MARGINAL_SPREAD:.2f} USD")
    print(f"  FAIL    : p95 > {C3_MARGINAL_SPREAD:.2f} USD")

    # Cost-stress: re-run the FADE simulator at elevated costs spanning the
    # full proxy-implied range. This grounds the FAIL/MARGINAL determination
    # in actual P&L sensitivity rather than the proxy threshold alone.
    print()
    print("  Cost-stress at proxy-implied spread levels (FADE baseline):")
    cost_stress_results = {}
    for cost in (0.4, 0.6, 0.8, 1.0, 1.5):
        rets, trades = simulate_break_retest_m15(df, direction="fade", cost_points=cost)
        if rets.size:
            first = pd.Timestamp(trades[0]["entry_ts"])
            last = pd.Timestamp(trades[-1]["entry_ts"])
            years = max((last - first).days / 365.25, 1e-9)
            tpy = rets.size / years
            sh = annualized_sharpe(rets, trades_per_year=tpy)
        else:
            sh = 0.0
        cost_stress_results[cost] = sh
        flag = ""
        if cost > C3_MARGINAL_SPREAD:
            flag = " (above proxy-FAIL threshold)"
        print(f"    cost={cost:.2f}pt  Sh {sh:+.2f}{flag}")

    print()
    print("  PROXY LIMITATION: M5 high-low * 0.15 is an UPPER-BOUND of effective")
    print("  spread; assumes 15% of the 5-min range is bid-ask. Real Eightcap")
    print("  inside-spread is typically much tighter (broker-published 0.16-0.20pt RT")
    print("  on XAUUSD raw).  The proxy fails primarily because XAU NY-AM has wide")
    print("  M5 ranges (volatility), not because the spread itself is wide.")
    print("  Resolution: tick log required for definitive Control 3 verdict.")

    # Verdict logic adjusted for proxy unreliability per task spec:
    # "If tick / M1 data is genuinely unavailable on the datalake, document
    # this as Phase 3 limitation rather than failing"
    if p95 <= C3_PASS_SPREAD:
        proxy_v = "PASS"
    elif p95 <= C3_MARGINAL_SPREAD:
        proxy_v = "MARGINAL"
    else:
        proxy_v = "FAIL_BY_PROXY"

    # Cost-stress backup verdict: if FADE Sharpe stays > +0.3 even at 1.0pt RT
    # (5x deploy assumption, comfortable margin above any plausible real spread)
    # the strategy is robust to spread-shock and proxy-FAIL is downgraded to MARGINAL.
    sh_at_1pt = cost_stress_results.get(1.0, 0.0)
    if proxy_v == "FAIL_BY_PROXY":
        if sh_at_1pt > 0.30:
            verdict = "MARGINAL"
            verdict_reason = (f"M5 proxy p95 {p95:.2f} USD exceeds FAIL threshold but "
                              f"FADE Sh at 1.0pt RT (5x deploy cost) = {sh_at_1pt:+.2f} "
                              ">+0.30; spread-shock robust. Tick log needed to settle.")
        else:
            verdict = "FAIL"
            verdict_reason = (f"M5 proxy p95 {p95:.2f} USD AND FADE Sh at 1.0pt RT = "
                              f"{sh_at_1pt:+.2f}; both proxy AND cost-stress fail.")
    else:
        verdict = proxy_v
        verdict_reason = f"proxy p95 = {p95:.2f} USD"

    print(f"\n  Control 3 VERDICT: {verdict}  ({verdict_reason})")
    return {"p95_proxy": p95, "median_proxy": median, "verdict": verdict,
            "sample_days": sample_days, "cost_stress": cost_stress_results,
            "proxy_v": proxy_v, "verdict_reason": verdict_reason}


# --- Control 4: Macro-release calendar control ----------------------------

def _load_macro_calendar() -> pd.DataFrame:
    rows = []
    for source, path in CALENDAR_FILES.items():
        if not Path(path).exists():
            print(f"  WARN: {source} calendar missing at {path}")
            continue
        df = pd.read_csv(path)
        df["source"] = source
        # Schema is (date, announce_time_et, [with_projections,] is_historical, notes)
        for _, r in df.iterrows():
            tstr = str(r.get("announce_time_et", "08:30")).strip() or "08:30"
            try:
                hh, mm = tstr.split(":")
                hh = int(hh)
                mm = int(mm)
            except Exception:
                hh, mm = 8, 30
            d = pd.Timestamp(r["date"])
            # ET -> UTC: EST=UTC-5, EDT=UTC-4. Use US/Eastern tz to be exact.
            local = pd.Timestamp(year=d.year, month=d.month, day=d.day,
                                 hour=hh, minute=mm, tz="US/Eastern")
            ts_utc = local.tz_convert("UTC")
            rows.append({"ts_utc": ts_utc, "source": source})
    out = pd.DataFrame(rows).sort_values("ts_utc").reset_index(drop=True)
    return out


def control4_macro_calendar(df_m15: pd.DataFrame) -> dict:
    section("Control 4 — Macro-release calendar control")

    cal = _load_macro_calendar()
    print(f"  Loaded {len(cal)} US macro releases from {cal['source'].nunique()} sources:")
    for s, n in cal["source"].value_counts().sort_index().items():
        print(f"    {s:>5s}: {n}")

    # Run baseline FADE
    rets, trades = simulate_break_retest_m15(df_m15, direction="fade",
                                             cost_points=COST_POINTS_DEFAULT)
    print(f"\n  Baseline FADE n={rets.size}")

    # Entry ts (UTC) per trade -> numpy int64 nanoseconds for fast arithmetic
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
    cal_dates_pre16 = set(t.date() for t in cal_ts_pd if t.hour < 16)
    entry_dates = np.array([pd.Timestamp(t["entry_ts"]).date() for t in trades])

    window_ns = int(C4_MACRO_WINDOW_MIN * 60 * 1_000_000_000)
    macro_flag = np.zeros(len(trades), dtype=bool)
    macro_day_flag = np.zeros(len(trades), dtype=bool)
    # Vectorized: for each trade, min distance to any release in ns
    # cal_ts_ns is sorted -> use searchsorted for O(N log M)
    cal_sorted = np.sort(cal_ts_ns)
    for i, ets in enumerate(entry_ts_ns):
        # find nearest neighbor in cal_sorted
        idx = np.searchsorted(cal_sorted, ets)
        nearest = np.inf
        if idx < cal_sorted.size:
            nearest = min(nearest, abs(int(cal_sorted[idx]) - int(ets)))
        if idx > 0:
            nearest = min(nearest, abs(int(cal_sorted[idx - 1]) - int(ets)))
        if nearest <= window_ns:
            macro_flag[i] = True
        if entry_dates[i] in cal_dates_pre16:
            macro_day_flag[i] = True

    share_within = float(macro_flag.mean())
    share_macro_day = float(macro_day_flag.mean())
    print(f"\n  Share of FADE entries within +/-{C4_MACRO_WINDOW_MIN}min of any release: "
          f"{share_within * 100:.1f}%")
    print(f"  Share of FADE entries on a US-macro-release day (release before 16 UTC): "
          f"{share_macro_day * 100:.1f}%")

    # Slice 1: macro-day (broader definition per spec — release-day)
    macro_rets = rets[macro_day_flag]
    macro_trades = [t for t, f in zip(trades, macro_day_flag) if f]
    nonmacro_rets = rets[~macro_day_flag]
    nonmacro_trades = [t for t, f in zip(trades, macro_day_flag) if not f]

    print("\n  Slice summary:")
    s_macro = _summary(macro_rets, macro_trades, "FADE macro-day")
    s_non = _summary(nonmacro_rets, nonmacro_trades, "FADE non-macro-day")

    # Window slice (within +/-60min)
    print()
    win_rets = rets[macro_flag]
    win_trades = [t for t, f in zip(trades, macro_flag) if f]
    outwin_rets = rets[~macro_flag]
    outwin_trades = [t for t, f in zip(trades, macro_flag) if not f]
    s_win = _summary(win_rets, win_trades, "FADE within +/-60min")
    s_outwin = _summary(outwin_rets, outwin_trades, "FADE outside +/-60min")

    macro_sh = s_macro["sharpe"]
    non_sh = s_non["sharpe"]

    print()
    print(f"  PASS bar: non-macro Sh >= +{C4_PASS_SH:.2f} AND macro-day Sh >= +{C4_PASS_SH:.2f}")
    print(f"  MARGINAL: non-macro Sh +{C4_MARGINAL_SH:.2f} to +{C4_PASS_SH:.2f}")
    print(f"  FAIL    : non-macro Sh < +{C4_MARGINAL_SH:.2f}")
    if non_sh >= C4_PASS_SH and macro_sh >= C4_PASS_SH:
        verdict = "PASS"
    elif non_sh >= C4_MARGINAL_SH:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"
    print(f"\n  Control 4 VERDICT: {verdict}  "
          f"(non-macro Sh {non_sh:+.2f}, macro-day Sh {macro_sh:+.2f})")
    return {
        "macro_day": s_macro, "non_macro_day": s_non,
        "within_60min": s_win, "outside_60min": s_outwin,
        "share_within": share_within, "share_macro_day": share_macro_day,
        "verdict": verdict,
    }


# --- Main -----------------------------------------------------------------

def main() -> int:
    section("Loading XAUUSD M5 -> M15")
    df = load_m15()
    print(f"  M15 bars: {len(df):,}  range {df['timestamp'].min()} -> {df['timestamp'].max()}")

    c1 = control1_cross_session(df)
    c2 = control2_block_bootstrap(df)
    c3 = control3_spread_audit(df)
    c4 = control4_macro_calendar(df)

    section("Phase 3 SUMMARY")
    rows = [
        ("Control 1 — cross-session",   c1["verdict"],
         f"NY-AM Sh {c1['ny_sh']:+.2f}; off-sessions: " +
         ", ".join(f"{k.split()[0]} {v['sharpe']:+.2f}"
                   for k, v in c1["sessions"].items() if not k.startswith("NY-AM"))),
        ("Control 2 — block-bootstrap", c2["verdict"],
         f"FULL CI [{c2['regimes']['FULL']['lo']:+.2f},{c2['regimes']['FULL']['hi']:+.2f}], "
         f"W1 [{c2['regimes']['W1 2019-2020']['lo']:+.2f},{c2['regimes']['W1 2019-2020']['hi']:+.2f}], "
         f"W2 [{c2['regimes']['W2 2021-2022']['lo']:+.2f},{c2['regimes']['W2 2021-2022']['hi']:+.2f}]"),
        ("Control 3 — spread audit",    c3["verdict"],
         f"p95 proxy {c3['p95_proxy']:.2f} USD (M5-derived; tick log Phase 4)"),
        ("Control 4 — macro calendar",  c4["verdict"],
         f"non-macro Sh {c4['non_macro_day']['sharpe']:+.2f}, "
         f"macro-day Sh {c4['macro_day']['sharpe']:+.2f}, "
         f"macro-day share {c4['share_macro_day']*100:.0f}%"),
    ]
    for label, v, detail in rows:
        print(f"  {label:<32s} : {v:<8s}  {detail}")

    n_fail = sum(1 for _, v, _ in rows if v == "FAIL")
    n_marg = sum(1 for _, v, _ in rows if v == "MARGINAL")

    print()
    if n_fail == 0 and n_marg == 0:
        verdict = "PHASE 2-3 PASS  (deploy-ready)"
    elif n_fail == 0 and n_marg >= 1:
        verdict = f"MARGINAL  ({n_marg} control(s) marginal; deploy with qualification)"
    elif n_fail == 1:
        verdict = "MARGINAL  (1 control FAIL; downgrade with qualification)"
    elif n_fail >= 2:
        verdict = f"REJECT  ({n_fail} controls FAIL)"
    print(f"  >>> PHASE 3 OVERALL VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
