#!/usr/bin/env python3
"""XAUUSD M15 — Break of Structure + Retest, LDN-AM session (07-10 UTC).

Thesis: experiments/xau_ldn_am_fade/xau_ldn_am_fade.md

Session-transplant of the deployed xau_break_retest_m15 (NY-AM 13-15 UTC FADE)
onto the LDN-AM 07-10 UTC window. Mechanism, instrument, simulator unchanged;
only the session bounds move. The diff is a single 3-arg change.

Pre-committed kill criteria mirror the deployed parent's grid with two
adjustments:
  - Full FADE Sh threshold loosened to +0.50 (secondary session, not primary)
  - Trade-by-trade correlation vs deployed NY-AM book added as binding tombstone

Run:
  venv\\Scripts\\python.exe experiments\\xau_ldn_am_fade\\xau_ldn_am_fade_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
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


DATA_PATH = os.path.join(_ROOT, "ohlc_data", "XAUUSD_M5.csv")


def load_m15() -> pd.DataFrame:
    """Local loader (parent's _ROOT resolves wrong from _live/ subdir)."""
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
# Session override + pre-committed kill criteria for THIS experiment
# ---------------------------------------------------------------------------

SESSION_START_UTC = 7
SESSION_END_UTC = 10
ENTRY_CUTOFF_UTC = 10

COST_POINTS_DEFAULT = 0.20
COST_POINTS_SWEEP = (0.10, 0.20, 0.40, 0.80)

# Kill criteria (per thesis doc §"Fail conditions")
KC_SHARPE_FULL = 0.50
KC_SHARPE_REGIME = 0.20         # W1, W2
KC_SHARPE_HOLDOUT = 0.0         # W3
KC_MDD = 0.15
KC_TRADES_MIN = 200
KC_FADE_GAP = 0.30
KC_COST_STRESS_PT = 0.40
KC_DEFLATED_SH = 0.20
KC_CORR_VS_NYAM = 0.70
N_VARIANTS_PRECOMMITTED = 6


# Parent NY-AM session (for correlation diagnostic only)
NYAM_SESSION_START = 13
NYAM_SESSION_END = 15
NYAM_ENTRY_CUTOFF = 15


# ---------------------------------------------------------------------------
# Reporting helpers (LDN-AM specific kill grid)
# ---------------------------------------------------------------------------

def kill_criteria_check(label: str, direction: str, stats: dict, regime: dict,
                        fade_gap: float, cost_stress_sh: float, deflated_sh: float,
                        corr_vs_nyam: float | None = None
                        ) -> tuple[bool, str]:
    sh = stats.get("sharpe", 0.0)
    mdd = stats.get("mdd", -1.0)
    n = stats.get("n", 0)
    wr = stats.get("wr", 0.0)
    pf = stats.get("pf", 0.0)
    w1 = regime.get("W1 2019-2020", {})
    w2 = regime.get("W2 2021-2022", {})
    ho = regime.get("W3 2023-2026 (holdout)", {})
    w1_sh = w1.get("sharpe", 0.0)
    w2_sh = w2.get("sharpe", 0.0)
    ho_sh = ho.get("sharpe", 0.0)

    insufficient = n < KC_TRADES_MIN

    print(f"  [{label} - {direction}]")
    checks = [
        (f"FULL Sharpe > {KC_SHARPE_FULL:.2f}", sh > KC_SHARPE_FULL, f"{sh:+.2f}"),
        (f"W1 Sharpe   > {KC_SHARPE_REGIME:.2f}", w1_sh > KC_SHARPE_REGIME, f"{w1_sh:+.2f}"),
        (f"W2 Sharpe   > {KC_SHARPE_REGIME:.2f}", w2_sh > KC_SHARPE_REGIME, f"{w2_sh:+.2f}"),
        (f"W3 Sharpe   > {KC_SHARPE_HOLDOUT:.2f}", ho_sh > KC_SHARPE_HOLDOUT, f"{ho_sh:+.2f}"),
        (f"MDD         < {KC_MDD * 100:.0f}%", abs(mdd) < KC_MDD, f"{mdd * 100:+.2f}%"),
        (f"Trades     >= {KC_TRADES_MIN}", n >= KC_TRADES_MIN, f"{n}"),
        (f"Fade-gap   > {KC_FADE_GAP:.2f}", fade_gap > KC_FADE_GAP, f"{fade_gap:+.2f}"),
        (f"Cost-stress Sh@{KC_COST_STRESS_PT}pt > 0", cost_stress_sh > 0, f"{cost_stress_sh:+.2f}"),
        (f"Deflated Sh > {KC_DEFLATED_SH:.2f}", deflated_sh > KC_DEFLATED_SH, f"{deflated_sh:+.2f}"),
    ]
    if corr_vs_nyam is not None:
        checks.append((f"Corr vs NY-AM < {KC_CORR_VS_NYAM:.2f}",
                       corr_vs_nyam < KC_CORR_VS_NYAM, f"{corr_vs_nyam:+.2f}"))

    all_pass = True
    for desc, ok, val in checks:
        print(f"    {desc:<32s} : {'PASS' if ok else 'FAIL'}  ({val})")
        if not ok:
            all_pass = False
    if insufficient:
        verdict = "INSUFFICIENT_N"
    else:
        verdict = "PASS" if all_pass else "FAIL"
    print(f"    -> {verdict} on Phase 2 kill criteria")
    return all_pass and not insufficient, verdict


def cost_sweep(df: pd.DataFrame, label: str, direction: str, **kwargs) -> None:
    print(f"  [{label} {direction} - cost sweep]")
    for cp in COST_POINTS_SWEEP:
        rets, trades = simulate_break_retest_m15(df, direction=direction,
                                                 cost_points=cp,
                                                 session_start_utc=SESSION_START_UTC,
                                                 session_end_utc=SESSION_END_UTC,
                                                 entry_cutoff_utc=ENTRY_CUTOFF_UTC,
                                                 **kwargs)
        if rets.size == 0:
            print(f"    cost={cp:.2f}pt  (no trades)")
            continue
        first = pd.Timestamp(trades[0]["entry_ts"])
        last = pd.Timestamp(trades[-1]["entry_ts"])
        years = max((last - first).days / 365.25, 1e-9)
        tpy = len(rets) / years
        sh = annualized_sharpe(rets, trades_per_year=tpy)
        eq = (1 + rets).cumprod()
        mdd = max_drawdown(eq)
        flag = " (deploy)" if cp == COST_POINTS_DEFAULT else \
               (" (stress)" if cp == KC_COST_STRESS_PT else "")
        print(f"    cost={cp:.2f}pt  Sh {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  "
              f"n={len(rets)}{flag}")


# ---------------------------------------------------------------------------
# Correlation diagnostic: LDN-AM trades vs deployed NY-AM trades
# ---------------------------------------------------------------------------

def per_day_pnl(rets: np.ndarray, trades: list[dict]) -> pd.Series:
    """Aggregate per-trade net returns to per-date totals.

    Operational view: if both EAs ran every day, what is the per-day pnl
    series each contributed? Days with no trade contribute 0.
    """
    if rets.size == 0:
        return pd.Series(dtype=np.float64)
    rows = []
    for r, t in zip(rets, trades):
        d = pd.Timestamp(t["entry_ts"]).normalize()
        rows.append((d, r))
    s = pd.DataFrame(rows, columns=["date", "ret"]).groupby("date")["ret"].sum()
    return s


def trade_corr_vs_nyam(rets_ldn: np.ndarray, trades_ldn: list[dict],
                       rets_ny: np.ndarray, trades_ny: list[dict]
                       ) -> tuple[float, int]:
    """Pearson correlation of per-day net-ret series (zero-fill on no-trade days)."""
    if rets_ldn.size == 0 or rets_ny.size == 0:
        return float("nan"), 0
    s_ldn = per_day_pnl(rets_ldn, trades_ldn)
    s_ny = per_day_pnl(rets_ny, trades_ny)
    # Union of dates over the overlap range only (to avoid head/tail of one series)
    lo = max(s_ldn.index.min(), s_ny.index.min())
    hi = min(s_ldn.index.max(), s_ny.index.max())
    s_ldn = s_ldn[(s_ldn.index >= lo) & (s_ldn.index <= hi)]
    s_ny = s_ny[(s_ny.index >= lo) & (s_ny.index <= hi)]
    all_dates = s_ldn.index.union(s_ny.index)
    a = s_ldn.reindex(all_dates, fill_value=0.0).to_numpy()
    b = s_ny.reindex(all_dates, fill_value=0.0).to_numpy()
    if a.std() == 0 or b.std() == 0:
        return float("nan"), len(all_dates)
    return float(np.corrcoef(a, b)[0, 1]), len(all_dates)


# ---------------------------------------------------------------------------
# Variant orchestrator
# ---------------------------------------------------------------------------

def run_variant_bidir(df: pd.DataFrame, label: str, nyam_pack: dict | None,
                      **filter_kwargs) -> dict:
    """Run one variant in BOTH directions on LDN-AM window."""
    section(f"Variant: {label}")

    out: dict = {"label": label}

    common = dict(session_start_utc=SESSION_START_UTC,
                  session_end_utc=SESSION_END_UTC,
                  entry_cutoff_utc=ENTRY_CUTOFF_UTC,
                  **filter_kwargs)

    # ---- CONTINUATION ----
    rets_c, trades_c = simulate_break_retest_m15(df, direction="continuation",
                                                 cost_points=COST_POINTS_DEFAULT,
                                                 **common)
    stats_c = report_run(f"{label} CONT", rets_c, trades_c)
    print()
    print(f"  Regime breakdown - {label} CONT:")
    rb_c = regime_breakdown(rets_c, trades_c)

    # ---- FADE ----
    print()
    rets_f, trades_f = simulate_break_retest_m15(df, direction="fade",
                                                 cost_points=COST_POINTS_DEFAULT,
                                                 **common)
    stats_f = report_run(f"{label} FADE", rets_f, trades_f)
    print()
    print(f"  Regime breakdown - {label} FADE:")
    rb_f = regime_breakdown(rets_f, trades_f)

    # ---- Cost sweep ----
    print()
    cost_sweep(df, label, "continuation", **filter_kwargs)
    print()
    cost_sweep(df, label, "fade", **filter_kwargs)

    # Cost-stress @ 0.4 pt
    rets_c_cs, _ = simulate_break_retest_m15(df, direction="continuation",
                                             cost_points=KC_COST_STRESS_PT,
                                             **common)
    cs_c = annualized_sharpe(rets_c_cs, trades_per_year=max(stats_c.get("tpy", 1), 1))
    rets_f_cs, _ = simulate_break_retest_m15(df, direction="fade",
                                             cost_points=KC_COST_STRESS_PT,
                                             **common)
    cs_f = annualized_sharpe(rets_f_cs, trades_per_year=max(stats_f.get("tpy", 1), 1))

    fg_c = stats_c["sharpe"] - stats_f["sharpe"]
    fg_f = stats_f["sharpe"] - stats_c["sharpe"]

    dsh_c = deflated_sharpe(stats_c["sharpe"], rets_c, n_trials=N_VARIANTS_PRECOMMITTED)
    dsh_f = deflated_sharpe(stats_f["sharpe"], rets_f, n_trials=N_VARIANTS_PRECOMMITTED)

    # Correlation vs deployed NY-AM (FADE only, since FADE is the deployed direction)
    corr_f = corr_n = None
    if nyam_pack is not None:
        corr_f, corr_n = trade_corr_vs_nyam(rets_f, trades_f,
                                            nyam_pack["rets"], nyam_pack["trades"])
        print()
        print(f"  Corr (per-day net-ret) vs deployed NY-AM FADE: "
              f"{corr_f:+.3f}  (n_days={corr_n})")

    # Kill criteria
    print()
    section(f"Kill criteria - {label}")
    passed_c, verdict_c = kill_criteria_check(label, "CONT", stats_c, rb_c,
                                              fg_c, cs_c, dsh_c, corr_vs_nyam=None)
    print()
    passed_f, verdict_f = kill_criteria_check(label, "FADE", stats_f, rb_f,
                                              fg_f, cs_f, dsh_f, corr_vs_nyam=corr_f)

    out["cont"] = {"stats": stats_c, "regime": rb_c, "fade_gap": fg_c,
                   "cost_stress_sh": cs_c, "deflated_sh": dsh_c,
                   "passed": passed_c, "verdict": verdict_c,
                   "rets": rets_c, "trades": trades_c}
    out["fade"] = {"stats": stats_f, "regime": rb_f, "fade_gap": fg_f,
                   "cost_stress_sh": cs_f, "deflated_sh": dsh_f,
                   "passed": passed_f, "verdict": verdict_f,
                   "corr_vs_nyam": corr_f, "corr_n_days": corr_n,
                   "rets": rets_f, "trades": trades_f}
    return out


def _row(label: str, direction: str, r: dict) -> str:
    s = r["stats"]
    rb = r["regime"]
    w1 = rb.get("W1 2019-2020", {}).get("sharpe", 0.0)
    w2 = rb.get("W2 2021-2022", {}).get("sharpe", 0.0)
    ho = rb.get("W3 2023-2026 (holdout)", {}).get("sharpe", 0.0)
    corr_str = f"{r.get('corr_vs_nyam'):+.2f}" if r.get("corr_vs_nyam") is not None else "  -- "
    return (
        f"  {label:<14s} {direction:<5s} {s.get('sharpe', 0):>+6.2f} "
        f"{w1:>+6.2f} {w2:>+6.2f} {ho:>+6.2f} "
        f"{s.get('mdd', 0) * 100:>+7.2f}% "
        f"{s.get('n', 0):>5d} "
        f"{s.get('wr', 0) * 100:>4.1f}% "
        f"{s.get('pf', 0):>4.2f} "
        f"{r['fade_gap']:>+6.2f} "
        f"{r['cost_stress_sh']:>+6.2f} "
        f"{r['deflated_sh']:>+6.2f} "
        f"{corr_str:>6s} "
        f"{r['verdict']}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section("Loading XAUUSD M5 -> resample to M15 (LDN-AM session 07-10 UTC)")
    df = load_m15()
    print(f"  M15 bars: {len(df):,}")
    print(f"  range   : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    in_session = df[(df["hour"] >= SESSION_START_UTC) & (df["hour"] < SESSION_END_UTC)]
    print(f"  in-session (07-10 UTC): {len(in_session):,} bars across "
          f"{in_session['date'].nunique()} days")
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    atr_arr, _ = compute_atr_adx(h, l, c)
    in_sess_mask = ((df["hour"].to_numpy() >= SESSION_START_UTC)
                    & (df["hour"].to_numpy() < SESSION_END_UTC))
    atr_sess = atr_arr[in_sess_mask]
    atr_sess = atr_sess[np.isfinite(atr_sess)]
    print(f"  in-session ATR(14) M15: "
          f"p10 {np.percentile(atr_sess, 10):.2f}, "
          f"p25 {np.percentile(atr_sess, 25):.2f}, "
          f"p50 {np.percentile(atr_sess, 50):.2f}, "
          f"p75 {np.percentile(atr_sess, 75):.2f}, "
          f"p90 {np.percentile(atr_sess, 90):.2f} USD")

    # ---- Pre-compute deployed NY-AM FADE baseline for correlation ----
    section("Pre-computing deployed NY-AM FADE baseline (correlation reference)")
    ny_rets, ny_trades = simulate_break_retest_m15(
        df, direction="fade",
        session_start_utc=NYAM_SESSION_START,
        session_end_utc=NYAM_SESSION_END,
        entry_cutoff_utc=NYAM_ENTRY_CUTOFF,
        cost_points=COST_POINTS_DEFAULT,
    )
    print(f"  NY-AM FADE baseline: n={len(ny_rets)}  "
          f"mean={ny_rets.mean()*10000:+.2f}bp  std={ny_rets.std()*10000:.2f}bp")
    nyam_pack = {"rets": ny_rets, "trades": ny_trades}

    results: list[dict] = []
    # 6 variants × 2 directions (matches parent's grid)
    results.append(run_variant_bidir(df, "baseline", nyam_pack))
    results.append(run_variant_bidir(df, "atr-3", nyam_pack, atr_floor_usd=3.0))
    results.append(run_variant_bidir(df, "atr-5", nyam_pack, atr_floor_usd=5.0))
    results.append(run_variant_bidir(df, "atr-7", nyam_pack, atr_floor_usd=7.0))
    results.append(run_variant_bidir(df, "atr-10", nyam_pack, atr_floor_usd=10.0))
    results.append(run_variant_bidir(df, "atr-5+adx-20", nyam_pack,
                                     atr_floor_usd=5.0, adx_thresh=20.0))

    # ---- Summary ----
    section("Phase 2 summary - all variants x directions (LDN-AM 07-10 UTC)")
    header = (
        f"  {'variant':<14s} {'dir':<5s} {'Sh':>6s} {'W1':>6s} {'W2':>6s} {'W3':>6s} "
        f"{'MDD':>8s} {'n':>5s} {'WR%':>5s} {'PF':>5s} {'fgap':>6s} {'Sh@CS':>6s} "
        f"{'dSh':>6s} {'corr':>6s} verdict"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in results:
        print(_row(r["label"], "CONT", r["cont"]))
        print(_row(r["label"], "FADE", r["fade"]))

    # Deploy candidates
    print()
    print("  Deploy candidates (any direction PASSING all kill criteria incl. corr<+0.70):")
    passers = []
    for r in results:
        for d in ("cont", "fade"):
            if r[d]["passed"]:
                passers.append((r["label"], d, r[d]["stats"]["sharpe"]))
    if passers:
        for lab, d, sh in sorted(passers, key=lambda x: -x[2]):
            print(f"    {lab:<14s} {d:<5s} Sh {sh:+.2f}")
    else:
        print("    NONE pass all kill criteria.")

    # Per-direction summary line
    print()
    print("  Per-direction summary (best Sh across variants):")
    for d_label, d_key in (("CONT", "cont"), ("FADE", "fade")):
        best = max(results, key=lambda r: r[d_key]["stats"].get("sharpe", -99))
        best_sh = best[d_key]["stats"]["sharpe"]
        best_lab = best["label"]
        best_v = best[d_key]["verdict"]
        print(f"    {d_label}: best Sh {best_sh:+.2f} on '{best_lab}' (verdict: {best_v})")

    # Mechanism-interpretation diagnostics: where do trades cluster within the window?
    section("Mechanism diagnostic - hour-of-entry distribution (baseline FADE)")
    base_f = results[0]["fade"]
    if base_f["trades"]:
        hours = [pd.Timestamp(t["entry_ts"]).hour for t in base_f["trades"]]
        from collections import Counter
        c_h = Counter(hours)
        for h in sorted(c_h.keys()):
            print(f"    hour {h:02d} UTC: {c_h[h]:>4d} trades")
        # Net per hour
        per_hour: dict = {}
        for r_, t in zip(base_f["rets"], base_f["trades"]):
            hh = pd.Timestamp(t["entry_ts"]).hour
            per_hour.setdefault(hh, []).append(r_)
        print()
        print("    Per-hour mean net-ret (bp), baseline FADE:")
        for hh in sorted(per_hour.keys()):
            arr = np.asarray(per_hour[hh])
            print(f"    hour {hh:02d} UTC: mean {arr.mean()*10000:+.2f}bp  n={len(arr)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
