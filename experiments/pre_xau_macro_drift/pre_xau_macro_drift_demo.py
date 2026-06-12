#!/usr/bin/env python3
"""pre_xau_macro_drift Phase 2 simulator + validation pipeline.

Cross-asset extension of the NDX `event_calendar` book onto XAUUSD.
Iterates over the four research-validated NDX events (FOMC, CPI, RS, NFP),
runs both directions per lesson #54, applies mechanism-aware kill criteria
per lesson #55, and reports a per-event verdict.

Calendars are re-used from the per-event experiments:
  - FOMC : experiments/macro_drift/fomc_calendar.csv
  - CPI  : experiments/pre_cpi_drift/cpi_calendar.csv
  - RS   : experiments/pre_retail_sales_drift/retail_sales_calendar.csv
  - NFP  : experiments/pre_nfp_drift/nfp_calendar.csv

Data: XAUUSD M5 from datalake (2018-01-02 -> 2026-04-30 coverage). First
run fetches and caches to ohlc_data/XAUUSD_M5.csv via utils.fetch_ohlc.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT / "experiments" / "macro_drift"))
from _profile_fomc_drift import et_to_utc  # type: ignore

import os
import requests
from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

DATALAKE_URL = os.getenv("DATALAKE_URL", "").rstrip("/")
DATALAKE_API_KEY = os.getenv("DATALAKE_API_KEY", "")
LOCAL_CACHE_DIR = _ROOT / "ohlc_data"


def fetch_ohlc(instrument: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch from datalake with local CSV cache (sibling utils is localhost-only)."""
    cache_path = LOCAL_CACHE_DIR / f"{instrument}_{timeframe}.csv"
    if cache_path.exists():
        df = pd.read_csv(cache_path, parse_dates=["timestamp"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        # only use cache if it spans the requested range (otherwise refetch)
        start_ts = pd.to_datetime(start_date).tz_localize("UTC")
        end_ts = pd.to_datetime(end_date).tz_localize("UTC")
        if df["timestamp"].min() <= start_ts and df["timestamp"].max() >= end_ts - pd.Timedelta(days=2):
            print(f"  [cache] loaded {len(df):,} rows from {cache_path}")
            return df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)].reset_index(drop=True)

    # paginated fetch from production datalake
    rows: list[dict] = []
    headers = {"X-API-Key": DATALAKE_API_KEY}
    print(f"  [datalake] fetching {instrument} {timeframe} {start_date} -> {end_date} (year-chunked) ...")
    start_year = pd.to_datetime(start_date).year
    end_year = pd.to_datetime(end_date).year
    for yr in range(start_year, end_year + 1):
        ys = max(pd.to_datetime(f"{yr}-01-01"), pd.to_datetime(start_date))
        ye = min(pd.to_datetime(f"{yr}-12-31"), pd.to_datetime(end_date))
        params = {"instrument": instrument, "timeframe": timeframe,
                  "start": ys.strftime("%Y-%m-%dT00:00:00"),
                  "end":   ye.strftime("%Y-%m-%dT23:59:59"),
                  "limit": 10000}
        year_rows = 0
        while True:
            r = requests.get(f"{DATALAKE_URL}/query", params=params, headers=headers, timeout=120)
            r.raise_for_status()
            body = r.json()
            page_rows = body.get("data", []) if isinstance(body, dict) else body
            if not page_rows: break
            rows.extend(page_rows)
            year_rows += len(page_rows)
            pagination = body.get("pagination", {}) if isinstance(body, dict) else {}
            if pagination.get("has_more") and pagination.get("next_cursor"):
                params["cursor"] = pagination["next_cursor"]
            else:
                break
        print(f"    {yr}: {year_rows:,} rows (cum {len(rows):,})")
    if not rows:
        raise RuntimeError(f"datalake returned 0 rows for {instrument} {timeframe}")
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    print(f"  [datalake] saved {len(df):,} rows to {cache_path}")
    return df

