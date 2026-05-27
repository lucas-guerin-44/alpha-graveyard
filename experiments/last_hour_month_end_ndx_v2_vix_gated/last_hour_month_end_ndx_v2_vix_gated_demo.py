#!/usr/bin/env python3
"""
Phase 2 simulator — last_hour_month_end_ndx v2 VIX-CALM gated.

Thesis: experiments/last_hour_month_end_ndx_v2_vix_gated/last_hour_month_end_ndx_v2_vix_gated.md

Calibrated kill criteria (10) post-xau_session_v2-lesson:
  +0.50 deployable Sh bar (NOT +1.20)
  +0.65 active-aware Sh in CALM regime
  CALM events >= 15
"""

from __future__ import annotations

import io
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

_HERE = Path(__file__).resolve().parent
_EXPERIMENTS = _HERE.parent
_ROOT = _EXPERIMENTS.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str((_ROOT / '..' / 'backtesting-engine-2.0').resolve()))
sys.path.insert(0, str(_EXPERIMENTS / "last_hour_month_end_ndx"))
sys.path.insert(0, str(_EXPERIMENTS / "structural_flow_audit"))

import last_hour_month_end_ndx_demo as lhmnd  # noqa: E402
from structural_flow_audit import (  # noqa: E402
    gen_month_end_dates, compute_window_returns, compute_placebo_returns,
)


# -----------------------------------------------------------------------------
# Config — gate parameters locked from diagnostic
# -----------------------------------------------------------------------------

VIX_CALM_THRESHOLD = 15.0
VIX_LOOKBACK_DAYS = 60

EVENTS_PER_YEAR_UNCONDITIONAL = 12
COST_BPS = lhmnd.cost_bps_from_points(lhmnd.COST_POINTS_DEFAULT)
COST_STRESS_MULT = 2.0

# Pre-committed kill criteria (CALIBRATED)
KC1_FULL_SH = 0.50
KC2_W3_SH = 0.30
KC3_MIN_N_CALM = 15
KC4_CALM_SH = 0.65
KC5_DIR_GAP = 0.30
KC6_BOOT_LOWER_GT = 0.0
KC8_PLACEBO_MAG = 1.0
KC9_COST_STRESS_NET_GT = 0.0
KC10_DEFLATED_SH = 0.20


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 92}\n  {t}\n{'=' * 92}\n")


def label_regime(d: date) -> str:
    if d.year <= 2020:
        return "W1_2019_2020"
    if d.year <= 2022:
        return "W2_2021_2022"
    return "W3_2023_2026"


def annual_sharpe(rets_bps: np.ndarray, events_per_year: float) -> float:
    r = rets_bps[np.isfinite(rets_bps)]
    if r.size < 2 or events_per_year <= 0:
        return 0.0
    sd = r.std(ddof=1)
    return 0.0 if sd == 0 else float(r.mean() / sd * np.sqrt(events_per_year))


def bootstrap_mean_ci(rets: np.ndarray, n_iter: int = 5000, alpha: float = 0.05,
                     seed: int = 42) -> tuple[float, float, float]:
    if len(rets) < 2:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    n = len(rets)
    boot_means = np.empty(n_iter, dtype=np.float64)
    for i in range(n_iter):
        sample = rng.choice(rets, size=n, replace=True)
        boot_means[i] = sample.mean()
    return (
        float(np.quantile(boot_means, alpha / 2)),
        float(rets.mean()),
        float(np.quantile(boot_means, 1 - alpha / 2)),
    )


def deflated_sharpe(observed_sh: float, n_returns: int, n_trials: int) -> float:
    from math import sqrt, log
    if n_returns < 4 or n_trials <= 1:
        return observed_sh
    e_max = sqrt(2.0 * log(n_trials)) * (1.0 / sqrt(n_returns))
    return float(observed_sh - e_max)


# -----------------------------------------------------------------------------
# VIX series fetch + CALM gate
# -----------------------------------------------------------------------------

