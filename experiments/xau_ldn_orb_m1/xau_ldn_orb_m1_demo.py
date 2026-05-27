#!/usr/bin/env python3
"""XAU London-open ORB at M1 — Phase 2 demo.

Thesis: experiments/xau_ldn_orb_m1/xau_ldn_orb_m1.md

Pre-committed rules (baseline):
  Asian range = [prior day 22:00 UTC, today 07:00 UTC)
  Trade window = [07:00 + LDN_OR_MIN, 10:00 UTC)  -- LDN_OR_MIN=5 cooldown
  Hard flat at 12:00 UTC (before NY-AM, avoid colliding w/ deployed XAU FADE)
  Stop = opposite Asian-range bound
  Time exit = T+90 min
  Cost = 0.20pt RT (Eightcap conservative; sweep 0.10/0.15/0.20/0.30)
  Asian-range floor = 15 bps (else skip day; too tight to extract directional info)
  Mon-Fri only

4-variant grid (lesson #13 + #-19):
  LONG-cont   : break-UP  -> LONG  (primary, the deploy candidate)
  SHORT-cont  : break-DOWN -> SHORT
  LONG-fade   : break-DOWN -> LONG  (null direction)
  SHORT-fade  : break-UP  -> SHORT  (null direction)

dir-gap = mean(CONT) - mean(FADE). Must be > +0.40 Sharpe.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_ldn_orb_m1/xau_ldn_orb_m1_demo.py
"""
from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_M1.csv')

# ---------------------------------------------------------------------------
# Config (PRE-COMMITTED)
# ---------------------------------------------------------------------------

ASIAN_START_HOUR = 22         # prior-calendar-day 22:00 UTC
ASIAN_END_HOUR = 7            # today 07:00 UTC (LDN cash-open anchor)
LDN_OR_MIN = 5                # cooldown — no entries in first LDN_OR_MIN minutes after 07:00
ENTRY_CUTOFF_HOUR = 10        # no new entries after 10:00 UTC
HARD_FLAT_HOUR = 12           # hard exit at 12:00 UTC (before deployed NY FADE windows)
T_EXIT_MIN = 90               # 90-min time exit
COST_POINTS_RT = 0.20         # Eightcap conservative
MIN_ASIAN_RANGE_BPS = 15.0    # below this, range too tight

# Annualization: ~250 trading days/year, ~1 trade/day max
TRADES_PER_YEAR = 250

# Pre-committed kill criteria
KC_SH_FULL = 0.30
KC_SH_W1 = 0.00
KC_SH_W2 = 0.00
KC_SH_W3 = 0.20
KC_MDD = 0.12
KC_TRADES = 300
KC_DIR_GAP = 0.40
KC_COST_STRESS_PT = 0.30
KC_CORR_BOOK = 0.50
KC_OFF_SESSION_DELTA = 0.40

# Cost sweep
COST_SWEEP_PT = (0.10, 0.15, 0.20, 0.30, 0.50)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def annualized_sharpe(r: np.ndarray, trades_per_year: float = TRADES_PER_YEAR) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    if s == 0 or not np.isfinite(s):
        return 0.0
    return float(r.mean() / s * np.sqrt(trades_per_year))


def tpy_from_trades(trades: list[dict]) -> float:
    if len(trades) < 2:
        return TRADES_PER_YEAR
    years = max((trades[-1]['exit_ts'] - trades[0]['entry_ts']).days / 365.25, 1e-9)
    return len(trades) / years


def max_drawdown(eq: np.ndarray) -> float:
    if len(eq) == 0:
        return 0.0
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min())


def label_regime(year: int) -> str:
    if year <= 2020:
        return 'W1'  # 2018-2020 pre/COVID  (3y because XAU M1 starts 2018)
    if year <= 2022:
        return 'W2'  # 2021-2022 vol
    return 'W3'      # 2023-2026 holdout


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_m1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    df['date'] = df['timestamp'].dt.date
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    df['dow'] = df['timestamp'].dt.dayofweek
    return df


