#!/usr/bin/env python3
"""CFD Wednesday triple-rollover unwind flow on EURUSD -- Phase 2 simulator.

Tests the thesis that retail CFD traders systematically unwind LONG-EURUSD
positions on Wednesdays before the 22:00 UTC triple-swap rollover, producing
a directional SHORT-EURUSD edge in the Wednesday 10:00-20:00 UTC window.

Pre-committed kill criteria (from cfd_wed_rollover_eurusd.md, 0.86 bp RT):
  1. Full-sample mean per-trade > +2 bps                          (SHORT)
  2. W3 (2023-2026 holdout) mean per-trade > +0 bps               (SHORT)
  3. Direction null-gap (SHORT - LONG mean) >= +3 bps
  4. Placebo (non-Wed weekdays): SHORT-EUR mean < +1 bps
  5. Trade count after filters >= 100
  6. Annualised Sharpe (carry filter ON) > +0.30 net
  7. MDD < 15%
  8. Walk-forward 3-fold OOS: mean Sh >= +0.20 AND min OOS Sh >= -0.10
  9. Cost-stress at 2 bp RT: SHORT-EUR mean still > 0 bps

Conventions:
  - All loops on numpy arrays (CLAUDE.md "PRIORITIZE NUMPY ALWAYS").
  - Cost in bps round-trip, returns in bps (CLAUDE.md cross-instrument rule).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

# ---------- config ----------

EURUSD_M5_PATH = _ROOT / "ohlc_data" / "EURUSD_M5.csv"
USD_RATE_PATH = _ROOT / "ohlc_data" / "rates" / "USD_rate.csv"
EUR_RATE_PATH = _ROOT / "ohlc_data" / "rates" / "EUR_rate.csv"

# Eightcap EURUSD ~0.86 bps RT (confirmed by user screenshot 2026-05-26).
COST_BPS_DEFAULT = 0.86

WED_ENTRY_HOUR_UTC = 10
WED_EXIT_HOUR_UTC = 20
CARRY_FILTER_BPS = 100.0   # only trade when |Fed - ECB| > 100 bp

# Sweeps
COST_SWEEP_BPS = (0.0, 0.86, 1.5, 2.0, 3.0)
CARRY_SWEEP_BPS = (0.0, 50.0, 100.0, 200.0, 300.0)
WINDOW_SWEEP = (
    (6, 16), (8, 18), (10, 20), (12, 22), (14, 22),
)

# US holiday weeks where broker rollover schedule may shift (Tue/Fri triple
# instead of Wed). Hard-coded for 2019-2026 sample.
US_HOLIDAY_DATES = {
    # New Year's Day
    "2019-01-01", "2020-01-01", "2021-01-01", "2022-01-01",
    "2023-01-02", "2024-01-01", "2025-01-01", "2026-01-01",
    # Independence Day (observed)
    "2019-07-04", "2020-07-03", "2021-07-05", "2022-07-04",
    "2023-07-04", "2024-07-04", "2025-07-04", "2026-07-03",
    # Thanksgiving (4th Thu of Nov)
    "2019-11-28", "2020-11-26", "2021-11-25", "2022-11-24",
    "2023-11-23", "2024-11-28", "2025-11-27", "2026-11-26",
    # Christmas
    "2019-12-25", "2020-12-25", "2021-12-24", "2022-12-26",
    "2023-12-25", "2024-12-25", "2025-12-25", "2026-12-25",
}


def label_regime(year: int) -> str:
    if year <= 2020:
        return "W1"
    if year <= 2022:
        return "W2"
    return "W3"


# ---------- data loading ----------

def load_m5(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[df["timestamp"] >= pd.Timestamp("2019-01-01", tz="UTC")].copy()
    return df


def load_rate_diff() -> pd.DataFrame:
    """Build daily |USD - EUR| rate differential in bps, ffilled to daily."""
    usd = pd.read_csv(USD_RATE_PATH, parse_dates=["date"])
    eur = pd.read_csv(EUR_RATE_PATH, parse_dates=["date"])
    usd = usd.rename(columns={"rate_pct": "usd_pct"})
    eur = eur.rename(columns={"rate_pct": "eur_pct"})
    # Build a daily index then ffill
    full = pd.date_range("2019-01-01", "2026-12-31", freq="D")
    out = pd.DataFrame({"date": full})
    out = out.merge(usd[["date", "usd_pct"]], on="date", how="left")
    out = out.merge(eur[["date", "eur_pct"]], on="date", how="left")
    out["usd_pct"] = out["usd_pct"].ffill()
    out["eur_pct"] = out["eur_pct"].ffill()
    out["diff_bps"] = (out["usd_pct"] - out["eur_pct"]) * 100.0
    return out


# ---------- core: vectorised event extraction ----------

def find_window_returns(ts: np.ndarray, close: np.ndarray,
                        weekday: int,
                        entry_hour: int, exit_hour: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """For each calendar date with weekday == `weekday`, find the close at
    entry_hour and exit_hour UTC.

    Returns: (dates_int64, entry_px, exit_px, year) -- only days where both
    bars are present within +/- 30 min of target.

    `ts` must be UTC-naive int64 nanoseconds for fast comparison.
    """
    # ts is datetime64[us, UTC] from pandas; build component arrays + a
    # tz-naive normalised date array (UTC midnights) for joining against
    # the daily rate-diff series.
    ts_dt = pd.to_datetime(ts, utc=True)
    dows = ts_dt.dayofweek.to_numpy()
    hours = ts_dt.hour.to_numpy()
    minutes = ts_dt.minute.to_numpy()
    dates = ts_dt.tz_convert(None).normalize().to_numpy()
    years = ts_dt.year.to_numpy()

    mask_dow = dows == weekday
    if not mask_dow.any():
        return (np.array([], dtype=np.int64), np.array([]), np.array([]), np.array([], dtype=np.int64))

    # For entry/exit, accept any 5-min bar where hour matches and minute==0
    # (the bar that opens at HH:00). This is the M5 "close at HH:05" via the
    # next bar's open ~ close-of-HH:00 bar. Use the bar at HH:00 close.
    entry_mask = mask_dow & (hours == entry_hour) & (minutes == 0)
    exit_mask = mask_dow & (hours == exit_hour) & (minutes == 0)

    entry_idx = np.where(entry_mask)[0]
    exit_idx = np.where(exit_mask)[0]

    if entry_idx.size == 0 or exit_idx.size == 0:
        return (np.array([], dtype="datetime64[ns]"), np.array([]), np.array([]), np.array([], dtype=np.int64))

    entry_dates = dates[entry_idx]
    exit_dates = dates[exit_idx]

    # Inner-join on date
    entry_df = pd.DataFrame({"date": entry_dates, "entry_px": close[entry_idx], "year": years[entry_idx]})
    exit_df = pd.DataFrame({"date": exit_dates, "exit_px": close[exit_idx]})
    merged = entry_df.merge(exit_df, on="date", how="inner")

    return (
        merged["date"].to_numpy(),
        merged["entry_px"].to_numpy(),
        merged["exit_px"].to_numpy(),
        merged["year"].to_numpy(),
    )


def build_trades(df: pd.DataFrame,
                 rate_df: pd.DataFrame,
                 weekday: int = 2,  # 2 = Wednesday
                 entry_hour: int = WED_ENTRY_HOUR_UTC,
                 exit_hour: int = WED_EXIT_HOUR_UTC,
                 direction: str = "short",
                 carry_filter_bps: float = CARRY_FILTER_BPS,
                 cost_bps: float = COST_BPS_DEFAULT,
                 exclude_holiday_weeks: bool = True) -> pd.DataFrame:
    """Return per-trade DataFrame: date, year, regime, entry_px, exit_px,
    gross_bps, net_bps, rate_diff_bps."""
    ts = df["timestamp"].to_numpy()
    close = df["close"].to_numpy()

    dates, entry_px, exit_px, years = find_window_returns(
        ts, close, weekday=weekday,
        entry_hour=entry_hour, exit_hour=exit_hour,
    )
    if dates.size == 0:
        return pd.DataFrame()

    sign = -1.0 if direction == "short" else +1.0
    gross_bps = sign * (exit_px - entry_px) / entry_px * 10000.0
    net_bps = gross_bps - cost_bps

    # Rate-diff lookup: dates are already tz-naive UTC midnights
    date_dt = pd.to_datetime(dates)
    rd = rate_df.set_index("date")["diff_bps"]
    rd_aligned = rd.reindex(date_dt).to_numpy()
    rd_abs = np.abs(rd_aligned)

    trades = pd.DataFrame({
        "date": date_dt,
        "year": years,
        "entry_px": entry_px,
        "exit_px": exit_px,
        "gross_bps": gross_bps,
        "net_bps": net_bps,
        "rate_diff_bps": rd_aligned,
        "rate_diff_abs": rd_abs,
    })
    trades["regime"] = trades["year"].map(label_regime)

    # Carry filter
    if carry_filter_bps > 0:
        trades = trades[trades["rate_diff_abs"] >= carry_filter_bps].copy()

    # Holiday exclusion (drop trade if the trade-date OR same-week is a US holiday)
    if exclude_holiday_weeks:
        hol_dates = pd.to_datetime(sorted(US_HOLIDAY_DATES))
        hol_weeks = set()
        for h in hol_dates:
            for d in range(-2, 3):  # Mon-Fri of holiday week
                hol_weeks.add((h + pd.Timedelta(days=d)).date())
        is_hw = trades["date"].dt.date.isin(hol_weeks)
        trades = trades[~is_hw].copy()

    return trades.reset_index(drop=True)


# ---------- stats ----------

def metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"n": 0, "mean": 0.0, "std": 0.0, "t": 0.0, "sh": 0.0,
                "mdd": 0.0, "wr": 0.0, "pf": 0.0, "total": 0.0, "cagr": 0.0}
    net = trades["net_bps"].to_numpy() / 10000.0  # bps -> fraction
    n = len(net)
    mean_bps = float(net.mean() * 10000)
    std_bps = float(net.std(ddof=1) * 10000) if n > 1 else 0.0
    se = std_bps / np.sqrt(n) if n > 0 else 0.0
    t = mean_bps / se if se > 0 else 0.0
    wr = float((net > 0).mean())
    eq = np.cumprod(1.0 + net)
    total = float(eq[-1] - 1.0)
    rm = np.maximum.accumulate(eq)
    mdd = float(((eq - rm) / rm).min())
    # ~40 Wed/yr after filter -> annualisation factor sqrt(n_per_year)
    if n > 1:
        dates = pd.to_datetime(trades["date"])
        years = max((dates.max() - dates.min()).days / 365.25, 1e-9)
        trades_per_year = n / years
        sh = (mean_bps / std_bps) * np.sqrt(trades_per_year) if std_bps > 0 else 0.0
        cagr = ((1.0 + total) ** (1.0 / years)) - 1.0 if total > -1 else -1.0
    else:
        sh = 0.0
        cagr = 0.0
    wins = net[net > 0]; losses = net[net <= 0]
    gw = float(wins.sum()) if wins.size else 0.0
    gl = float(-losses.sum()) if losses.size else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    return {"n": n, "mean": mean_bps, "std": std_bps, "t": t, "sh": sh,
            "mdd": mdd, "wr": wr, "pf": pf, "total": total, "cagr": cagr}


def section(s: str) -> None:
    print(f'\n{"=" * 92}\n  {s}\n{"=" * 92}\n')


def report(label: str, trades: pd.DataFrame) -> None:
    m = metrics(trades)
    if m["n"] == 0:
        print(f"  [{label}] no trades"); return
    print(f"  [{label}]")
    print(f"    trades    : {m['n']}")
    print(f"    mean_net  : {m['mean']:+.2f} bps  std {m['std']:.2f} bps  t {m['t']:+.2f}")
    print(f"    Sharpe    : {m['sh']:+.2f}  (ann)")
    print(f"    MDD       : {m['mdd']*100:+.2f}%")
    print(f"    CAGR      : {m['cagr']*100:+.2f}%  (total {m['total']*100:+.2f}%)")
    print(f"    WR        : {m['wr']*100:.1f}%   PF {m['pf']:.2f}")


def regime_table(trades: pd.DataFrame) -> None:
    print(f'  {"regime":<6s} {"n":>4s}  {"mean":>9s} {"std":>8s} {"t":>6s}  {"WR":>6s} {"Sh":>7s}')
    for w in ("W1", "W2", "W3"):
        sub = trades[trades["regime"] == w]
        m = metrics(sub)
        if m["n"] < 3:
            print(f"  {w:<6s} {m['n']:>4d}  (sparse)"); continue
        marker = ""
        if w == "W3":
            if m["mean"] > 2.0: marker = "  <<< W3 PASS"
            elif m["mean"] > 0.0: marker = "  <<< W3 MARGINAL"
            else: marker = "  <<< W3 FAIL"
        print(f"  {w:<6s} {m['n']:>4d}  {m['mean']:>+7.2f}bp {m['std']:>6.2f}bp {m['t']:>+5.2f}  {m['wr']*100:>5.1f}% {m['sh']:>+6.2f}{marker}")


def rate_diff_tercile_table(trades: pd.DataFrame) -> None:
    if trades.empty:
        print("  (no trades)"); return
    q33, q66 = np.quantile(trades["rate_diff_abs"], [1/3, 2/3])
    bins = [("LOW", trades[trades["rate_diff_abs"] <= q33]),
            ("MID", trades[(trades["rate_diff_abs"] > q33) & (trades["rate_diff_abs"] <= q66)]),
            ("HIGH", trades[trades["rate_diff_abs"] > q66])]
    print(f"  tercile thresholds (abs rate-diff, bps): q33={q33:.0f}  q66={q66:.0f}")
    print(f'  {"tercile":<7s} {"n":>4s}  {"mean":>9s} {"t":>6s}  {"WR":>6s} {"Sh":>7s}')
    for name, sub in bins:
        m = metrics(sub)
        if m["n"] < 3:
            print(f"  {name:<7s} {m['n']:>4d}  (sparse)"); continue
        print(f"  {name:<7s} {m['n']:>4d}  {m['mean']:>+7.2f}bp {m['t']:>+5.2f}  {m['wr']*100:>5.1f}% {m['sh']:>+6.2f}")


# ---------- walk-forward ----------

def walk_forward(df: pd.DataFrame, rate_df: pd.DataFrame,
                 cost_bps: float = COST_BPS_DEFAULT) -> list[dict]:
    splits = [
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2019-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2026-12-31")),
    ]
    all_trades = build_trades(df, rate_df, direction="short", cost_bps=cost_bps)
    results = []
    for is_start, oos_start, oos_end in splits:
        is_t = all_trades[(all_trades["date"] >= is_start) & (all_trades["date"] < oos_start)]
        oos_t = all_trades[(all_trades["date"] >= oos_start) & (all_trades["date"] < oos_end)]
        is_m = metrics(is_t); oos_m = metrics(oos_t)
        results.append({
            "split": f"IS {is_start.year}->{oos_start.year} / OOS {oos_start.year}-{oos_end.year}",
            "is_n": is_m["n"], "is_sh": is_m["sh"], "is_mean": is_m["mean"],
            "oos_n": oos_m["n"], "oos_sh": oos_m["sh"], "oos_mean": oos_m["mean"],
        })
    return results


# ---------- main ----------

def main() -> None:
    section("CFD WED ROLLOVER UNWIND (EURUSD) -- Phase 2")
    print(f"M5 data:  {EURUSD_M5_PATH}")
    print(f"Entry:    Wed {WED_ENTRY_HOUR_UTC:02d}:00 UTC")
    print(f"Exit:     Wed {WED_EXIT_HOUR_UTC:02d}:00 UTC (no overnight, zero swap)")
    print(f"Cost:     {COST_BPS_DEFAULT} bp RT (Eightcap EURUSD live spread)")
    print(f"Carry filter: |Fed - ECB| > {CARRY_FILTER_BPS:.0f} bp")

    df = load_m5(EURUSD_M5_PATH)
    rate_df = load_rate_diff()
    print(f"\nLoaded {len(df):,} EURUSD M5 bars "
          f"({df['timestamp'].min().date()} -> {df['timestamp'].max().date()})")
    print(f"Loaded rate-diff series: min {rate_df['diff_bps'].min():.0f}bp  "
          f"max {rate_df['diff_bps'].max():.0f}bp  "
          f"last {rate_df['diff_bps'].iloc[-1]:.0f}bp")

    # === Baseline: SHORT primary ===
    section(f"BASELINE -- SHORT EURUSD, Wed {WED_ENTRY_HOUR_UTC:02d}-{WED_EXIT_HOUR_UTC:02d} UTC, carry>100bp, {COST_BPS_DEFAULT}bp RT")
    base = build_trades(df, rate_df, direction="short")
    report("baseline_short", base)
    print()
    regime_table(base)
    print()
    section("Rate-diff tercile breakdown (mechanism should scale with |rate-diff|)")
    rate_diff_tercile_table(base)

    # === Direction null-check ===
    section("DIRECTION NULL-CHECK -- LONG EURUSD, same setup")
    null_long = build_trades(df, rate_df, direction="long")
    report("null_long", null_long)
    m_short = metrics(base); m_long = metrics(null_long)
    null_gap = m_short["mean"] - m_long["mean"]
    print(f"\n  direction null-gap (SHORT - LONG mean) : {null_gap:+.2f} bps per trade")
    if null_gap >= 3.0:
        print(f"  null-gap PASS (>= +3 bps)")
    else:
        print(f"  null-gap FAIL (< +3 bps) -- mechanism lacks directional content")

    # === Placebo: non-Wednesday weekdays ===
    section("PLACEBO -- non-Wednesday weekdays (same 10-20 UTC window, same carry filter)")
    placebo_results = {}
    for dow, name in [(0, "Mon"), (1, "Tue"), (3, "Thu"), (4, "Fri")]:
        plc = build_trades(df, rate_df, weekday=dow, direction="short")
        m = metrics(plc)
        placebo_results[name] = m
        print(f"  {name}  n={m['n']:>4d}  mean {m['mean']:>+6.2f} bps  t {m['t']:>+5.2f}  Sh {m['sh']:>+5.2f}  WR {m['wr']*100:>5.1f}%")
    # Aggregate placebo (all non-Wed days pooled)
    all_placebo = pd.concat([build_trades(df, rate_df, weekday=d, direction="short")
                             for d in (0, 1, 3, 4)], ignore_index=True)
    m_plc = metrics(all_placebo)
    print(f"\n  POOL n={m_plc['n']:>4d}  mean {m_plc['mean']:>+6.2f} bps  t {m_plc['t']:>+5.2f}  Sh {m_plc['sh']:>+5.2f}")
    if m_plc["mean"] < 1.0:
        print(f"  placebo PASS (pool mean < +1 bp -- Wed is distinct)")
    else:
        print(f"  placebo FAIL (pool mean >= +1 bp -- edge not Wednesday-specific)")

    # === Goodhart diagnostic: edge migration to Tuesday-evening ===
    section("GOODHART DIAGNOSTIC -- has the unwind migrated upstream?")
    print("  Testing: SHORT EURUSD on Tuesday late session (entry 18:00 Tue UTC, exit 02:00 Wed UTC)")
    print("  If retail front-runs the Wed unwind, signal shifts to Tue evening.")
    # Tue 18-22 UTC (within same broker-server-day, no swap) as a proxy
    tue_evening = build_trades(df, rate_df, weekday=1, entry_hour=18, exit_hour=22, direction="short")
    report("tue_evening_short", tue_evening)
    m_tue = metrics(tue_evening)
    if m_tue["mean"] > m_short["mean"]:
        print(f"\n  WARNING: Tuesday-evening edge ({m_tue['mean']:+.2f}bp) exceeds Wed 10-20 ({m_short['mean']:+.2f}bp).")
        print("  Mechanism may have migrated upstream (front-running).")
    else:
        print(f"\n  Wed 10-20 ({m_short['mean']:+.2f}bp) > Tue 18-22 ({m_tue['mean']:+.2f}bp). No migration detected.")

    # === Carry-filter sweep ===
    section("CARRY-FILTER SWEEP (SHORT, Wed 10-20 UTC)")
    print(f"  {'filter(bp)':>10s} {'n':>4s} {'mean':>9s} {'t':>6s} {'Sh':>7s}")
    for f in CARRY_SWEEP_BPS:
        t = build_trades(df, rate_df, direction="short", carry_filter_bps=f)
        m = metrics(t)
        print(f"  {f:>10.0f} {m['n']:>4d} {m['mean']:>+7.2f}bp {m['t']:>+5.2f} {m['sh']:>+6.2f}")

    # === Window timing sweep ===
    section("WINDOW TIMING SWEEP (SHORT, carry>100bp)")
    print(f"  {'entry-exit (UTC)':<16s} {'n':>4s} {'mean':>9s} {'t':>6s} {'Sh':>7s}")
    for eh, xh in WINDOW_SWEEP:
        t = build_trades(df, rate_df, entry_hour=eh, exit_hour=xh, direction="short")
        m = metrics(t)
        label = f"{eh:02d}-{xh:02d}"
        print(f"  {label:<16s} {m['n']:>4d} {m['mean']:>+7.2f}bp {m['t']:>+5.2f} {m['sh']:>+6.2f}")

    # === Cost sensitivity ===
    section("COST SENSITIVITY (SHORT, baseline window/filter)")
    print(f"  {'cost(bp)':>8s} {'n':>4s} {'mean':>9s} {'Sh':>7s}")
    for c in COST_SWEEP_BPS:
        t = build_trades(df, rate_df, direction="short", cost_bps=c)
        m = metrics(t)
        print(f"  {c:>8.2f} {m['n']:>4d} {m['mean']:>+7.2f}bp {m['sh']:>+6.2f}")

    # === Walk-forward ===
    section("WALK-FORWARD (3 IS/OOS splits, SHORT)")
    wf = walk_forward(df, rate_df)
    print(f"  {'split':<42s} {'IS n':>5s} {'IS Sh':>7s} {'IS mean':>9s}   {'OOS n':>5s} {'OOS Sh':>7s} {'OOS mean':>9s}")
    for r in wf:
        print(f"  {r['split']:<42s} {r['is_n']:>5d} {r['is_sh']:>+7.2f} {r['is_mean']:>+7.2f}bp   {r['oos_n']:>5d} {r['oos_sh']:>+7.2f} {r['oos_mean']:>+7.2f}bp")
    wf_oos = [r["oos_sh"] for r in wf if r["oos_n"] >= 3]
    wf_mean = float(np.mean(wf_oos)) if wf_oos else 0.0
    wf_min = float(np.min(wf_oos)) if wf_oos else 0.0
    print(f"\n  walk-forward OOS Sh: mean {wf_mean:+.2f}  min {wf_min:+.2f}")
    print(f"  WF mean >= +0.20:    {'PASS' if wf_mean >= 0.20 else 'FAIL'}")
    print(f"  WF min  >= -0.10:    {'PASS' if wf_min  >= -0.10 else 'FAIL'}")

    # === Kill-criteria summary ===
    section("KILL-CRITERIA CHECK (pre-committed)")
    w3 = base[base["regime"] == "W3"]
    m_w3 = metrics(w3)
    cost_stress = build_trades(df, rate_df, direction="short", cost_bps=2.0)
    m_cs = metrics(cost_stress)

    checks = {
        "1. full-sample mean > +2 bps       ": m_short["mean"] > 2.0,
        "2. W3 mean > +0 bps                ": m_w3["mean"] > 0.0,
        "3. null-gap (S-L) >= +3 bps        ": null_gap >= 3.0,
        "4. placebo pool mean < +1 bps      ": m_plc["mean"] < 1.0,
        "5. trade count >= 100              ": m_short["n"] >= 100,
        "6. Sharpe > +0.30                  ": m_short["sh"] > 0.30,
        "7. MDD < 15%                       ": abs(m_short["mdd"]) < 0.15,
        "8a. WF OOS mean Sh >= +0.20        ": wf_mean >= 0.20,
        "8b. WF OOS min Sh >= -0.10         ": wf_min >= -0.10,
        "9. cost-stress @2bp mean > 0       ": m_cs["mean"] > 0.0,
    }
    for k, v in checks.items():
        print(f"  {k} : {'PASS' if v else 'FAIL'}")

    n_pass = sum(checks.values()); n_total = len(checks)
    section("FINAL VERDICT")
    print(f"  {n_pass}/{n_total} kill criteria passed")
    if n_pass == n_total:
        print("  PASS -- Wed-CFD-rollover edge validated on EURUSD; "
              "proceed to Phase 3 cross-pair (GBPUSD/USDJPY/AUDUSD)")
    elif n_pass >= 7 and m_short["mean"] > 1.0 and null_gap > 0:
        print("  MARGINAL -- mechanism present but failed >=1 pre-commit; "
              "do NOT deploy without strengthening the case")
    else:
        print("  REJECT -- tombstone; mechanism does not survive pre-commits")
    print()


if __name__ == "__main__":
    main()
