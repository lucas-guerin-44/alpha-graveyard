#!/usr/bin/env python3
"""
GER40 ORB partial-exit "runner" overlay -- Phase 2 demo.

Thesis: experiments/orb_runner/orb_runner.md

Overlay on the DEPLOYED GER40 T+180 LONG-only ORB (experiments/_live/orb/):
  - Bank BANK_FRACTION of the position at the T+180 clock (the "normal" gain).
  - On days that look like trend days at T+180, keep (1-BANK_FRACTION) running to
    cash-close (still OR-low stop-protected). On other days, fully exit at T+180.

The entry->T+180 P&L is identical to the deployed strat by construction; the overlay
only adds the runner leg's (1-BANK_FRACTION) * (T+180 -> close) return on gated days.

Variants run:
  base      -- deployed T+180 LONG-only (sanity vs orb.md +0.76 / HO +0.93)
  gated     -- runner kept only on trend-day-gated days (frozen config)
  ungated   -- runner kept on EVERY T+180 day (null check for the gate)
  + BANK_FRACTION sweep, runner-exit sweep, convexity stats.

Run:
  ORB_SYMBOL=GER40 ORB_SESSION=EU venv/Scripts/python.exe experiments/orb_runner/orb_runner_demo.py
"""

from __future__ import annotations

import os
import sys
from datetime import time as dtime

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))

from data import fetch_ohlc  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SYMBOL = os.environ.get("ORB_SYMBOL", "GER40")
TIMEFRAME = "M5"
START_DATE = "2019-01-01"
END_DATE = "2026-05-29"

OR_MINUTES = 30
ENTRY_CUTOFF_MIN = 180
EXIT_MIN_BEFORE_CLOSE = 5
TOD_EXIT_MIN = 180          # the deployed clock
COST_POINTS_ROUND_TRIP = 1.0

# --- Frozen overlay params (pre-committed, see orb_runner.md) ---
BANK_FRACTION = 0.75        # close 75% at T+180, keep 25% running
K_RANGE = 2.0               # trend gate: day range >= K_RANGE * OR width
NEAR_HIGH = 0.70            # trend gate: close in top (1-NEAR_HIGH) of day range

SESSIONS = {
    "US": (dtime(9, 30), dtime(16, 0), "US/Eastern"),
    "EU": (dtime(9, 0), dtime(17, 30), "Europe/Berlin"),
    "UK": (dtime(8, 0), dtime(16, 30), "Europe/London"),
    # DEPLOY = the live GER40 TZ-fix shifted session (orb.md banner 2026-05-28):
    # broker GMT+3 07:00-15:30 == real Berlin 06:00-14:30 CEST.
    "DEPLOY": (dtime(6, 0), dtime(14, 30), "Europe/Berlin"),
}
SESSION_KEY = os.environ.get("ORB_SESSION", "EU").upper()
RTH_OPEN, RTH_CLOSE, SESSION_TZ = SESSIONS[SESSION_KEY]

_rth_minutes = (RTH_CLOSE.hour * 60 + RTH_CLOSE.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)
BARS_PER_DAY = _rth_minutes // 5
DAYS_PER_YEAR = 252
BARS_PER_YEAR = BARS_PER_DAY * DAYS_PER_YEAR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 80}\n  {t}\n{'=' * 80}\n")


def load_m5(symbol: str) -> pd.DataFrame:
    raw = fetch_ohlc(symbol, TIMEFRAME, START_DATE, END_DATE)
    if raw is None or raw.empty:
        raise RuntimeError(f"No bars for {symbol} {TIMEFRAME}.")
    df = raw[["timestamp", "open", "high", "low", "close"]].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df.index = df.index.tz_convert(SESSION_TZ)
    times = df.index.time
    mask = (times >= RTH_OPEN) & (times < RTH_CLOSE)
    df = df.loc[mask]
    df = df.loc[df.index.dayofweek < 5]
    return df


