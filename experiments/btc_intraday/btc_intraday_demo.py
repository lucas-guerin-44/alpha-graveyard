#!/usr/bin/env python3
"""BTCUSD intraday Tokyo-open Phase 1 simulator (Variant E).

Thesis: experiments/btc_intraday/btc_intraday.md

Strategy:
  Trigger: weekday in {Tue, Thu, Fri} (UTC) AND |prior-24h zscore| > 1.0
  Entry:   long BTCUSD at close of 23:00 UTC H1 bar (~23:55 UTC tape)
  Exit:    close of (23:00 + DEFAULT_HOLD_HOURS) H1 bar
  Cost:    5 bps RT baseline (Eightcap-verified median during 00-07 UTC)

Run:
    venv/Scripts/python.exe experiments/btc_intraday/btc_intraday_demo.py
"""
from __future__ import annotations

import os
import sys
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M5.csv')

ENTRY_HOUR_UTC = 0
ENTRY_DOWS = ('Tuesday', 'Thursday', 'Friday')
PRIOR_24H_ZSCORE_THRESHOLD = float(os.environ.get('BTC_Z_THR', 1.0))
ATR_DAYS = 20
DEFAULT_HOLD_HOURS = int(os.environ.get('BTC_HOLD', 2))
COST_RT_BPS = float(os.environ.get('BTC_COST_BPS', 5.0))

WINDOWS = [
    ('W1 2018-2019', '2018-01-01', '2019-12-31'),
    ('W2 2020-2021', '2020-01-01', '2021-12-31'),
    ('W3 2022-2023', '2022-01-01', '2023-12-31'),
    ('W4 2024-2026', '2024-01-01', '2026-04-30'),
]
SUB_SLICES = [
    ('W4-2024',     '2024-01-01', '2024-12-31'),
    ('W4-2025-26',  '2025-01-01', '2026-04-30'),
    ('W4-2025',     '2025-01-01', '2025-12-31'),
    ('W4-2026',     '2026-01-01', '2026-04-30'),
]

# Pre-committed kill criteria (per thesis)
KILL_2025_26_NET_SHARPE = 0.30
KILL_2026_QUARTER_MEAN = 0.02   # %
KILL_W4_FULL_SHARPE = 1.0
KILL_MDD_PCT = -20.0            # negative is the threshold
KILL_TRADES_PER_YR = 50
KILL_FADE_GAP = 0.40
KILL_NET_SH_AT_10BP = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f"\n{'=' * 88}\n  {t}\n{'=' * 88}\n")


def annualized_sharpe(r: np.ndarray, trades_per_year: float) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2 or trades_per_year <= 0:
        return 0.0
    s = float(r.std(ddof=1))
    if s == 0 or not np.isfinite(s):
        return 0.0
    return float(r.mean() / s * np.sqrt(trades_per_year))


def max_drawdown_pct(r_pct: np.ndarray) -> float:
    """Compounding equity MDD, repo convention (matches orb_demo/lunch_fade).

    r_pct is per-trade return in percent (e.g. +0.50 = +0.5%). Builds the
    multiplicative equity curve (1 + r/100).cumprod() and returns the worst
    relative drawdown as a percent (negative).
    """
    if r_pct.size == 0:
        return 0.0
    eq = np.cumprod(1.0 + r_pct / 100.0)
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    return float(dd.min()) * 100.0


def trades_per_year_est(timestamps: np.ndarray, n: int) -> float:
    if n < 2:
        return 0.0
    span_days = (timestamps[-1] - timestamps[0]) / np.timedelta64(1, 'D')
    years = float(span_days) / 365.25
    return n / years if years > 0 else 0.0


# ---------------------------------------------------------------------------
# Load and prep
# ---------------------------------------------------------------------------