# ---------------------------------------------------------------------------
# Simulator (numpy inner loop per lesson "PRIORITIZE NUMPY ALWAYS")
# ---------------------------------------------------------------------------

def simulate_orb_m1(
    df: pd.DataFrame,
    variant: str,                          # 'LONG_cont' | 'SHORT_cont' | 'LONG_fade' | 'SHORT_fade'
    cost_points: float = COST_POINTS_RT,
    min_asian_range_bps: float = MIN_ASIAN_RANGE_BPS,
    ldn_or_min: int = LDN_OR_MIN,
    entry_cutoff_hour: int = ENTRY_CUTOFF_HOUR,
    hard_flat_hour: int = HARD_FLAT_HOUR,
    t_exit_min: int = T_EXIT_MIN,
    asian_start_hour: int = ASIAN_START_HOUR,
    asian_end_hour: int = ASIAN_END_HOUR,
    # off-session control: shift the whole strategy to a different break-of-prior-range window
    session_shift_hours: int = 0,
) -> tuple[list[dict], np.ndarray]:
    """Returns (trades, per-trade-net-return-array).

    variant maps:
      LONG_cont:  break-UP   -> LONG
      SHORT_cont: break-DOWN -> SHORT
      LONG_fade:  break-DOWN -> LONG   (null check)
      SHORT_fade: break-UP   -> SHORT  (null check)
    """
    # Apply session shift for off-session control (Phase 0b lesson #-14)
    asian_start_eff = (asian_start_hour + session_shift_hours) % 24
    asian_end_eff = (asian_end_hour + session_shift_hours) % 24
    entry_cutoff_eff = (entry_cutoff_hour + session_shift_hours) % 24
    hard_flat_eff = (hard_flat_hour + session_shift_hours) % 24

    ts = df['timestamp'].values.astype('datetime64[m]')      # minute resolution
    hour = df['hour'].to_numpy(dtype=np.int32)
    minute = df['minute'].to_numpy(dtype=np.int32)
    dow = df['dow'].to_numpy(dtype=np.int32)
    high = df['high'].to_numpy(dtype=np.float64)
    low = df['low'].to_numpy(dtype=np.float64)
    open_ = df['open'].to_numpy(dtype=np.float64)
    close = df['close'].to_numpy(dtype=np.float64)

    # Build "session day" key. Session day = the calendar date of the LDN-OR anchor (07:00 UTC).
    # Bars at hour >= asian_start_eff but before next day's asian_end_eff belong to the NEXT session.
    # For the no-shift baseline: bars [D-1 22:00, D 07:00) belong to session day D.
    # General: bars from hour >= asian_start_eff (prior day) through hour < asian_end_eff (today) -> session=today.
    # Build it via minute-of-week offset trick:
    dates = df['date'].values  # numpy array of datetime.date

    # session_day[i] = the date of the LDN-OR (asian_end_eff hour) that this bar belongs to.
    # If hour >= asian_start_eff: belongs to NEXT day's session (rolls forward).
    # If hour <  asian_end_eff:   belongs to TODAY's session.
    # If asian_end_eff <= hour < asian_start_eff: belongs to NEXT day's session  (in the
    #    trading-window itself before the next Asian range starts).
    one_day = pd.Timedelta(days=1).to_numpy()  # numpy.timedelta64
    session_day = np.empty_like(dates)
    for i in range(len(dates)):
        h = hour[i]
        if asian_start_eff <= asian_end_eff:
            # No wrap (e.g., shift=+12 puts start=10, end=19) — session = today
            session_day[i] = dates[i]
        else:
            # Wrap (baseline: start=22, end=7) — bars [22:00, 24:00) belong to next session
            if h >= asian_start_eff:
                session_day[i] = dates[i] + pd.Timedelta(days=1).to_pytimedelta()
            else:
                session_day[i] = dates[i]

    # Day boundaries by session_day
    change = np.empty(len(session_day), dtype=bool)
    change[0] = True
    change[1:] = session_day[1:] != session_day[:-1]
    day_starts = np.flatnonzero(change)
    day_ends = np.empty_like(day_starts)
    day_ends[:-1] = day_starts[1:]
    day_ends[-1] = len(session_day)

    # Variant decode
    if variant == 'LONG_cont':
        position_dir, break_dir = +1, +1   # break-UP, go LONG
    elif variant == 'SHORT_cont':
        position_dir, break_dir = -1, -1   # break-DOWN, go SHORT
    elif variant == 'LONG_fade':
        position_dir, break_dir = +1, -1   # break-DOWN, go LONG
    elif variant == 'SHORT_fade':
        position_dir, break_dir = -1, +1   # break-UP, go SHORT
    else:
        raise ValueError(variant)

    trades = []

    for di in range(len(day_starts)):
        s = int(day_starts[di])
        e = int(day_ends[di])

        sub_hour = hour[s:e]
        sub_min = minute[s:e]
        sub_dow = dow[s:e]
        sub_high = high[s:e]
        sub_low = low[s:e]
        sub_open = open_[s:e]
        sub_close = close[s:e]
        sub_ts = ts[s:e]

        # Skip weekends (any Saturday/Sunday bars; LDN open should be Mon-Fri)
        # Use the most-frequent dow in the trade window as the session weekday
        if asian_end_eff < 24:
            tw_mask = (sub_hour == asian_end_eff)
            if tw_mask.any():
                sess_dow = int(sub_dow[tw_mask][0])
                if sess_dow >= 5:
                    continue

        # Asian range mask: bars from [asian_start_eff, 24) prior calendar day
        #                   PLUS bars [0, asian_end_eff) today
        # Within sub-day arrays this is just "bars before the LDN-OR anchor"
        if asian_start_eff > asian_end_eff:
            asian_mask = (sub_hour >= asian_start_eff) | (sub_hour < asian_end_eff)
        else:
            asian_mask = (sub_hour >= asian_start_eff) & (sub_hour < asian_end_eff)

        if not asian_mask.any():
            continue
        asian_high = float(sub_high[asian_mask].max())
        asian_low = float(sub_low[asian_mask].min())
        if not np.isfinite(asian_high) or not np.isfinite(asian_low) or asian_high <= asian_low:
            continue

        # Trade window: bars at hour == asian_end_eff (with minute >= ldn_or_min cooldown)
        #               through bars at hour < entry_cutoff_eff
        # Need to be careful with wrap-around (baseline doesn't wrap because end=7, cutoff=10)
        if asian_end_eff <= entry_cutoff_eff:
            tw_mask = (sub_hour > asian_end_eff) & (sub_hour < entry_cutoff_eff)
            # Include hour == asian_end_eff but only minutes >= ldn_or_min
            tw_mask = tw_mask | ((sub_hour == asian_end_eff) & (sub_min >= ldn_or_min))
        else:
            tw_mask = ((sub_hour >= asian_end_eff) | (sub_hour < entry_cutoff_eff))

        # Hard-flat boundary: bars at hour >= hard_flat_eff
        if asian_end_eff <= hard_flat_eff:
            hf_mask = (sub_hour >= hard_flat_eff)
        else:
            hf_mask = (sub_hour >= hard_flat_eff) & (sub_hour < asian_start_eff)

        # Asian range filter
        # Reference price for bps calc: open at first trade-window bar
        tw_idx = np.flatnonzero(tw_mask)
        if tw_idx.size == 0:
            continue
        ref_px = float(sub_open[tw_idx[0]])
        if ref_px <= 0:
            continue
        asian_range_bps = (asian_high - asian_low) / ref_px * 1e4
        if asian_range_bps < min_asian_range_bps:
            continue

        # Walk forward through trade window looking for first break
        entry_i_local = -1
        for k in tw_idx:
            c = sub_close[k]
            # Break detection direction = break_dir
            if break_dir > 0 and c > asian_high:
                entry_i_local = int(k) + 1   # enter next bar's open
                break
            if break_dir < 0 and c < asian_low:
                entry_i_local = int(k) + 1
                break

        if entry_i_local <= 0 or entry_i_local >= len(sub_close):
            continue

        entry_px = float(sub_open[entry_i_local])
        if entry_px <= 0:
            continue
        entry_ts = sub_ts[entry_i_local]

        # Stop = symmetric stop DISTANCE equal to Asian-range width (per lesson #17).
        # For CONT variants this matches "opposite Asian-range bound" since the entry
        # is roughly at the broken bound. For FADE variants this enforces a real
        # stop-loss in the loss direction (not the in-profit-by-construction level).
        stop_dist = asian_high - asian_low
        if position_dir > 0:
            stop_px = entry_px - stop_dist
        else:
            stop_px = entry_px + stop_dist

        # Walk to exit
        exit_i_local = -1
        exit_px = float('nan')
        exit_reason = ''
        for j in range(entry_i_local, len(sub_close)):
            bar_low = sub_low[j]
            bar_high = sub_high[j]
            # Stop hit
            if position_dir > 0 and bar_low <= stop_px:
                exit_i_local = j
                exit_px = stop_px
                exit_reason = 'stop'
                break
            if position_dir < 0 and bar_high >= stop_px:
                exit_i_local = j
                exit_px = stop_px
                exit_reason = 'stop'
                break
            # Hard flat
            if hf_mask[j]:
                exit_i_local = j
                exit_px = float(sub_open[j])
                exit_reason = 'hard_flat'
                break
            # Time exit (T+90 min)
            minutes_since_entry = (sub_ts[j] - entry_ts) / np.timedelta64(1, 'm')
            if minutes_since_entry >= t_exit_min:
                exit_i_local = j
                exit_px = float(sub_close[j])
                exit_reason = 't_exit'
                break

        if exit_i_local < 0:
            # Ran off end of day -> exit at last close
            exit_i_local = len(sub_close) - 1
            exit_px = float(sub_close[exit_i_local])
            exit_reason = 'eod'

        gross_ret = position_dir * (exit_px - entry_px) / entry_px
        cost_ret = cost_points / entry_px
        net_ret = gross_ret - cost_ret

        trades.append({
            'session_day': session_day[s],
            'entry_ts': pd.Timestamp(sub_ts[entry_i_local]),
            'exit_ts': pd.Timestamp(sub_ts[exit_i_local]),
            'entry_px': entry_px,
            'exit_px': exit_px,
            'asian_range_bps': asian_range_bps,
            'gross_ret': gross_ret,
            'net_ret': net_ret,
            'reason': exit_reason,
            'regime': label_regime(pd.Timestamp(sub_ts[entry_i_local]).year),
            'variant': variant,
        })

    rets = np.array([t['net_ret'] for t in trades], dtype=np.float64)
    return trades, rets


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, trades: list[dict], rets: np.ndarray) -> dict:
    if len(rets) == 0:
        print(f'  [{label}]: empty')
        return {}
    eq = (1.0 + rets).cumprod()
    n = len(rets)
    if n > 0:
        first_ts = trades[0]['entry_ts']
        last_ts = trades[-1]['exit_ts']
        years = max((last_ts - first_ts).days / 365.25, 1e-9)
    else:
        years = 0.0
    total = float(eq[-1] - 1.0) if len(eq) > 0 else 0.0
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    tpy = n / years
    sh = annualized_sharpe(rets, trades_per_year=tpy)
    mdd = max_drawdown(eq)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    wr = len(wins) / n
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gw / gl if gl > 0 else float('inf')
    print(f'  [{label}]')
    print(f'    period      : {first_ts.date()} -> {last_ts.date()} ({years:.1f}y)')
    print(f'    total ret   : {total * 100:+.2f}%')
    print(f'    CAGR        : {cagr * 100:+.2f}%')
    print(f'    Sharpe      : {sh:+.2f}')
    print(f'    Max DD      : {mdd * 100:+.2f}%')
    print(f'    trades      : {n}  ({tpy:.0f}/yr)')
    print(f'    win rate    : {wr * 100:.1f}%')
    print(f'    profit fac. : {pf:.2f}')
    print(f'    mean/trade  : {rets.mean() * 100:+.4f}%')
    return {'sharpe': sh, 'mdd': mdd, 'cagr': cagr, 'n': n, 'wr': wr, 'pf': pf, 'mean': rets.mean()}