# ---------- config ----------

INSTRUMENT = "XAUUSD"
TIMEFRAME = "M5"
DATA_START = "2018-01-02"
DATA_END = "2026-04-30"

# XAUUSD typical RT cost: 0.20-0.40 USD spread on ~2,400 = ~0.85-1.7 bps.
# 2bp pessimistic-realistic default; sweep [0,1,2,5,10].
COST_BPS_DEFAULT = 2.0
WINDOW_HOURS = 24
EXIT_BUFFER_MIN = 30
COST_SWEEP_BPS = (0, 1, 2, 5, 10)
WINDOW_HOURS_SWEEP = (6, 12, 18, 24, 48)

EVENTS = [
    {
        "name": "FOMC",
        "cal": _ROOT / "experiments" / "macro_drift" / "fomc_calendar.csv",
        "events_per_year": 8,
        "ndx_dir": "LONG",
    },
    {
        "name": "CPI",
        "cal": _ROOT / "experiments" / "pre_cpi_drift" / "cpi_calendar.csv",
        "events_per_year": 12,
        "ndx_dir": "LONG",
    },
    {
        "name": "RS",
        "cal": _ROOT / "experiments" / "pre_retail_sales_drift" / "retail_sales_calendar.csv",
        "events_per_year": 12,
        "ndx_dir": "LONG",
    },
    {
        "name": "NFP",
        "cal": _ROOT / "experiments" / "pre_nfp_drift" / "nfp_calendar.csv",
        "events_per_year": 12,
        "ndx_dir": "SHORT",
    },
]


def label_regime(year: int) -> str:
    if year <= 2019: return "W1"
    if year <= 2021: return "W2"
    if year <= 2023: return "W3"
    return "W4"


# ---------- data loading ----------

def load_calendar(cal_path: Path) -> pd.DataFrame:
    df = pd.read_csv(cal_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["is_historical"] == "yes"].copy()
    rows = []
    for _, r in df.iterrows():
        h, m = map(int, r["announce_time_et"].split(":"))
        et_dt = r["date"] + pd.Timedelta(hours=h, minutes=m)
        utc_dt = et_to_utc(et_dt)
        rows.append({"date": r["date"], "year": r["date"].year,
                      "regime": label_regime(r["date"].year),
                      "announce_utc": utc_dt})
    return pd.DataFrame(rows)


def closest_bar_close(ts_arr: np.ndarray, close_arr: np.ndarray,
                       target_utc: pd.Timestamp, tolerance_min: int = 5) -> float | None:
    """Numpy-fast nearest-bar lookup; tolerance_min seconds caps mismatch."""
    target_ns = np.int64(target_utc.value)
    idx = int(np.searchsorted(ts_arr, target_ns))
    if idx == 0:
        nearest = 0
    elif idx >= len(ts_arr):
        nearest = len(ts_arr) - 1
    else:
        # pick closer of [idx-1, idx]
        if (ts_arr[idx] - target_ns) < (target_ns - ts_arr[idx - 1]):
            nearest = idx
        else:
            nearest = idx - 1
    delta_min = abs(int(ts_arr[nearest]) - target_ns) / 1e9 / 60.0
    if delta_min > tolerance_min:
        return None
    return float(close_arr[nearest])


# ---------- core ----------