def max_drawdown(eq: np.ndarray) -> float:
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min()) if len(dd) else 0.0


def annualized_sharpe(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if r.size == 0:
        return 0.0
    std = r.std(ddof=1)
    if std == 0 or not np.isfinite(std):
        return 0.0
    return float(r.mean() / std * np.sqrt(BARS_PER_YEAR))


# ---------------------------------------------------------------------------
# Simulator with partial-exit runner overlay (LONG-only, numpy inner loop)
# ---------------------------------------------------------------------------

def simulate_runner(
    bars: pd.DataFrame,
    or_minutes: int = OR_MINUTES,
    entry_cutoff_min: int = ENTRY_CUTOFF_MIN,
    exit_min_before_close: int = EXIT_MIN_BEFORE_CLOSE,
    tod_exit_minutes: int = TOD_EXIT_MIN,
    cost_points: float = COST_POINTS_ROUND_TRIP,
    bank_fraction: float = BANK_FRACTION,
    gate_mode: str = "off",          # "off" = plain T+180; "gated"; "all" (null check)
    k_range: float = K_RANGE,
    near_high: float = NEAR_HIGH,
    runner_exit_minutes: int | None = None,  # None = cash-close; else T+N from entry
) -> tuple[pd.Series, list[dict]]:
    """LONG-only ORB with optional partial-bank-and-run at the T+180 clock.

    gate_mode:
      "off"   -> behaves as deployed T+180 LONG-only (full exit at T+180).
      "gated" -> on trend-day-gated bars, bank `bank_fraction`, run the rest.
      "all"   -> keep the runner on every T+180 day (no gate) -- null check.

    Returns (bar_ret, trades). Each trade dict carries the FULL day P&L
    (bank leg + runner leg) plus a `runner_pnl` field isolating the overlay's
    incremental contribution `(1-bank_fraction) * (T+180 -> exit return)`.
    """
    idx = bars.index
    n_bars = len(bars)
    if n_bars == 0:
        return pd.Series(dtype=float, name="ret"), []

    open_arr = bars["open"].to_numpy(dtype=np.float64)
    high_arr = bars["high"].to_numpy(dtype=np.float64)
    low_arr = bars["low"].to_numpy(dtype=np.float64)
    close_arr = bars["close"].to_numpy(dtype=np.float64)

    rth_open_min = RTH_OPEN.hour * 60 + RTH_OPEN.minute
    rth_close_min = RTH_CLOSE.hour * 60 + RTH_CLOSE.minute
    hours = np.asarray(idx.hour, dtype=np.int32)
    minutes = np.asarray(idx.minute, dtype=np.int32)
    minute_of_day = hours * 60 + minutes - rth_open_min

    dates = np.asarray(idx.date)
    change = np.empty(n_bars, dtype=bool)
    change[0] = True
    change[1:] = dates[1:] != dates[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = n_bars

    ret_arr = np.zeros(n_bars, dtype=np.float64)
    trades: list[dict] = []

    rth_minutes = rth_close_min - rth_open_min
    exit_cutoff = rth_minutes - exit_min_before_close
    or_end = or_minutes
    min_day_bars = (or_minutes // 5) + 4

    for d_i in range(len(day_starts)):
        s = int(day_starts[d_i])
        e = int(day_ends[d_i])
        n = e - s
        if n < min_day_bars:
            continue

        day_open = open_arr[s:e]
        day_high = high_arr[s:e]
        day_low = low_arr[s:e]
        day_close = close_arr[s:e]
        day_mod = minute_of_day[s:e]

        or_mask = day_mod < or_end
        if not or_mask.any():
            continue
        or_high = float(day_high[or_mask].max())
        or_low = float(day_low[or_mask].min())
        if not (np.isfinite(or_high) and np.isfinite(or_low)) or or_high <= or_low:
            continue
        or_width = or_high - or_low

        post_or = np.flatnonzero(day_mod >= or_end)
        if post_or.size == 0:
            continue
        first_post = int(post_or[0])

        # running day extremes (incl. OR) for the trend gate
        run_hi = float(day_high[:first_post].max()) if first_post > 0 else or_high
        run_lo = float(day_low[:first_post].min()) if first_post > 0 else or_low

        position = 0          # 0 flat, 1 long
        size = 0.0            # current position size (1.0 full, then 1-bank after run)
        entry_px = 0.0
        entry_global_i = -1
        entry_bar_idx = -1
        stop_px = 0.0
        long_taken = False
        runner_active = False
        banked = False
        bank_pnl = 0.0        # entry -> T+180 return (full size), for trade record
        bank_px = 0.0         # price at which the bulk was banked (= T+180 close)

        for i in range(first_post, n):
            mod = int(day_mod[i])
            is_last = (i == n - 1)
            # update running extremes through this bar
            if day_high[i] > run_hi:
                run_hi = float(day_high[i])
            if day_low[i] < run_lo:
                run_lo = float(day_low[i])

            if position != 0 and i > first_post:
                prev_close = day_close[i - 1]
                ret_arr[s + i] = size * position * (day_close[i] - prev_close) / prev_close

            if position != 0:
                bar_low = day_low[i]
                bar_high = day_high[i]
                hit_stop = bar_low <= stop_px

                mins_in = (i - entry_bar_idx) * 5 if entry_bar_idx >= 0 else 0
                at_tod = (not banked) and mins_in >= tod_exit_minutes
                runner_done = False
                if runner_active:
                    if runner_exit_minutes is not None:
                        runner_done = mins_in >= runner_exit_minutes
                    # else cash-close handled by exit_cutoff/is_last below
                forced_close = (mod >= exit_cutoff) or is_last or runner_done

                # ---- decision at the T+180 clock ----
                if at_tod and not hit_stop and not forced_close:
                    rng = run_hi - run_lo
                    near = ((day_close[i] - run_lo) / rng) if rng > 0 else 0.0
                    in_profit = day_close[i] > entry_px
                    if gate_mode == "gated":
                        gate = (rng >= k_range * or_width) and (near >= near_high) and in_profit
                    elif gate_mode == "all":
                        gate = True
                    else:
                        gate = False

                    if gate and bank_fraction < 1.0:
                        # bank the bulk at this bar's close; keep the runner
                        bank_px = float(day_close[i])
                        bank_pnl = position * (bank_px - entry_px) / entry_px
                        # cost charged here on the full round-trip (in==out notional)
                        ret_arr[s + i] -= cost_points / entry_px
                        size = 1.0 - bank_fraction
                        banked = True
                        runner_active = True
                        # bar return already booked at full size above (correct: we
                        # held full size through this bar's close, then reduce)
                        continue
                    else:
                        # full exit at T+180 close (deployed behavior)
                        exit_px = float(day_close[i])
                        cost_ret = cost_points / entry_px
                        ret_arr[s + i] -= cost_ret
                        trades.append(_mk_trade(dates[s], idx, entry_global_i, s + i,
                                                entry_px, exit_px, position, cost_ret,
                                                "tod", 0.0))
                        position = 0
                        size = 0.0
                        continue

                # ---- stop / forced close (applies to base trade or active runner) ----
                if hit_stop or forced_close:
                    if hit_stop:
                        exit_px = stop_px
                        reason = "stop"
                    elif runner_done:
                        exit_px = float(day_close[i])
                        reason = "runner_tod"
                    else:
                        exit_px = float(day_close[i])
                        reason = "eod" if is_last or mod >= exit_cutoff else "close"

                    if i > first_post:
                        prev_close = day_close[i - 1]
                        ret_arr[s + i] = size * position * (exit_px - prev_close) / prev_close
                    else:
                        ret_arr[s + i] = size * position * (exit_px - entry_px) / entry_px

                    if not banked:
                        # never reached T+180 (stopped early) -> single full exit
                        cost_ret = cost_points / entry_px
                        ret_arr[s + i] -= cost_ret
                        trades.append(_mk_trade(dates[s], idx, entry_global_i, s + i,
                                                entry_px, exit_px, position, cost_ret,
                                                reason, 0.0))
                    else:
                        # runner leg closing; cost already paid at bank time
                        full_to_t180 = bank_pnl
                        runner_leg = size * position * (exit_px - bank_px) / bank_px
                        total_pnl = full_to_t180 + runner_leg - cost_points / entry_px
                        trades.append(_mk_trade(dates[s], idx, entry_global_i, s + i,
                                                entry_px, exit_px, position,
                                                cost_points / entry_px,
                                                "runner_" + reason, runner_leg,
                                                total_pnl=total_pnl))
                    position = 0
                    size = 0.0
                    runner_active = False
                    continue

            # ---- entry (LONG-only, first up-break) ----
            if position == 0 and mod < entry_cutoff_min and i + 1 < n and not long_taken:
                if day_close[i] > or_high:
                    position = 1
                    size = 1.0
                    entry_px = float(day_open[i + 1])
                    stop_px = entry_px - or_width
                    entry_global_i = s + i + 1
                    entry_bar_idx = i + 1
                    long_taken = True

        # safety: still holding at day end
        if position != 0:
            last_close = float(day_close[n - 1])
            if not banked:
                trades.append(_mk_trade(dates[s], idx, entry_global_i, s + n - 1,
                                        entry_px, last_close, position,
                                        cost_points / entry_px, "eod-safety", 0.0))
            else:
                runner_leg = size * position * (last_close - _bank_px) / _bank_px
                total_pnl = bank_pnl + runner_leg - cost_points / entry_px
                trades.append(_mk_trade(dates[s], idx, entry_global_i, s + n - 1,
                                        entry_px, last_close, position,
                                        cost_points / entry_px, "runner_eod-safety",
                                        runner_leg, total_pnl=total_pnl))

    bar_ret = pd.Series(ret_arr, index=idx, name="ret")
    return bar_ret, trades


def _mk_trade(date, idx, entry_gi, exit_gi, entry_px, exit_px, position, cost_ret,
              reason, runner_pnl, total_pnl=None):
    base_pnl = position * (exit_px - entry_px) / entry_px - cost_ret
    return {
        "date": date,
        "direction": "LONG" if position == 1 else "SHORT",
        "entry_ts": idx[entry_gi],
        "exit_ts": idx[exit_gi],
        "entry_px": float(entry_px),
        "exit_px": float(exit_px),
        "pnl_pct": base_pnl if total_pnl is None else total_pnl,
        "runner_pnl": runner_pnl,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def stats(bar_ret: pd.Series, trades: list[dict]) -> dict:
    eq = (1.0 + bar_ret).cumprod()
    years = (bar_ret.index[-1] - bar_ret.index[0]).days / 365.25
    total = float(eq.iloc[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    sh = annualized_sharpe(bar_ret.to_numpy())
    mdd = max_drawdown(eq.to_numpy())
    pnls = np.array([t["pnl_pct"] for t in trades], dtype=float)
    n = len(trades)
    wr = float((pnls > 0).mean()) if n else 0.0
    gw = pnls[pnls > 0].sum()
    gl = -pnls[pnls < 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    skew = float(pd.Series(pnls).skew()) if n > 2 else 0.0
    max_win = float(pnls.max()) if n else 0.0
    return dict(years=years, total=total, cagr=cagr, sh=sh, mdd=mdd, n=n, wr=wr,
                pf=pf, skew=skew, max_win=max_win)


def report(label: str, bar_ret: pd.Series, trades: list[dict]) -> dict:
    st = stats(bar_ret, trades)
    print(f"  [{label}]")
    print(f"    Sharpe {st['sh']:+.2f}   CAGR {st['cagr']*100:+.2f}%   "
          f"total {st['total']*100:+.1f}%   MDD {st['mdd']*100:+.2f}%")
    print(f"    trades {st['n']}  ({st['n']/max(st['years']*52,1e-9):.2f}/wk)   "
          f"WR {st['wr']*100:.1f}%   PF {st['pf']:.2f}")
    print(f"    pnl skew {st['skew']:+.2f}   max winner {st['max_win']*100:+.2f}%")
    return st


def regime(label: str, bar_ret: pd.Series, trades: list[dict]) -> None:
    windows = [
        ("2019-2020", "2019-01-01", "2020-12-31"),
        ("2021-2022", "2021-01-01", "2022-12-31"),
        ("2023-2026 HO", "2023-01-01", "2026-12-31"),
    ]
    print(f"  [{label}] regimes:")
    for w, s, e in windows:
        sub = bar_ret.loc[s:e]
        if len(sub) < 200:
            print(f"    {w:<14s} (insufficient)")
            continue
        eq = (1.0 + sub).cumprod()
        yrs = (sub.index[-1] - sub.index[0]).days / 365.25
        cagr = float(eq.iloc[-1]) ** (1 / max(yrs, 1e-9)) - 1
        sh = annualized_sharpe(sub.to_numpy())
        mdd = max_drawdown(eq.to_numpy())
        nt = sum(1 for t in trades if s <= str(t["date"]) <= e)
        print(f"    {w:<14s} Sharpe {sh:>+6.2f}  CAGR {cagr*100:>+7.2f}%  "
              f"MDD {mdd*100:>+7.2f}%  trades {nt:>4d}")


def runner_overlay_attribution(label: str, trades: list[dict]) -> None:
    """Isolate the runner leg's incremental P&L (the overlay's actual contribution)."""
    legs = [t["runner_pnl"] for t in trades if t.get("runner_pnl", 0.0) != 0.0]
    if not legs:
        print(f"  [{label}] no runner legs fired.")
        return
    arr = np.array(legs, dtype=float)
    print(f"  [{label}] runner legs: {len(arr)} days  "
          f"sum {arr.sum()*100:+.2f}%  mean {arr.mean()*100:+.4f}%  "
          f"WR {(arr>0).mean()*100:.1f}%  skew {pd.Series(arr).skew():+.2f}")
    top5 = np.sort(arr)[-5:]
    print(f"    top-5 runner days sum {top5.sum()*100:+.2f}%  "
          f"(share of runner total: {top5.sum()/arr.sum()*100 if arr.sum()!=0 else 0:.0f}%)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section(f"Loading {SYMBOL} {TIMEFRAME} ({SESSION_KEY} session)")
    bars = load_m5(SYMBOL)
    print(f"  bars {len(bars):,}   {bars.index[0]} -> {bars.index[-1]}   "
          f"days {len(set(bars.index.date))}")

    section("Base: deployed T+180 LONG-only (sanity vs orb.md +0.76 / HO +0.93)")
    base_r, base_t = simulate_runner(bars, gate_mode="off")
    base_st = report("base", base_r, base_t)
    regime("base", base_r, base_t)

    section(f"Gated runner (frozen: bank={BANK_FRACTION}, K_range={K_RANGE}, near_high={NEAR_HIGH}, exit=close)")
    g_r, g_t = simulate_runner(bars, gate_mode="gated")
    g_st = report("gated", g_r, g_t)
    regime("gated", g_r, g_t)
    runner_overlay_attribution("gated", g_t)

    section("NULL CHECK -- ungated runner (keep sliver EVERY day, no trend gate)")
    u_r, u_t = simulate_runner(bars, gate_mode="all")
    u_st = report("ungated", u_r, u_t)
    regime("ungated", u_r, u_t)
    runner_overlay_attribution("ungated", u_t)

    section("BANK_FRACTION sweep (gated)")
    for bf in (0.5, 0.75, 0.9):
        r, t = simulate_runner(bars, gate_mode="gated", bank_fraction=bf)
        st = stats(r, t)
        print(f"  bank={bf:.2f}  Sharpe {st['sh']:+.2f}  CAGR {st['cagr']*100:+.2f}%  "
              f"MDD {st['mdd']*100:+.2f}%  skew {st['skew']:+.2f}  maxW {st['max_win']*100:+.2f}%")

    section("Runner-exit sweep (gated, bank=0.75)")
    for rx, lbl in ((None, "close"), (240, "T+240"), (300, "T+300")):
        r, t = simulate_runner(bars, gate_mode="gated", runner_exit_minutes=rx)
        st = stats(r, t)
        print(f"  exit={lbl:<6s}  Sharpe {st['sh']:+.2f}  CAGR {st['cagr']*100:+.2f}%  "
              f"MDD {st['mdd']*100:+.2f}%  skew {st['skew']:+.2f}")

    section("VERDICT SCORECARD (vs pre-committed fail conditions)")
    ho = lambda r: annualized_sharpe(r.loc["2023-01-01":"2026-12-31"].to_numpy())
    base_ho, g_ho, u_ho = ho(base_r), ho(g_r), ho(u_r)
    print(f"  base   : full Sh {base_st['sh']:+.2f}  HO {base_ho:+.2f}  CAGR {base_st['cagr']*100:+.2f}%  skew {base_st['skew']:+.2f}  maxW {base_st['max_win']*100:+.2f}%")
    print(f"  gated  : full Sh {g_st['sh']:+.2f}  HO {g_ho:+.2f}  CAGR {g_st['cagr']*100:+.2f}%  skew {g_st['skew']:+.2f}  maxW {g_st['max_win']*100:+.2f}%")
    print(f"  ungated: full Sh {u_st['sh']:+.2f}  HO {u_ho:+.2f}  CAGR {u_st['cagr']*100:+.2f}%  skew {u_st['skew']:+.2f}  maxW {u_st['max_win']*100:+.2f}%")
    print()
    c1 = g_ho >= base_ho - 1e-9
    c2 = g_st['sh'] >= base_st['sh'] - 0.05
    c3 = (g_st['cagr'] > base_st['cagr']) and (g_st['skew'] > base_st['skew']) and (g_st['max_win'] > base_st['max_win'])
    c4 = (g_st['sh'] > u_st['sh']) and (g_st['cagr'] > u_st['cagr'])
    c5 = abs(g_st['mdd']) < 0.25
    v = lambda b: "PASS" if b else "FAIL"
    print(f"  [1] holdout not degraded (g_HO >= base_HO)     : {v(c1)}  ({g_ho:+.2f} vs {base_ho:+.2f})")
    print(f"  [2] Sharpe guard (g_full >= base - 0.05)        : {v(c2)}  ({g_st['sh']:+.2f} vs {base_st['sh']:+.2f})")
    print(f"  [3] convexity real (CAGR & skew & maxW all up)  : {v(c3)}")
    print(f"  [4] NULL: gated beats ungated (Sh & CAGR)       : {v(c4)}  (Sh {g_st['sh']:+.2f} vs {u_st['sh']:+.2f}, CAGR {g_st['cagr']*100:+.2f} vs {u_st['cagr']*100:+.2f})")
    print(f"  [5] MDD < 25%                                   : {v(c5)}  ({g_st['mdd']*100:+.2f}%)")
    print()
    if c1 and c2 and c3 and c4 and c5:
        print("  => PASS (adopt as overlay)")
    elif c3 and c4 and not c2:
        print("  => MARGINAL (convexity real but Sharpe cost; CAGR-vs-Sharpe tradeoff)")
    else:
        print("  => REJECT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