def regime_breakdown(trades: list[dict], rets: np.ndarray, label: str) -> dict[str, dict]:
    out = {}
    print(f'  [{label} — regime breakdown]')
    tpy_global = tpy_from_trades(trades)
    for w in ('W1', 'W2', 'W3'):
        mask = np.array([t['regime'] == w for t in trades])
        sub_trades = [t for t in trades if t['regime'] == w]
        sub = rets[mask]
        if len(sub) < 20:
            print(f'    {w} (n={len(sub):3d}, insufficient)')
            continue
        tpy = tpy_from_trades(sub_trades) if sub_trades else tpy_global
        eq = (1 + sub).cumprod()
        n = len(sub)
        sh = annualized_sharpe(sub, trades_per_year=tpy)
        mdd = max_drawdown(eq)
        print(f'    {w} n={n:>4d}  Sh {sh:>+6.2f}  MDD {mdd * 100:>+6.2f}%  mean {sub.mean() * 100:>+7.4f}%')
        out[w] = {'sharpe': sh, 'mdd': mdd, 'n': n, 'mean': sub.mean()}
    return out


def cost_sweep(df: pd.DataFrame, variant: str) -> None:
    print(f'  [{variant} — cost sweep]')
    for cp in COST_SWEEP_PT:
        trades, rets = simulate_orb_m1(df, variant=variant, cost_points=cp)
        if len(rets) == 0:
            continue
        eq = (1 + rets).cumprod()
        sh = annualized_sharpe(rets, trades_per_year=tpy_from_trades(trades))
        mdd = max_drawdown(eq)
        flag = ' (deploy)' if cp == COST_POINTS_RT else (' (stress)' if cp == KC_COST_STRESS_PT else '')
        print(f'    cost={cp:>5.2f}pt  Sh {sh:>+6.2f}  MDD {mdd * 100:>+6.2f}%  n={len(rets):>4d}{flag}')


