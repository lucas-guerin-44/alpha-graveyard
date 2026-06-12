#!/usr/bin/env python3
"""XAUUSD M15 — Break of Structure + Retest, ATR-floor filtered (NY-AM session).

Thesis: experiments/xau_break_retest_m15/xau_break_retest_m15.md

Follow-up to the M5 REJECT (experiments/xau_break_retest/xau_break_retest.md).
Tests M15 + ATR floor in BOTH directions (continuation AND fade) side-by-side.

Rules:
  Session window     = 13:00 -> 15:00 UTC (NY cash open + first 2h).
  Entry cutoff       = 15:00 UTC.
  For each in-session M15 bar b:
    Skip if ATR(14)[b-1] < ATR_FLOOR_USD (volatility regime gate).
    Skip if ADX_THRESH set and ADX(14)[b-1] < ADX_THRESH.
    swing_high = max(high[b-LOOKBACK : b]); swing_low = min(low[...])
    If flat and bar closes > swing_high AND no UP break today: arm UP break.
    If flat and bar closes < swing_low  AND no DOWN break today: arm DOWN break.
  Within RETEST_WINDOW bars of break:
    UP retest: bar low touches near level AND close stays above swing_high.
      direction = +1 (continuation) or -1 (fade).
      ENTER at close; stop = swing_high - direction * STOP_ATR_MULT * ATR_at_break.
    DOWN retest: symmetric.
  Exit: stop / time-exit (90 min = 6 M15 bars) / session-end (15:00 UTC).
  Max 1 round-trip per direction per day.

Bidirectional: every variant is run BOTH as continuation and as fade, reported
side-by-side. Fade-gap is computed per filter combo. M5 thesis used fade as a
null check; here it's a primary candidate too (per M5 mechanistic interpretation).

Run:
  venv\\Scripts\\python.exe experiments\\xau_break_retest_m15\\xau_break_retest_m15_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
# experiments/_live/xau_break_retest_m15/ -> repo root is 3 dirs up
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, "..", "backtesting-engine-2.0")))

DATA_PATH = os.path.join(_ROOT, "ohlc_data", "XAUUSD_M5.csv")

# ---------------------------------------------------------------------------
# Config (6-7 free parameters max — see thesis §"Signal math")
# ---------------------------------------------------------------------------

SWING_LOOKBACK_BARS = 16          # M15 bars = 4 hours
RETEST_WINDOW_BARS = 3            # M15 bars = 45 min
RETEST_TOL_ATR = 0.30
STOP_ATR_MULT = 1.20
SESSION_START_UTC = 13
SESSION_END_UTC = 15              # tighter than M5 (16)
ENTRY_CUTOFF_UTC = 15

ATR_PERIOD = 14
ADX_PERIOD = 14
TIME_EXIT_MIN = 90                # 6 M15 bars
TIME_EXIT_BARS = TIME_EXIT_MIN // 15

# Cost (XAU points per round-trip).
COST_POINTS_DEFAULT = 0.20
COST_POINTS_SWEEP = (0.1, 0.2, 0.4, 0.8)

# Pre-committed kill criteria
KC_SHARPE_FULL = 0.30
KC_SHARPE_REGIME = 0.30           # both W1 and W2 must clear this
KC_SHARPE_HOLDOUT = 0.0
KC_MDD = 0.25
KC_TRADES_MIN = 100               # below this = INSUFFICIENT_N
KC_WR = 0.35
KC_PF = 1.10
KC_FADE_GAP = 0.30
KC_COST_STRESS_PT = 0.4
KC_DEFLATED_SH = 0.20
N_VARIANTS_PRECOMMITTED = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 92}\n  {t}\n{'=' * 92}\n")


def label_regime(year: int) -> str:
    if year <= 2020:
        return "W1 2019-2020"
    if year <= 2022:
        return "W2 2021-2022"
    return "W3 2023-2026 (holdout)"


def annualized_sharpe(r: np.ndarray, trades_per_year: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(trades_per_year))


def max_drawdown(eq: np.ndarray) -> float:
    if len(eq) == 0:
        return 0.0
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min())


def deflated_sharpe(observed_sh: float, returns: np.ndarray, n_trials: int) -> float:
    r = returns[np.isfinite(returns)]
    n = r.size
    if n < 30 or n_trials < 2:
        return observed_sh
    from math import sqrt, log
    g3 = float(pd.Series(r).skew())
    g4 = float(pd.Series(r).kurt())
    sr_std = sqrt(max((1 - g3 * observed_sh + (g4 / 4.0) * observed_sh ** 2) / max(n - 1, 1), 1e-9))
    e_max = sr_std * sqrt(2 * log(max(n_trials, 2)))
    return float(observed_sh - e_max)


# ---------------------------------------------------------------------------
# Data load + M15 resample
# ---------------------------------------------------------------------------

def load_m15() -> pd.DataFrame:
    """Load M5 CSV, restrict to true-M5 era, resample to M15."""
    df = pd.read_csv(DATA_PATH, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df = df[~df["timestamp"].duplicated(keep="first")].reset_index(drop=True)
    # Restrict to era where data is true-M5 (early file has H1-stride backfill).
    # By inspection, true-M5 starts mid-2018.
    df = df[df["timestamp"] >= pd.Timestamp("2018-08-01", tz="UTC")].reset_index(drop=True)

    # Resample to M15 OHLC. Index on timestamp, then resample.
    df = df.set_index("timestamp")
    m15 = df.resample("15min", label="left", closed="left").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
    })
    m15 = m15.dropna(how="any").reset_index()
    m15["hour"] = m15["timestamp"].dt.hour
    m15["minute"] = m15["timestamp"].dt.minute
    m15["date"] = m15["timestamp"].dt.date
    m15["dow"] = m15["timestamp"].dt.dayofweek
    return m15


# ---------------------------------------------------------------------------
# Indicators (numpy)
# ---------------------------------------------------------------------------

def compute_atr_adx(h: np.ndarray, l: np.ndarray, c: np.ndarray, period: int = 14
                    ) -> tuple[np.ndarray, np.ndarray]:
    """Wilder-style ATR + ADX. Both shifted naturally via the rolling window —
    callers should still read atr[g-1] to avoid lookahead.
    """
    n = len(h)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = h[0] - l[0]
    prev_c = c[:-1]
    cur_h = h[1:]
    cur_l = l[1:]
    tr[1:] = np.maximum.reduce([cur_h - cur_l, np.abs(cur_h - prev_c), np.abs(cur_l - prev_c)])

    # Wilder smoothing approximated by SMA (matches the M5 demo's approach).
    atr = pd.Series(tr).rolling(period, min_periods=period).mean().to_numpy()

    # +DM / -DM
    up_move = np.zeros(n, dtype=np.float64)
    dn_move = np.zeros(n, dtype=np.float64)
    up_move[1:] = h[1:] - h[:-1]
    dn_move[1:] = l[:-1] - l[1:]
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)

    plus_dm_s = pd.Series(plus_dm).rolling(period, min_periods=period).mean().to_numpy()
    minus_dm_s = pd.Series(minus_dm).rolling(period, min_periods=period).mean().to_numpy()
    # Guard div-by-zero
    safe_atr = np.where((atr > 0) & np.isfinite(atr), atr, np.nan)
    plus_di = 100.0 * plus_dm_s / safe_atr
    minus_di = 100.0 * minus_dm_s / safe_atr
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) > 0,
                                                       plus_di + minus_di, np.nan)
    adx = pd.Series(dx).rolling(period, min_periods=period).mean().to_numpy()
    return atr, adx


# ---------------------------------------------------------------------------
# Simulator (numpy inner loop)
# ---------------------------------------------------------------------------

def simulate_break_retest_m15(
    df: pd.DataFrame,
    direction: str = "continuation",   # 'continuation' | 'fade'
    swing_lookback: int = SWING_LOOKBACK_BARS,
    retest_window: int = RETEST_WINDOW_BARS,
    retest_tol_atr: float = RETEST_TOL_ATR,
    stop_atr_mult: float = STOP_ATR_MULT,
    session_start_utc: int = SESSION_START_UTC,
    session_end_utc: int = SESSION_END_UTC,
    entry_cutoff_utc: int = ENTRY_CUTOFF_UTC,
    time_exit_bars: int = TIME_EXIT_BARS,
    cost_points: float = COST_POINTS_DEFAULT,
    atr_floor_usd: float = 0.0,
    adx_thresh: float = 0.0,
) -> tuple[np.ndarray, list[dict]]:
    """Run the BoS+retest simulator on M15 XAU.

    direction: 'continuation' enters with the break; 'fade' enters against it.
    atr_floor_usd, adx_thresh: regime gates (0 = disabled).

    Returns (per-trade net return array, trade-list).
    """
    fade = (direction == "fade")
    ts = df["timestamp"].to_numpy()
    hour = df["hour"].to_numpy(dtype=np.int32)
    o = df["open"].to_numpy(dtype=np.float64)
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    dows = df["dow"].to_numpy(dtype=np.int32)
    dates = df["timestamp"].dt.normalize().to_numpy()

    atr, adx = compute_atr_adx(h, l, c, period=ATR_PERIOD)

    n = len(df)
    change = np.empty(n, dtype=bool)
    change[0] = True
    change[1:] = dates[1:] != dates[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = n

    trades: list[dict] = []
    rets: list[float] = []

    for d_i in range(len(day_starts)):
        s = int(day_starts[d_i])
        e = int(day_ends[d_i])
        if dows[s] >= 5:
            continue

        day_h = hour[s:e]
        day_in = np.flatnonzero((day_h >= session_start_utc) & (day_h < session_end_utc))
        if day_in.size < 2:
            continue
        day_entry_mask = day_h < entry_cutoff_utc

        up_break_armed = False
        down_break_armed = False
        up_break_swing = 0.0
        down_break_swing = 0.0
        up_break_atr = 0.0
        down_break_atr = 0.0
        up_break_idx = -1
        down_break_idx = -1
        long_taken = False
        short_taken = False

        for local_i in day_in:
            g = s + int(local_i)
            cur_atr = atr[g - 1] if g - 1 >= 0 else np.nan
            cur_adx = adx[g - 1] if g - 1 >= 0 else np.nan
            if not np.isfinite(cur_atr) or cur_atr <= 0:
                continue
            # Regime gates (signal-bar must clear)
            if atr_floor_usd > 0 and cur_atr < atr_floor_usd:
                continue
            if adx_thresh > 0 and (not np.isfinite(cur_adx) or cur_adx < adx_thresh):
                continue
            if g < swing_lookback:
                continue

            window_hi = float(h[g - swing_lookback:g].max())
            window_lo = float(l[g - swing_lookback:g].min())
            cur_close = c[g]
            cur_high = h[g]
            cur_low = l[g]
            in_entry_window = day_entry_mask[local_i]

            # ---- Break detection ----
            if not up_break_armed and not long_taken and cur_close > window_hi and in_entry_window:
                up_break_armed = True
                up_break_swing = window_hi
                up_break_atr = cur_atr
                up_break_idx = int(local_i)
            if not down_break_armed and not short_taken and cur_close < window_lo and in_entry_window:
                down_break_armed = True
                down_break_swing = window_lo
                down_break_atr = cur_atr
                down_break_idx = int(local_i)

            entered = False
            # ---- UP retest ----
            if up_break_armed and not long_taken:
                bars_since = int(local_i) - up_break_idx
                if 1 <= bars_since <= retest_window:
                    if cur_low <= up_break_swing + retest_tol_atr * up_break_atr:
                        if cur_close > up_break_swing:
                            entry_dir = -1 if fade else +1
                            _enter_and_exit(
                                trades, rets, g, entry_dir, "up_retest",
                                h, l, c, dates, dows, ts,
                                swing_level=up_break_swing,
                                atr_at_entry=up_break_atr,
                                stop_atr_mult=stop_atr_mult,
                                time_exit_bars=time_exit_bars,
                                session_end_utc=session_end_utc,
                                hour=hour, cost_points=cost_points,
                                day_end_g=e,
                            )
                            long_taken = True
                            entered = True
                        else:
                            up_break_armed = False
                elif bars_since > retest_window:
                    up_break_armed = False

            # ---- DOWN retest ----
            if down_break_armed and not short_taken and not entered:
                bars_since = int(local_i) - down_break_idx
                if 1 <= bars_since <= retest_window:
                    if cur_high >= down_break_swing - retest_tol_atr * down_break_atr:
                        if cur_close < down_break_swing:
                            entry_dir = +1 if fade else -1
                            _enter_and_exit(
                                trades, rets, g, entry_dir, "down_retest",
                                h, l, c, dates, dows, ts,
                                swing_level=down_break_swing,
                                atr_at_entry=down_break_atr,
                                stop_atr_mult=stop_atr_mult,
                                time_exit_bars=time_exit_bars,
                                session_end_utc=session_end_utc,
                                hour=hour, cost_points=cost_points,
                                day_end_g=e,
                            )
                            short_taken = True
                        else:
                            down_break_armed = False
                elif bars_since > retest_window:
                    down_break_armed = False

    return np.asarray(rets, dtype=np.float64), trades


def _enter_and_exit(
    trades_list, rets_list,
    entry_g: int, direction: int, entry_reason: str,
    h, l, c, dates, dows, ts,
    swing_level: float, atr_at_entry: float,
    stop_atr_mult: float, time_exit_bars: int,
    session_end_utc: int, hour, cost_points: float, day_end_g: int,
) -> None:
    """Resolve a trade from entry_g onward. direction = +1 long / -1 short."""
    entry_px = float(c[entry_g])
    if direction == +1:
        stop_px = swing_level - stop_atr_mult * atr_at_entry
    else:
        stop_px = swing_level + stop_atr_mult * atr_at_entry

    # 2026-05-28 geometry guard (RESEARCH_NOTES.md lesson #81): if the retest bar
    # closes past the stop level (entry on wrong side of stop), MT5 would reject
    # the order in live with TRADE_RETCODE_INVALID_STOPS. Pre-fix simulator
    # silently recorded these as wins on subsequent bars when bar high/low fired
    # the stop check. Skip the trade entirely to match live broker behavior.
    if direction == +1 and entry_px <= stop_px:
        return
    if direction == -1 and entry_px >= stop_px:
        return

    max_bar = min(entry_g + time_exit_bars + 1, day_end_g)
    exit_px = entry_px
    exit_reason = "session_end"

    for j in range(entry_g + 1, max_bar):
        if hour[j] >= session_end_utc:
            exit_px = float(c[j - 1]) if hour[j - 1] < session_end_utc else float(c[entry_g])
            exit_reason = "session_end"
            break
        bar_low = l[j]
        bar_high = h[j]
        if direction == +1 and bar_low <= stop_px:
            exit_px = stop_px
            exit_reason = "stop"
            break
        if direction == -1 and bar_high >= stop_px:
            exit_px = stop_px
            exit_reason = "stop"
            break
        if j - entry_g >= time_exit_bars:
            exit_px = float(c[j])
            exit_reason = "time"
            break
    else:
        exit_px = float(c[max_bar - 1]) if max_bar > entry_g + 1 else float(c[entry_g])
        exit_reason = "time_or_session"

    gross_points = direction * (exit_px - entry_px)
    net_points = gross_points - cost_points
    net_ret = net_points / entry_px

    rets_list.append(net_ret)
    trades_list.append({
        "entry_ts": ts[entry_g],
        "entry_px": entry_px,
        "exit_px": exit_px,
        "direction": direction,
        "entry_reason": entry_reason,
        "exit_reason": exit_reason,
        "gross_points": gross_points,
        "net_points": net_points,
        "net_ret": net_ret,
        "swing_level": swing_level,
        "stop_px": stop_px,
        "atr": atr_at_entry,
        "year": pd.Timestamp(ts[entry_g]).year,
        "regime": label_regime(pd.Timestamp(ts[entry_g]).year),
        "dow": int(dows[entry_g]),
    })


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, rets: np.ndarray, trades: list[dict]) -> dict:
    if rets.size == 0:
        print(f"  [{label}]: empty (0 trades)")
        return {"sharpe": 0.0, "mdd": 0.0, "n": 0, "wr": 0.0, "pf": 0.0,
                "mean": 0.0, "tpy": 0.0, "total_pts": 0.0}
    eq = (1.0 + rets).cumprod()
    n = len(rets)
    first_ts = trades[0]["entry_ts"]
    last_ts = trades[-1]["entry_ts"]
    years = max((pd.Timestamp(last_ts) - pd.Timestamp(first_ts)).days / 365.25, 1e-9)
    tpy = n / years
    sh = annualized_sharpe(rets, trades_per_year=tpy)
    mdd = max_drawdown(eq)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    wr = len(wins) / n if n else 0.0
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gw / gl if gl > 0 else float("inf")
    total_pts = float(np.sum([t["net_points"] for t in trades]))
    total_ret = float(eq[-1] - 1.0)

    print(f"  [{label}]")
    print(f"    period      : {pd.Timestamp(first_ts).date()} -> {pd.Timestamp(last_ts).date()} "
          f"({years:.1f}y)")
    print(f"    trades      : {n}  ({tpy:.0f}/yr)")
    print(f"    Sharpe      : {sh:+.2f}")
    print(f"    Max DD      : {mdd * 100:+.2f}%")
    print(f"    total ret   : {total_ret * 100:+.2f}%")
    print(f"    WR / PF     : {wr * 100:.1f}% / {pf:.2f}")
    print(f"    mean/trade  : {rets.mean() * 100:+.4f}%  ({rets.mean() * 10000:+.2f} bp)")
    print(f"    total points: {total_pts:+.1f}")
    return {"sharpe": sh, "mdd": mdd, "n": n, "wr": wr, "pf": pf,
            "mean": float(rets.mean()), "tpy": tpy, "total_pts": total_pts}


def regime_breakdown(rets: np.ndarray, trades: list[dict], silent: bool = False) -> dict:
    if rets.size == 0:
        return {}
    out = {}
    by_regime: dict = {}
    for r, t in zip(rets, trades):
        by_regime.setdefault(t["regime"], []).append((r, t["entry_ts"]))
    for w in ("W1 2019-2020", "W2 2021-2022", "W3 2023-2026 (holdout)"):
        rows = by_regime.get(w, [])
        if len(rows) < 20:
            if not silent:
                print(f"  {w:<26s} (n={len(rows)} insufficient)")
            continue
        arr = np.asarray([r for r, _ in rows], dtype=np.float64)
        tss = [pd.Timestamp(t) for _, t in rows]
        years = max((tss[-1] - tss[0]).days / 365.25, 1e-9)
        tpy = arr.size / years
        eq = (1 + arr).cumprod()
        sh = annualized_sharpe(arr, trades_per_year=tpy)
        mdd = max_drawdown(eq)
        wr = float((arr > 0).sum()) / arr.size
        if not silent:
            print(f"  {w:<26s} n={arr.size:>4d}  Sh {sh:>+6.2f}  MDD {mdd * 100:>+7.2f}%  "
                  f"WR {wr * 100:>4.1f}%  mean {arr.mean() * 10000:>+6.2f}bp")
        out[w] = {"sharpe": sh, "mdd": mdd, "n": arr.size, "wr": wr,
                  "mean": float(arr.mean())}
    return out


def cost_sweep(df: pd.DataFrame, label: str, direction: str, **kwargs) -> None:
    print(f"  [{label} {direction} — cost sweep]")
    for cp in COST_POINTS_SWEEP:
        rets, trades = simulate_break_retest_m15(df, direction=direction,
                                                 cost_points=cp, **kwargs)
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


def kill_criteria_check(label: str, direction: str, stats: dict, regime: dict,
                        fade_gap: float, cost_stress_sh: float, deflated_sh: float
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

    print(f"  [{label} — {direction}]")
    wr_pf_joint_fail = (wr < KC_WR) and (pf < KC_PF)
    checks = [
        (f"FULL Sharpe > {KC_SHARPE_FULL:.2f}", sh > KC_SHARPE_FULL, f"{sh:+.2f}"),
        (f"W1 Sharpe   > {KC_SHARPE_REGIME:.2f}", w1_sh > KC_SHARPE_REGIME, f"{w1_sh:+.2f}"),
        (f"W2 Sharpe   > {KC_SHARPE_REGIME:.2f}", w2_sh > KC_SHARPE_REGIME, f"{w2_sh:+.2f}"),
        (f"MDD         < {KC_MDD * 100:.0f}%", abs(mdd) < KC_MDD, f"{mdd * 100:+.2f}%"),
        (f"Trades     >= {KC_TRADES_MIN}", n >= KC_TRADES_MIN, f"{n}"),
        (f"WR>{KC_WR*100:.0f}% OR PF>{KC_PF:.2f}", not wr_pf_joint_fail,
         f"WR {wr * 100:.1f}% PF {pf:.2f}"),
        (f"Fade-gap   > {KC_FADE_GAP:.2f}", fade_gap > KC_FADE_GAP, f"{fade_gap:+.2f}"),
        (f"Holdout Sh > {KC_SHARPE_HOLDOUT:.2f}", ho_sh > KC_SHARPE_HOLDOUT, f"{ho_sh:+.2f}"),
        (f"Cost-stress Sh@{KC_COST_STRESS_PT}pt > 0", cost_stress_sh > 0, f"{cost_stress_sh:+.2f}"),
        (f"Deflated Sh > {KC_DEFLATED_SH:.2f}", deflated_sh > KC_DEFLATED_SH, f"{deflated_sh:+.2f}"),
    ]
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


# ---------------------------------------------------------------------------
# Variant orchestrator
# ---------------------------------------------------------------------------

def run_variant_bidir(df: pd.DataFrame, label: str, **filter_kwargs) -> dict:
    """Run one variant in BOTH directions; return side-by-side dict."""
    section(f"Variant: {label}")

    out: dict = {"label": label}

    # ---- CONTINUATION ----
    rets_c, trades_c = simulate_break_retest_m15(df, direction="continuation",
                                                 cost_points=COST_POINTS_DEFAULT,
                                                 **filter_kwargs)
    stats_c = report_run(f"{label} CONT", rets_c, trades_c)
    print()
    print(f"  Regime breakdown — {label} CONT:")
    rb_c = regime_breakdown(rets_c, trades_c)

    # ---- FADE ----
    print()
    rets_f, trades_f = simulate_break_retest_m15(df, direction="fade",
                                                 cost_points=COST_POINTS_DEFAULT,
                                                 **filter_kwargs)
    stats_f = report_run(f"{label} FADE", rets_f, trades_f)
    print()
    print(f"  Regime breakdown — {label} FADE:")
    rb_f = regime_breakdown(rets_f, trades_f)

    # ---- Cost-stress and cost sweep (continuation only for sweep — fade gets stress) ----
    print()
    cost_sweep(df, label, "continuation", **filter_kwargs)
    print()
    cost_sweep(df, label, "fade", **filter_kwargs)

    # Cost-stress @ 0.4 pt
    rets_c_cs, _ = simulate_break_retest_m15(df, direction="continuation",
                                             cost_points=KC_COST_STRESS_PT,
                                             **filter_kwargs)
    cs_c = annualized_sharpe(rets_c_cs, trades_per_year=max(stats_c.get("tpy", 1), 1))
    rets_f_cs, _ = simulate_break_retest_m15(df, direction="fade",
                                             cost_points=KC_COST_STRESS_PT,
                                             **filter_kwargs)
    cs_f = annualized_sharpe(rets_f_cs, trades_per_year=max(stats_f.get("tpy", 1), 1))

    # Fade-gap (per direction). Continuation's fade-gap is (cont - fade); fade's is (fade - cont).
    fg_c = stats_c["sharpe"] - stats_f["sharpe"]
    fg_f = stats_f["sharpe"] - stats_c["sharpe"]

    # Deflated Sharpe
    dsh_c = deflated_sharpe(stats_c["sharpe"], rets_c, n_trials=N_VARIANTS_PRECOMMITTED)
    dsh_f = deflated_sharpe(stats_f["sharpe"], rets_f, n_trials=N_VARIANTS_PRECOMMITTED)

    # Kill-criteria
    print()
    section(f"Kill criteria — {label}")
    passed_c, verdict_c = kill_criteria_check(label, "continuation", stats_c, rb_c,
                                              fg_c, cs_c, dsh_c)
    print()
    passed_f, verdict_f = kill_criteria_check(label, "fade", stats_f, rb_f,
                                              fg_f, cs_f, dsh_f)

    out["cont"] = {"stats": stats_c, "regime": rb_c, "fade_gap": fg_c,
                   "cost_stress_sh": cs_c, "deflated_sh": dsh_c,
                   "passed": passed_c, "verdict": verdict_c}
    out["fade"] = {"stats": stats_f, "regime": rb_f, "fade_gap": fg_f,
                   "cost_stress_sh": cs_f, "deflated_sh": dsh_f,
                   "passed": passed_f, "verdict": verdict_f}
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _row(label: str, direction: str, r: dict) -> str:
    s = r["stats"]
    rb = r["regime"]
    w1 = rb.get("W1 2019-2020", {}).get("sharpe", 0.0)
    w2 = rb.get("W2 2021-2022", {}).get("sharpe", 0.0)
    ho = rb.get("W3 2023-2026 (holdout)", {}).get("sharpe", 0.0)
    return (
        f"  {label:<22s} {direction:<5s} {s.get('sharpe', 0):>+6.2f} "
        f"{w1:>+6.2f} {w2:>+6.2f} {ho:>+6.2f} "
        f"{s.get('mdd', 0) * 100:>+7.2f}% "
        f"{s.get('n', 0):>5d} "
        f"{s.get('wr', 0) * 100:>4.1f}% "
        f"{s.get('pf', 0):>4.2f} "
        f"{r['fade_gap']:>+6.2f} "
        f"{r['cost_stress_sh']:>+6.2f} "
        f"{r['deflated_sh']:>+6.2f} "
        f"{r['verdict']}"
    )


def main() -> int:
    section("Loading XAUUSD M5 -> resample to M15 (NY-AM session 13-15 UTC)")
    df = load_m15()
    print(f"  M15 bars: {len(df):,}")
    print(f"  range   : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    in_session = df[(df["hour"] >= SESSION_START_UTC) & (df["hour"] < SESSION_END_UTC)]
    print(f"  in-session (13-15 UTC): {len(in_session):,} bars across "
          f"{in_session['date'].nunique()} days")
    # Quick ATR(14) percentile summary so the user can sanity-check the floor sweep.
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    atr_arr, _ = compute_atr_adx(h, l, c)
    in_sess_mask = (df["hour"].to_numpy() >= SESSION_START_UTC) & \
                   (df["hour"].to_numpy() < SESSION_END_UTC)
    atr_sess = atr_arr[in_sess_mask]
    atr_sess = atr_sess[np.isfinite(atr_sess)]
    print(f"  in-session ATR(14) M15: "
          f"p10 {np.percentile(atr_sess, 10):.2f}, "
          f"p25 {np.percentile(atr_sess, 25):.2f}, "
          f"p50 {np.percentile(atr_sess, 50):.2f}, "
          f"p75 {np.percentile(atr_sess, 75):.2f}, "
          f"p90 {np.percentile(atr_sess, 90):.2f} USD")

    results: list[dict] = []
    # 1. baseline — no ATR/ADX filter
    results.append(run_variant_bidir(df, "baseline"))
    # 2. atr-3
    results.append(run_variant_bidir(df, "atr-3", atr_floor_usd=3.0))
    # 3. atr-5
    results.append(run_variant_bidir(df, "atr-5", atr_floor_usd=5.0))
    # 4. atr-7
    results.append(run_variant_bidir(df, "atr-7", atr_floor_usd=7.0))
    # 5. atr-10
    results.append(run_variant_bidir(df, "atr-10", atr_floor_usd=10.0))
    # 6. atr-5 + adx-20
    results.append(run_variant_bidir(df, "atr-5+adx-20", atr_floor_usd=5.0, adx_thresh=20.0))

    # ----- Summary -----
    section("Phase 2 summary — all variants × directions")
    header = (
        f"  {'variant':<22s} {'dir':<5s} {'Sh':>6s} {'W1':>6s} {'W2':>6s} {'W3':>6s} "
        f"{'MDD':>8s} {'n':>5s} {'WR%':>5s} {'PF':>5s} {'fgap':>6s} {'Sh@CS':>6s} "
        f"{'dSh':>6s} verdict"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for r in results:
        print(_row(r["label"], "CONT", r["cont"]))
        print(_row(r["label"], "FADE", r["fade"]))

    # Deploy candidate
    print()
    print("  Deploy candidates (any direction PASSING tighter criterion):")
    passers = []
    for r in results:
        for d in ("cont", "fade"):
            if r[d]["passed"]:
                passers.append((r["label"], d, r[d]["stats"]["sharpe"]))
    if passers:
        for lab, d, sh in sorted(passers, key=lambda x: -x[2]):
            print(f"    {lab:<22s} {d:<5s} Sh {sh:+.2f}")
    else:
        print("    NONE pass all kill criteria.")

    # Per-direction summary line for the main thread
    print()
    print("  Per-direction summary (best Sh across variants):")
    for d_label, d_key in (("CONT", "cont"), ("FADE", "fade")):
        best = max(results, key=lambda r: r[d_key]["stats"].get("sharpe", -99))
        best_sh = best[d_key]["stats"]["sharpe"]
        best_lab = best["label"]
        best_v = best[d_key]["verdict"]
        print(f"    {d_label}: best Sh {best_sh:+.2f} on '{best_lab}' (verdict: {best_v})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
