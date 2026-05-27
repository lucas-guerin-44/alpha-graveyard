#!/usr/bin/env python3
"""XAUUSD Asia-range level-touch continuation — Phase 1 simulator.

Thesis: experiments/xau_asia_range/xau_asia_range.md (Phase 0 complete 2026-05-27).

Mechanism: the high/low of XAUUSD's 23-07 UTC range act as breakout-confirmation
levels during 07-21 UTC. A touch of range-high signals continuation UP (mean
+1.8 bps over 240m FULL, +5.2 bps W4); a touch of range-low signals continuation
DOWN (mirror). Real levels carry information that placebo (translated by +/-1
range-width) levels do not.

Variants tested:
  A_baseline    every touch, both directions, all touch numbers
  B_first       touch_num == 1 only (per direction per day)
  C_lon         London-confirmation: long if lon_open=UP, short if DOWN
  D_asym        long (high-touch & 1st-touch & lon_UP) + short (low-touch & 3rd+ & lon_DOWN)

Null check: each variant re-run with directions REVERSED (long on low-touch,
short on high-touch). Fade-direction Sharpe must be << continuation Sharpe.

Bullrun-isolation control: identical simulator with range window shifted to
11-19 UTC (London-session) and trade window 19 UTC -> 09 UTC next day. If the
Asia mechanism is structural (not just bullrun-driven), Asia should beat the
London-range control by Sharpe gap >= +0.30 in W4.

Cost: 2 bps RT realistic. Stress at 4 bps / 6 bps.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_asia_range/xau_asia_range_demo.py
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_M5.csv')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

T_HOLD_BARS = int(os.environ.get('HOLD_BARS', '48'))  # 48 M5 bars = 240 min default
COST_BPS_DEFAULT = 2.0    # Eightcap Raw realistic
COST_BPS_SWEEP = (0.0, 2.0, 4.0, 6.0)
WICK_MIN_FRAC = float(os.environ.get('WICK_FRAC', '0.0'))  # require wick of N*range_size beyond level

# Annualization: per-trade Sharpe x sqrt(trades_per_year)
# trades_per_year computed from actual trade count / years_in_window

# Pre-committed kill criteria
KC_SHARPE_FULL = 0.30
KC_SHARPE_W4 = 0.50
KC_MDD = 0.15
KC_TRADES = 200
KC_FADE_GAP = 0.40
KC_WF_DEG = 0.50
KC_DOW_MAX_SHARE = 0.50
KC_COST_STRESS_BP = 4.0
KC_BULLRUN_GAP = 0.30

# Two range definitions: primary Asia + bullrun-isolation control
# (range_hours = set of UTC hours, trade_hours = list of UTC hours, with
#  trade window allowed to wrap past midnight)
ASIA_CFG = {
    'name': 'asia',
    'range_hours': set(list(range(23, 24)) + list(range(0, 7))),  # 23-07 UTC
    'range_end_hour': 7,
    'trade_hours': set(range(7, 21)),  # 07-21 UTC (no wrap)
    'trade_wraps': False,
}
LONDON_CFG = {
    'name': 'london_control',
    'range_hours': set(range(11, 19)),  # 11-19 UTC
    'range_end_hour': 19,
    'trade_hours': set(list(range(19, 24)) + list(range(0, 9))),  # 19 today -> 09 tomorrow
    'trade_wraps': True,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}')


def label_regime(d) -> str:
    y = d.year
    if y <= 2019: return 'W1'
    if y <= 2021: return 'W2'
    if y <= 2023: return 'W3'
    return 'W4'


def sharpe_annual(per_trade_bps: np.ndarray, n_years: float) -> float:
    """Per-trade Sharpe annualized using actual trades-per-year."""
    r = per_trade_bps[np.isfinite(per_trade_bps)]
    if r.size < 5:
        return 0.0
    std = r.std(ddof=1)
    if std == 0:
        return 0.0
    tpy = r.size / max(n_years, 0.1)
    return float(r.mean() / std * np.sqrt(tpy))


def max_drawdown(returns_bps: np.ndarray) -> float:
    """Max drawdown in pct, from per-trade returns (bps)."""
    if len(returns_bps) == 0:
        return 0.0
    eq = (1.0 + returns_bps / 10000.0).cumprod()
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return float(-dd.min())


# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------

print(f"\nLoading {DATA_PATH} ...")
df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
df = df.sort_values('timestamp').reset_index(drop=True)
df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
df = df.reset_index(drop=True)

df['hour'] = df['timestamp'].dt.hour.astype(np.int32)
df['date'] = df['timestamp'].dt.date
df['dow'] = df['timestamp'].dt.day_name()

ts_arr = df['timestamp'].values
hour_arr = df['hour'].values
date_arr = df['date'].values
dow_arr = df['dow'].values
high_arr = df['high'].values.astype(np.float64)
low_arr = df['low'].values.astype(np.float64)
open_arr = df['open'].values.astype(np.float64)
close_arr = df['close'].values.astype(np.float64)

# Pre-compute trade_date for both configs (for ASIA, hour-23 belongs to tomorrow)
def make_trade_date(cfg):
    """trade_date = the UTC date during which post-range trading begins."""
    td = df['date'].values.copy()
    if cfg['name'] == 'asia':
        evening_mask = df['hour'].values == 23
        evening_dates = (df['timestamp'][evening_mask] + pd.Timedelta(days=1)).dt.date.values
        td[evening_mask] = evening_dates
    elif cfg['name'] == 'london_control':
        # range is 11-19, all same-day; trade window 19-23 same day, 0-9 next day.
        # Define trade_date = the date of the range bars (range_start_date).
        # Bars in trade window with hour 0-8 belong to PRIOR day's trade_date.
        early_mask = df['hour'].values < 9
        early_dates = (df['timestamp'][early_mask] - pd.Timedelta(days=1)).dt.date.values
        td[early_mask] = early_dates
    return td


# ---------------------------------------------------------------------------
# Trade generation per config
# ---------------------------------------------------------------------------

def build_trades(cfg, variant_filter_fn, reverse_direction=False):
    """Walk every trade_date for this cfg, detect touches, apply variant filter,
    generate non-overlapping trades with T_HOLD_BARS exit.

    variant_filter_fn(touch_type, touch_num, lon_open_sign, prior_ny_sign, ...) -> bool

    Returns DataFrame of trade records:
      entry_ts, exit_ts, dow, regime, direction (+1 long, -1 short),
      entry_price, exit_price, gross_bps (pre-cost), touch_type, touch_num,
      lon_open_sign, prior_ny_sign, range_size_bps
    """
    trade_date_arr = make_trade_date(cfg)
    day_idxs = defaultdict(list)
    for i in range(len(df)):
        day_idxs[trade_date_arr[i]].append(i)
    day_idxs = {k: np.array(v, dtype=np.int64) for k, v in day_idxs.items()}

    range_hours = cfg['range_hours']
    trade_hours = cfg['trade_hours']

    trades = []
    for d, idxs in day_idxs.items():
        hours = hour_arr[idxs]
        range_mask = np.array([h in range_hours for h in hours])
        trade_mask = np.array([h in trade_hours for h in hours])
        range_idxs = idxs[range_mask]
        trade_idxs = idxs[trade_mask]
        if len(range_idxs) < 12 or len(trade_idxs) < 24:
            continue
        r_high = float(high_arr[range_idxs].max())
        r_low = float(low_arr[range_idxs].min())
        r_size = r_high - r_low
        if r_size <= 0:
            continue
        r_mid = (r_high + r_low) / 2.0
        r_size_bps = r_size / r_mid * 10000.0

        # Prior-NY direction (yesterday's 13-20 UTC return)
        yesterday = (pd.Timestamp(d) - pd.Timedelta(days=1)).date()
        prior_ny_sign = 'NA'
        if yesterday in day_idxs:
            y_idxs = day_idxs[yesterday]
            y_hours = hour_arr[y_idxs]
            ny_mask = (y_hours >= 13) & (y_hours < 21)
            ny_idxs = y_idxs[ny_mask]
            if len(ny_idxs) >= 24:
                ny_open_p = float(open_arr[ny_idxs[0]])
                ny_close_p = float(close_arr[ny_idxs[-1]])
                ny_ret = ny_close_p - ny_open_p
                prior_ny_sign = 'UP' if ny_ret > 0 else 'DOWN' if ny_ret < 0 else 'NA'

        # London-open direction = first 30 min of the trade window
        first_trade_bar = trade_idxs[0]
        if len(trade_idxs) >= 6:
            lo_open = float(open_arr[trade_idxs[0]])
            lo_close = float(close_arr[trade_idxs[5]])
            lo_ret = lo_close - lo_open
            lon_open_sign = 'UP' if lo_ret > 0 else 'DOWN' if lo_ret < 0 else 'NA'
        else:
            lon_open_sign = 'NA'

        # Touch detection
        t_high = high_arr[trade_idxs]
        t_low = low_arr[trade_idxs]
        t_close = close_arr[trade_idxs]
        t_hours = hour_arr[trade_idxs]
        t_ts = ts_arr[trade_idxs]
        t_dow = dow_arr[trade_idxs]

        if WICK_MIN_FRAC > 0:
            wick_thresh = WICK_MIN_FRAC * r_size
            above_high = t_high >= (r_high + wick_thresh)
            below_low = t_low <= (r_low - wick_thresh)
        else:
            above_high = t_high >= r_high
            below_low = t_low <= r_low

        high_first = above_high.copy()
        low_first = below_low.copy()
        if len(high_first) > 1:
            high_first[1:] = above_high[1:] & (~above_high[:-1])
            low_first[1:] = below_low[1:] & (~below_low[:-1])

        # Build event list: (local_i, touch_type, touch_num)
        events = []
        h_count = 0
        for li in np.where(high_first)[0]:
            h_count += 1
            events.append((int(li), 'high', h_count))
        l_count = 0
        for li in np.where(low_first)[0]:
            l_count += 1
            events.append((int(li), 'low', l_count))
        events.sort(key=lambda x: x[0])

        # Generate non-overlapping trades
        current_exit_local = -1
        for li, ttype, tnum in events:
            if li < current_exit_local:
                continue
            allow = variant_filter_fn(
                touch_type=ttype, touch_num=tnum,
                lon_open_sign=lon_open_sign,
                prior_ny_sign=prior_ny_sign,
            )
            if not allow:
                continue
            # Direction: continuation by default. high-touch -> LONG, low-touch -> SHORT
            direction = +1 if ttype == 'high' else -1
            if reverse_direction:
                direction = -direction

            entry_price = float(t_close[li])
            entry_ts = t_ts[li]
            entry_dow = t_dow[li]

            exit_local = min(li + T_HOLD_BARS, len(t_close) - 1)
            exit_price = float(t_close[exit_local])
            exit_ts = t_ts[exit_local]

            gross_bps = (exit_price - entry_price) / entry_price * 10000.0 * direction

            trades.append({
                'entry_ts': entry_ts, 'exit_ts': exit_ts,
                'dow': entry_dow, 'regime': label_regime(pd.Timestamp(d)),
                'direction': direction, 'entry_price': entry_price,
                'exit_price': exit_price, 'gross_bps': gross_bps,
                'touch_type': ttype, 'touch_num': tnum,
                'lon_open_sign': lon_open_sign, 'prior_ny_sign': prior_ny_sign,
                'range_size_bps': r_size_bps, 'trade_date': d,
            })
            current_exit_local = exit_local

    return pd.DataFrame(trades)


# ---------------------------------------------------------------------------
# Variant filters
# ---------------------------------------------------------------------------

def filt_A_baseline(**kw):
    return True


def filt_B_first(touch_num=None, **kw):
    return touch_num == 1


def filt_C_lon(touch_type=None, lon_open_sign=None, **kw):
    if touch_type == 'high':
        return lon_open_sign == 'UP'
    return lon_open_sign == 'DOWN'


def filt_D_asym(touch_type=None, touch_num=None, lon_open_sign=None, **kw):
    if touch_type == 'high':
        return touch_num == 1 and lon_open_sign == 'UP'
    return touch_num >= 3 and lon_open_sign == 'DOWN'


VARIANTS = [
    ('A_baseline', filt_A_baseline),
    ('B_first', filt_B_first),
    ('C_lon', filt_C_lon),
    ('D_asym', filt_D_asym),
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def years_span(trades: pd.DataFrame) -> float:
    if len(trades) == 0:
        return 0.0
    return (trades['exit_ts'].max() - trades['entry_ts'].min()) / np.timedelta64(1, 'D') / 365.25


def report_variant(variant_name, trades_df, cost_bps=COST_BPS_DEFAULT):
    if len(trades_df) == 0:
        print(f"  {variant_name}: NO TRADES")
        return None
    net_bps = trades_df['gross_bps'].values - cost_bps
    yrs = years_span(trades_df)
    tpy = len(trades_df) / max(yrs, 0.1)
    sh_full = sharpe_annual(net_bps, yrs)
    mdd = max_drawdown(net_bps)
    # Per-regime
    reg_sh = {}
    for reg in ['W1', 'W2', 'W3', 'W4']:
        sub = trades_df[trades_df['regime'] == reg]
        if len(sub) >= 10:
            rb = sub['gross_bps'].values - cost_bps
            ryrs = years_span(sub)
            reg_sh[reg] = sharpe_annual(rb, ryrs)
        else:
            reg_sh[reg] = np.nan
    mean_bps = net_bps.mean()
    win_rate = (net_bps > 0).mean() * 100
    pf = (net_bps[net_bps > 0].sum() / -net_bps[net_bps < 0].sum()
          if (net_bps < 0).any() else float('inf'))
    return {
        'variant': variant_name, 'n': len(trades_df), 'tpy': tpy,
        'sh_full': sh_full, 'sh_W1': reg_sh['W1'], 'sh_W2': reg_sh['W2'],
        'sh_W3': reg_sh['W3'], 'sh_W4': reg_sh['W4'],
        'mdd': mdd, 'mean_bps': mean_bps, 'wr': win_rate, 'pf': pf,
    }


def print_summary(rows, title):
    print(f"\n  -- {title} (cost = {COST_BPS_DEFAULT} bp) --")
    print(f"  {'variant':>12s} {'n':>5s} {'tpy':>5s} "
          f"{'Sh_full':>8s} {'Sh_W1':>7s} {'Sh_W2':>7s} {'Sh_W3':>7s} {'Sh_W4':>7s} "
          f"{'MDD':>6s} {'mean':>7s} {'WR':>5s} {'PF':>5s}")
    for r in rows:
        if r is None: continue
        print(f"  {r['variant']:>12s} {r['n']:>5d} {r['tpy']:>5.0f} "
              f"{r['sh_full']:>+7.2f} {r['sh_W1']:>+6.2f} {r['sh_W2']:>+6.2f} "
              f"{r['sh_W3']:>+6.2f} {r['sh_W4']:>+6.2f} "
              f"{r['mdd']*100:>5.1f}% {r['mean_bps']:>+6.1f} "
              f"{r['wr']:>4.1f}% {r['pf']:>5.2f}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

section("XAUUSD Asia-Range Phase 1 — kill-criteria battery")
print(f"Cost = {COST_BPS_DEFAULT} bp RT. Hold = {T_HOLD_BARS} M5 bars = {T_HOLD_BARS*5} min.")

# 1. Run all variants on Asia config
section("1. ASIA config — continuation direction (primary)")
asia_rows = []
asia_trades = {}
for vname, vfn in VARIANTS:
    tr = build_trades(ASIA_CFG, vfn, reverse_direction=False)
    asia_trades[vname] = tr
    asia_rows.append(report_variant(vname, tr))
print_summary(asia_rows, 'ASIA continuation')

# 2. Fade null-check: same Asia variants with reversed direction
section("2. ASIA config — FADE direction null (reversed)")
fade_rows = []
fade_trades = {}
for vname, vfn in VARIANTS:
    tr = build_trades(ASIA_CFG, vfn, reverse_direction=True)
    fade_trades[vname] = tr
    fade_rows.append(report_variant(vname, tr))
print_summary(fade_rows, 'ASIA fade (null)')

# 3. London-range bullrun-isolation control
section("3. LONDON-RANGE control (bullrun-isolation)")
lon_rows = []
lon_trades = {}
for vname, vfn in VARIANTS:
    tr = build_trades(LONDON_CFG, vfn, reverse_direction=False)
    lon_trades[vname] = tr
    lon_rows.append(report_variant(vname, tr))
print_summary(lon_rows, 'LONDON-RANGE continuation (control)')

# 4. Continuation-vs-fade gap per variant
section("4. Continuation-vs-fade Sharpe gap (FULL)")
print(f"  {'variant':>12s} {'cont_full':>11s} {'fade_full':>11s} {'gap':>7s} {'pass':>6s}")
for ar, fr in zip(asia_rows, fade_rows):
    if ar is None or fr is None: continue
    gap = ar['sh_full'] - fr['sh_full']
    ok = 'PASS' if gap >= KC_FADE_GAP else 'fail'
    print(f"  {ar['variant']:>12s} {ar['sh_full']:>+10.2f} {fr['sh_full']:>+10.2f} "
          f"{gap:>+6.2f} {ok:>6s}")

# 5. Bullrun-isolation gap per variant (Asia W4 - London W4)
section("5. Bullrun-isolation gap (Asia W4 vs London-control W4)")
print(f"  {'variant':>12s} {'asia_W4':>9s} {'lon_W4':>9s} {'gap':>7s} {'pass':>6s}")
for ar, lr in zip(asia_rows, lon_rows):
    if ar is None or lr is None: continue
    a4 = ar['sh_W4'] if np.isfinite(ar['sh_W4']) else 0
    l4 = lr['sh_W4'] if np.isfinite(lr['sh_W4']) else 0
    gap = a4 - l4
    ok = 'PASS' if gap >= KC_BULLRUN_GAP else 'fail'
    print(f"  {ar['variant']:>12s} {a4:>+8.2f} {l4:>+8.2f} {gap:>+6.2f} {ok:>6s}")

# 6. Cost stress
section("6. Cost-stress: Sharpe FULL at each cost level")
print(f"  {'variant':>12s} " + "  ".join([f"{c}bp".rjust(7) for c in COST_BPS_SWEEP]))
for vname, _ in VARIANTS:
    tr = asia_trades[vname]
    if len(tr) == 0:
        continue
    yrs = years_span(tr)
    gross = tr['gross_bps'].values
    parts = []
    for c in COST_BPS_SWEEP:
        nb = gross - c
        sh = sharpe_annual(nb, yrs)
        parts.append(f"{sh:>+6.2f}")
    print(f"  {vname:>12s} " + "  ".join(parts))

# 7. Walk-forward (5 rolling 3y-IS / 2y-OOS) — Sharpe on OOS, mean deg
section("7. Walk-forward: 5 rolling 3y-IS / 2y-OOS, mean Sharpe-degradation")
SPLITS = [
    ('S1', 2018, 2020, 2021, 2022),
    ('S2', 2019, 2021, 2022, 2023),
    ('S3', 2020, 2022, 2023, 2024),
    ('S4', 2021, 2023, 2024, 2025),
    ('S5', 2022, 2024, 2025, 2026),
]
print(f"  {'variant':>12s} {'split':>5s} {'IS Sh':>7s} {'OOS Sh':>7s} {'deg':>6s}")
deg_summary = {}
for vname, _ in VARIANTS:
    tr = asia_trades[vname].copy()
    if len(tr) == 0: continue
    tr['year'] = pd.to_datetime(tr['entry_ts']).dt.year
    degs = []
    for sn, isy0, isy1, oosy0, oosy1 in SPLITS:
        is_sub = tr[(tr['year'] >= isy0) & (tr['year'] <= isy1)]
        oos_sub = tr[(tr['year'] >= oosy0) & (tr['year'] <= oosy1)]
        if len(is_sub) < 20 or len(oos_sub) < 20:
            continue
        is_sh = sharpe_annual(is_sub['gross_bps'].values - COST_BPS_DEFAULT,
                              years_span(is_sub))
        oos_sh = sharpe_annual(oos_sub['gross_bps'].values - COST_BPS_DEFAULT,
                               years_span(oos_sub))
        deg = is_sh - oos_sh
        degs.append(deg)
        print(f"  {vname:>12s} {sn:>5s} {is_sh:>+6.2f} {oos_sh:>+6.2f} {deg:>+5.2f}")
    deg_summary[vname] = np.mean(degs) if degs else np.nan

print(f"\n  Mean degradation per variant:")
for v, d in deg_summary.items():
    flag = 'PASS' if d < KC_WF_DEG else 'fail'
    print(f"    {v:>12s}  mean_deg = {d:>+5.2f}  {flag}")

# 8. DOW concentration
section("8. Day-of-week concentration (% of trades per DOW)")
print(f"  {'variant':>12s} " + "  ".join([f"{d[:3]}".rjust(6) for d in
                                            ['Monday', 'Tuesday', 'Wednesday',
                                             'Thursday', 'Friday']]))
for vname, _ in VARIANTS:
    tr = asia_trades[vname]
    if len(tr) == 0: continue
    parts = []
    for d in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
        share = (tr['dow'] == d).mean() * 100
        parts.append(f"{share:>5.1f}%")
    print(f"  {vname:>12s} " + "  ".join(parts))

# 9. Pre-committed kill-criteria scoreboard
section("9. Pre-committed kill-criteria scoreboard")
print(f"  {'variant':>12s} {'Sh_full':>7s} {'Sh_W4':>7s} {'MDD':>6s} {'n':>5s} "
      f"{'fadegap':>7s} {'WF_deg':>6s} {'Sh@4bp':>6s} {'bullgap':>7s} {'pass':>5s}")
for ar, fr, lr in zip(asia_rows, fade_rows, lon_rows):
    if ar is None: continue
    vname = ar['variant']
    fade_gap = ar['sh_full'] - (fr['sh_full'] if fr else 0)
    a4 = ar['sh_W4'] if np.isfinite(ar['sh_W4']) else 0
    l4 = lr['sh_W4'] if (lr and np.isfinite(lr['sh_W4'])) else 0
    bull_gap = a4 - l4
    tr = asia_trades[vname]
    yrs = years_span(tr)
    sh_4 = sharpe_annual(tr['gross_bps'].values - 4.0, yrs) if len(tr) else 0
    wf_deg = deg_summary.get(vname, np.nan)

    checks = [
        ar['sh_full'] >= KC_SHARPE_FULL,
        a4 >= KC_SHARPE_W4,
        ar['mdd'] <= KC_MDD,
        ar['n'] >= KC_TRADES,
        fade_gap >= KC_FADE_GAP,
        (wf_deg < KC_WF_DEG) if np.isfinite(wf_deg) else False,
        sh_4 > 0,
        bull_gap >= KC_BULLRUN_GAP,
    ]
    score = sum(checks)
    verdict = 'PASS' if score >= 7 else 'fail'
    print(f"  {vname:>12s} {ar['sh_full']:>+6.2f} {a4:>+6.2f} {ar['mdd']*100:>5.1f}% "
          f"{ar['n']:>5d} {fade_gap:>+6.2f} {wf_deg:>+5.2f} {sh_4:>+5.2f} "
          f"{bull_gap:>+6.2f} {score}/8 {verdict}")

print(f"\nDone. Pre-committed bar: PASS = >=7/8 criteria cleared.")
