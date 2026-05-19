#!/usr/bin/env python3
"""USOUSD overnight Asia-session hold (Variant C: 22:00 UTC -> 07:00 UTC, 9h).

Thesis: experiments/wti_session/wti_session.md (Phase 0 complete 2026-05-16).

Mechanism: Asian-session structural drift up on USOUSD. Asia 23-07 UTC
cumulative drift +5.41 bps/day FULL, all 4 regimes positive (+8.37/+2.86/
+5.60/+4.83). Hour 10 UTC standalone t=+2.08. Variant C captures the
overnight 22->07 UTC window (entry at Asian session start, exit at
European morning open).

Variants tested:
  baseline      Variant C unconditional (long every trade-day 22->07 UTC)
  filter_z      Variant C with prior-US |zscore| > 1.0 filter
  filter_dnmed  Variant C with prior-US DOWN + medium-magnitude filter
                (PRIOR-US-DOWN AND 0.5 < |z| < 1.5)
  short_null    Same entry/exit but direction=short (null check)

Cost: 5 bps RT realistic (Eightcap Raw USOUSD ~3-5 bp spread + ~1 bp commission).
Stress at 0/3/5/8/12 bp.

Pre-committed kill criteria (from thesis doc):
  Full Sharpe > +0.30 at 5bp
  W4 Sharpe > +0.40 at 5bp (binding per W4-floor rule)
  MDD < 20%
  Trade count >= 200
  Fade-gap > +0.40 vs short_null
  Walk-forward mean degradation < 0.6
  Cost stress at 8bp: Sharpe > 0
  All-regime Sharpe > -0.3

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/wti_session/wti_session_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'USOUSD_H1.csv')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENTRY_HOUR = 22   # UTC; prior day's 22:00-23:00 bar close = entry price
EXIT_HOUR = 7     # UTC; same-day 06:00-07:00 bar close = exit price
ENTRY_IS_PRIOR_DAY = True

US_START_HOUR = 13       # US morning ~ 09 ET
US_END_HOUR = 21         # exclusive — bars starting at 13..20 (US close 16 ET = 20 UTC)
ATR_DAYS = 20

# Cost in basis points RT (Eightcap Raw realistic for USOUSD CFD)
COST_BPS_DEFAULT = 5.0
COST_BPS_SWEEP = (0.0, 3.0, 5.0, 8.0, 12.0)

TRADES_PER_YEAR_ANNUAL = 252

# Pre-committed kill criteria
KC_SHARPE_FULL = 0.30
KC_SHARPE_W4 = 0.40
KC_MDD = 0.20
KC_TRADES = 200
KC_FADE_GAP = 0.40
KC_WF_DEG = 0.60
KC_DOW_MAX_SHARE = 0.50
KC_COST_STRESS_BP = 8.0
KC_REGIME_FLOOR = -0.30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 96}\n  {t}\n{"=" * 96}\n')


def label_regime(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2019:
        return 'W1'
    if y <= 2021:
        return 'W2'
    if y <= 2023:
        return 'W3'
    return 'W4'


def annualized_sharpe(r: np.ndarray, trades_per_year: float = TRADES_PER_YEAR_ANNUAL) -> float:
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


def fmt_pct(x: float, decimals: int = 4) -> str:
    return f'{x * 100:+.{decimals}f}%'


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_h1() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    df['hour'] = df['timestamp'].dt.hour
    df['date'] = df['timestamp'].dt.normalize()
    return df


def build_us_summary(df: pd.DataFrame) -> pd.DataFrame:
    us_mask = (df['hour'] >= US_START_HOUR) & (df['hour'] < US_END_HOUR)
    us = df.loc[us_mask].copy()
    g = us.groupby('date')
    out = pd.DataFrame({
        'us_open': g['open'].first(),
        'us_close': g['close'].last(),
        'us_n_bars': g.size(),
    })
    out['us_ret_pct'] = (out['us_close'] - out['us_open']) / out['us_open'] * 100.0
    out = out.sort_index()
    out['us_atr_pct'] = (
        out['us_ret_pct']
        .rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1)
        .shift(1)
    )
    return out


# ---------------------------------------------------------------------------
# Simulator — numpy-fast inner loop
# ---------------------------------------------------------------------------

def simulate(
    df: pd.DataFrame,
    us: pd.DataFrame,
    filter_mode: str = 'unconditional',  # 'unconditional' | 'mag' | 'dnmed' | 'short_null'
    z_threshold: float = 1.0,
    cost_bps: float = COST_BPS_DEFAULT,
    direction: str = 'long',  # 'long' (baseline) | 'short' (null-check)
) -> tuple[pd.Series, list[dict]]:
    """Build per-trade return series. Index = trade exit date.

    filter_mode:
      'unconditional' — every trade-day fires
      'mag'           — fire only when |prior US zscore| > z_threshold
      'dnmed'         — fire only when prior US direction = DOWN AND 0.5<|z|<1.5
      'short_null'    — same as 'unconditional' but flip direction (null-check)
    """
    # (date, hour) -> close lookup
    closes = df.set_index(['date', 'hour'])['close']
    # Trade-dates = dates that have an EXIT_HOUR bar
    trade_dates = sorted(df.loc[df['hour'] == EXIT_HOUR, 'date'].unique())

    one_day = pd.Timedelta(days=1)
    rows = []
    cost_pct = cost_bps / 10000.0
    for d in trade_dates:
        d = pd.Timestamp(d)
        entry_date = d - one_day if ENTRY_IS_PRIOR_DAY else d
        prior_date = d - one_day
        try:
            entry_close = closes.loc[(entry_date, ENTRY_HOUR)]
            exit_close = closes.loc[(d, EXIT_HOUR)]
        except KeyError:
            continue
        if prior_date not in us.index:
            continue
        us_row = us.loc[prior_date]
        atr = us_row['us_atr_pct']
        if pd.isna(atr) or atr == 0:
            continue
        z = us_row['us_ret_pct'] / atr

        # Filter gate
        if filter_mode == 'mag':
            if not (abs(z) > z_threshold):
                continue
        elif filter_mode == 'dnmed':
            if not (z < 0 and 0.5 < abs(z) < 1.5):
                continue
        # 'unconditional' / 'short_null' have no extra gate

        gross_pct = (exit_close - entry_close) / entry_close
        if direction == 'long' and filter_mode != 'short_null':
            net_pct = gross_pct - cost_pct
        else:
            net_pct = -gross_pct - cost_pct

        rows.append({
            'date': d,
            'entry_close': entry_close,
            'exit_close': exit_close,
            'gross_pct': gross_pct,
            'net_pct': net_pct,
            'prior_us_z': z,
            'regime': label_regime(d),
            'dow': d.day_name(),
        })

    if not rows:
        return pd.Series(dtype=float, name='ret'), []

    trades_df = pd.DataFrame(rows)
    ret = pd.Series(trades_df['net_pct'].to_numpy(), index=pd.to_datetime(trades_df['date']),
                    name='ret')
    return ret, trades_df.to_dict('records')


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, ret: pd.Series, trades: list[dict]) -> dict:
    if len(ret) == 0:
        print(f'  [{label}]: empty')
        return {}
    r = ret.to_numpy()
    eq = (1.0 + r).cumprod()
    n = len(r)
    years = (ret.index[-1] - ret.index[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1
    tpy = n / max(years, 1e-9)
    sh = annualized_sharpe(r, trades_per_year=tpy)
    mdd = max_drawdown(eq)
    mean_pct = r.mean()
    wins = r[r > 0]
    losses = r[r <= 0]
    wr = len(wins) / n if n else 0.0
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gw / gl if gl > 0 else float('inf')

    print(f'  [{label}]')
    print(f'    period      : {ret.index[0].date()} -> {ret.index[-1].date()} ({years:.1f}y)')
    print(f'    total ret   : {total * 100:+.2f}%')
    print(f'    CAGR        : {cagr * 100:+.2f}%')
    print(f'    Sharpe      : {sh:+.2f}')
    print(f'    Max DD      : {mdd * 100:+.2f}%')
    print(f'    trades      : {n}  ({tpy:.0f}/yr)')
    print(f'    win rate    : {wr * 100:.1f}%')
    print(f'    profit fac. : {pf:.2f}')
    print(f'    mean/trade  : {mean_pct * 100:+.4f}%')
    return {'sharpe': sh, 'mdd': mdd, 'cagr': cagr, 'n': n, 'wr': wr, 'pf': pf,
            'mean': mean_pct, 'tpy': tpy}


def regime_breakdown(ret: pd.Series, trades: list[dict]) -> dict:
    out = {}
    for w, ys, ye in [
        ('W1 2018-2019', 2018, 2019),
        ('W2 2020-2021', 2020, 2021),
        ('W3 2022-2023', 2022, 2023),
        ('W4 2024-2026', 2024, 2026),
    ]:
        mask = (ret.index.year >= ys) & (ret.index.year <= ye)
        sub_ret = ret[mask]
        if len(sub_ret) < 20:
            print(f'  {w:<22s} (insufficient)')
            continue
        r = sub_ret.to_numpy()
        eq = (1 + r).cumprod()
        years = (sub_ret.index[-1] - sub_ret.index[0]).days / 365.25
        cagr = (1 + (float(eq[-1]) - 1)) ** (1 / max(years, 1e-9)) - 1
        tpy = len(r) / max(years, 1e-9)
        sh = annualized_sharpe(r, trades_per_year=tpy)
        mdd = max_drawdown(eq)
        n = len(r)
        mean = r.mean()
        print(f'  {w:<22s} CAGR {cagr * 100:>+6.2f}%  Sharpe {sh:>+6.2f}  '
              f'MDD {mdd * 100:>+7.2f}%  trades {n:>4d}  mean {mean * 100:>+6.4f}%')
        out[w] = {'sharpe': sh, 'mdd': mdd, 'cagr': cagr, 'n': n, 'mean': mean}
    return out


def cost_sweep(df: pd.DataFrame, us: pd.DataFrame, filter_mode: str, label: str) -> None:
    print(f'  [{label} — cost sweep]')
    for cb in COST_BPS_SWEEP:
        ret, _ = simulate(df, us, filter_mode=filter_mode, cost_bps=cb)
        if len(ret) == 0:
            continue
        r = ret.to_numpy()
        eq = (1 + r).cumprod()
        years = (ret.index[-1] - ret.index[0]).days / 365.25
        tpy = len(r) / max(years, 1e-9)
        sh = annualized_sharpe(r, trades_per_year=tpy)
        mdd = max_drawdown(eq)
        cagr = (1 + (float(eq[-1]) - 1)) ** (1 / max(years, 1e-9)) - 1
        flag = ' (deploy)' if cb == COST_BPS_DEFAULT else (' (stress)' if cb == KC_COST_STRESS_BP else '')
        print(f'    cost={cb:>4.1f}bp  Sharpe {sh:>+6.2f}  CAGR {cagr * 100:>+6.2f}%  '
              f'MDD {mdd * 100:>+7.2f}%  n={len(r)}{flag}')


def walk_forward(df: pd.DataFrame, us: pd.DataFrame, filter_mode: str, label: str) -> float:
    """5 rolling 3y-IS / 2y-OOS splits. Returns mean(IS_Sharpe - OOS_Sharpe)."""
    print(f'  [{label} — walk-forward]')
    splits = [
        ('S1', 2018, 2020, 2021, 2022),
        ('S2', 2019, 2021, 2022, 2023),
        ('S3', 2020, 2022, 2023, 2024),
        ('S4', 2021, 2023, 2024, 2025),
        ('S5', 2022, 2024, 2025, 2026),
    ]
    ret, _ = simulate(df, us, filter_mode=filter_mode)
    if len(ret) == 0:
        return float('nan')
    print(f'    {"split":<5s} {"IS years":<12s} {"OOS years":<12s} '
          f'{"IS Sh":>8s} {"OOS Sh":>8s} {"deg":>8s}')
    print('    ' + '-' * 70)
    degs = []
    for name, isa, isb, osa, osb in splits:
        is_mask = (ret.index.year >= isa) & (ret.index.year <= isb)
        oos_mask = (ret.index.year >= osa) & (ret.index.year <= osb)
        is_r = ret[is_mask].to_numpy()
        oos_r = ret[oos_mask].to_numpy()
        if len(is_r) < 20 or len(oos_r) < 20:
            print(f'    {name} insufficient')
            continue
        is_years = max((ret[is_mask].index[-1] - ret[is_mask].index[0]).days / 365.25, 1e-9)
        oos_years = max((ret[oos_mask].index[-1] - ret[oos_mask].index[0]).days / 365.25, 1e-9)
        is_sh = annualized_sharpe(is_r, trades_per_year=len(is_r) / is_years)
        oos_sh = annualized_sharpe(oos_r, trades_per_year=len(oos_r) / oos_years)
        deg = is_sh - oos_sh
        degs.append(deg)
        print(f'    {name:<5s} {isa}-{isb:<7d} {osa}-{osb:<7d} '
              f'{is_sh:>+7.2f}  {oos_sh:>+7.2f}  {deg:>+7.2f}')
    mean_deg = float(np.mean(degs)) if degs else float('nan')
    print(f'    mean degradation: {mean_deg:+.3f}  (bar: < {KC_WF_DEG:.2f})')
    return mean_deg


def dow_concentration(trades: list[dict]) -> tuple[float, dict]:
    if not trades:
        return 0.0, {}
    df = pd.DataFrame(trades)
    dow_pnl = df.groupby('dow')['net_pct'].sum()
    total = dow_pnl.abs().sum()
    if total == 0:
        return 0.0, {}
    shares = (dow_pnl.abs() / total).to_dict()
    max_share = max(shares.values())
    return max_share, shares


# ---------------------------------------------------------------------------
# Kill-criteria check
# ---------------------------------------------------------------------------

def kill_criteria_check(
    full: dict, w4: dict, fade_gap: float, wf_deg: float,
    cost_stress_sharpe: float, regime_min_sh: float, dow_max_share: float,
) -> tuple[bool, list[tuple[str, bool, str]]]:
    checks = [
        ('Full Sharpe > +0.30',
         full.get('sharpe', 0) > KC_SHARPE_FULL,
         f"{full.get('sharpe', 0):+.2f} vs +{KC_SHARPE_FULL:.2f}"),
        ('W4 Sharpe > +0.40',
         w4.get('sharpe', -99) > KC_SHARPE_W4,
         f"{w4.get('sharpe', float('nan')):+.2f} vs +{KC_SHARPE_W4:.2f}"),
        ('MDD < 20%',
         abs(full.get('mdd', -1)) < KC_MDD,
         f"{full.get('mdd', 0) * 100:+.2f}% vs <{KC_MDD * 100:.0f}%"),
        ('Trade count >= 200',
         full.get('n', 0) >= KC_TRADES,
         f"{full.get('n', 0)} vs {KC_TRADES}"),
        ('Fade-gap > +0.40',
         fade_gap > KC_FADE_GAP,
         f"{fade_gap:+.2f} vs +{KC_FADE_GAP:.2f}"),
        ('WF mean deg < 0.6',
         wf_deg < KC_WF_DEG,
         f"{wf_deg:+.3f} vs <{KC_WF_DEG:.2f}"),
        ('Cost stress @ 8bp Sh > 0',
         cost_stress_sharpe > 0,
         f"{cost_stress_sharpe:+.2f} vs >0"),
        ('All-regime Sh > -0.3',
         regime_min_sh > KC_REGIME_FLOOR,
         f"min {regime_min_sh:+.2f} vs >{KC_REGIME_FLOOR:.2f}"),
        ('DOW concentration < 50%',
         dow_max_share < KC_DOW_MAX_SHARE,
         f"{dow_max_share * 100:.1f}% vs <{KC_DOW_MAX_SHARE * 100:.0f}%"),
    ]
    passing = sum(1 for _, ok, _ in checks if ok)
    n = len(checks)
    print(f'\n  Pre-committed kill criteria: {passing}/{n} PASS')
    for label, ok, val in checks:
        mark = 'PASS' if ok else 'FAIL'
        print(f'    [{mark}] {label:<28s} {val}')
    return passing == n, checks


# ---------------------------------------------------------------------------
# Cost stress at specific BP
# ---------------------------------------------------------------------------

def sharpe_at_cost(df: pd.DataFrame, us: pd.DataFrame, filter_mode: str, cost_bps: float) -> float:
    ret, _ = simulate(df, us, filter_mode=filter_mode, cost_bps=cost_bps)
    if len(ret) == 0:
        return float('nan')
    r = ret.to_numpy()
    years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1e-9)
    return annualized_sharpe(r, trades_per_year=len(r) / years)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    df = load_h1()
    us = build_us_summary(df)
    print(f'Loaded {len(df):,} H1 bars: {df["timestamp"].min().date()} -> {df["timestamp"].max().date()}')
    print(f'US-session summary: {len(us)} days')
    print(f'Cost default: {COST_BPS_DEFAULT} bps RT  |  Stress: {KC_COST_STRESS_BP} bps RT')

    variants = ['unconditional', 'mag', 'dnmed']

    for vm in variants:
        section(f'VARIANT: {vm}')
        ret, trades = simulate(df, us, filter_mode=vm, cost_bps=COST_BPS_DEFAULT)
        full = report_run(f'{vm} @ {COST_BPS_DEFAULT}bp', ret, trades)
        print('\n  Regime breakdown:')
        regs = regime_breakdown(ret, trades)
        w4 = regs.get('W4 2024-2026', {})

        # Null check (symmetric short)
        ret_short, _ = simulate(df, us, filter_mode='short_null', cost_bps=COST_BPS_DEFAULT,
                                direction='short') if vm == 'unconditional' else (None, None)
        if vm == 'unconditional' and ret_short is not None and len(ret_short) > 0:
            short_sh = annualized_sharpe(ret_short.to_numpy(),
                                         trades_per_year=len(ret_short) / max(
                                             (ret_short.index[-1] - ret_short.index[0]).days / 365.25, 1e-9))
            fade_gap = full.get('sharpe', 0) - short_sh
            print(f'\n  Null check (symmetric short): Sharpe {short_sh:+.2f}  fade-gap {fade_gap:+.2f}')
        else:
            ret_short_v, _ = simulate(df, us, filter_mode=vm, cost_bps=COST_BPS_DEFAULT,
                                      direction='short')
            if len(ret_short_v) > 0:
                short_sh = annualized_sharpe(ret_short_v.to_numpy(),
                                             trades_per_year=len(ret_short_v) / max(
                                                 (ret_short_v.index[-1] - ret_short_v.index[0]).days / 365.25, 1e-9))
                fade_gap = full.get('sharpe', 0) - short_sh
                print(f'\n  Null check (same filter, short): Sharpe {short_sh:+.2f}  fade-gap {fade_gap:+.2f}')
            else:
                fade_gap = float('nan')

        print()
        cost_sweep(df, us, vm, vm)
        cost_stress = sharpe_at_cost(df, us, vm, KC_COST_STRESS_BP)

        print()
        wf_deg = walk_forward(df, us, vm, vm)

        max_share, shares = dow_concentration(trades)
        print(f'\n  DOW concentration: max share {max_share * 100:.1f}% '
              f'({sorted(shares.items(), key=lambda x: -x[1])[0][0] if shares else "n/a"})')

        regime_sharpes = [v['sharpe'] for v in regs.values() if 'sharpe' in v]
        regime_min = min(regime_sharpes) if regime_sharpes else 0
        kill_criteria_check(full, w4, fade_gap, wf_deg, cost_stress, regime_min, max_share)

    # Summary table
    section('SUMMARY — all variants @ deploy cost 5bp RT')
    print(f'  {"variant":<14s} {"Sh full":>8s} {"Sh W4":>7s} {"MDD":>7s} {"n":>6s} {"fade-gap":>9s} {"WF deg":>8s} {"Sh@8bp":>8s}')
    print('  ' + '-' * 80)
    for vm in variants:
        ret, trades = simulate(df, us, filter_mode=vm, cost_bps=COST_BPS_DEFAULT)
        if len(ret) == 0:
            continue
        r = ret.to_numpy()
        eq = (1 + r).cumprod()
        years = max((ret.index[-1] - ret.index[0]).days / 365.25, 1e-9)
        sh = annualized_sharpe(r, trades_per_year=len(r) / years)
        mdd = max_drawdown(eq)
        n = len(r)
        w4_mask = (ret.index.year >= 2024)
        w4_r = ret[w4_mask].to_numpy()
        w4_years = max((ret[w4_mask].index[-1] - ret[w4_mask].index[0]).days / 365.25, 1e-9) if w4_mask.sum() > 0 else 1
        w4_sh = annualized_sharpe(w4_r, trades_per_year=len(w4_r) / w4_years)
        ret_s, _ = simulate(df, us, filter_mode=vm, cost_bps=COST_BPS_DEFAULT, direction='short')
        if len(ret_s) > 0:
            s_sh = annualized_sharpe(ret_s.to_numpy(),
                                     trades_per_year=len(ret_s) / max(
                                         (ret_s.index[-1] - ret_s.index[0]).days / 365.25, 1e-9))
        else:
            s_sh = 0.0
        fade_gap = sh - s_sh
        wf_deg = walk_forward(df, us, vm, f'sum-{vm}')  # prints; we just need the number
        cost_stress = sharpe_at_cost(df, us, vm, KC_COST_STRESS_BP)
        print(f'  {vm:<14s} {sh:>+7.2f}  {w4_sh:>+6.2f}  {mdd * 100:>+6.2f}%  {n:>5d}  {fade_gap:>+8.2f}  {wf_deg:>+7.3f}  {cost_stress:>+7.2f}')


if __name__ == '__main__':
    main()