def dir_gap_check(df: pd.DataFrame) -> dict:
    print('  [4-variant grid + dir-gap]')
    results = {}
    for v in ('LONG_cont', 'SHORT_cont', 'LONG_fade', 'SHORT_fade'):
        trades, rets = simulate_orb_m1(df, variant=v)
        if len(rets) == 0:
            results[v] = {'sharpe': 0.0, 'mean': 0.0, 'n': 0}
            continue
        sh = annualized_sharpe(rets, trades_per_year=tpy_from_trades(trades))
        results[v] = {'sharpe': sh, 'mean': float(rets.mean()), 'n': len(rets)}
        print(f'    {v:<12s} n={len(rets):>4d}  Sh {sh:>+6.2f}  mean/trade {rets.mean() * 100:>+7.4f}%')
    # CONT Sh = avg(LONG_cont, SHORT_cont); FADE Sh = avg(LONG_fade, SHORT_fade)
    cont_sh = (results['LONG_cont']['sharpe'] + results['SHORT_cont']['sharpe']) / 2
    fade_sh = (results['LONG_fade']['sharpe'] + results['SHORT_fade']['sharpe']) / 2
    gap = cont_sh - fade_sh
    print(f'    CONT avg Sh : {cont_sh:+.2f}')
    print(f'    FADE avg Sh : {fade_sh:+.2f}')
    print(f'    dir-gap     : {gap:+.2f}   (bar: > +{KC_DIR_GAP:.2f})')
    return {'cont_sh': cont_sh, 'fade_sh': fade_sh, 'dir_gap': gap, 'detail': results}


