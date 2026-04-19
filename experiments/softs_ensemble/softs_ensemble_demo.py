#!/usr/bin/env python3
"""
Softs TSMOM ensemble (COCOA + COFFEE + COTTON) -- Phase 2 demo.

Thesis: experiments/softs_ensemble/softs_ensemble.md

Per-instrument MH-LO + pyramid, equal-weight daily returns blend. Key
question: does the ensemble materially beat single-instrument Sharpes of
0.40-0.45 via diversification?
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
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'gold_trend'))

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series, simulate_tsmom_pyramid,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Full candidate universe -- softs + grains + OJ. Runs per-instrument, then
# blends. Per-instrument performance is reported so weak names are visible.
# The blend arithmetically down-weights weak legs in proportion (equal-weight
# across N, so each leg contributes 1/N of the blend's vol/return budget).
CANDIDATE_UNIVERSE = [
    # Softs (scan-validated passers)
    "COCOA", "COFFEE", "COTTON",
    # Grains (first expansion batch)
    "WHEAT", "CORN", "SOYBEAN", "ORANGE_JUICE",
    # Livestock + oats + KC wheat (second expansion batch)
    "LIVE_CATTLE", "FEEDER_CATTLE", "LEAN_HOGS", "OATS", "KC_WHEAT",
]
# Final UNIVERSE used in the blend -- set after per-instrument screen below.
UNIVERSE = CANDIDATE_UNIVERSE

COST_BPS_PER_SIDE = 5.0           # per-side; scan baseline
START = "2015-01-01"
END = "2026-04-18"
# Phase-2 per-instrument gate for ensemble inclusion
INCLUDE_SHARPE_MIN = 0.30
INCLUDE_ALPHA_MIN = 0.00          # signal must at least match B&H


def section(t: str) -> None:
    print(f"\n{'=' * 84}\n  {t}\n{'=' * 84}\n")


def metrics(r: pd.Series) -> dict:
    """Return dict of common perf metrics for a daily-return series."""
    rn = r.dropna()
    if len(rn) < 5:
        return {"years": 0, "total": 0.0, "cagr": 0.0, "sharpe": 0.0, "mdd": 0.0}
    eq = (1.0 + rn).cumprod().to_numpy()
    years = (rn.index[-1] - rn.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(rn.to_numpy())
    mdd = max_drawdown(eq)
    return {"years": years, "total": total, "cagr": cagr, "sharpe": sh, "mdd": mdd}


def report_block(label: str, r: pd.Series) -> None:
    m = metrics(r)
    if m["years"] == 0:
        print(f"  {label:<22s} (no data)")
        return
    print(f"  {label:<22s} ret {m['total'] * 100:>+8.2f}%  CAGR {m['cagr'] * 100:>+7.2f}%  "
          f"Sharpe {m['sharpe']:>+6.2f}  MDD {m['mdd'] * 100:>+7.2f}%")


# ---------------------------------------------------------------------------
# Per-instrument runner
# ---------------------------------------------------------------------------

def run_instrument(sym: str, cost_bps: float = COST_BPS_PER_SIDE) -> dict | None:
    df = load_series(sym)
    if df is None or len(df) < max(LOOKBACKS) + 100:
        return None
    df = df.loc[START:END]
    close = df["close"]
    high = df["high"]
    low = df["low"]
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)
    strat_ret, stats = simulate_tsmom_pyramid(
        close, sig, rv, atr, f"{sym}-MH-LO-P",
        long_only=True, cost_bps_per_side=cost_bps,
    )
    bh_ret = ret.rename(f"{sym}-BH")
    return {
        "symbol": sym,
        "strat_ret": strat_ret,
        "bh_ret": bh_ret,
        "stats": stats,
        "close": close,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section("Screening candidate universe (per-instrument MH-LO + pyramid)")
    all_results: dict[str, dict] = {}
    print(f"  {'symbol':<14s} {'strat-Sh':>9s} {'strat-CAGR':>11s} {'strat-MDD':>10s}  "
          f"{'B&H-Sh':>7s} {'alpha':>7s}  {'gate':>5s}")
    for sym in CANDIDATE_UNIVERSE:
        r = run_instrument(sym)
        if r is None:
            print(f"  {sym:<14s} (load failed)")
            continue
        all_results[sym] = r
        m = metrics(r["strat_ret"])
        bh_m = metrics(r["bh_ret"])
        alpha = m["sharpe"] - bh_m["sharpe"]
        passes_gate = (m["sharpe"] >= INCLUDE_SHARPE_MIN and alpha >= INCLUDE_ALPHA_MIN)
        gate_str = "PASS" if passes_gate else "drop"
        r["_passes_gate"] = passes_gate
        r["_metrics"] = m
        r["_bh_metrics"] = bh_m
        r["_alpha"] = alpha
        print(f"  {sym:<14s} {m['sharpe']:>+8.2f}  {m['cagr'] * 100:>+10.2f}% "
              f"{m['mdd'] * 100:>+9.2f}%  {bh_m['sharpe']:>+6.2f}  {alpha:>+6.2f}  "
              f"{gate_str:>5s}")

    # Build final ensemble from instruments passing the gate.
    results = {s: r for s, r in all_results.items() if r["_passes_gate"]}
    ensemble_universe = list(results.keys())
    print(f"\n  Gate: Sharpe >= {INCLUDE_SHARPE_MIN}, alpha vs B&H >= {INCLUDE_ALPHA_MIN}")
    print(f"  Ensemble survivors ({len(ensemble_universe)}): {', '.join(ensemble_universe)}")

    if len(ensemble_universe) < 3:
        print(f"\n  Ensemble too small ({len(ensemble_universe)}) -- aborting")
        return 1

    # Use the survivors as the working UNIVERSE for rest of the demo.
    global UNIVERSE
    UNIVERSE = ensemble_universe

    # ----- Per-instrument full stats ------------------------------------
    section("Per-instrument performance (Phase 2 check per instrument)")
    print(f"  {'variant':<22s} {'ret':>10s}  {'CAGR':>8s}  {'Sharpe':>7s}  {'MDD':>8s}")
    for sym in UNIVERSE:
        report_block(f"{sym}-MH-LO-P", results[sym]["strat_ret"])
        report_block(f"{sym}-BuyHold", results[sym]["bh_ret"])

    # ----- Within-ensemble correlations ----------------------------------
    section("Within-ensemble correlations (strategy daily returns)")
    df_strat = pd.concat(
        [results[s]["strat_ret"].rename(s) for s in UNIVERSE], axis=1, join="inner"
    ).dropna()
    corr = df_strat.corr()
    print(f"  Daily correlation matrix  ({len(df_strat)} common bars):")
    print(corr.round(3).to_string())

    monthly = (1.0 + df_strat).resample("ME").prod() - 1.0
    mcorr = monthly.corr()
    print(f"\n  Monthly correlation matrix  ({len(monthly)} months):")
    print(mcorr.round(3).to_string())

    off_diag = corr.values[np.triu_indices_from(corr, k=1)]
    avg_corr = float(np.mean(off_diag))
    print(f"\n  Average off-diagonal daily corr: {avg_corr:+.3f}")

    # ----- Equal-weight blend --------------------------------------------
    section("Equal-weight blend of 3 softs (strategy)")
    blend_strat = df_strat.mean(axis=1).rename("softs-blend")
    report_block("COCOA-MH-LO-P", df_strat["COCOA"])
    report_block("COFFEE-MH-LO-P", df_strat["COFFEE"])
    report_block("COTTON-MH-LO-P", df_strat["COTTON"])
    report_block("EW-blend (strategy)", blend_strat)

    # ----- Equal-weight passive benchmark --------------------------------
    section("Reference: EW passive basket of 3 softs (B&H)")
    df_bh = pd.concat(
        [results[s]["bh_ret"].rename(s) for s in UNIVERSE], axis=1, join="inner"
    ).dropna()
    blend_bh = df_bh.mean(axis=1).rename("softs-bh-blend")
    report_block("COCOA B&H", df_bh["COCOA"])
    report_block("COFFEE B&H", df_bh["COFFEE"])
    report_block("COTTON B&H", df_bh["COTTON"])
    report_block("EW-blend (B&H basket)", blend_bh)

    # ----- Regime breakdown ----------------------------------------------
    section("Regime sub-periods (blend strategy)")
    windows = [
        ("2015-2017",         "2015-01-01", "2017-12-31"),
        ("2018-2019",         "2018-01-01", "2019-12-31"),
        ("2020-2021",         "2020-01-01", "2021-12-31"),
        ("2022",              "2022-01-01", "2022-12-31"),
        ("2023-2026 holdout", "2023-01-01", "2026-12-31"),
    ]
    print(f"  {'window':<22s} {'ret':>10s}  {'CAGR':>8s}  {'Sharpe':>7s}  {'MDD':>8s}")
    regime_returns = []
    for wl, s, e in windows:
        sub = blend_strat.loc[s:e]
        if len(sub) < 50:
            continue
        m = metrics(sub)
        regime_returns.append((wl, m["total"]))
        report_block(wl, sub)

    # Concentration check
    tot = sum(abs(r) for _, r in regime_returns)
    max_share = max(abs(r) for _, r in regime_returns) / tot if tot > 0 else 0.0
    print(f"\n  Max regime share of total abs return: {max_share * 100:.1f}%  "
          f"({'PASS' if max_share < 0.60 else 'FAIL'} -- need < 60%)")

    # Per-instrument contribution to total blend return
    section("Per-instrument contribution to blend CAGR")
    blend_total = float((1.0 + blend_strat).cumprod().iloc[-1] - 1.0)
    for sym in UNIVERSE:
        sym_total = float((1.0 + df_strat[sym]).cumprod().iloc[-1] - 1.0)
        print(f"  {sym:<14s} strat-total {sym_total * 100:>+8.2f}%  "
              f"(blend {blend_total * 100:>+8.2f}%)")

    # ----- Q1 2026 focus -------------------------------------------------
    section("Q1 2026 (recent quarter, latest real-OOS)")
    q1_26_strat = blend_strat.loc["2026-01-01":"2026-03-31"]
    q1_26_bh = blend_bh.loc["2026-01-01":"2026-03-31"]
    if len(q1_26_strat) >= 5:
        eq_s = (1.0 + q1_26_strat).cumprod()
        eq_bh = (1.0 + q1_26_bh).cumprod()
        print(f"  Blend strategy : ret {eq_s.iloc[-1] - 1:>+7.2%}  "
              f"Sharpe {annualized_sharpe(q1_26_strat.to_numpy()):>+5.2f}  "
              f"MDD {max_drawdown(eq_s.to_numpy()):>+7.2%}")
        print(f"  EW B&H basket  : ret {eq_bh.iloc[-1] - 1:>+7.2%}  "
              f"Sharpe {annualized_sharpe(q1_26_bh.to_numpy()):>+5.2f}  "
              f"MDD {max_drawdown(eq_bh.to_numpy()):>+7.2%}")
        print(f"\n  Per-instrument Q1 2026 (strategy):")
        for sym in UNIVERSE:
            sub = df_strat[sym].loc["2026-01-01":"2026-03-31"]
            if len(sub) < 5:
                continue
            eq = (1.0 + sub).cumprod()
            print(f"    {sym:<14s} ret {eq.iloc[-1] - 1:>+7.2%}  "
                  f"MDD {max_drawdown(eq.to_numpy()):>+7.2%}")
        print(f"\n  Per-instrument Q1 2026 (buy & hold underlying):")
        for sym in UNIVERSE:
            sub = df_bh[sym].loc["2026-01-01":"2026-03-31"]
            if len(sub) < 5:
                continue
            eq = (1.0 + sub).cumprod()
            print(f"    {sym:<14s} ret {eq.iloc[-1] - 1:>+7.2%}")
    else:
        print("  Not enough Q1 2026 data yet")

    # ----- Phase 2 kill-criteria check -----------------------------------
    section("Phase 2 kill-criteria check (ensemble blend)")
    blend_m = metrics(blend_strat)
    blend_bh_m = metrics(blend_bh)
    alpha = blend_m["sharpe"] - blend_bh_m["sharpe"]
    n_trades_total = sum(results[s]["stats"]["trades"] for s in UNIVERSE)

    def v(c: bool) -> str: return "PASS" if c else "FAIL"
    print(f"  Blend Sharpe > 0.50       : {v(blend_m['sharpe'] > 0.50)}  ({blend_m['sharpe']:+.2f})")
    print(f"  Alpha vs B&H basket >= +0.10 : {v(alpha >= 0.10)}  ({alpha:+.2f})")
    print(f"  MDD < 35%                 : {v(abs(blend_m['mdd']) < 0.35)}  ({blend_m['mdd'] * 100:+.2f}%)")
    print(f"  Total trades >= 150       : {v(n_trades_total >= 150)}  ({n_trades_total})")
    print(f"  Avg pairwise corr < 0.5   : {v(avg_corr < 0.5)}  ({avg_corr:+.3f})")
    print(f"  Max regime share < 60%    : {v(max_share < 0.60)}  ({max_share * 100:.1f}%)")

    phase2_pass = (blend_m["sharpe"] > 0.50
                   and alpha >= 0.10
                   and abs(blend_m["mdd"]) < 0.35
                   and n_trades_total >= 150
                   and avg_corr < 0.5
                   and max_share < 0.60)

    section("Summary")
    print(f"  Per-instrument Sharpes   : " + ", ".join(
        f"{s}={metrics(results[s]['strat_ret'])['sharpe']:+.2f}" for s in UNIVERSE
    ))
    print(f"  Blend (strategy) Sharpe  : {blend_m['sharpe']:+.2f}  CAGR {blend_m['cagr'] * 100:+.2f}%  "
          f"MDD {blend_m['mdd'] * 100:+.2f}%")
    print(f"  Blend (B&H basket)       : {blend_bh_m['sharpe']:+.2f}  CAGR {blend_bh_m['cagr'] * 100:+.2f}%  "
          f"MDD {blend_bh_m['mdd'] * 100:+.2f}%")
    print(f"  Alpha vs B&H basket      : {alpha:+.2f} Sharpe")
    print(f"  Diversification lift     : blend - avg single = "
          f"{blend_m['sharpe'] - np.mean([metrics(results[s]['strat_ret'])['sharpe'] for s in UNIVERSE]):+.2f}")
    print()
    if phase2_pass:
        print("  Phase 2 OVERALL: PASS -- proceed to Phase 3 stat battery.")
    else:
        print("  Phase 2 OVERALL: FAIL -- rethink or expand universe.")

    return 0 if phase2_pass else 1


if __name__ == "__main__":
    sys.exit(main())