def load_h1_with_signal() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (timestamps_np, close_np, entry_mask, prior_24h_zscore_np)."""
    m5 = pd.read_csv(M5_PATH, parse_dates=['timestamp'])
    m5['timestamp'] = pd.to_datetime(m5['timestamp'], utc=True, format='mixed')
    m5 = m5.sort_values('timestamp').reset_index(drop=True)
    m5 = m5[m5['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    m5['h1_bucket'] = m5['timestamp'].dt.floor('1h')
    h1 = (
        m5.groupby('h1_bucket', as_index=False)
          .agg(open=('open', 'first'),
               high=('high', 'max'),
               low=('low', 'min'),
               close=('close', 'last'))
          .rename(columns={'h1_bucket': 'timestamp'})
    )
    h1 = h1.sort_values('timestamp').reset_index(drop=True)
    h1['hour'] = h1['timestamp'].dt.hour
    h1['dow'] = h1['timestamp'].dt.day_name()

    # Prior-24h return: close 24 H1 bars ago
    h1['close_shift_24'] = h1['close'].shift(24)
    h1['prior_24h_ret_pct'] = (
        (h1['close'] - h1['close_shift_24']) / h1['close_shift_24'] * 100.0
    )

    # Daily-cadence ATR on hour-00 bars (one sample per UTC day)
    hour0 = h1[h1['hour'] == ENTRY_HOUR_UTC].copy()
    hour0['atr_pct'] = (
        hour0['prior_24h_ret_pct']
        .rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1).shift(1)
    )
    hour0['prior_24h_zscore'] = hour0['prior_24h_ret_pct'] / hour0['atr_pct']
    h1 = h1.merge(
        hour0[['timestamp', 'prior_24h_zscore']],
        on='timestamp', how='left',
    )

    entry_mask = (
        (h1['hour'] == ENTRY_HOUR_UTC)
        & (h1['dow'].isin(ENTRY_DOWS))
        & (h1['prior_24h_zscore'].abs() > PRIOR_24H_ZSCORE_THRESHOLD)
    ).to_numpy()

    timestamps_np = h1['timestamp'].to_numpy()
    close_np = h1['close'].to_numpy()
    z_np = h1['prior_24h_zscore'].to_numpy()
    return timestamps_np, close_np, entry_mask, z_np


# ---------------------------------------------------------------------------
# Simulator (numpy-indexed, per CLAUDE.md PRIORITIZE NUMPY rule)
# ---------------------------------------------------------------------------

def simulate(
    timestamps: np.ndarray,
    close: np.ndarray,
    entry_mask: np.ndarray,
    hold_hours: int,
    cost_rt_bps: float,
    direction: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (per-trade net returns in %, entry timestamps)."""
    entry_indices = np.flatnonzero(entry_mask)
    cost_pct = cost_rt_bps / 100.0  # bps -> percent

    out_rets = []
    out_ts = []
    n = len(close)
    for ei in entry_indices:
        # Entry price = close of the bar BEFORE the hour-00 label bar
        if ei == 0:
            continue
        entry_idx = ei - 1
        exit_idx = entry_idx + hold_hours
        if exit_idx >= n:
            continue
        p_in = close[entry_idx]
        p_out = close[exit_idx]
        if not (np.isfinite(p_in) and np.isfinite(p_out)) or p_in <= 0:
            continue
        gross_pct = direction * (p_out - p_in) / p_in * 100.0
        net_pct = gross_pct - cost_pct
        out_rets.append(net_pct)
        out_ts.append(timestamps[ei])
    return np.asarray(out_rets), np.asarray(out_ts, dtype='datetime64[ns]')


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, rets: np.ndarray, ts: np.ndarray) -> dict:
    n = rets.size
    if n < 5:
        print(f"  {label:<28s} n={n} (too sparse)")
        return {'label': label, 'n': n, 'sharpe': float('nan'),
                'mean': float('nan'), 'mdd': float('nan')}
    tpy = trades_per_year_est(ts, n)
    sh = annualized_sharpe(rets, tpy)
    mdd = max_drawdown_pct(rets)
    mean = float(rets.mean())
    std = float(rets.std(ddof=1))
    win = float((rets > 0).mean() * 100.0)
    print(f"  {label:<28s} n={n:>4d} tpy={tpy:>5.0f} mean={mean:+.4f}% "
          f"std={std:.4f}% Sh={sh:+.2f} MDD={mdd:+.2f}% WR={win:.0f}%")
    return {'label': label, 'n': n, 'tpy': tpy, 'sharpe': sh,
            'mdd': mdd, 'mean': mean, 'std': std, 'win_rate': win}