def off_session_c1_control(df: pd.DataFrame) -> dict:
    """Lesson #-14 binding: compare in-session (LDN) vs off-session at zero cost.
    Off-session shift candidates:
      +7 hours: Asian range = today 05:00 -> 14:00 UTC; trade 14:00-17:00 UTC (NY-AM)
      +12 hours: Asian range = today 10:00 -> 19:00 UTC; trade 19:00-22:00 UTC (late NY)
    """
    print('  [Off-session C1 control (zero-cost mean comparison)]')
    out = {}
    for shift in (0, 7, 12):
        trades, _ = simulate_orb_m1(df, variant='LONG_cont', cost_points=0.0, session_shift_hours=shift)
        if not trades:
            continue
        means = np.array([t['gross_ret'] for t in trades])
        sh = annualized_sharpe(means, trades_per_year=tpy_from_trades(trades))
        label = 'LDN-open (baseline)' if shift == 0 else f'shift+{shift}h'
        print(f'    {label:<22s} n={len(trades):>4d}  zero-cost mean {means.mean() * 100:>+7.4f}%  Sh {sh:>+6.2f}')
        out[shift] = {'mean': means.mean(), 'sharpe': sh, 'n': len(trades)}
    if 0 in out:
        base_sh = out[0]['sharpe']
        best_offsession_sh = max(out[s]['sharpe'] for s in out if s != 0) if len(out) > 1 else 0.0
        delta = base_sh - best_offsession_sh
        print(f'    in-session - best-off-session delta: {delta:+.2f}  (bar: > +{KC_OFF_SESSION_DELTA:.2f})')
        out['delta'] = delta
    return out


