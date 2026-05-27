#!/usr/bin/env python3
"""
Regime classifier diagnostic — Phase 1 audit.

Thesis: experiments/regime_classifier_diagnostic/regime_classifier_diagnostic.md

For each (strategy × regime gate × regime state), computes per-regime daily
PnL Sharpe + active-day count + mean daily return. Surfaces:
  - Which strategies are regime-conditional candidates (max-Sh-spread ≥ +0.5)
  - Which gate discriminates the most strategies
  - Resurrect candidates (Pool B tombstoned strategies with regime-on Sh > +0.5)

Usage:
  venv/Scripts/python.exe experiments/regime_classifier_diagnostic/regime_classifier_diagnostic.py
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

_HERE = Path(__file__).resolve().parent
_EXPERIMENTS = _HERE.parent
_ROOT = _EXPERIMENTS.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str((_ROOT / '..' / 'backtesting-engine-2.0').resolve()))
sys.path.insert(0, str(_EXPERIMENTS / '_live' / 'portfolio_risk_parity'))
sys.path.insert(0, str(_EXPERIMENTS / 'last_hour_month_end_ndx'))
sys.path.insert(0, str(_EXPERIMENTS / 'structural_flow_audit'))


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 96}\n  {t}\n{'=' * 96}\n")


def fred_csv(series_id: str) -> pd.DataFrame:
    """Pull a daily FRED series via the public fredgraph CSV endpoint."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    # FRED CSVs have columns 'DATE' (or 'observation_date') and the series id
    date_col = "DATE" if "DATE" in df.columns else df.columns[0]
    val_col = series_id if series_id in df.columns else df.columns[1]
    df = df[[date_col, val_col]].rename(columns={date_col: "date", val_col: series_id})
    df["date"] = pd.to_datetime(df["date"])
    df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
    df = df.dropna(subset=[series_id])
    return df.set_index("date")


def annual_sharpe(r: np.ndarray, bpy: int = 252) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    sd = r.std(ddof=1)
    return 0.0 if sd == 0 else float(r.mean() / sd * np.sqrt(bpy))


def annual_sharpe_active_aware(active_returns: np.ndarray,
                               active_per_year: float) -> float:
    """Honest annualized Sharpe for sparse-event strategies.

    Computes trade-Sharpe over active days (zero-days excluded) and annualizes
    by sqrt(active_per_year), NOT sqrt(252). For dense strategies (orb_dax,
    xau_br_*) where active_per_year ≈ 252, this reduces to the standard formula.
    For sparse (lunch_fade ~16/yr, macro events ~8/yr), it gives the honest
    Sharpe matching the strategy's research-side annualization.
    """
    r = active_returns[np.isfinite(active_returns)]
    if r.size < 2 or active_per_year <= 0:
        return 0.0
    sd = r.std(ddof=1)
    return 0.0 if sd == 0 else float(r.mean() / sd * np.sqrt(active_per_year))


# -----------------------------------------------------------------------------
# Macro data fetch
# -----------------------------------------------------------------------------

def fetch_macro_series() -> pd.DataFrame:
    """Pull FFR, 10y, 2y, breakeven, VIX from FRED. Returns a daily DataFrame."""
    section("Fetching macro series from FRED")
    parts = {}
    series = ["DFF", "DGS10", "DGS2", "T10YIE", "VIXCLS"]
    for sid in series:
        try:
            parts[sid] = fred_csv(sid)
            n = len(parts[sid])
            print(f"  {sid:<8s}: {n:,} obs   {parts[sid].index.min().date()} -> {parts[sid].index.max().date()}")
        except Exception as e:
            print(f"  {sid:<8s}: FAILED ({e})")
            parts[sid] = None
    df = pd.concat([p for p in parts.values() if p is not None], axis=1).sort_index()
    df = df.ffill()  # forward-fill weekend/holiday gaps
    df = df.loc["2018-01-01":]  # match strategy lookbacks
    return df