def slice_by_dates(ts: np.ndarray, rets: np.ndarray,
                   start: str, end: str) -> tuple[np.ndarray, np.ndarray]:
    ts_pd = pd.to_datetime(ts, utc=True)
    s = pd.Timestamp(start, tz='UTC').tz_convert(None).to_datetime64()
    e = pd.Timestamp(end, tz='UTC').tz_convert(None).to_datetime64()
    # ts is already datetime64[ns] (naive). Build mask manually.
    ts_naive = ts.astype('datetime64[ns]')
    mask = (ts_naive >= s) & (ts_naive <= e)
    return rets[mask], ts[mask]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    timestamps, close, entry_mask, z_np = load_h1_with_signal()
    n_h1 = len(timestamps)
    n_entries = int(entry_mask.sum())
    span_days = (timestamps[-1] - timestamps[0]) / np.timedelta64(1, 'D')
    span_years = float(span_days) / 365.25
    print(f"  H1 bars loaded: {n_h1:,}  ({span_years:.2f} years)")
    print(f"  Entries pre-filter (hour-00 UTC bars): "
          f"{int(((entry_mask) | (pd.Series(z_np).abs() > 0)).sum()):,}  (informational)")
    print(f"  Entries POST-filter (Variant E trigger): {n_entries:,}  "
          f"({n_entries / span_years:.0f}/yr)")
    print(f"  Config: hold={DEFAULT_HOLD_HOURS}h, "
          f"|z|>{PRIOR_24H_ZSCORE_THRESHOLD}, "
          f"DOW={set(ENTRY_DOWS)}, "
          f"cost={COST_RT_BPS}bp RT")

    # === BASELINE ===
    section('BASELINE (Variant E, long-only, 2h hold, 5 bps RT)')
    rets, ts = simulate(timestamps, close, entry_mask,
                        DEFAULT_HOLD_HOURS, COST_RT_BPS, direction=+1)
    baseline = report_run('BASELINE LONG', rets, ts)

    # === NULL CHECK (short variant) ===
    section('Null check -- same triggers, SHORT direction')
    rets_short, ts_short = simulate(timestamps, close, entry_mask,
                                    DEFAULT_HOLD_HOURS, COST_RT_BPS, direction=-1)
    nullc = report_run('NULL SHORT', rets_short, ts_short)
    fade_gap = baseline['sharpe'] - nullc['sharpe']
    print(f"  Fade-gap (long Sh - short Sh): {fade_gap:+.2f}  "
          f"(need > +{KILL_FADE_GAP})")

    # === HOLD-WINDOW SUB-SWEEP ===
    section('Hold-window sub-sweep (1/2/3/4 hours)')
    for h in (1, 2, 3, 4):
        rh, th = simulate(timestamps, close, entry_mask, h, COST_RT_BPS, direction=+1)
        report_run(f'hold={h}h', rh, th)

    # === REGIME BREAKDOWN ===
    section('Regime breakdown (W1-W4)')
    for wname, ws, we in WINDOWS:
        r_, t_ = slice_by_dates(ts, rets, ws, we)
        report_run(wname, r_, t_)

    # === W4 SUB-SLICES (THE BINDING TEST) ===
    section('W4 sub-slices -- the binding kill criterion')
    sub_results = {}
    for sname, ws, we in SUB_SLICES:
        r_, t_ = slice_by_dates(ts, rets, ws, we)
        sub_results[sname] = report_run(sname, r_, t_)

    # === COST SENSITIVITY ===
    section('Cost sensitivity (RT bps)')
    print(f"  {'cost':>6s} {'full Sh':>8s} {'full net mean':>14s} "
          f"{'W4 Sh':>7s} {'2025-26 Sh':>11s} {'2025-26 net mean':>17s}")
    for cost_bps in (3.0, 5.0, 7.0, 10.0):
        rc, tc = simulate(timestamps, close, entry_mask,
                          DEFAULT_HOLD_HOURS, cost_bps, direction=+1)
        full_sh = annualized_sharpe(rc, trades_per_year_est(tc, rc.size))
        full_mean = float(rc.mean()) if rc.size else 0.0
        rw4, tw4 = slice_by_dates(tc, rc, '2024-01-01', '2026-04-30')
        sh_w4 = annualized_sharpe(rw4, trades_per_year_est(tw4, rw4.size))
        r2526, t2526 = slice_by_dates(tc, rc, '2025-01-01', '2026-04-30')
        sh_2526 = annualized_sharpe(r2526, trades_per_year_est(t2526, r2526.size))
        mean_2526 = float(r2526.mean()) if r2526.size else 0.0
        print(f"  {cost_bps:>5.1f}  {full_sh:>+7.2f}  {full_mean:>+12.4f}%  "
              f"{sh_w4:>+6.2f}  {sh_2526:>+10.2f}  {mean_2526:>+15.4f}%")

    # === W4 QUARTERLY TRAJECTORY ===
    section('W4 quarterly trajectory (in lieu of formal walk-forward)')
    rw4, tw4 = slice_by_dates(ts, rets, '2024-01-01', '2026-04-30')
    if rw4.size > 0:
        ts_w4_pd = pd.to_datetime(tw4)
        df_w4 = pd.DataFrame({
            'q': ts_w4_pd.to_period('Q').astype(str),
            'r': rw4,
        })
        print(f"  {'quarter':<10s} {'n':>4s} {'mean':>10s} {'std':>9s} {'Sh':>6s}")
        quarter_sharpes = []
        for q, sub in df_w4.groupby('q'):
            n = len(sub)
            if n < 3:
                continue
            m = sub['r'].mean()
            s = sub['r'].std(ddof=1)
            sh = m / s * np.sqrt(60.0) if s > 0 else 0.0  # ~60 trades/yr post-filter
            quarter_sharpes.append((q, n, m, sh))
            print(f"  {q:<10s} {n:>4d} {m:+.4f}% {s:.4f}% {sh:+.2f}")

    # === KILL CRITERIA SUMMARY ===
    section('Pre-committed kill criteria check (Phase 1)')

    def check(label: str, value: float, threshold: float,
              op: str = '>', precision: int = 2) -> bool:
        ok = (value > threshold) if op == '>' else (value < threshold)
        flag = 'PASS' if ok else 'FAIL'
        print(f"  [{flag}] {label:<55s} actual {value:+.{precision}f}  "
              f"need {op} {threshold:+.{precision}f}")
        return ok

    passed = 0
    total = 0

    # 1. 2025-2026 net Sharpe > +0.30
    sh_2526 = sub_results.get('W4-2025-26', {}).get('sharpe', float('nan'))
    total += 1; passed += int(check('2025-2026 net Sharpe', sh_2526, KILL_2025_26_NET_SHARPE))

    # 2. 2026 mean trade return > +0.02% (proxy: W4-2026 slice)
    mean_2026 = sub_results.get('W4-2026', {}).get('mean', float('nan'))
    total += 1; passed += int(check('W4-2026 mean trade return (%)',
                                    mean_2026, KILL_2026_QUARTER_MEAN, precision=4))

    # 3. Full-W4 Sharpe > +1.0
    sh_w4 = next((report_run('_W4', *slice_by_dates(ts, rets, ws, we))['sharpe']
                  for w, ws, we in WINDOWS if w.startswith('W4')), float('nan'))
    total += 1; passed += int(check('Full-W4 Sharpe', sh_w4, KILL_W4_FULL_SHARPE))

    # 4. MDD < 20% (i.e., mdd > -20.0%)
    mdd = baseline['mdd']
    total += 1; passed += int(check('MDD (cumulative bps)', mdd, KILL_MDD_PCT))

    # 5. Trades/yr >= 50
    tpy = baseline['tpy']
    total += 1; passed += int(check('Trades/yr', tpy, KILL_TRADES_PER_YR))

    # 6. Fade-gap > +0.40
    total += 1; passed += int(check('Fade-gap (long - short Sh)',
                                    fade_gap, KILL_FADE_GAP))

    # 7. Cost-robustness: net Sharpe at 10bp RT > 0
    r10, t10 = simulate(timestamps, close, entry_mask,
                        DEFAULT_HOLD_HOURS, 10.0, direction=+1)
    sh_10 = annualized_sharpe(r10, trades_per_year_est(t10, r10.size))
    total += 1; passed += int(check('Cost-robustness (Sh at 10bp RT)',
                                    sh_10, KILL_NET_SH_AT_10BP))

    print(f"\n  Phase 1 verdict: {passed}/{total} kill criteria pass.")
    if passed == total:
        print("  -> PASS_PENDING_VALIDATION. Proceed to Phase 2 (statistical battery).")
    elif passed >= total - 1:
        print("  -> MARGINAL. One criterion failed; review the failing diagnostic.")
    else:
        print("  -> FAIL. Multiple criteria failed; KEEP_FOR_REFERENCE.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