def correlation_vs_book(trades: list[dict], rets: np.ndarray) -> None:
    """Per-trading-day PnL correlation vs deployed XAU book (xau_session daily PnL).
    Use H1 file as proxy for xau_session: Asian-handoff long 23->08 UTC, every trade day.
    """
    print('  [Correlation vs deployed XAU book (xau_session-proxy)]')
    h1_path = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv')
    if not os.path.exists(h1_path):
        print('    H1 data not available; skip')
        return
    h1 = pd.read_csv(h1_path, parse_dates=['timestamp'])
    h1['timestamp'] = pd.to_datetime(h1['timestamp'], utc=True)
    h1['date'] = h1['timestamp'].dt.date
    h1['hour'] = h1['timestamp'].dt.hour
    # xau_session daily: entry at prior 23:00 UTC, exit at 08:00 UTC same day
    closes = h1.set_index(['date', 'hour'])['close']
    daily_dates = sorted(h1['date'].unique())
    pnl_rows = []
    one_day = pd.Timedelta(days=1)
    for d in daily_dates:
        pd_ts = pd.Timestamp(d)
        prior = (pd_ts - one_day).date()
        try:
            entry = closes.loc[(prior, 23)]
            exitp = closes.loc[(d, 8)]
        except KeyError:
            continue
        pnl_rows.append({'date': d, 'session_pnl': (exitp - entry) / entry})
    sess_df = pd.DataFrame(pnl_rows).set_index('date')

    # Our strategy daily-aggregated
    our_pnl = pd.DataFrame([
        {'date': pd.Timestamp(t['entry_ts']).date(), 'our_pnl': t['net_ret']}
        for t in trades
    ])
    if our_pnl.empty:
        print('    no trades to correlate')
        return
    our_pnl = our_pnl.groupby('date')['our_pnl'].sum().to_frame()
    merged = our_pnl.join(sess_df, how='inner').dropna()
    if len(merged) < 30:
        print(f'    insufficient overlap (n={len(merged)})')
        return
    corr = merged['our_pnl'].corr(merged['session_pnl'])
    print(f'    n shared days   : {len(merged)}')
    print(f'    corr (Pearson)  : {corr:+.3f}   (bar: < +{KC_CORR_BOOK:.2f})')
    flag = 'PASS' if corr < KC_CORR_BOOK else 'FAIL'
    print(f'    verdict         : {flag}')


