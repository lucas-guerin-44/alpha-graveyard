#!/usr/bin/env python3
"""
Single-instrument MH-LO + pyramid scan.

Runs the multi-horizon long-only TSMOM with 1-unit pyramid (from
gold_trend_demo.py) on every instrument in a broad trend-prone universe.
Reports per-instrument Sharpe / CAGR / MDD against each instrument's own
buy-and-hold. Goal is to find where TSMOM actually earns alpha vs passive
exposure, single-instrument.

No portfolio construction -- each instrument stands or falls alone.
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

from gold_trend_demo import (
    LOOKBACKS, VOL_LOOKBACK, VOL_TARGET_ANN, BARS_PER_YEAR,
    annualized_sharpe, max_drawdown, load_series,
    multi_horizon_signal, atr_series,
    simulate_tsmom, simulate_tsmom_pyramid,
)


# ---------------------------------------------------------------------------
# Universe -- trend-prone asset classes only (no single equities / vol / cash)
# ---------------------------------------------------------------------------

UNIVERSE = [
    # FX crosses (exotic + major)
    "AUDNZD", "NZDCAD", "GBPNZD", "AUDCAD", "CADJPY", "NZDJPY",
    "EURGBP", "EURNOK", "USDZAR", "EURUSD", "GBPUSD",
    # Commodities
    "XAUUSD", "USOUSD", "COCOA", "COFFEE", "SUGAR", "COTTON", "LUMBER",
    # Equity indices (CFD)
    "SPX500", "NDX100", "GER40",
    # Country ETFs
    "EWZ", "FXI", "EWJ",
    # Crypto
    "BTCUSD",
    # Long-duration rates
    "TLT",
]


# ---------------------------------------------------------------------------
# Per-instrument runner
# ---------------------------------------------------------------------------

def run_one(sym: str) -> dict | None:
    df = load_series(sym)
    if df is None or len(df) < max(LOOKBACKS) + 100:
        return None
    close = df["close"]
    high = df["high"]
    low = df["low"]
    ret = close.pct_change().fillna(0.0)
    rv = ret.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).std(ddof=1) * np.sqrt(BARS_PER_YEAR)
    rv = rv.shift(1)
    sig = multi_horizon_signal(close, LOOKBACKS)
    atr = atr_series(high, low, close)

    # Strategy: MH-LO + pyramid at baseline (K=3, atr_mult=1.0, cap=1.0x)
    strat_ret, strat_stats = simulate_tsmom_pyramid(
        close, sig, rv, atr, f"{sym}-MH-LO-P", long_only=True,
    )
    # Also plain MH-LO (no pyramid) for comparison
    plain_ret, plain_stats = simulate_tsmom(close, sig, rv, f"{sym}-MH-LO", long_only=True)

    bh = ret.rename(f"{sym}-BH")

    def metrics(r: pd.Series) -> tuple[float, float, float, float]:
        eq = (1.0 + r).cumprod()
        years = (r.index[-1] - r.index[0]).days / 365.25
        total = float(eq.iloc[-1] - 1.0)
        cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
        sh = annualized_sharpe(r.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        return total, cagr, sh, mdd

    s_total, s_cagr, s_sh, s_mdd = metrics(strat_ret)
    p_total, p_cagr, p_sh, p_mdd = metrics(plain_ret)
    b_total, b_cagr, b_sh, b_mdd = metrics(bh)

    years = (close.index[-1] - close.index[0]).days / 365.25

    return {
        "symbol": sym,
        "years": years,
        "bars": len(close),
        "trades": strat_stats["trades"],
        "strat_cagr": s_cagr,
        "strat_sharpe": s_sh,
        "strat_mdd": s_mdd,
        "plain_sharpe": p_sh,
        "bh_cagr": b_cagr,
        "bh_sharpe": b_sh,
        "bh_mdd": b_mdd,
        "alpha_sharpe": s_sh - b_sh,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"\n{'=' * 100}")
    print(f"  MH-LO + pyramid scan across {len(UNIVERSE)} instruments")
    print(f"  Params: LOOKBACKS={LOOKBACKS}  VOL_TARGET={VOL_TARGET_ANN:.0%}  K=3  atr_mult=1.0  cap=1.00x")
    print(f"{'=' * 100}\n")

    rows: list[dict] = []
    failed: list[str] = []
    for sym in UNIVERSE:
        print(f"  {sym} ...", end=" ", flush=True)
        try:
            r = run_one(sym)
        except Exception as e:
            print(f"ERROR ({e})")
            failed.append(sym)
            continue
        if r is None:
            print("insufficient data")
            failed.append(sym)
            continue
        rows.append(r)
        print(f"Sharpe {r['strat_sharpe']:+.2f}  vs B&H {r['bh_sharpe']:+.2f}  (alpha {r['alpha_sharpe']:+.2f})")

    if not rows:
        print("No instruments produced results.")
        return 1

    # --- Sorted table ---
    rows.sort(key=lambda r: r["strat_sharpe"], reverse=True)

    print(f"\n{'=' * 100}")
    print("  Results sorted by strategy Sharpe")
    print(f"{'=' * 100}\n")
    hdr = (
        f"  {'symbol':<8s} {'years':>5s} {'trades':>6s} "
        f"{'strat-CAGR':>10s} {'strat-Sh':>9s} {'strat-MDD':>10s}  "
        f"{'B&H-CAGR':>9s} {'B&H-Sh':>7s} {'B&H-MDD':>8s}  "
        f"{'alpha-Sh':>9s}  {'plain-Sh':>9s}"
    )
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        print(
            f"  {r['symbol']:<8s} {r['years']:>5.1f} {r['trades']:>6d} "
            f"{r['strat_cagr'] * 100:>+9.2f}% {r['strat_sharpe']:>+8.2f} {r['strat_mdd'] * 100:>+9.2f}%  "
            f"{r['bh_cagr'] * 100:>+8.2f}% {r['bh_sharpe']:>+6.2f} {r['bh_mdd'] * 100:>+7.2f}%  "
            f"{r['alpha_sharpe']:>+8.2f}  {r['plain_sharpe']:>+8.2f}"
        )

    # --- Aggregate stats ---
    print(f"\n{'=' * 100}")
    print("  Summary")
    print(f"{'=' * 100}\n")
    n = len(rows)
    pass_phase2 = sum(1 for r in rows if r["strat_sharpe"] > 0.30 and abs(r["strat_mdd"]) < 0.30 and r["trades"] >= 50)
    beat_bh = sum(1 for r in rows if r["strat_sharpe"] > r["bh_sharpe"])
    beat_bh_meaningfully = sum(1 for r in rows if r["alpha_sharpe"] > 0.10)
    pyramid_helps = sum(1 for r in rows if r["strat_sharpe"] > r["plain_sharpe"])

    print(f"  Instruments scanned successfully : {n}/{len(UNIVERSE)}")
    if failed:
        print(f"  Skipped / failed                  : {', '.join(failed)}")
    print(f"  Pass Phase 2 kill-criteria       : {pass_phase2}/{n}")
    print(f"    (Sharpe > 0.30 AND MDD < 30% AND trades >= 50)")
    print(f"  Beat own buy-and-hold on Sharpe  : {beat_bh}/{n}")
    print(f"  Beat B&H by >= 0.10 Sharpe       : {beat_bh_meaningfully}/{n}")
    print(f"  Pyramid beats plain MH-LO        : {pyramid_helps}/{n}")

    print(f"\n  Top 5 by strategy Sharpe         :")
    for r in rows[:5]:
        print(f"    {r['symbol']:<8s} Sharpe {r['strat_sharpe']:+.2f}  CAGR {r['strat_cagr'] * 100:+.2f}%  "
              f"MDD {r['strat_mdd'] * 100:+.2f}%  alpha {r['alpha_sharpe']:+.2f}")
    print(f"\n  Top 5 by alpha vs B&H            :")
    for r in sorted(rows, key=lambda x: x["alpha_sharpe"], reverse=True)[:5]:
        print(f"    {r['symbol']:<8s} alpha {r['alpha_sharpe']:+.2f}  (strat {r['strat_sharpe']:+.2f}  B&H {r['bh_sharpe']:+.2f})")
    print(f"\n  Bottom 5 by strategy Sharpe      :")
    for r in rows[-5:]:
        print(f"    {r['symbol']:<8s} Sharpe {r['strat_sharpe']:+.2f}  CAGR {r['strat_cagr'] * 100:+.2f}%  "
              f"MDD {r['strat_mdd'] * 100:+.2f}%  alpha {r['alpha_sharpe']:+.2f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
