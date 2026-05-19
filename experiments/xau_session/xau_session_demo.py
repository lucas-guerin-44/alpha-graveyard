#!/usr/bin/env python3
"""XAUUSD overnight Asia-open hold (Variant C: 23:00 UTC -> 08:00 UTC, 9h).

Thesis: experiments/xau_session/xau_session.md (Phase 0 complete 2026-05-16).

Mechanism: Asian-session structural drift up on XAUUSD. Hour 00 UTC drift
+5.26t FULL, all 4 regimes positive, W4 amplified 3.5x. Likely driver:
Asian OTC physical / sovereign / Indian / Chinese flow rotation concentrating
at session open. Variant C captures the overnight 23->08 UTC window
(includes the open-hour drift + early-Asia momentum, exits at London open
before the 04-07 mid-Asia weakness fully reverses things).

Variants tested:
  baseline      Variant C unconditional (long every trade-day 23->08 UTC)
  filter_z      Variant C with prior-NY |zscore| > 1.0 filter
  filter_dnmed  Variant C with prior-NY DOWN + medium-magnitude filter
                (PRIOR-NY-DOWN × 0.5 < |z| < 1.5 — the W4-strongest bucket)

Cost: 2 bps RT realistic (Eightcap raw 0.35 bp spread + commission ~1.5 bp).
Stress at 4 bp / 6 bp / 10 bp.

Null check: Variant C-SHORT (enter short at 23, cover at 08).

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/xau_session/xau_session_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'XAUUSD_H1.csv')

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENTRY_HOUR = 23   # UTC; prior day's 23:00-00:00 bar close = entry price
EXIT_HOUR = 8     # UTC; same-day 08:00-09:00 bar close = exit price
ENTRY_IS_PRIOR_DAY = True

NY_START_HOUR = 13
NY_END_HOUR = 21       # exclusive — bars starting at 13..20
ATR_DAYS = 20

# Cost in basis points RT (Eightcap raw realistic)
COST_BPS_DEFAULT = 2.0
COST_BPS_SWEEP = (0.0, 2.0, 4.0, 6.0, 10.0)

# Annualization assumption: ~252 trade-days/year (XAUUSD is ~5-day-week with broker pause)
TRADES_PER_YEAR_ANNUAL = 252

# Pre-committed kill criteria (from thesis doc, finalized 2026-05-16)
KC_SHARPE_FULL = 0.30
KC_SHARPE_W4 = 0.50
KC_MDD = 0.15
KC_TRADES = 200
KC_FADE_GAP = 0.40
KC_WF_DEG = 0.50
KC_DOW_MAX_SHARE = 0.50
KC_COST_STRESS_BP = 4.0   # must still pass at 2x realistic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


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


def build_ny_summary(df: pd.DataFrame) -> pd.DataFrame:
    ny_mask = (df['hour'] >= NY_START_HOUR) & (df['hour'] < NY_END_HOUR)
    ny = df.loc[ny_mask].copy()
    g = ny.groupby('date')
    out = pd.DataFrame({
        'ny_open': g['open'].first(),
        'ny_close': g['close'].last(),
        'ny_n_bars': g.size(),
    })
    out['ny_ret_pct'] = (out['ny_close'] - out['ny_open']) / out['ny_open'] * 100.0
    out = out.sort_index()
    out['ny_atr_pct'] = (
        out['ny_ret_pct']
        .rolling(ATR_DAYS, min_periods=max(2, ATR_DAYS // 2))
        .std(ddof=1)
        .shift(1)
    )
    return out


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def simulate(
    df: pd.DataFrame,
    ny: pd.DataFrame,
    filter_mode: str = 'unconditional',  # 'unconditional' | 'mag' | 'dnmed' | 'short_null'
    z_threshold: float = 1.0,
    cost_bps: float = COST_BPS_DEFAULT,
    direction: str = 'long',  # 'long' (baseline) | 'short' (null-check)
) -> tuple[pd.Series, list[dict]]:
    """Build per-trade return series. Index = trade exit date.

    filter_mode:
      'unconditional' — every trade-day fires
      'mag'           — fire only when |prior NY zscore| > z_threshold
      'dnmed'         — fire only when prior NY direction = DOWN AND 0.5<|z|<1.5
      'short_null'    — same as 'unconditional' but flip direction (null-check)
    """
    # (date, hour) -> close lookup
    closes = df.set_index(['date', 'hour'])['close']
    # Trade-dates = dates that have an EXIT_HOUR bar
    trade_dates = sorted(df.loc[df['hour'] == EXIT_HOUR, 'date'].unique())

    one_day = pd.Timedelta(days=1)
    rows = []
    cost_pct = cost_bps / 10000.0   # 1 bp = 0.0001 fraction
    for d in trade_dates:
        d = pd.Timestamp(d)
        entry_date = d - one_day if ENTRY_IS_PRIOR_DAY else d
        prior_date = d - one_day
        try:
            entry_close = closes.loc[(entry_date, ENTRY_HOUR)]
            exit_close = closes.loc[(d, EXIT_HOUR)]
        except KeyError:
            continue
        if prior_date not in ny.index:
            continue
        ny_row = ny.loc[prior_date]
        atr = ny_row['ny_atr_pct']
        if pd.isna(atr) or atr == 0:
            continue
        z = ny_row['ny_ret_pct'] / atr

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
            'prior_ny_z': z,
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


def cost_sweep(df: pd.DataFrame, ny: pd.DataFrame, filter_mode: str, label: str) -> None:
    print(f'  [{label} — cost sweep]')
    for cb in COST_BPS_SWEEP:
        ret, _ = simulate(df, ny, filter_mode=filter_mode, cost_bps=cb)
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


def walk_forward(df: pd.DataFrame, ny: pd.DataFrame, filter_mode: str, label: str) -> float:
    """5 rolling 3y-IS / 2y-OOS splits. Returns mean(IS_Sharpe - OOS_Sharpe)."""
    print(f'  [{label} — walk-forward]')
    splits = [
        ('S1', 2018, 2020, 2021, 2022),
        ('S2', 2019, 2021, 2022, 2023),
        ('S3', 2020, 2022, 2023, 2024),
        ('S4', 2021, 2023, 2024, 2025),
        ('S5', 2022, 2024, 2025, 2026),
    ]
    ret, _ = simulate(df, ny, filter_mode=filter_mode)
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
    counts = df['dow'].value_counts()
    n = len(df)
    share = counts / n
    max_share = float(share.max())
    return max_share, share.to_dict()


def kill_criteria_check(
    label: str,
    full_stats: dict,
    regime_stats: dict,
    fade_gap: float,
    wf_deg: float,
    cost_stress_sh: float,
    dow_max_share: float,
) -> bool:
    def v(ok: bool) -> str:
        return 'PASS' if ok else 'FAIL'
    print(f'  [{label}]')
    sh_full = full_stats.get('sharpe', 0.0)
    mdd = full_stats.get('mdd', -1.0)
    n = full_stats.get('n', 0)
    w4 = regime_stats.get('W4 2024-2026', {})
    sh_w4 = w4.get('sharpe', 0.0)

    checks = [
        (f'FULL Sharpe > {KC_SHARPE_FULL:.2f}', sh_full > KC_SHARPE_FULL, f'{sh_full:+.2f}'),
        (f'W4 Sharpe   > {KC_SHARPE_W4:.2f}',   sh_w4 > KC_SHARPE_W4,    f'{sh_w4:+.2f}'),
        (f'MDD         < {KC_MDD * 100:.0f}%',  abs(mdd) < KC_MDD,       f'{mdd * 100:+.2f}%'),
        (f'Trades     >= {KC_TRADES}',          n >= KC_TRADES,          f'{n}'),
        (f'Fade-gap   > {KC_FADE_GAP:.2f}',     fade_gap > KC_FADE_GAP,  f'{fade_gap:+.2f}'),
        (f'WF deg     < {KC_WF_DEG:.2f}',       wf_deg < KC_WF_DEG,      f'{wf_deg:+.3f}'),
        (f'DOW share  < {KC_DOW_MAX_SHARE * 100:.0f}%',
                                                dow_max_share < KC_DOW_MAX_SHARE,
                                                f'{dow_max_share * 100:.1f}%'),
        (f'Cost-stress Sh@{KC_COST_STRESS_BP:.0f}bp > 0',
                                                cost_stress_sh > 0,
                                                f'{cost_stress_sh:+.2f}'),
    ]
    all_pass = True
    for desc, ok, val in checks:
        print(f'    {desc:<28s} : {v(ok)}  ({val})')
        if not ok:
            all_pass = False
    print(f'    -> {"PASS" if all_pass else "FAIL"} on Phase 2 kill criteria')
    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section('Loading XAUUSD H1 (2018-2026, UTC)')
    df = load_h1()
    print(f'  bars   : {len(df):,}')
    print(f'  range  : {df["timestamp"].min()} -> {df["timestamp"].max()}')
    ny = build_ny_summary(df)
    print(f'  NY-session summary rows: {len(ny):,}')

    # ----- BASELINE: Variant C unconditional, 2bp cost -----
    section('Baseline — Variant C (23:00->08:00 UTC, 9h hold), unconditional, cost 2bp RT')
    ret_b, tr_b = simulate(df, ny, filter_mode='unconditional', cost_bps=COST_BPS_DEFAULT)
    stats_b = report_run('baseline', ret_b, tr_b)

    section('Regime breakdown — baseline')
    rb_baseline = regime_breakdown(ret_b, tr_b)

    section('Cost sweep — baseline')
    cost_sweep(df, ny, 'unconditional', 'baseline')

    # Null check: SHORT-direction
    section('Null check — Variant C SHORT (cost 2bp RT)')
    ret_s, tr_s = simulate(df, ny, filter_mode='unconditional', cost_bps=COST_BPS_DEFAULT,
                           direction='short')
    # Direct short: re-simulate with direction='short' returns -gross-cost; report PnL of that
    # (note: simulate flips sign in 'short' direction or 'short_null' mode)
    stats_s = report_run('SHORT-null', ret_s, tr_s)
    fade_gap_b = stats_b['sharpe'] - stats_s['sharpe']
    print(f'\n  direction-gap (LONG - SHORT): {fade_gap_b:+.2f}  (bar: > {KC_FADE_GAP:.2f})')

    # Walk-forward
    section('Walk-forward — baseline')
    wf_b = walk_forward(df, ny, 'unconditional', 'baseline')

    # Cost-stress @ 4bp
    section('Cost-stress @ 4bp RT — baseline')
    ret_c4, _ = simulate(df, ny, filter_mode='unconditional', cost_bps=KC_COST_STRESS_BP)
    stats_c4 = report_run('baseline @ 4bp', ret_c4, [])
    cs_sh_b = stats_c4['sharpe']

    # DOW
    dow_max_b, dow_dist_b = dow_concentration(tr_b)
    print(f'\n  DOW distribution (baseline): {dow_dist_b}')
    print(f'  DOW max share: {dow_max_b * 100:.1f}%  (bar: < {KC_DOW_MAX_SHARE * 100:.0f}%)')

    # Kill-criteria check on baseline
    section('Phase 2 kill criteria — BASELINE (Variant C unconditional)')
    pass_b = kill_criteria_check('baseline', stats_b, rb_baseline, fade_gap_b, wf_b,
                                 cs_sh_b, dow_max_b)

    # ----- VARIANT 1: filter |z| > 1.0 -----
    section('Variant 1 — Variant C + |prior NY z| > 1.0 filter, cost 2bp RT')
    ret_z, tr_z = simulate(df, ny, filter_mode='mag', z_threshold=1.0, cost_bps=COST_BPS_DEFAULT)
    stats_z = report_run('filter_z>1.0', ret_z, tr_z)
    rb_z = regime_breakdown(ret_z, tr_z)
    section('Cost sweep — filter_z>1.0')
    cost_sweep(df, ny, 'mag', 'filter_z')
    section('Null check — filter_z>1.0 SHORT')
    ret_zs, _ = simulate(df, ny, filter_mode='mag', cost_bps=COST_BPS_DEFAULT, direction='short')
    stats_zs = report_run('filter_z SHORT', ret_zs, [])
    fade_gap_z = stats_z['sharpe'] - stats_zs['sharpe']
    print(f'\n  direction-gap: {fade_gap_z:+.2f}')
    section('Walk-forward — filter_z>1.0')
    wf_z = walk_forward(df, ny, 'mag', 'filter_z')
    section('Cost-stress @ 4bp RT — filter_z>1.0')
    ret_zc4, _ = simulate(df, ny, filter_mode='mag', cost_bps=KC_COST_STRESS_BP)
    stats_zc4 = report_run('filter_z @ 4bp', ret_zc4, [])
    dow_max_z, _ = dow_concentration(tr_z)
    section('Phase 2 kill criteria — filter_z>1.0')
    pass_z = kill_criteria_check('filter_z>1.0', stats_z, rb_z, fade_gap_z, wf_z,
                                 stats_zc4['sharpe'], dow_max_z)

    # ----- VARIANT 2: DOWN-med filter -----
    section('Variant 2 — Variant C + DOWN-med filter (prior-NY DOWN × 0.5<|z|<1.5), cost 2bp RT')
    ret_dm, tr_dm = simulate(df, ny, filter_mode='dnmed', cost_bps=COST_BPS_DEFAULT)
    stats_dm = report_run('filter_dnmed', ret_dm, tr_dm)
    rb_dm = regime_breakdown(ret_dm, tr_dm)
    section('Cost sweep — filter_dnmed')
    cost_sweep(df, ny, 'dnmed', 'filter_dnmed')
    section('Null check — filter_dnmed SHORT')
    ret_dms, _ = simulate(df, ny, filter_mode='dnmed', cost_bps=COST_BPS_DEFAULT, direction='short')
    stats_dms = report_run('dnmed SHORT', ret_dms, [])
    fade_gap_dm = stats_dm['sharpe'] - stats_dms['sharpe']
    print(f'\n  direction-gap: {fade_gap_dm:+.2f}')
    section('Walk-forward — filter_dnmed')
    wf_dm = walk_forward(df, ny, 'dnmed', 'filter_dnmed')
    section('Cost-stress @ 4bp RT — filter_dnmed')
    ret_dmc4, _ = simulate(df, ny, filter_mode='dnmed', cost_bps=KC_COST_STRESS_BP)
    stats_dmc4 = report_run('dnmed @ 4bp', ret_dmc4, [])
    dow_max_dm, _ = dow_concentration(tr_dm)
    section('Phase 2 kill criteria — filter_dnmed')
    pass_dm = kill_criteria_check('filter_dnmed', stats_dm, rb_dm, fade_gap_dm, wf_dm,
                                  stats_dmc4['sharpe'], dow_max_dm)

    # ----- SUMMARY -----
    section('Phase 2 summary')
    rows = [
        ('baseline (C unc)', stats_b, rb_baseline.get('W4 2024-2026', {}),
         fade_gap_b, wf_b, stats_c4['sharpe'], dow_max_b, pass_b),
        ('filter_z>1.0',     stats_z, rb_z.get('W4 2024-2026', {}),
         fade_gap_z, wf_z, stats_zc4['sharpe'], dow_max_z, pass_z),
        ('filter_dnmed',     stats_dm, rb_dm.get('W4 2024-2026', {}),
         fade_gap_dm, wf_dm, stats_dmc4['sharpe'], dow_max_dm, pass_dm),
    ]
    print(f'  {"variant":<18s} {"Sh full":>8s} {"Sh W4":>8s} {"MDD":>8s} {"n":>5s} '
          f'{"f-gap":>7s} {"WF deg":>8s} {"Sh@4bp":>8s} {"DOW%":>6s} verdict')
    print('  ' + '-' * 110)
    for label, sf, sw4, fg, wf, cs, dm, p in rows:
        verdict = 'PASS' if p else 'FAIL'
        print(f'  {label:<18s} {sf.get("sharpe", 0):>+7.2f}  {sw4.get("sharpe", 0):>+7.2f}  '
              f'{sf.get("mdd", 0) * 100:>+6.1f}%  {sf.get("n", 0):>5d}  '
              f'{fg:>+6.2f}  {wf:>+7.3f}  {cs:>+7.2f}  '
              f'{dm * 100:>5.1f}%  {verdict}')

    # Pick deploy candidate
    print(f'\n  Deploy candidate:')
    candidates = [(label, sf) for label, sf, _, _, _, _, _, p in rows if p]
    if candidates:
        best = max(candidates, key=lambda x: x[1].get('sharpe', 0))
        print(f'    {best[0]} (Sharpe {best[1]["sharpe"]:+.2f})')
    else:
        print('    NONE pass all kill criteria. Investigate variant tradeoffs.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