# -----------------------------------------------------------------------------
# Regime gate definitions (all observable at date t, no lookahead)
# -----------------------------------------------------------------------------

def gate_ffr_direction(macro: pd.DataFrame, neutral_bp: float = 25.0) -> pd.Series:
    """6-month FFR change sign. NEUTRAL if |Δ| < neutral_bp (25 bp default)."""
    delta = macro["DFF"] - macro["DFF"].shift(180)
    states = pd.Series("NEUTRAL", index=macro.index)
    states[delta > neutral_bp / 100.0] = "TIGHTENING"
    states[delta < -neutral_bp / 100.0] = "EASING"
    return states


def gate_real_rate_sign(macro: pd.DataFrame) -> pd.Series:
    """10y nominal - 10y breakeven. Positive = tight real conditions."""
    real = macro["DGS10"] - macro["T10YIE"]
    return real.apply(lambda x: "POSITIVE" if x > 0 else "NEGATIVE" if x < 0 else "ZERO")


def gate_yield_curve_sign(macro: pd.DataFrame) -> pd.Series:
    """10y - 2y. Inverted = recession-precursor regime."""
    spread = macro["DGS10"] - macro["DGS2"]
    return spread.apply(lambda x: "INVERTED" if x < 0 else "NORMAL")


def gate_vix_regime(macro: pd.DataFrame) -> pd.Series:
    """60d trailing median VIX. CALM <15, STRESS >=22, else NORMAL."""
    med = macro["VIXCLS"].rolling(60, min_periods=20).median()
    states = pd.Series("NORMAL", index=macro.index)
    states[med < 15] = "CALM"
    states[med >= 22] = "STRESS"
    return states


REGIME_GATES = {
    "ffr_direction": gate_ffr_direction,
    "real_rate_sign": gate_real_rate_sign,
    "yield_curve_sign": gate_yield_curve_sign,
    "vix_regime": gate_vix_regime,
}


# -----------------------------------------------------------------------------
# Pool A: load all deployed strategies' daily PnL via portfolio_risk_parity
# -----------------------------------------------------------------------------

def load_pool_a() -> pd.DataFrame:
    """Pool A: 10 deployed-strategy daily PnL streams (reuses RP infrastructure)."""
    section("Loading Pool A — 10 deployed PnL streams")
    import portfolio_risk_parity_demo as rp
    df = rp.load_all_daily()
    # df has columns = STRATS, index = dates, values = daily fractional returns (0 = no trade)
    print(f"  shape: {df.shape}  date range: {df.index.min().date()} -> {df.index.max().date()}")
    return df


# -----------------------------------------------------------------------------
# Pool B: re-simulate tombstoned regime-conditional candidates
# -----------------------------------------------------------------------------