def compute_event_returns(ts_arr: np.ndarray, close_arr: np.ndarray, cal: pd.DataFrame,
                           window_hours: int = WINDOW_HOURS,
                           exit_buffer_min: int = EXIT_BUFFER_MIN,
                           cost_bps: float = COST_BPS_DEFAULT,
                           direction: str = "long") -> pd.DataFrame:
    sign = +1.0 if direction == "long" else -1.0
    rows = []
    for _, ev in cal.iterrows():
        announce = ev["announce_utc"]
        entry_t = announce - pd.Timedelta(hours=window_hours)
        exit_t  = announce - pd.Timedelta(minutes=exit_buffer_min)
        entry_px = closest_bar_close(ts_arr, close_arr, entry_t)
        exit_px  = closest_bar_close(ts_arr, close_arr, exit_t)
        if entry_px is None or exit_px is None:
            continue
        gross = sign * (exit_px - entry_px) / entry_px * 100.0
        net = gross - cost_bps / 100.0
        rows.append({"date": ev["date"], "year": ev["year"], "regime": ev["regime"],
                      "entry_px": entry_px, "exit_px": exit_px,
                      "gross_pct": gross, "net_pct": net})
    return pd.DataFrame(rows)


# ---------- stats ----------

def event_metrics(trades: pd.DataFrame, events_per_year: int = 12) -> dict:
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
    sh_annual = sh_per_trade * np.sqrt(events_per_year)
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


def report(label: str, trades: pd.DataFrame, evpy: int) -> dict:
    m = event_metrics(trades, evpy)
    if m["n"] == 0:
        print(f"  [{label}] no trades"); return m
    print(f"  [{label}]  n={m['n']}  mean {m['mean']:+.3f}%  Sh {m['sh']:+.2f}  "
          f"MDD {m['mdd']*100:+.2f}%  WR {m['wr']*100:.1f}%  PF {m['pf']:.2f}  t {m['t']:+.2f}")
    return m


def regime_table(trades: pd.DataFrame, evpy: int) -> dict:
    out = {}
    print(f'  {"regime":<8s} {"n":>4s}  {"mean":>9s} {"std":>7s} {"t":>6s}  {"WR":>6s} {"Sh":>7s}')
    for w in ("W1", "W2", "W3", "W4"):
        sub = trades[trades["regime"] == w]
        m = event_metrics(sub, evpy)
        out[w] = m
        if m["n"] < 3:
            print(f"  {w:<8s} {m['n']:>4d}  (sparse)"); continue
        marker = "  <<< W4" if w == "W4" else ""
        print(f"  {w:<8s} {m['n']:>4d}  {m['mean']:>+8.3f}% {m['std']:>6.3f}% {m['t']:>+5.2f}  "
              f"{m['wr']*100:>5.1f}% {m['sh']:>+6.2f}{marker}")
    return out


# ---------- placebo ----------

def placebo_check(ts_arr: np.ndarray, close_arr: np.ndarray, cal: pd.DataFrame,
                   direction: str, evpy: int, cost_bps: float = COST_BPS_DEFAULT,
                   seed: int = 42) -> dict:
    event_dates = set(cal["date"].dt.date)
    et_hour, et_min = 8, 30
    if not event_dates:
        return {"mean": 0.0, "t": 0.0, "n": 0, "sh": 0.0, "wr": 0.0}
    # weekday-match the placebo population to the event weekday distribution
    event_weekdays = [d.weekday() for d in event_dates]
    wd_counts = pd.Series(event_weekdays).value_counts()
    pool_by_wd: dict[int, list] = {wd: [] for wd in wd_counts.index}
    start_ts = pd.Timestamp(ts_arr[0], tz="UTC").date()
    end_ts = pd.Timestamp(ts_arr[-1], tz="UTC").date()
    d = start_ts
    while d <= end_ts:
        if d.weekday() in pool_by_wd and d not in event_dates:
            pool_by_wd[d.weekday()].append(d)
        d = d + pd.Timedelta(days=1).to_pytimedelta()
    rng = np.random.default_rng(seed)
    sample = []
    for wd, n_wd in wd_counts.items():
        pool = pool_by_wd[wd]
        if not pool: continue
        idx = rng.choice(len(pool), size=min(n_wd, len(pool)), replace=False)
        sample.extend([pool[i] for i in idx])
    sample = sorted(sample)
    fake_rows = []
    for d in sample:
        et_dt = pd.Timestamp(d) + pd.Timedelta(hours=et_hour, minutes=et_min)
        utc_dt = et_to_utc(et_dt)
        fake_rows.append({"date": pd.Timestamp(d), "year": d.year,
                           "regime": label_regime(d.year), "announce_utc": utc_dt})
    fake_cal = pd.DataFrame(fake_rows)
    trades = compute_event_returns(ts_arr, close_arr, fake_cal, cost_bps=cost_bps, direction=direction)
    return event_metrics(trades, evpy)