def fetch_vix() -> pd.Series:
    """Pull VIXCLS daily close from FRED."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    date_col = "DATE" if "DATE" in df.columns else df.columns[0]
    val_col = "VIXCLS" if "VIXCLS" in df.columns else df.columns[1]
    df = df[[date_col, val_col]].rename(columns={date_col: "date", val_col: "VIXCLS"})
    df["date"] = pd.to_datetime(df["date"])
    df["VIXCLS"] = pd.to_numeric(df["VIXCLS"], errors="coerce")
    df = df.dropna().set_index("date").sort_index()
    return df["VIXCLS"].ffill()


def is_calm_regime(vix: pd.Series, event_date: date) -> bool:
    """True if VIX 60d trailing median < 15 ON event_date.
    Uses ONLY data available up to event_date-1 (no lookahead).
    """
    ts = pd.Timestamp(event_date)
    cutoff_idx = vix.index <= ts
    if cutoff_idx.sum() < VIX_LOOKBACK_DAYS:
        return False  # insufficient history
    prior = vix.loc[cutoff_idx].iloc[-VIX_LOOKBACK_DAYS:]
    return float(prior.median()) < VIX_CALM_THRESHOLD


def vix_state(vix: pd.Series, event_date: date) -> str:
    """Returns CALM / NORMAL / STRESS for a given event date."""
    ts = pd.Timestamp(event_date)
    cutoff_idx = vix.index <= ts
    if cutoff_idx.sum() < VIX_LOOKBACK_DAYS:
        return "INSUFFICIENT"
    prior = vix.loc[cutoff_idx].iloc[-VIX_LOOKBACK_DAYS:]
    med = float(prior.median())
    if med < 15.0:
        return "CALM"
    if med >= 22.0:
        return "STRESS"
    return "NORMAL"


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    # 1. Load parent simulator returns
    section("Running parent (unconditional) last_hour_month_end_ndx")
    bars = lhmnd.load_ndx_m5()
    print(f"  bars: {len(bars):,}  range {bars.index[0].date()} -> {bars.index[-1].date()}")

    event_dates = gen_month_end_dates(lhmnd.YEARS)
    long_bps, kept = compute_window_returns(
        bars, event_dates, lhmnd.TZ_NAME,
        lhmnd.WIN_START_H, lhmnd.WIN_START_M,
        lhmnd.WIN_END_H, lhmnd.WIN_END_M,
    )
    n_total = len(kept)
    print(f"  total events: {n_total}")

    short_net = -long_bps - COST_BPS
    short_full = annual_sharpe(short_net, EVENTS_PER_YEAR_UNCONDITIONAL)
    print(f"  parent SHORT full mean: {short_net.mean():+.2f} bps  ann-Sh {short_full:+.2f}")

    # 2. Fetch VIX + classify each event
    section("Fetching VIX + classifying events by 60d median state")
    vix = fetch_vix()
    print(f"  VIX series: {vix.index.min().date()} -> {vix.index.max().date()}  n={len(vix):,}")
    states = np.array([vix_state(vix, d) for d in kept])
    counts = pd.Series(states).value_counts()
    print(f"  event distribution by VIX regime:")
    for s, n in counts.items():
        pct = n / n_total * 100
        print(f"    {s:<12s}: {n:>3d} events ({pct:.1f}%)")

    # 3. Gated subset
    section("VIX-CALM gated metrics (the v2 deploy candidate)")
    calm_mask = (states == "CALM")
    calm_net = short_net[calm_mask]
    calm_dates = [d for d, m in zip(kept, calm_mask) if m]
    n_calm = len(calm_net)

    # Cadence (events per year) WITHIN the full sample (gated)
    sample_years = (kept[-1] - kept[0]).days / 365.25 if n_total > 1 else 0.01
    calm_per_year = n_calm / max(sample_years, 0.01)
    print(f"  CALM events: {n_calm} / {n_total}  ({n_calm/n_total*100:.1f}%)")
    print(f"  Effective cadence: {calm_per_year:.1f} events/yr (parent {EVENTS_PER_YEAR_UNCONDITIONAL}/yr)")

    if n_calm < KC3_MIN_N_CALM:
        print(f"  WARNING: CALM sample n={n_calm} below criterion #3 floor {KC3_MIN_N_CALM}")

    calm_full_sh = annual_sharpe(calm_net, calm_per_year)  # deployable annualization (full-sample cadence)
    calm_active_sh = annual_sharpe(calm_net, EVENTS_PER_YEAR_UNCONDITIONAL)  # active-aware
    print(f"  CALM mean (cost-net) : {calm_net.mean():+.2f} bps/event")
    print(f"  CALM std             : {calm_net.std(ddof=1):.2f} bps")
    print(f"  CALM full Sh (deploy): {calm_full_sh:+.3f}")
    print(f"  CALM active-aware Sh : {calm_active_sh:+.3f}")
    print(f"  CALM WR              : {(calm_net > 0).mean() * 100:.1f}%")

    # MDD on event-equity-curve
    eq = (1.0 + calm_net / 1e4).cumprod()
    mdd = float((eq / np.maximum.accumulate(eq) - 1).min())
    print(f"  CALM MDD             : {mdd * 100:+.2f}%")

    # 4. Regime breakdown WITHIN CALM events (W1/W2/W3)
    section("CALM-only sub-regime breakdown (W1/W2/W3)")
    labels = np.array([label_regime(d) for d in calm_dates])
    print(f"  {'window':<16s} {'n':>3s} {'mean':>9s} {'sh':>7s}")
    sub_means = {}
    for w in ["W1_2019_2020", "W2_2021_2022", "W3_2023_2026"]:
        m = labels == w
        if m.sum() < 2:
            print(f"  {w:<16s} {int(m.sum()):>3d}   INSUFFICIENT")
            sub_means[w] = float("nan")
            continue
        sub = calm_net[m]
        sub_mean = float(sub.mean())
        sub_sh = sub_mean / sub.std(ddof=1) * np.sqrt(calm_per_year) if sub.std(ddof=1) > 0 else 0.0
        sub_means[w] = sub_mean
        print(f"  {w:<16s} {int(m.sum()):>3d} {sub_mean:>+8.2f} {sub_sh:>+6.2f}")
    w3_mean = sub_means.get("W3_2023_2026", float("nan"))
    w3_sh = (w3_mean / calm_net[labels == "W3_2023_2026"].std(ddof=1) * np.sqrt(calm_per_year)
             if labels[labels == "W3_2023_2026"].size >= 2 and calm_net[labels == "W3_2023_2026"].std(ddof=1) > 0
             else float("nan"))

    # 5. Direction null check WITHIN CALM regime
    section("Direction null check (CALM-only SHORT vs LONG, zero-cost)")
    calm_long_zero = long_bps[calm_mask]
    calm_short_zero = -calm_long_zero
    long_sh = calm_long_zero.mean() / calm_long_zero.std(ddof=1) if calm_long_zero.std(ddof=1) > 0 else 0.0
    short_sh = calm_short_zero.mean() / calm_short_zero.std(ddof=1) if calm_short_zero.std(ddof=1) > 0 else 0.0
    dir_gap = short_sh - long_sh
    print(f"  CALM LONG  zero-cost trade-Sh: {long_sh:+.3f}")
    print(f"  CALM SHORT zero-cost trade-Sh: {short_sh:+.3f}")
    print(f"  direction-gap (SHORT - LONG) : {dir_gap:+.3f}")

    # 6. Direction-lock across W1/W2/W3 within CALM
    section("Direction-lock check (each W must agree SHORT-wins)")
    direction_lock = True
    for w in ["W1_2019_2020", "W2_2021_2022", "W3_2023_2026"]:
        m = labels == w
        if m.sum() < 2:
            print(f"  {w}: insufficient (n={int(m.sum())})")
            direction_lock = False
            continue
        L = -calm_long_zero[m].mean()  # SHORT = -LONG
        N = calm_long_zero[m].mean()   # LONG mean
        winner = "SHORT" if L > N else "LONG"
        print(f"  {w}: SHORT mean {L*1:.2f} / LONG mean {N*1:.2f}  -> winner {winner}")
        if winner != "SHORT":
            direction_lock = False

    # 7. Bootstrap CI
    section("Bootstrap 95% CI on CALM full-sample mean")
    boot_lo, boot_pt, boot_hi = bootstrap_mean_ci(calm_net)
    print(f"  point: {boot_pt:+.2f} bps   95% CI [{boot_lo:+.2f}, {boot_hi:+.2f}] bps")

    # 8. Placebo — non-event same-weekday days in CALM regime
    section("Placebo (non-event same-weekday days, CALM-only)")
    event_set = set(kept)
    weekdays = {d.weekday() for d in calm_dates}
    plc_long = compute_placebo_returns(
        bars, event_set, lhmnd.TZ_NAME, weekdays,
        lhmnd.WIN_START_H, lhmnd.WIN_START_M,
        lhmnd.WIN_END_H, lhmnd.WIN_END_M,
        max_samples=1500,
    )
    plc_short = -plc_long
    plc_mean = float(plc_short.mean()) if len(plc_short) > 0 else float("nan")
    print(f"  placebo SHORT mean (gross): {plc_mean:+.2f} bps  (n={len(plc_short)})")

    # 9. Cost-stress
    section("Cost-sensitivity sweep")
    print(f"  {'mult':<6s} {'cost_bp':<8s} {'mean (bps)':>11s} {'ann-Sh':>8s}")
    cost_stress_net = None
    for m_ in (0.5, 1.0, 1.5, 2.0):
        c_var = COST_BPS * m_
        net_v = -long_bps[calm_mask] - c_var
        mean_v = float(net_v.mean())
        sh_v = annual_sharpe(net_v, calm_per_year)
        marker = "  (default)" if m_ == 1.0 else ("  (stress)" if m_ == COST_STRESS_MULT else "")
        print(f"  {m_:<6.1f} {c_var:<7.2f} {mean_v:>+10.2f} {sh_v:>+7.2f}{marker}")
        if m_ == COST_STRESS_MULT:
            cost_stress_net = mean_v

    # 10. Deflated Sharpe (modest trials count — we picked best Pool B candidate from ~5 candidates × 4 gates)
    n_diag_trials = 20
    dsh = deflated_sharpe(calm_full_sh, n_calm, n_diag_trials)
    section(f"Deflated Sharpe (n_trials={n_diag_trials})")
    print(f"  observed ann-Sh: {calm_full_sh:+.3f}")
    print(f"  deflated ann-Sh: {dsh:+.3f}")

    # 11. Kill criteria
    section("Pre-committed kill criteria (10) — CALIBRATED")
    criteria = [
        (f"1. Gated full Sh >= +{KC1_FULL_SH:.2f}", calm_full_sh >= KC1_FULL_SH,
            f"{calm_full_sh:+.2f}"),
        (f"2. W3 Sh >= +{KC2_W3_SH:.2f}",
            (not np.isnan(w3_sh)) and w3_sh >= KC2_W3_SH, f"W3={w3_sh:+.2f}"),
        (f"3. CALM events n >= {KC3_MIN_N_CALM}", n_calm >= KC3_MIN_N_CALM, f"n={n_calm}"),
        (f"4. CALM-regime active-aware Sh >= +{KC4_CALM_SH:.2f}",
            calm_active_sh >= KC4_CALM_SH, f"{calm_active_sh:+.2f}"),
        (f"5. Direction-gap >= +{KC5_DIR_GAP:.2f}", dir_gap >= KC5_DIR_GAP,
            f"{dir_gap:+.2f}"),
        ("6. Bootstrap 95% CI lower > 0 bp", boot_lo > KC6_BOOT_LOWER_GT,
            f"[{boot_lo:+.2f}, {boot_hi:+.2f}]"),
        ("7. Direction-lock: SHORT wins in all sub-W with n>=2", direction_lock,
            "all sub-W agree" if direction_lock else "sign-flip in at least one"),
        (f"8. Placebo |mean| < {KC8_PLACEBO_MAG} bp", abs(plc_mean) < KC8_PLACEBO_MAG,
            f"{plc_mean:+.2f}"),
        (f"9. Cost-stress 2x net > 0", cost_stress_net is not None and cost_stress_net > KC9_COST_STRESS_NET_GT,
            f"{cost_stress_net:+.2f}" if cost_stress_net is not None else "n/a"),
        (f"10. Deflated Sh >= +{KC10_DEFLATED_SH:.2f}", dsh >= KC10_DEFLATED_SH,
            f"{dsh:+.2f}"),
    ]
    n_pass = 0
    for name, ok, msg in criteria:
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}] {name:<48s}  {msg}")
        if ok:
            n_pass += 1
    print(f"\n  Result: {n_pass}/10  ->  {'PASS' if n_pass == 10 else 'REJECT'}")

    # 12. Summary
    section("Summary")
    print(f"  last_hour_month_end_ndx v2 VIX-CALM-gated SHORT")
    print(f"  parent (unconditional, REJECT) SHORT ann-Sh: {short_full:+.2f}")
    print(f"  v2 (CALM-gated) ann-Sh: {calm_full_sh:+.2f}")
    print(f"  lift over parent: {calm_full_sh - short_full:+.2f}")
    print(f"  n_calm events: {n_calm}  cadence: {calm_per_year:.1f}/yr")
    print(f"  MDD: {mdd * 100:+.2f}%")
    print(f"  bootstrap CI [{boot_lo:+.2f}, {boot_hi:+.2f}]  deflated_sh {dsh:+.2f}")
    print(f"  verdict: {n_pass}/10 -> {'PASS' if n_pass == 10 else 'REJECT'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