def load_pool_b() -> pd.DataFrame:
    """Pool B v2: 2 regime-conditional REJECTed strategies for resurrect-question.
       - last_hour_month_end_ndx (lesson #74, W2 sign-flip)
       - opex_pin_fade (lesson #-5, 0DTE-amplification sign-inversion)"""
    section("Loading Pool B v2 — tombstoned regime-conditional REJECTs")
    series_dict = {}

    # 1. last_hour_month_end_ndx (SHORT direction, best aggregate)
    try:
        import last_hour_month_end_ndx_demo as lhmnd
        from structural_flow_audit import gen_month_end_dates, compute_window_returns
        bars = lhmnd.load_ndx_m5()
        event_dates = gen_month_end_dates(lhmnd.YEARS)
        long_bps, kept = compute_window_returns(
            bars, event_dates, lhmnd.TZ_NAME,
            lhmnd.WIN_START_H, lhmnd.WIN_START_M, lhmnd.WIN_END_H, lhmnd.WIN_END_M,
        )
        cost_bps = lhmnd.cost_bps_from_points(lhmnd.COST_POINTS_DEFAULT)
        short_net = -long_bps - cost_bps
        s = pd.Series(short_net / 1e4, index=pd.to_datetime([str(d) for d in kept]))
        s.name = "last_hour_month_end_ndx_REJ"
        s = s.groupby(level=0).sum()
        # Reindex onto continuous daily index for fair regime partitioning
        full_idx = pd.date_range(s.index.min(), s.index.max(), freq="B")
        s_cont = s.reindex(full_idx, fill_value=0.0)
        s_cont.name = "last_hour_month_end_ndx_REJ"
        series_dict["last_hour_month_end_ndx_REJ"] = s_cont
        print(f"  last_hour_month_end_ndx_REJ : {(s_cont != 0).sum()} active days / "
              f"{s_cont.index.min().date()} -> {s_cont.index.max().date()}")
    except Exception as e:
        print(f"  last_hour_month_end_ndx_REJ : FAILED ({e})")

    # 2. opex_pin_fade (NDX FADE, monthly OPEX Friday last 2h)
    try:
        sys.path.insert(0, str(_EXPERIMENTS / "opex_pin_fade"))
        import opex_pin_fade_demo as opf
        bars = opf.load_m5("NDX100")
        bar_ret, trades = opf.simulate_opex_pin_fade(bars)
        # Aggregate per-trade pnl to daily
        if trades:
            rows = []
            for t in trades:
                d = pd.Timestamp(t["entry_ts"]).tz_convert("UTC").tz_localize(None).normalize() \
                    if pd.Timestamp(t["entry_ts"]).tz is not None \
                    else pd.Timestamp(t["entry_ts"]).normalize()
                rows.append((d, t["pnl_pct"] / 100.0))
            tr_df = pd.DataFrame(rows, columns=["date", "ret"])
            daily = tr_df.groupby("date")["ret"].sum()
            full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="B")
            s_cont = daily.reindex(full_idx, fill_value=0.0)
            s_cont.name = "opex_pin_fade_REJ"
            series_dict["opex_pin_fade_REJ"] = s_cont
            print(f"  opex_pin_fade_REJ           : {len(trades)} trades / "
                  f"{(s_cont != 0).sum()} active days / "
                  f"{s_cont.index.min().date()} -> {s_cont.index.max().date()}")
        else:
            print(f"  opex_pin_fade_REJ           : no trades returned")
    except Exception as e:
        print(f"  opex_pin_fade_REJ           : FAILED ({e})")

    if not series_dict:
        return pd.DataFrame()
    return pd.concat(series_dict.values(), axis=1).fillna(0.0)


# -----------------------------------------------------------------------------
# Audit: per-strategy × per-gate × per-regime Sharpe matrix
# -----------------------------------------------------------------------------

