#!/usr/bin/env python3
"""pre_fomc_drift Phase 2 simulator + validation pipeline.

FX-side falsification test of the deployed NDX-LONG-pre-FOMC mechanism. Same
calendar (`experiments/_live/macro_drift/fomc_calendar.csv`), same 24h window,
same 30-min exit buffer; vessel is EURUSD M5 not NDX100 M5.

Per lesson #54 (validated in pre_nfp_drift), runs BOTH directions (LONG / SHORT)
in parallel and selects the deploy direction ex-post from the null-gap. User-
stated prior is SHORT EURUSD (= LONG USD, risk-premium-flow-into-Fed story),
but that's used only for interpretation.

Pre-committed kill criteria (applied to BEST direction):
  1. Per-trade mean > +0.05% at 1 bp RT cost
  2. W4 (2024-2026) per-trade mean > +0.03%
  3. PF > 1.3
  4. Sharpe (x sqrt(8)) > +0.30
  5. MDD < 25%
  6. Events >= 40
  7. Direction null-gap |LONG-SHORT| Sh >= +0.30
  8. Walk-forward OOS mean Sh >= +0.30, min OOS Sh >= 0
  9. Placebo non-FOMC Wednesdays benign (|mean| < 0.04% or |t| < 1.5)

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/pre_fomc_drift/pre_fomc_drift_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT / "experiments" / "_live" / "macro_drift"))
from _profile_fomc_drift import et_to_utc, label_regime  # type: ignore


# ---------- config ----------

CAL_PATH = _ROOT / "experiments" / "_live" / "macro_drift" / "fomc_calendar.csv"
EURUSD_M5_PATH = _ROOT / "ohlc_data" / "EURUSD_M5.csv"

COST_BPS_DEFAULT = 1.0  # EURUSD CFD Eightcap ~0.5-1 bp RT
WINDOW_HOURS = 24
EXIT_BUFFER_MIN = 30

WINDOW_HOURS_SWEEP = (6, 12, 18, 24, 48)
EXIT_BUFFER_SWEEP = (5, 15, 30, 60)
COST_SWEEP_BPS = (0.0, 0.5, 1.0, 2.0, 5.0)

ANNUALIZER = 8.0  # ~8 FOMC events/yr


# ---------- data loading ----------

def load_calendar(historical_only: bool = True) -> pd.DataFrame:
    df = pd.read_csv(CAL_PATH)
    df["date"] = pd.to_datetime(df["date"])
    if historical_only:
        df = df[df["is_historical"] == "yes"].copy()
    rows = []
    for _, r in df.iterrows():
        h, m = map(int, r["announce_time_et"].split(":"))
        et_dt = r["date"] + pd.Timedelta(hours=h, minutes=m)
        utc_dt = et_to_utc(et_dt)
        rows.append({
            "date": r["date"], "year": r["date"].year,
            "regime": label_regime(r["date"].year),
            "announce_utc": utc_dt,
            "with_projections": r.get("with_projections", "no") == "yes",
        })
    return pd.DataFrame(rows)


def load_m5(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def build_ts_array(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    ts = df["timestamp"].values.astype("datetime64[ns]")
    close = df["close"].to_numpy(dtype=np.float64)
    return ts, close


def closest_close(ts: np.ndarray, close: np.ndarray, target_utc: pd.Timestamp,
                  tolerance_min: int = 30) -> float | None:
    target = np.datetime64(target_utc.tz_convert("UTC").tz_localize(None))
    idx = np.searchsorted(ts, target)
    candidates = []
    if idx > 0:
        candidates.append(idx - 1)
    if idx < len(ts):
        candidates.append(idx)
    best_idx = None
    best_delta = pd.Timedelta(days=10)
    for c in candidates:
        delta = abs(pd.Timestamp(ts[c]) - pd.Timestamp(target))
        if delta < best_delta:
            best_delta = delta
            best_idx = c
    if best_idx is None or best_delta > pd.Timedelta(minutes=tolerance_min):
        return None
    return float(close[best_idx])


# ---------- core ----------

def compute_event_returns(ts: np.ndarray, close: np.ndarray, cal: pd.DataFrame,
                          window_hours: int = WINDOW_HOURS,
                          exit_buffer_min: int = EXIT_BUFFER_MIN,
                          cost_bps: float = COST_BPS_DEFAULT,
                          direction: str = "long") -> pd.DataFrame:
    sign = +1.0 if direction == "long" else -1.0
    rows = []
    for _, ev in cal.iterrows():
        announce = ev["announce_utc"]
        entry_t = announce - pd.Timedelta(hours=window_hours)
        exit_t = announce - pd.Timedelta(minutes=exit_buffer_min)
        entry_px = closest_close(ts, close, entry_t)
        exit_px = closest_close(ts, close, exit_t)
        if entry_px is None or exit_px is None:
            continue
        gross = sign * (exit_px - entry_px) / entry_px * 100.0
        net = gross - cost_bps / 100.0
        rows.append({
            "date": ev["date"], "year": ev["year"], "regime": ev["regime"],
            "with_projections": ev["with_projections"],
            "entry_px": entry_px, "exit_px": exit_px,
            "gross_pct": gross, "net_pct": net,
        })
    return pd.DataFrame(rows)


# ---------- stats ----------

def event_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"n": 0, "sh": 0.0, "mdd": 0.0, "cagr": 0.0, "wr": 0.0, "pf": 0.0,
                "mean": 0.0, "std": 0.0, "t": 0.0, "total": 0.0}
    net = trades["net_pct"].to_numpy() / 100.0
    n = len(net)
    mean = float(net.mean())
    std = float(net.std(ddof=1)) if n > 1 else 0.0
    se = std / np.sqrt(n) if n > 0 else 0.0
    t = mean / se if se > 0 else 0.0
    wr = float((net > 0).mean())
    eq = (1.0 + net).cumprod()
    total = float(eq[-1] - 1.0)
    sh_per_trade = mean / std if std > 0 else 0.0
    sh_annual = sh_per_trade * np.sqrt(ANNUALIZER)
    rm = np.maximum.accumulate(eq)
    mdd = float(((eq - rm) / rm).min())
    dates = pd.to_datetime(trades["date"])
    years = max((dates.max() - dates.min()).days / 365.25, 1e-9)
    cagr = ((1.0 + total) ** (1.0 / years)) - 1.0 if total > -1 else -1.0
    wins = net[net > 0]; losses = net[net <= 0]
    gw = float(wins.sum()) if wins.size else 0.0
    gl = float(-losses.sum()) if losses.size else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    return {"n": n, "sh": sh_annual, "mdd": mdd, "cagr": cagr, "wr": wr, "pf": pf,
            "mean": mean * 100, "std": std * 100, "t": t, "total": total}


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def report(label: str, trades: pd.DataFrame) -> None:
    m = event_metrics(trades)
    if m["n"] == 0:
        print(f"  [{label}] no trades"); return
    print(f"  [{label}]")
    print(f"    events    : {m['n']}")
    print(f"    mean_net  : {m['mean']:+.4f}%  std {m['std']:.4f}%  t {m['t']:+.2f}")
    print(f"    Sharpe    : {m['sh']:+.2f}  (ann x sqrt(8))")
    print(f"    MDD       : {m['mdd']*100:+.2f}%")
    print(f"    CAGR      : {m['cagr']*100:+.2f}%  (total {m['total']*100:+.2f}%)")
    print(f"    WR        : {m['wr']*100:.1f}%   PF {m['pf']:.2f}")


def regime_table(trades: pd.DataFrame) -> None:
    print(f'  {"regime":<8s} {"n":>4s}  {"mean":>10s} {"std":>8s} {"t":>6s}  {"WR":>6s} {"Sh":>7s}')
    for w in ("W1", "W2", "W3", "W4"):
        sub = trades[trades["regime"] == w]
        m = event_metrics(sub)
        if m["n"] < 3:
            print(f"  {w:<8s} {m['n']:>4d}  (sparse)"); continue
        marker = ""
        if w == "W4":
            if m["mean"] > 0.05: marker = "  <<< W4 PASS"
            elif m["mean"] > 0.03: marker = "  <<< W4 MARGINAL"
            elif m["mean"] < 0: marker = "  <<< W4 FAIL"
        print(f"  {w:<8s} {m['n']:>4d}  {m['mean']:>+9.4f}% {m['std']:>7.4f}% {m['t']:>+5.2f}  {m['wr']*100:>5.1f}% {m['sh']:>+6.2f}{marker}")


def kill_check(label: str, trades: pd.DataFrame) -> dict:
    m = event_metrics(trades)
    if m["n"] == 0:
        print(f"  [{label}] NO TRADES -- KILL"); return {}
    w4 = trades[trades["regime"] == "W4"]
    w4m = event_metrics(w4) if len(w4) >= 3 else {"mean": 0.0}
    checks = {
        "mean > +0.05%      ": m["mean"] > 0.05,
        "W4_mean > +0.03%   ": w4m.get("mean", 0) > 0.03,
        "PF   > 1.3         ": m["pf"] > 1.3,
        "Sh   > +0.30       ": m["sh"] > 0.30,
        "MDD  < 25%         ": abs(m["mdd"]) < 0.25,
        "events >= 40       ": m["n"] >= 40,
    }
    print(f"  [{label}]   n={m['n']}  mean {m['mean']:+.4f}%  Sh {m['sh']:+.2f}  MDD {m['mdd']*100:+.2f}%  WR {m['wr']*100:.1f}%  PF {m['pf']:.2f}")
    for c, ok in checks.items():
        print(f"    {c} : {'PASS' if ok else 'FAIL'}")
    return checks


# ---------- placebo ----------

def placebo_check(ts: np.ndarray, close: np.ndarray, cal: pd.DataFrame,
                  direction: str, cost_bps: float = COST_BPS_DEFAULT,
                  seed: int = 42) -> dict:
    """Same 24h pre-14:00-ET window on random non-FOMC Wednesdays."""
    fomc_dates = set(cal["date"].dt.date)
    start = pd.Timestamp(ts[0]).date()
    end = pd.Timestamp(ts[-1]).date()
    all_wed = []
    d = pd.Timestamp(start)
    while d.date() <= end:
        if d.dayofweek == 2 and d.date() not in fomc_dates:
            all_wed.append(d)
        d += pd.Timedelta(days=1)
    rng = np.random.default_rng(seed)
    n = len(cal)
    if len(all_wed) < n:
        print(f"  placebo: not enough non-FOMC Wednesdays ({len(all_wed)})")
        return {"n": 0, "mean": 0.0, "t": 0.0, "sh": 0.0, "wr": 0.0}
    sampled = rng.choice(len(all_wed), size=n, replace=False)
    rows = []
    for idx in sampled:
        wed = all_wed[idx]
        et_dt = pd.Timestamp(wed.date()) + pd.Timedelta(hours=14)
        utc_dt = et_to_utc(et_dt)
        sign = +1.0 if direction == "long" else -1.0
        entry_t = utc_dt - pd.Timedelta(hours=24)
        exit_t = utc_dt - pd.Timedelta(minutes=30)
        e_px = closest_close(ts, close, entry_t)
        x_px = closest_close(ts, close, exit_t)
        if e_px is None or x_px is None:
            continue
        gross = sign * (x_px - e_px) / e_px * 100.0
        net = gross - cost_bps / 100.0
        rows.append({"date": wed, "gross_pct": gross, "net_pct": net,
                     "regime": label_regime(wed.year)})
    placebo = pd.DataFrame(rows)
    m = event_metrics(placebo)
    print(f"  placebo non-FOMC Wed ({direction:<5s})  n={m['n']}  mean {m['mean']:+.4f}%  t {m['t']:+.2f}  Sh {m['sh']:+.2f}  WR {m['wr']*100:.1f}%")
    return m


# ---------- walk-forward ----------

def walk_forward(ts: np.ndarray, close: np.ndarray, cal: pd.DataFrame,
                 direction: str, cost_bps: float = COST_BPS_DEFAULT) -> list[dict]:
    splits = [
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2026-12-31")),
    ]
    results = []
    for is_start, oos_start, oos_end in splits:
        is_cal = cal[(cal["date"] >= is_start) & (cal["date"] < oos_start)]
        oos_cal = cal[(cal["date"] >= oos_start) & (cal["date"] < oos_end)]
        is_t = compute_event_returns(ts, close, is_cal, cost_bps=cost_bps, direction=direction)
        oos_t = compute_event_returns(ts, close, oos_cal, cost_bps=cost_bps, direction=direction)
        is_m, oos_m = event_metrics(is_t), event_metrics(oos_t)
        results.append({
            "split": f"IS {is_start.year}->{oos_start.year} / OOS {oos_start.year}-{oos_end.year}",
            "is_n": is_m["n"], "is_sh": is_m["sh"], "is_mean": is_m["mean"],
            "oos_n": oos_m["n"], "oos_sh": oos_m["sh"], "oos_mean": oos_m["mean"],
        })
    return results


# ---------- main ----------

def main() -> int:
    section("PRE-FOMC DRIFT (EURUSD) -- Phase 2  (FX-side falsification test of NDX-LONG-pre-FOMC)")
    print(f"Calendar: {CAL_PATH}")
    print(f"M5 data:  {EURUSD_M5_PATH}")
    print(f"Window:   {WINDOW_HOURS}h entry / {EXIT_BUFFER_MIN}min exit buffer")
    print(f"Cost:     {COST_BPS_DEFAULT} bp RT default")
    print(f"User prior: SHORT EURUSD (= LONG USD); both directions run per lesson #54.")

    cal = load_calendar(historical_only=True)
    df = load_m5(EURUSD_M5_PATH)
    ts, close = build_ts_array(df)
    print(f"\nLoaded {len(cal)} historical FOMC events ({cal['date'].min().date()} -> {cal['date'].max().date()})")
    print(f"Loaded {len(df):,} EURUSD M5 bars ({df['timestamp'].min().date()} -> {df['timestamp'].max().date()})")

    section("BASELINE -- 24h, both directions, 1bp RT")
    base_long = compute_event_returns(ts, close, cal, direction="long")
    base_short = compute_event_returns(ts, close, cal, direction="short")
    report("LONG  EURUSD", base_long)
    print()
    report("SHORT EURUSD", base_short)

    m_long = event_metrics(base_long)
    m_short = event_metrics(base_short)
    sh_gap = m_long["sh"] - m_short["sh"]
    print(f"\n  Sharpe null-gap (LONG - SHORT)  : {sh_gap:+.2f}")
    print(f"  Mean   null-gap (LONG - SHORT)  : {m_long['mean'] - m_short['mean']:+.4f}%")
    best_dir = "long" if m_long["mean"] > m_short["mean"] else "short"
    null_ok = abs(sh_gap) >= 0.30
    print(f"  -> best direction (by mean): {best_dir.upper()}     null-gap >= 0.30: {'PASS' if null_ok else 'FAIL'}")

    best_trades = base_long if best_dir == "long" else base_short

    section(f"REGIME BREAKDOWN -- best direction = {best_dir.upper()}")
    regime_table(best_trades)

    section(f"KILL-CHECK (best = {best_dir.upper()}, 24h, 1bp)")
    checks = kill_check("baseline_best", best_trades)

    section(f"PLACEBO -- non-FOMC Wednesdays at 14:00-ET anchor (both directions)")
    placebo_best = placebo_check(ts, close, cal, direction=best_dir)
    placebo_opp = placebo_check(ts, close, cal, direction=("short" if best_dir == "long" else "long"))

    section(f"WALK-FORWARD (3 IS/OOS splits, {best_dir.upper()})")
    wf = walk_forward(ts, close, cal, direction=best_dir)
    print(f"  {'split':<42s} {'IS n':>5s} {'IS Sh':>7s} {'IS mean':>9s}   {'OOS n':>5s} {'OOS Sh':>7s} {'OOS mean':>9s}")
    for r in wf:
        print(f"  {r['split']:<42s} {r['is_n']:>5d} {r['is_sh']:>+7.2f} {r['is_mean']:>+8.4f}%   {r['oos_n']:>5d} {r['oos_sh']:>+7.2f} {r['oos_mean']:>+8.4f}%")
    wf_oos = [r["oos_sh"] for r in wf if r["oos_n"] >= 3]
    wf_mean = float(np.mean(wf_oos)) if wf_oos else float("nan")
    wf_min = float(np.min(wf_oos)) if wf_oos else float("nan")
    print(f"\n  Walk-forward OOS Sh: mean {wf_mean:+.2f}  min {wf_min:+.2f}")
    wf_ok = (len(wf_oos) >= 2) and (wf_mean >= 0.30) and (wf_min >= 0.0)
    print(f"  -> walk-forward: {'PASS' if wf_ok else 'FAIL'}")

    section(f"COST SENSITIVITY ({best_dir.upper()})")
    print(f"  {'cost(bp)':>8s} {'n':>4s} {'mean':>10s} {'Sh':>7s}")
    for c in COST_SWEEP_BPS:
        t = compute_event_returns(ts, close, cal, cost_bps=c, direction=best_dir)
        m = event_metrics(t)
        print(f"  {c:>8.1f} {m['n']:>4d} {m['mean']:>+9.4f}% {m['sh']:>+7.2f}")

    section(f"WINDOW x BUFFER SWEEP (1bp RT, {best_dir.upper()})")
    print(f"  {'window_h':>8s} {'buffer_min':>10s} {'n':>4s} {'mean':>10s} {'Sh':>7s}")
    for wh in WINDOW_HOURS_SWEEP:
        for eb in EXIT_BUFFER_SWEEP:
            t = compute_event_returns(ts, close, cal, window_hours=wh,
                                      exit_buffer_min=eb, direction=best_dir)
            m = event_metrics(t)
            print(f"  {wh:>8d} {eb:>10d} {m['n']:>4d} {m['mean']:>+9.4f}% {m['sh']:>+7.2f}")

    section("FINAL VERDICT SUMMARY")
    all_basic = all(checks.values()) if checks else False
    plc_ok = (abs(placebo_best.get("mean", 0)) < 0.04) or (abs(placebo_best.get("t", 0)) < 1.5)
    print(f"  Basic kill set (6 checks)    : {'PASS' if all_basic else 'FAIL'}")
    print(f"  Direction null-gap >= +0.30  : {'PASS' if null_ok else 'FAIL'} ({sh_gap:+.2f})")
    print(f"  Placebo benign               : {'PASS' if plc_ok else 'FAIL'} (mean {placebo_best.get('mean',0):+.4f}%, t {placebo_best.get('t',0):+.2f})")
    print(f"  Walk-forward OOS pass        : {'PASS' if wf_ok else 'FAIL'} (mean {wf_mean:+.2f} min {wf_min:+.2f})")

    section("VERDICT")
    user_match = (best_dir == "short")
    if all_basic and null_ok and plc_ok and wf_ok:
        verdict = "PASS"
        print(f"  PASS -- pre-FOMC {best_dir.upper()} EURUSD validated.")
        if user_match:
            print(f"         User prior (SHORT EURUSD = LONG USD risk-premium-flow) CONFIRMED.")
            print(f"         Refines lesson #62: pre-FOMC drift extends to USD-leg, not equity-vessel-only.")
        else:
            print(f"         User prior (SHORT) REFUTED; signal lives in LONG EURUSD direction.")
            print(f"         Mechanism story = carry-unwind or post-2022 risk-on USD-weakening, not risk-premium-flow.")
    elif null_ok and (event_metrics(best_trades)["mean"] > 0.03) and not all_basic:
        verdict = "MARGINAL"
        print(f"  MARGINAL -- directional signal exists ({best_dir.upper()}) but not deploy-grade.")
    else:
        verdict = "REJECT"
        print(f"  REJECT -- FX-side has no pre-FOMC drift mechanism.")
        print(f"         Sharpens lesson #62: NDX-pre-FOMC LONG is equity-cash-microstructure-specific,")
        print(f"         not generic USD-risk-premium-accumulation. The 'parallel FX leg' hypothesis is REFUTED.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