# ---------- walk-forward ----------

def walk_forward(ts_arr: np.ndarray, close_arr: np.ndarray, cal: pd.DataFrame,
                  direction: str, evpy: int, cost_bps: float = COST_BPS_DEFAULT) -> list[dict]:
    splits = [
        (pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2018-01-01"), pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
        (pd.Timestamp("2018-01-01"), pd.Timestamp("2024-01-01"), pd.Timestamp("2026-12-31")),
    ]
    out = []
    for is_start, oos_start, oos_end in splits:
        is_cal  = cal[(cal["date"] >= is_start) & (cal["date"] < oos_start)]
        oos_cal = cal[(cal["date"] >= oos_start) & (cal["date"] < oos_end)]
        is_t  = compute_event_returns(ts_arr, close_arr, is_cal,  cost_bps=cost_bps, direction=direction)
        oos_t = compute_event_returns(ts_arr, close_arr, oos_cal, cost_bps=cost_bps, direction=direction)
        is_m, oos_m = event_metrics(is_t, evpy), event_metrics(oos_t, evpy)
        out.append({
            "split": f"IS->{oos_start.year} / OOS {oos_start.year}-{oos_end.year}",
            "is_n": is_m["n"], "is_sh": is_m["sh"], "is_mean": is_m["mean"],
            "oos_n": oos_m["n"], "oos_sh": oos_m["sh"], "oos_mean": oos_m["mean"],
        })
    return out


# ---------- per-event runner ----------

def run_event(event: dict, ts_arr: np.ndarray, close_arr: np.ndarray) -> dict:
    name = event["name"]
    evpy = event["events_per_year"]
    ndx_dir = event["ndx_dir"]
    section(f"EVENT {name} on XAUUSD  (NDX direction = {ndx_dir})")
    cal = load_calendar(event["cal"])
    print(f"  Calendar: {event['cal'].relative_to(_ROOT)}  ({len(cal)} historical events)")

    # Both directions
    base_long  = compute_event_returns(ts_arr, close_arr, cal, direction="long")
    base_short = compute_event_returns(ts_arr, close_arr, cal, direction="short")
    print()
    m_long  = report("LONG ", base_long,  evpy)
    m_short = report("SHORT", base_short, evpy)
    gap = m_long["mean"] - m_short["mean"]
    best_dir = "long" if m_long["mean"] > m_short["mean"] else "short"
    best_m = m_long if best_dir == "long" else m_short
    best_trades = base_long if best_dir == "long" else base_short
    print(f"\n  Null-gap LONG-SHORT: {gap:+.3f}%   Best dir: {best_dir.upper()}   "
          f"Matches NDX dir? {'YES' if best_dir.upper() == ndx_dir else 'NO'}")

    print("\n  Regime breakdown (best direction):")
    regimes = regime_table(best_trades, evpy)

    # Placebo on best direction
    placebo = placebo_check(ts_arr, close_arr, cal, best_dir, evpy)
    placebo_opp = placebo_check(ts_arr, close_arr, cal, "short" if best_dir == "long" else "long", evpy)
    print(f"\n  Placebo non-event weekdays ({best_dir.upper()}): n={placebo['n']}  "
          f"mean {placebo['mean']:+.3f}%  t {placebo['t']:+.2f}  Sh {placebo['sh']:+.2f}")
    print(f"  Placebo non-event weekdays ({'SHORT' if best_dir == 'long' else 'LONG'}): "
          f"n={placebo_opp['n']}  mean {placebo_opp['mean']:+.3f}%  t {placebo_opp['t']:+.2f}  Sh {placebo_opp['sh']:+.2f}")
    placebo_gap = placebo["mean"] - placebo_opp["mean"]
    print(f"  Placebo null-gap: {placebo_gap:+.3f}%  (if comparable to event null-gap, the lift is structural-drift not event-specific)")

    # Walk-forward
    wf = walk_forward(ts_arr, close_arr, cal, best_dir, evpy)
    print(f"\n  Walk-forward ({best_dir.upper()}):")
    print(f"  {'split':<32s} {'IS n':>5s} {'IS Sh':>7s} {'IS mean':>9s}   {'OOS n':>5s} {'OOS Sh':>7s} {'OOS mean':>9s}")
    for r in wf:
        print(f"  {r['split']:<32s} {r['is_n']:>5d} {r['is_sh']:>+7.2f} {r['is_mean']:>+8.3f}%   "
              f"{r['oos_n']:>5d} {r['oos_sh']:>+7.2f} {r['oos_mean']:>+8.3f}%")
    wf_oos = [r["oos_sh"] for r in wf if r["oos_n"] >= 3]
    wf_mean = float(np.mean(wf_oos)) if wf_oos else float("nan")
    wf_min  = float(np.min(wf_oos))  if wf_oos else float("nan")

    # Cost sensitivity
    print(f"\n  Cost sensitivity ({best_dir.upper()}):")
    print(f"  {'cost(bp)':>8s} {'n':>4s} {'mean':>9s} {'Sh':>7s}")
    for c in COST_SWEEP_BPS:
        t = compute_event_returns(ts_arr, close_arr, cal, cost_bps=c, direction=best_dir)
        m = event_metrics(t, evpy)
        print(f"  {c:>8d} {m['n']:>4d} {m['mean']:>+8.3f}% {m['sh']:>+7.2f}")

    # Window sweep (just window_hours, exit buffer fixed at 30)
    print(f"\n  Window sweep ({best_dir.upper()}, exit buffer = 30min):")
    print(f"  {'window_h':>8s} {'n':>4s} {'mean':>9s} {'Sh':>7s}")
    for wh in WINDOW_HOURS_SWEEP:
        t = compute_event_returns(ts_arr, close_arr, cal, window_hours=wh, direction=best_dir)
        m = event_metrics(t, evpy)
        print(f"  {wh:>8d} {m['n']:>4d} {m['mean']:>+8.3f}% {m['sh']:>+7.2f}")

    # Pre-commit kill check
    w4 = regimes.get("W4", {"mean": 0.0})
    checks = {
        "mean > +0.10%        ": best_m["mean"] > 0.10,
        "W4_mean > +0.05%     ": w4.get("mean", 0) > 0.05,
        "PF   > 1.3           ": best_m["pf"] > 1.3,
        "Sh   > +0.30         ": best_m["sh"] > 0.30,
        "MDD  < 25%           ": abs(best_m["mdd"]) < 0.25,
        "events >= 50         ": best_m["n"] >= 50,
        "null-gap >= +0.30    ": abs(gap) >= 0.30,
        "WF OOS mean >= +0.30 ": wf_mean >= 0.30,
        "WF OOS min  >= 0     ": wf_min >= 0.0,
        "placebo benign       ": abs(placebo["mean"]) < 0.05 or abs(placebo["t"]) < 1.5,
    }
    print(f"\n  Pre-commit kill check ({best_dir.upper()}):")
    n_pass = 0
    for c, ok in checks.items():
        print(f"    {c} : {'PASS' if ok else 'FAIL'}")
        n_pass += int(ok)
    verdict = "PASS" if n_pass == len(checks) else (
        "MARGINAL" if n_pass >= len(checks) - 2 and best_m["mean"] > 0.05 else "REJECT")
    print(f"\n  ==> {name} on XAUUSD ({best_dir.upper()}): {verdict}  ({n_pass}/{len(checks)} kill criteria pass)")

    return {
        "name": name, "best_dir": best_dir, "ndx_dir": ndx_dir,
        "matches_ndx": best_dir.upper() == ndx_dir,
        "mean": best_m["mean"], "sh": best_m["sh"], "mdd": best_m["mdd"],
        "wr": best_m["wr"], "pf": best_m["pf"], "n": best_m["n"], "t": best_m["t"],
        "w4_mean": w4.get("mean", 0.0), "w4_sh": w4.get("sh", 0.0),
        "wf_mean_oos_sh": wf_mean, "wf_min_oos_sh": wf_min,
        "placebo_mean": placebo["mean"], "placebo_t": placebo["t"],
        "null_gap": gap, "verdict": verdict, "n_pass": n_pass, "n_total": len(checks),
    }


# ---------- main ----------

def main() -> None:
    section("PRE-XAU MACRO-DRIFT BOOK -- Phase 2  (4 events, direction TBD per #54, mech-aware KCs per #55)")
    print(f"Instrument: {INSTRUMENT}  Timeframe: {TIMEFRAME}")
    print(f"Data range: {DATA_START} -> {DATA_END}")
    print(f"Cost default: {COST_BPS_DEFAULT} bp RT.  Window: {WINDOW_HOURS}h entry / {EXIT_BUFFER_MIN}min exit buffer.")

    print("\nFetching XAUUSD M5 from datalake (cached locally on first run)...")
    df = fetch_ohlc(INSTRUMENT, TIMEFRAME, DATA_START, DATA_END)
    df = df.sort_values("timestamp").reset_index(drop=True)
    print(f"  Loaded {len(df):,} bars  ({df['timestamp'].min()} -> {df['timestamp'].max()})")
    # Force nanosecond precision so pd.Timestamp.value (always ns) comparisons line up
    ts_arr = df["timestamp"].values.astype("datetime64[ns]").astype("int64")
    close_arr = df["close"].to_numpy(dtype=np.float64)

    results = []
    for event in EVENTS:
        try:
            r = run_event(event, ts_arr, close_arr)
            results.append(r)
        except Exception as e:
            print(f"\n  ERROR running {event['name']}: {e}")
            import traceback; traceback.print_exc()

    section("BOOK SUMMARY -- XAUUSD")
    print(f"  {'Event':<6s} {'NDX dir':>8s} {'XAU dir':>8s} {'match':>6s} "
          f"{'n':>4s} {'mean':>8s} {'Sh':>7s} {'W4 Sh':>7s} {'WF mean':>8s} "
          f"{'placebo_t':>10s} {'verdict':>10s}")
    for r in results:
        print(f"  {r['name']:<6s} {r['ndx_dir']:>8s} {r['best_dir'].upper():>8s} "
              f"{('YES' if r['matches_ndx'] else 'NO'):>6s} "
              f"{r['n']:>4d} {r['mean']:>+7.3f}% {r['sh']:>+6.2f} {r['w4_sh']:>+6.2f} "
              f"{r['wf_mean_oos_sh']:>+7.2f} {r['placebo_t']:>+9.2f} {r['verdict']:>10s}")

    # Cross-event aggregate
    passing = [r for r in results if r["verdict"] == "PASS"]
    marginal = [r for r in results if r["verdict"] == "MARGINAL"]
    rejected = [r for r in results if r["verdict"] == "REJECT"]
    match_count = sum(1 for r in results if r["matches_ndx"])
    print(f"\n  Verdict tally: {len(passing)} PASS, {len(marginal)} MARGINAL, {len(rejected)} REJECT")
    print(f"  Direction agreement with NDX: {match_count}/{len(results)} events")
    if passing:
        print(f"  Deploy candidates (XAU direction): " + ", ".join(f"{r['name']}-{r['best_dir'].upper()}" for r in passing))
    print()


if __name__ == "__main__":
    main()