def audit_one_strategy(daily_pnl: pd.Series, gates: dict[str, pd.Series],
                      strategy_name: str) -> pd.DataFrame:
    """For one strategy and all gates, compute per-regime stats.

    TWO Sharpe columns reported:
      - `sharpe_active_aware`: mean / std × sqrt(active_per_year_IN_regime).
        "If you only ever traded in this regime forever, what's your Sharpe?"
        This is what the diagnostic surfaces as the regime-conditional spread.
      - `sharpe_deployable`:   mean / std × sqrt(active_per_year_FULL_SAMPLE_with_gate).
        "If you GATE the strategy to this regime within the full sample, what's
        your live deployable Sharpe?" This is the honest deploy estimate.

    Calibrated from xau_session_v2_ffr_gated REJECT: active-aware Sh +0.80 lift
    translated to deployable Sh +0.30 lift — deflation factor ~sqrt(regime_years/
    full_years) ≈ 0.4-0.6 for typical regime widths.
    """
    rows = []
    nz = daily_pnl[daily_pnl != 0]
    if len(nz) < 30:
        return pd.DataFrame()
    # Strategy's full sample span (used for deflation calc)
    strat_total_days = (daily_pnl.index.max() - daily_pnl.index.min()).days
    if strat_total_days < 60:
        return pd.DataFrame()
    strat_years = strat_total_days / 365.25
    # Align gate state to each PnL date
    for gate_name, gate_series in gates.items():
        gate_aligned = gate_series.reindex(daily_pnl.index, method="ffill")
        for state in gate_aligned.unique():
            if pd.isna(state):
                continue
            # Regime-total calendar days: use the FULL daily macro index (gate_series),
            # not the strategy's index (which is sparse for event-driven strategies).
            # This gives honest calendar-time span of the regime regardless of
            # whether the strategy fired during it.
            regime_total_days_calendar = int((gate_series == state).sum())
            if regime_total_days_calendar < 60:
                continue
            # Active days within regime (from the strategy's PnL)
            active_mask = (gate_aligned == state) & (daily_pnl != 0)
            sub = daily_pnl[active_mask]
            if len(sub) < 5:
                continue
            # Regime-conditional active-per-year cadence (IN regime)
            regime_years = regime_total_days_calendar / 252.0
            active_per_year_in_regime = len(sub) / max(regime_years, 0.01)
            sh_active_aware = annual_sharpe_active_aware(sub.to_numpy(), active_per_year_in_regime)
            # DEPLOYABLE: same trades, but annualized over the FULL strategy sample
            # (because if we gate to this regime, we still measure Sharpe vs all days)
            active_per_year_full_sample = len(sub) / max(strat_years, 0.01)
            sh_deployable = annual_sharpe_active_aware(sub.to_numpy(), active_per_year_full_sample)
            # Deflation factor for reference (= sqrt(regime_years / strat_years))
            deflation = sh_deployable / sh_active_aware if sh_active_aware != 0 else 1.0
            mean = float(sub.mean())
            rows.append({
                "strategy": strategy_name,
                "gate": gate_name,
                "regime": state,
                "n_days": len(sub),
                "regime_total_days": regime_total_days_calendar,
                "active_per_year_in_regime": active_per_year_in_regime,
                "active_per_year_full_sample": active_per_year_full_sample,
                "mean_daily_pct": mean * 100,
                "sharpe": sh_active_aware,             # legacy column name = active-aware
                "sharpe_active_aware": sh_active_aware,
                "sharpe_deployable": sh_deployable,
                "deflation_factor": deflation,
            })
    return pd.DataFrame(rows)