def kill_criteria_summary(label: str, trades: list[dict], rets: np.ndarray,
                          regime: dict, dir_gap: float, cost_stress_sh: float) -> None:
    print(f'\n  [{label} — kill criteria summary]')
    if len(rets) == 0:
        print('    EMPTY — REJECT')
        return
    eq = (1 + rets).cumprod()
    sh = annualized_sharpe(rets, trades_per_year=tpy_from_trades(trades))
    mdd = max_drawdown(eq)
    n = len(rets)

    def v(ok): return 'PASS' if ok else 'FAIL'

    checks = [
        ('#1 FULL Sh > +0.30', sh > KC_SH_FULL, f'{sh:+.2f}'),
        ('#2 W1 Sh > 0.00',    regime.get('W1', {}).get('sharpe', 0) > KC_SH_W1,
                                f'{regime.get("W1", {}).get("sharpe", float("nan")):+.2f}'),
        ('#3 W2 Sh > 0.00',    regime.get('W2', {}).get('sharpe', 0) > KC_SH_W2,
                                f'{regime.get("W2", {}).get("sharpe", float("nan")):+.2f}'),
        ('#4 W3 Sh > +0.20',   regime.get('W3', {}).get('sharpe', 0) > KC_SH_W3,
                                f'{regime.get("W3", {}).get("sharpe", float("nan")):+.2f}'),
        ('#5 MDD < 12%',       abs(mdd) < KC_MDD,            f'{mdd*100:+.2f}%'),
        ('#6 trades >= 300',   n >= KC_TRADES,               f'{n}'),
        ('#7 dir-gap > +0.40', dir_gap > KC_DIR_GAP,          f'{dir_gap:+.2f}'),
        ('#8 stress@0.30pt>0', cost_stress_sh > 0.0,          f'{cost_stress_sh:+.2f}'),
    ]
    n_pass = sum(1 for _, ok, _ in checks if ok)
    for name, ok, val in checks:
        print(f'    {name:<28s} {v(ok):4s}  ({val})')
    print(f'    -- PASS {n_pass}/{len(checks)}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section('Loading XAUUSD M1')
    if not os.path.exists(DATA_PATH):
        print(f'  {DATA_PATH} not found; run _fetch_xau_m1.py first')
        return 1
    df = load_m1()
    print(f'  bars     : {len(df):,}')
    print(f'  range    : {df["timestamp"].iloc[0]} -> {df["timestamp"].iloc[-1]}')
    print(f'  days     : {df["date"].nunique():,}')

    section('Phase 2 baseline — LONG_cont (primary), 0.20pt RT')
    trades_long, rets_long = simulate_orb_m1(df, variant='LONG_cont')
    report_run('LONG_cont baseline', trades_long, rets_long)

    section('Regime breakdown — LONG_cont')
    regime = regime_breakdown(trades_long, rets_long, 'LONG_cont')

    section('4-variant grid + direction null check (lesson #13, #-19)')
    dg = dir_gap_check(df)

    section('Cost sweep — LONG_cont')
    cost_sweep(df, 'LONG_cont')
    # Get the stress @ 0.30pt explicitly
    trades_stress, rets_stress = simulate_orb_m1(df, variant='LONG_cont', cost_points=KC_COST_STRESS_PT)
    cost_stress_sh = annualized_sharpe(rets_stress, trades_per_year=tpy_from_trades(trades_stress)) if len(rets_stress) else 0.0

    section('Off-session C1 control (lesson #-14)')
    off_session_c1_control(df)

    section('Correlation vs deployed XAU book')
    correlation_vs_book(trades_long, rets_long)

    section('Kill-criteria summary')
    kill_criteria_summary('LONG_cont baseline', trades_long, rets_long,
                          regime, dg['dir_gap'], cost_stress_sh)
    return 0


if __name__ == '__main__':
    sys.exit(main())