def compute_spreads(audit_df: pd.DataFrame) -> pd.DataFrame:
    """For each (strategy, gate), compute max-min Sharpe spread + max-regime.
    Reports both active-aware (for diagnostic) and deployable (for honest
    deploy estimates per xau_session_v2 calibration)."""
    rows = []
    for (strat, gate), grp in audit_df.groupby(["strategy", "gate"]):
        if len(grp) < 2:
            continue
        # Active-aware (legacy)
        sh_max_aa = grp["sharpe_active_aware"].max()
        sh_min_aa = grp["sharpe_active_aware"].min()
        regime_max = grp.loc[grp["sharpe_active_aware"].idxmax(), "regime"]
        regime_min = grp.loc[grp["sharpe_active_aware"].idxmin(), "regime"]
        # Deployable (calibrated)
        sh_max_dep = grp["sharpe_deployable"].max()
        sh_min_dep = grp["sharpe_deployable"].min()
        rows.append({
            "strategy": strat, "gate": gate, "n_states": len(grp),
            "sh_max_active": sh_max_aa, "sh_min_active": sh_min_aa,
            "spread_active": sh_max_aa - sh_min_aa,
            "sh_max_deploy": sh_max_dep, "sh_min_deploy": sh_min_dep,
            "spread_deploy": sh_max_dep - sh_min_dep,
            "regime_max": regime_max, "regime_min": regime_min,
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    # 1. Macro series
    macro = fetch_macro_series()
    print(f"\n  macro daily frame: {macro.shape}")

    # 2. Compute gate states
    section("Computing regime gate states")
    gate_states = {name: fn(macro) for name, fn in REGIME_GATES.items()}
    for name, s in gate_states.items():
        counts = s.value_counts().to_dict()
        print(f"  {name:<20s}  states: {counts}")

    # 3. Pool A
    pool_a = load_pool_a()

    # 4. Pool B (v1 — just last_hour_month_end_ndx)
    try:
        pool_b = load_pool_b()
    except Exception as e:
        print(f"  Pool B load failed: {e}")
        pool_b = pd.DataFrame()

    # 5. Audit each strategy
    section("Auditing each strategy × gate × regime")
    all_rows = []
    for col in pool_a.columns:
        df = audit_one_strategy(pool_a[col], gate_states, f"A:{col}")
        if not df.empty:
            all_rows.append(df)
    if not pool_b.empty:
        for col in pool_b.columns:
            df = audit_one_strategy(pool_b[col], gate_states, f"B:{col}")
            if not df.empty:
                all_rows.append(df)
    audit_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    print(f"  total audit rows: {len(audit_df)}")

    # 6. Output per-gate matrix
    if audit_df.empty:
        print("  No data — aborting.")
        return 1

    for gate_name in REGIME_GATES.keys():
        section(f"GATE: {gate_name}")
        sub = audit_df[audit_df["gate"] == gate_name].copy()
        if sub.empty:
            print("  (no data)")
            continue
        # Pivot: rows = strategy, cols = regime, values = Sharpe
        pivot_sh = sub.pivot_table(index="strategy", columns="regime", values="sharpe", aggfunc="first")
        pivot_n = sub.pivot_table(index="strategy", columns="regime", values="n_days", aggfunc="first")
        print("  Sharpe by regime:")
        print(pivot_sh.round(2).to_string())
        print("\n  n_days by regime:")
        print(pivot_n.fillna(0).astype(int).to_string())

    # 7. Spread ranking
    section("Spread ranking — DEPLOYABLE Sh (calibrated from xau_session_v2 lift)")
    spreads = compute_spreads(audit_df)
    spreads_sorted = spreads.sort_values("spread_deploy", ascending=False)
    print(f"  {'strategy':<40s} {'gate':<20s} "
          f"{'sh_max_dep':>10s} {'sh_min_dep':>10s} {'spread_dep':>10s}  "
          f"{'(active-aware):':>18s} {'sh_max_aa':>9s} {'spread_aa':>10s}")
    for _, r in spreads_sorted.iterrows():
        marker = ""
        # Use deployable spread thresholds (more honest)
        if r["spread_deploy"] > 0.5:
            marker = "  ** STRONG"
        elif r["spread_deploy"] > 0.3:
            marker = "  * MODERATE"
        print(f"  {r['strategy']:<40s} {r['gate']:<20s} "
              f"{r['sh_max_deploy']:>+9.2f} {r['sh_min_deploy']:>+9.2f} {r['spread_deploy']:>+9.2f}"
              f"  ({r['regime_max']:<12s})  "
              f"{r['sh_max_active']:>+8.2f} {r['spread_active']:>+9.2f}{marker}")

    # 8. Per-gate cross-strategy discrimination
    section("Per-gate cross-strategy discrimination (DEPLOYABLE spread)")
    print("  (sum of deployable spread across all strategies — higher = more universally discriminating)")
    print(f"  {'gate':<22s} {'n_strats':>10s} {'mean_dep_spread':>16s} {'sum_dep_spread':>15s} {'n_strong_dep':>13s}")
    for gate_name in REGIME_GATES.keys():
        gs = spreads[spreads["gate"] == gate_name]
        if gs.empty:
            continue
        mean_spread = float(gs["spread_deploy"].mean())
        sum_spread = float(gs["spread_deploy"].sum())
        n_strong = int((gs["spread_deploy"] > 0.5).sum())
        print(f"  {gate_name:<22s} {len(gs):>10d} {mean_spread:>+15.2f} "
              f"{sum_spread:>+14.2f} {n_strong:>13d}")

    # 9. Pre-committed verdicts
    section("Pre-committed verdicts")
    pool_a_strats = [s for s in spreads["strategy"].unique() if s.startswith("A:")]
    pool_b_strats = [s for s in spreads["strategy"].unique() if s.startswith("B:")]

    print("\n  POOL A (deployed strategies) — by DEPLOYABLE spread:")
    pool_a_strong_per_gate = {}
    for gate_name in REGIME_GATES.keys():
        sub = spreads[(spreads["gate"] == gate_name) & (spreads["strategy"].str.startswith("A:"))]
        strong = sub[sub["spread_deploy"] > 0.5]
        pool_a_strong_per_gate[gate_name] = len(strong)
    max_a_strong_gate = max(pool_a_strong_per_gate, key=pool_a_strong_per_gate.get)
    max_a_strong_n = pool_a_strong_per_gate[max_a_strong_gate]
    print(f"  Max strong-deploy-spread strategies under any single gate: {max_a_strong_n} (gate={max_a_strong_gate})")
    if max_a_strong_n >= 3:
        a_verdict = "DEPLOYED-BOOK GATING HAS LEGS"
    elif max_a_strong_n >= 1:
        a_verdict = "TARGETED DEPLOYED GATING"
    else:
        max_a_moderate = max(
            (spreads[(spreads["gate"] == g) & (spreads["strategy"].str.startswith("A:"))]["spread_deploy"] > 0.3).sum()
            for g in REGIME_GATES.keys()
        )
        if max_a_moderate >= 1:
            a_verdict = "WEAK DEPLOYED-BOOK SIGNAL (moderate-spread strategies exist; small-n caution)"
        else:
            a_verdict = "DEPLOYED BOOK IS REGIME-NEUTRAL (per deflated lift estimate, after xau_session_v2 calibration)"
    print(f"  -> POOL A verdict: {a_verdict}")

    print("\n  POOL B (tombstoned resurrect candidates):")
    if pool_b_strats:
        for gate_name in REGIME_GATES.keys():
            sub = spreads[(spreads["gate"] == gate_name) & (spreads["strategy"].str.startswith("B:"))]
            for _, r in sub.iterrows():
                tag = ""
                # Resurrect threshold: deployable spread > 0.4 AND best-regime deployable Sh > 0.4
                if r["spread_deploy"] > 0.4 and r["sh_max_deploy"] > 0.4:
                    tag = "  ** RESURRECT CANDIDATE"
                print(f"  {r['strategy']:<40s} {gate_name:<20s} "
                      f"spread_dep={r['spread_deploy']:+.2f} sh_max_dep={r['sh_max_deploy']:+.2f}"
                      f"  (active-aware spread={r['spread_active']:+.2f}){tag}")
    else:
        print("  (Pool B empty / failed to load)")

    print("\n  COMBINED book vision verdict:")
    if "HAS LEGS" in a_verdict:
        print("  -> REGIME-BOOK VISION EMPIRICALLY SUPPORTED on deployed strategies")
    elif "TARGETED" in a_verdict:
        print("  -> TARGETED REGIME-GATING valuable for specific deployed responders")
    elif "WEAK" in a_verdict:
        print("  -> WEAK DEPLOYED SIGNAL — selection-bias-confirmation; check Pool B (which has fewer events)")
    else:
        print("  -> DEPLOYED BOOK IS REGIME-NEUTRAL — selection-bias hypothesis confirmed")
    print()
    print(f"  Highest-cross-strategy-discrimination gate: {max(pool_a_strong_per_gate, key=pool_a_strong_per_gate.get)}")
    print(f"  Next action: build v2-gated thesis on the highest-spread responder using the best gate")

    # 10. Save outputs
    out_dir = _HERE / "outputs"
    out_dir.mkdir(exist_ok=True)
    audit_df.to_csv(out_dir / "audit_matrix.csv", index=False)
    spreads_sorted.to_csv(out_dir / "spread_ranking.csv", index=False)
    print(f"\n  Saved:")
    print(f"    {out_dir / 'audit_matrix.csv'}")
    print(f"    {out_dir / 'spread_ranking.csv'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
