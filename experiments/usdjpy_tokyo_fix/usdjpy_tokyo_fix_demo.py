#!/usr/bin/env python3
"""USDJPY Tokyo morning fix flow — Phase 0a/0b + Phase 2 simulator.

Thesis: experiments/usdjpy_tokyo_fix/usdjpy_tokyo_fix.md

Mechanism: Tokyo WMR fix at 09:55 JST = 00:55 UTC year-round (Japan
doesn't observe DST). Japanese real-money flow is asymmetric by day-of-week:
exporters (JPY-buying, USDJPY-selling) heavier Mon/Tue; importers (JPY-
selling, USDJPY-buying) heavier Wed; Thu/Fri no consistent skew.

Trade: enter at OPEN of 00:45 UTC M5 bar (T-10 min), exit at OPEN of 01:05
UTC M5 bar (T+10 min), 20-min symmetric window around the fix.
  - Mon/Tue: SHORT USDJPY
  - Wed:     LONG USDJPY
  - Thu/Fri: SKIP

Phase 0a (spread audit): broker M1 spread for the window — NOT implemented
in this demo (requires separate tick/spread data pull). Documented as a
follow-up; default COST_BPS = 1.0 RT per thesis.

Phase 0b (magnitude check): gross zero-cost mean per-day must be >= +1.5 bps
on the day-of-week mapping (full sample). If below, REJECT before Phase 2.

Phase 2 kill criteria (run only if 0b passes):
  1. Full-sample net mean per-day > +1 bp
  2. W3 (modern regime) mean per-day > 0 bps
  3. Direction null-gap (DOW mapping vs flat-direction) > +1 bp
  4. DOW-shuffle null: actual mapping beats >=75% of permutations
  5. Trades >= 200
  6. WR >= 52% AND PF >= 1.10
  7. MDD <= 10%
  8. Walk-forward 3-fold: mean OOS Sharpe >= +0.15, min OOS Sharpe >= -0.10
  9. MEF days gross > non-MEF days gross (or drop MEF)
 10. Cost-stress at 2 bps: net mean > 0

Data constraint: USDJPY M5 only available 2022-10-07 onward (~3.6y, W3+W4
era only). The thesis assumed 2019-2026 (~7.4y); W1/W2 regime checks are
infeasible. This makes the BoJ-intervention era the *primary* sample, not
a holdout — flagged in verdict.

Run:
  PYTHONIOENCODING=utf-8 venv/Scripts/python.exe \
    experiments/usdjpy_tokyo_fix/usdjpy_tokyo_fix_demo.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
DATA_PATH = os.path.join(_ROOT, 'ohlc_data', 'USDJPY_M5.csv')

# ---------------------------------------------------------------------------
# Config — pre-committed per thesis doc
# ---------------------------------------------------------------------------

# Tokyo fix anchor: 09:55 JST = 00:55 UTC year-round (Japan no DST)
FIX_HOUR_UTC = 0
FIX_MIN_UTC = 55
ENTRY_OFFSET_MIN = -10   # T-10 = 00:45 UTC entry
EXIT_OFFSET_MIN = +10    # T+10 = 01:05 UTC exit

# Day-of-week direction map (PRE-COMMITTED — do not adjust post-hoc)
DOW_DIRECTION = {
    0: -1,   # Monday    SHORT
    1: -1,   # Tuesday   SHORT
    2: +1,   # Wednesday LONG
    3: 0,    # Thursday  SKIP
    4: 0,    # Friday    SKIP
    5: 0,    # Saturday  SKIP
    6: 0,    # Sunday    SKIP
}

# Cost (bps RT) — Eightcap USDJPY ~1 pip RT at quote ~160 = 0.625 bps
# Default uses 1.0 bp as a conservative round number; sweep across realistic range.
COST_BPS_DEFAULT = 1.0
COST_BPS_SWEEP = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)

# Phase 0b floor: gross zero-cost mean per-day must clear this (bps)
PHASE0_GROSS_FLOOR_BPS = 1.5

# Month-end-fix amplification (optional discretionary add)
MEF_AMPLIFY = 2.0

# Pre-committed Phase 2 kill criteria
KC_NET_MEAN_BPS = 1.0           # full-sample net mean per-day > 1 bp
KC_W3_MEAN_BPS = 0.0            # W3 modern-regime net mean > 0
KC_DIR_NULL_GAP_BPS = 1.0       # mapping vs flat-direction-null gap > 1 bp
KC_DOW_SHUFFLE_PCT = 0.75       # actual mapping beats 75% of shuffled-null perms
KC_TRADES = 200
KC_WR = 0.52
KC_PF = 1.10
KC_MDD = 0.10
KC_WF_OOS_SHARPE_MEAN = 0.15
KC_WF_OOS_SHARPE_MIN = -0.10
KC_COST_STRESS_BP = 2.0         # net mean still > 0 at 2x realistic cost

# Trades-per-year for Sharpe annualization. Mon+Tue+Wed × ~50 weeks × ~0.95
# (holiday/data-gap) ~= 142 trades/yr theoretical, but we'll use empirical.
DOW_SHUFFLE_PERMS = 200

RNG_SEED = 20260526


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def label_regime_usdjpy(ts: pd.Timestamp) -> str:
    """USDJPY-specific regime tags reflecting BoJ era.

    W2: 2022-10 → 2023-12  (pre-YCC-exit; aggressive easing)
    W3: 2024-01 → 2024-12  (YCC-exit + Apr/Jul BoJ interventions)
    W4: 2025-01 → 2026-05  (post-intervention; normalizing)
    """
    y = ts.year
    if y <= 2023:
        return 'W2 2022-10..2023-12'
    if y == 2024:
        return 'W3 2024 (YCC-exit + intervention)'
    return 'W4 2025-2026 (post-intervention)'


def fmt_bps(x: float) -> str:
    return f'{x:+.3f} bps'


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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_m5() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    df['date'] = df['timestamp'].dt.normalize()
    df['dow'] = df['timestamp'].dt.dayofweek
    return df


def is_month_end_fix(d: pd.Timestamp, valid_dates: set) -> bool:
    """True if d is the last valid trade-date of its month.

    'valid' = a date that has an entry bar in our dataset.
    """
    if d not in valid_dates:
        return False
    next_d = d + pd.Timedelta(days=1)
    cap = d + pd.Timedelta(days=10)
    while next_d <= cap:
        if next_d.month != d.month:
            return True
        if next_d in valid_dates:
            return False
        next_d = next_d + pd.Timedelta(days=1)
    return True


# ---------------------------------------------------------------------------
# Trade construction
# ---------------------------------------------------------------------------

def build_trades_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-day trade candidate table.

    For each date that has both an entry bar (00:45 UTC) and exit bar
    (01:05 UTC), compute:
      - entry_px = open of 00:45 bar
      - exit_px  = open of 01:05 bar
      - gross_pct = (exit_px - entry_px) / entry_px   (no direction yet)
      - dow, is_mef
    """
    # Entry bar = timestamp at 00:45; exit bar = timestamp at 01:05
    entry_mask = (df['hour'] == 0) & (df['minute'] == 45)
    exit_mask = (df['hour'] == 1) & (df['minute'] == 5)

    entry = df.loc[entry_mask, ['date', 'dow', 'open']].rename(columns={'open': 'entry_px'})
    exit_ = df.loc[exit_mask, ['date', 'open']].rename(columns={'open': 'exit_px'})
    tbl = entry.merge(exit_, on='date', how='inner').sort_values('date').reset_index(drop=True)

    tbl['gross_pct'] = (tbl['exit_px'] - tbl['entry_px']) / tbl['entry_px']
    tbl['gross_bps'] = tbl['gross_pct'] * 10000.0

    valid_dates = set(tbl['date'].tolist())
    tbl['is_mef'] = tbl['date'].apply(lambda d: is_month_end_fix(d, valid_dates))
    return tbl


def apply_direction_mapping(tbl: pd.DataFrame,
                            dow_map: dict[int, int] | None = None) -> pd.DataFrame:
    if dow_map is None:
        dow_map = DOW_DIRECTION
    out = tbl.copy()
    out['direction'] = out['dow'].map(dow_map).fillna(0).astype(int)
    out = out[out['direction'] != 0].copy()
    out['gross_dir_bps'] = out['direction'] * out['gross_bps']
    return out.reset_index(drop=True)


def attach_net(tr: pd.DataFrame, cost_bps: float,
               mef_amplify: float = 1.0) -> pd.DataFrame:
    out = tr.copy()
    out['notional'] = np.where(out['is_mef'].to_numpy() & (mef_amplify != 1.0),
                                mef_amplify, 1.0)
    out['net_bps'] = out['notional'] * out['gross_dir_bps'] - cost_bps
    out['net_pct'] = out['net_bps'] / 10000.0
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_run(label: str, tr: pd.DataFrame) -> dict:
    if len(tr) == 0:
        print(f'  [{label}]: empty')
        return {}
    r = tr['net_pct'].to_numpy()
    eq = (1.0 + r).cumprod()
    n = len(r)
    years = (tr['date'].iloc[-1] - tr['date'].iloc[0]).days / 365.25
    total = float(eq[-1] - 1.0)
    cagr = (1 + total) ** (1 / max(years, 1e-9)) - 1 if years > 0 else 0.0
    tpy = n / max(years, 1e-9)
    sh = annualized_sharpe(r, trades_per_year=tpy)
    mdd = max_drawdown(eq)
    mean_bps = float(tr['net_bps'].mean())
    gross_bps = float(tr['gross_dir_bps'].mean())
    wins = r[r > 0]
    losses = r[r <= 0]
    wr = len(wins) / n
    gw = float(wins.sum()) if len(wins) else 0.0
    gl = float(-losses.sum()) if len(losses) else 0.0
    pf = gw / gl if gl > 0 else float('inf')

    print(f'  [{label}]')
    print(f'    period      : {tr["date"].iloc[0].date()} -> {tr["date"].iloc[-1].date()} ({years:.2f}y)')
    print(f'    trades      : {n}  ({tpy:.0f}/yr)')
    print(f'    gross/trade : {gross_bps:+.3f} bps')
    print(f'    net/trade   : {mean_bps:+.3f} bps')
    print(f'    total ret   : {total * 100:+.3f}%')
    print(f'    CAGR        : {cagr * 100:+.3f}%')
    print(f'    Sharpe      : {sh:+.2f}')
    print(f'    Max DD      : {mdd * 100:+.2f}%')
    print(f'    win rate    : {wr * 100:.1f}%')
    print(f'    profit fac  : {pf:.2f}')
    return {'sharpe': sh, 'mdd': mdd, 'cagr': cagr, 'n': n, 'wr': wr, 'pf': pf,
            'mean_bps': mean_bps, 'gross_bps': gross_bps, 'tpy': tpy}


def regime_breakdown(tr: pd.DataFrame) -> dict:
    out = {}
    tr = tr.copy()
    tr['regime'] = tr['date'].apply(label_regime_usdjpy)
    for w in sorted(tr['regime'].unique()):
        sub = tr[tr['regime'] == w]
        if len(sub) < 20:
            print(f'  {w:<38s} (insufficient n={len(sub)})')
            continue
        r = sub['net_pct'].to_numpy()
        eq = (1 + r).cumprod()
        years = max((sub['date'].iloc[-1] - sub['date'].iloc[0]).days / 365.25, 1e-9)
        cagr = (1 + (float(eq[-1]) - 1)) ** (1 / years) - 1
        tpy = len(r) / years
        sh = annualized_sharpe(r, trades_per_year=tpy)
        mdd = max_drawdown(eq)
        mean_bps = float(sub['net_bps'].mean())
        gross_bps = float(sub['gross_dir_bps'].mean())
        print(f'  {w:<38s} n={len(r):>4d}  '
              f'gross {gross_bps:>+6.2f}bp  net {mean_bps:>+6.2f}bp  '
              f'Sh {sh:>+5.2f}  MDD {mdd * 100:>+6.2f}%')
        out[w] = {'sharpe': sh, 'mdd': mdd, 'cagr': cagr, 'n': len(r),
                  'mean_bps': mean_bps, 'gross_bps': gross_bps}
    return out


def cost_sweep(tr_unc: pd.DataFrame) -> dict:
    print(f'  [cost sweep — net mean/trade & Sharpe]')
    out = {}
    for cb in COST_BPS_SWEEP:
        tr = attach_net(tr_unc, cost_bps=cb)
        r = tr['net_pct'].to_numpy()
        n = len(r)
        if n == 0:
            continue
        years = max((tr['date'].iloc[-1] - tr['date'].iloc[0]).days / 365.25, 1e-9)
        tpy = n / years
        sh = annualized_sharpe(r, trades_per_year=tpy)
        mean_bps = float(tr['net_bps'].mean())
        flag = ''
        if abs(cb - COST_BPS_DEFAULT) < 1e-9:
            flag = ' (deploy)'
        elif abs(cb - KC_COST_STRESS_BP) < 1e-9:
            flag = ' (stress)'
        print(f'    cost={cb:>4.1f}bp  net {mean_bps:>+6.3f}bp  Sh {sh:>+5.2f}{flag}')
        out[cb] = {'mean_bps': mean_bps, 'sharpe': sh}
    return out


def dow_shuffle_null(tbl: pd.DataFrame, cost_bps: float,
                      perms: int = DOW_SHUFFLE_PERMS) -> tuple[float, float, np.ndarray]:
    """Return (actual_mean_bps, percentile, shuffled_means).

    Permute the day-of-week → direction mapping (over Mon/Tue/Wed only,
    since Thu/Fri are pre-committed SKIP), compute mean net bps for each
    permutation, return where actual falls.
    """
    rng = np.random.default_rng(RNG_SEED)
    actual = apply_direction_mapping(tbl, DOW_DIRECTION)
    actual = attach_net(actual, cost_bps=cost_bps)
    actual_mean = float(actual['net_bps'].mean())

    # All 3^3 = 27 distinct (mon, tue, wed) direction assignments (each in
    # {-1, 0, +1}), of which 26 are non-trivial (skip all-zero). We'll
    # sample with replacement up to `perms`.
    from itertools import product
    all_maps = []
    for m, t, w in product([-1, 0, +1], repeat=3):
        if m == 0 and t == 0 and w == 0:
            continue
        all_maps.append({0: m, 1: t, 2: w, 3: 0, 4: 0, 5: 0, 6: 0})
    # The actual mapping IS one of these — exclude it from the null set.
    actual_key = (DOW_DIRECTION[0], DOW_DIRECTION[1], DOW_DIRECTION[2])
    all_maps = [m for m in all_maps
                if (m[0], m[1], m[2]) != actual_key]

    means = []
    for mapping in all_maps:
        sub = apply_direction_mapping(tbl, mapping)
        if len(sub) < 20:
            continue
        sub_net = attach_net(sub, cost_bps=cost_bps)
        means.append(float(sub_net['net_bps'].mean()))
    means_arr = np.array(means)
    pct = float((means_arr < actual_mean).sum()) / max(len(means_arr), 1)
    return actual_mean, pct, means_arr


def flat_direction_null(tbl: pd.DataFrame, cost_bps: float) -> dict:
    """Null: same trade days (Mon/Tue/Wed), but ignore the DOW direction
    mapping — instead, randomize direction per trade with equal prob.

    Use the deterministic 'always LONG' and 'always SHORT' on Mon/Tue/Wed
    as the two reference flat directions; report the better of the two as
    the flat-null baseline."""
    rng = np.random.default_rng(RNG_SEED)
    out = {}
    for name, dmap in [
        ('always-LONG  M/T/W', {0: +1, 1: +1, 2: +1, 3: 0, 4: 0, 5: 0, 6: 0}),
        ('always-SHORT M/T/W', {0: -1, 1: -1, 2: -1, 3: 0, 4: 0, 5: 0, 6: 0}),
    ]:
        sub = apply_direction_mapping(tbl, dmap)
        sub_net = attach_net(sub, cost_bps=cost_bps)
        m = float(sub_net['net_bps'].mean())
        n = len(sub_net)
        print(f'    flat-{name:<22s} : net mean {m:>+6.3f}bp  (n={n})')
        out[name] = m
    return out


def walk_forward(tr: pd.DataFrame, n_folds: int = 3) -> tuple[float, float, list]:
    """N-fold chronological walk-forward. Each fold uses (fold_i) as OOS.

    No parameter fitting — the strategy is pre-committed deterministic. So
    'walk-forward' here is really a chronological-stability check: split
    the sample into n_folds equal-time chunks, report Sharpe of each, the
    mean, and the min.
    """
    if len(tr) < 100:
        return float('nan'), float('nan'), []
    tr = tr.sort_values('date').reset_index(drop=True)
    n = len(tr)
    fold_size = n // n_folds
    sharpes = []
    print(f'  [chronological {n_folds}-fold Sharpe — pre-committed strategy, '
          f'no in-sample fitting]')
    for i in range(n_folds):
        lo = i * fold_size
        hi = (i + 1) * fold_size if i < n_folds - 1 else n
        sub = tr.iloc[lo:hi]
        r = sub['net_pct'].to_numpy()
        if len(r) < 20:
            continue
        years = max((sub['date'].iloc[-1] - sub['date'].iloc[0]).days / 365.25, 1e-9)
        tpy = len(r) / years
        sh = annualized_sharpe(r, trades_per_year=tpy)
        sharpes.append(sh)
        print(f'    fold {i+1}/{n_folds}: {sub["date"].iloc[0].date()} -> '
              f'{sub["date"].iloc[-1].date()}  n={len(r):>3d}  Sh {sh:>+5.2f}')
    if not sharpes:
        return float('nan'), float('nan'), []
    return float(np.mean(sharpes)), float(np.min(sharpes)), sharpes


def mef_diagnostic(tr_unc: pd.DataFrame, cost_bps: float) -> dict:
    """Compare MEF days vs non-MEF days at constant notional (no MEF amp).

    The diagnostic question is: do month-end-fix days show meaningfully
    higher per-trade gross than non-MEF days? If yes, MEF amplification
    has a basis. If no, drop MEF entirely.
    """
    tr = attach_net(tr_unc, cost_bps=cost_bps, mef_amplify=1.0)
    mef = tr[tr['is_mef']]
    non_mef = tr[~tr['is_mef']]
    out = {}
    print(f'  [MEF vs non-MEF diagnostic at constant 1x notional, '
          f'cost={cost_bps:.1f}bp]')
    for name, sub in [('MEF', mef), ('non-MEF', non_mef)]:
        if len(sub) == 0:
            continue
        gross = float(sub['gross_dir_bps'].mean())
        net = float(sub['net_bps'].mean())
        print(f'    {name:<8s} n={len(sub):>4d}  gross {gross:>+6.3f}bp  '
              f'net {net:>+6.3f}bp')
        out[name] = {'n': len(sub), 'gross_bps': gross, 'net_bps': net}
    if 'MEF' in out and 'non-MEF' in out:
        gap = out['MEF']['gross_bps'] - out['non-MEF']['gross_bps']
        print(f'    gap (MEF - non-MEF) gross : {gap:+.3f}bp  '
              f'(thesis predicts MEF stronger by 1.5x to 2x)')
        out['gap_gross_bps'] = gap
    return out


# ---------------------------------------------------------------------------
# Kill-criteria
# ---------------------------------------------------------------------------

def kill_criteria_check(stats_full: dict, regime: dict,
                         dir_null_gap_bps: float, dow_shuffle_pct: float,
                         wf_mean_sh: float, wf_min_sh: float,
                         cost_stress_mean_bps: float,
                         mef_gap_bps: float) -> bool:
    print(f'  [Phase 2 kill criteria — pre-committed]')
    n = stats_full.get('n', 0)
    wr = stats_full.get('wr', 0.0)
    pf = stats_full.get('pf', 0.0)
    mdd = stats_full.get('mdd', -1.0)
    mean_bps = stats_full.get('mean_bps', 0.0)
    w3_key = next((k for k in regime if k.startswith('W3')), None)
    w3_mean = regime.get(w3_key, {}).get('mean_bps', 0.0) if w3_key else 0.0

    def v(ok: bool) -> str:
        return 'PASS' if ok else 'FAIL'

    checks = [
        ('1. Full net/trade > {:+.1f}bp'.format(KC_NET_MEAN_BPS),
         mean_bps > KC_NET_MEAN_BPS, f'{mean_bps:+.3f}bp'),
        ('2. W3-modern net/trade > {:+.1f}bp'.format(KC_W3_MEAN_BPS),
         w3_mean > KC_W3_MEAN_BPS, f'{w3_mean:+.3f}bp ({w3_key or "n/a"})'),
        ('3. Dir-null gap > {:+.1f}bp'.format(KC_DIR_NULL_GAP_BPS),
         dir_null_gap_bps > KC_DIR_NULL_GAP_BPS, f'{dir_null_gap_bps:+.3f}bp'),
        ('4. DOW-shuffle pct >= {:.0%}'.format(KC_DOW_SHUFFLE_PCT),
         dow_shuffle_pct >= KC_DOW_SHUFFLE_PCT, f'{dow_shuffle_pct:.1%}'),
        ('5. Trades >= {}'.format(KC_TRADES),
         n >= KC_TRADES, f'{n}'),
        ('6. WR >= {:.0%} AND PF >= {:.2f}'.format(KC_WR, KC_PF),
         (wr >= KC_WR) and (pf >= KC_PF), f'WR {wr:.1%} PF {pf:.2f}'),
        ('7. MDD <= {:.0%}'.format(KC_MDD),
         abs(mdd) <= KC_MDD, f'{mdd*100:+.2f}%'),
        ('8. WF OOS Sh mean >= {:+.2f}, min >= {:+.2f}'.format(
            KC_WF_OOS_SHARPE_MEAN, KC_WF_OOS_SHARPE_MIN),
         (wf_mean_sh >= KC_WF_OOS_SHARPE_MEAN) and (wf_min_sh >= KC_WF_OOS_SHARPE_MIN),
         f'mean {wf_mean_sh:+.2f} min {wf_min_sh:+.2f}'),
        ('9. MEF gross > non-MEF gross (else drop MEF)',
         mef_gap_bps > 0, f'gap {mef_gap_bps:+.3f}bp'),
        ('10. Cost-stress@{:.0f}bp net > 0'.format(KC_COST_STRESS_BP),
         cost_stress_mean_bps > 0, f'{cost_stress_mean_bps:+.3f}bp'),
    ]
    all_pass = True
    for desc, ok, val in checks:
        print(f'    {desc:<48s} : {v(ok):<4s} ({val})')
        if not ok:
            all_pass = False
    print(f'  -> {"PASS" if all_pass else "FAIL"} on Phase 2 kill criteria')
    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    section('Loading USDJPY M5 (UTC, 2022-10 -> present)')
    df = load_m5()
    print(f'  bars   : {len(df):,}')
    print(f'  range  : {df["timestamp"].min()} -> {df["timestamp"].max()}')

    section('Build per-day trade table (entry 00:45 UTC, exit 01:05 UTC)')
    tbl = build_trades_table(df)
    print(f'  candidate days (any DOW): {len(tbl):,}')
    print(f'  DOW distribution of candidates:')
    dow_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}
    for d, name in dow_names.items():
        sub = tbl[tbl['dow'] == d]
        if len(sub):
            print(f'    {name}: n={len(sub):>4d}  gross {sub["gross_bps"].mean():+.3f}bp  '
                  f'std {sub["gross_bps"].std():.2f}bp')
    n_mef = int(tbl['is_mef'].sum())
    print(f'  month-end-fix candidate days: {n_mef}')

    # --------------------------------------------------------------------
    # Phase 0b — magnitude check (gross zero-cost mean on full sample
    #   with day-of-week direction mapping)
    # --------------------------------------------------------------------
    section('Phase 0b — magnitude check (gross zero-cost, DOW mapping)')
    tr_unc = apply_direction_mapping(tbl)
    tr_unc_net = attach_net(tr_unc, cost_bps=0.0)
    gross_mean = float(tr_unc_net['gross_dir_bps'].mean())
    n_tr = len(tr_unc_net)
    print(f'  trades (Mon/Tue SHORT + Wed LONG) : n={n_tr}')
    print(f'  gross mean per-day                : {gross_mean:+.3f} bps')
    print(f'  Phase 0 floor                     : {PHASE0_GROSS_FLOOR_BPS:+.3f} bps')
    phase0_pass = gross_mean >= PHASE0_GROSS_FLOOR_BPS
    if phase0_pass:
        print(f'  -> PASS Phase 0 magnitude floor; proceeding to Phase 2.')
    else:
        print(f'  -> REJECT at Phase 0. Gross magnitude below floor.')

    # Also: report each DOW arm in isolation, gross
    print(f'\n  Per-arm gross zero-cost (no cost, no direction-aggregation):')
    arms = [
        ('Mon SHORT', tbl[tbl['dow'] == 0], -1),
        ('Tue SHORT', tbl[tbl['dow'] == 1], -1),
        ('Wed LONG ', tbl[tbl['dow'] == 2], +1),
    ]
    for label, sub, sign in arms:
        if len(sub) == 0:
            continue
        g = sign * sub['gross_bps'].mean()
        t = (sign * sub['gross_bps']).mean() / (sub['gross_bps'].std() / np.sqrt(max(len(sub), 1)))
        print(f'    {label:<11s} n={len(sub):>4d}  gross {g:+.3f}bp  t={t:+.2f}')

    if not phase0_pass:
        section('VERDICT')
        print('  Phase 0b FAILED — mechanism gross magnitude below +1.5 bps floor.')
        print('  Lesson #45 corroborated for USDJPY at Eightcap cost level.')
        print('  No Phase 2 run; demo exits.')
        return 0

    # --------------------------------------------------------------------
    # Phase 2 — full kill-criteria battery at COST_BPS_DEFAULT
    # --------------------------------------------------------------------
    section('Phase 2 baseline — DOW mapping, cost={:.1f}bp RT, no MEF amp'.format(COST_BPS_DEFAULT))
    tr_baseline = attach_net(tr_unc, cost_bps=COST_BPS_DEFAULT, mef_amplify=1.0)
    stats_baseline = report_run('baseline (constant notional)', tr_baseline)

    section('Phase 2 baseline + MEF amp 2x — cost={:.1f}bp RT'.format(COST_BPS_DEFAULT))
    tr_mef = attach_net(tr_unc, cost_bps=COST_BPS_DEFAULT, mef_amplify=MEF_AMPLIFY)
    stats_mef = report_run('baseline + MEF 2x', tr_mef)

    section('Regime breakdown — baseline (no MEF)')
    rb_baseline = regime_breakdown(tr_baseline)

    section('Cost sweep — baseline (no MEF)')
    cs = cost_sweep(tr_unc)

    section('Flat-direction null — always-LONG / always-SHORT on M/T/W')
    flat = flat_direction_null(tbl, COST_BPS_DEFAULT)
    # Direction-null gap: how much does the actual mapping beat the BEST flat null?
    best_flat = max(flat.values()) if flat else 0.0
    dir_null_gap = stats_baseline['mean_bps'] - best_flat
    print(f'    actual DOW-mapping net mean      : {stats_baseline["mean_bps"]:+.3f}bp')
    print(f'    best flat-direction null net mean: {best_flat:+.3f}bp')
    print(f'    gap (actual - best flat)         : {dir_null_gap:+.3f}bp')

    section('Day-of-week shuffle null — actual mapping vs permutations')
    actual_mean, dow_pct, shuffled_means = dow_shuffle_null(tbl, COST_BPS_DEFAULT)
    print(f'    actual mapping net mean          : {actual_mean:+.3f}bp')
    print(f'    n shuffled mappings              : {len(shuffled_means)}')
    if len(shuffled_means) > 0:
        print(f'    shuffled distribution: min {shuffled_means.min():+.3f}  '
              f'p25 {np.percentile(shuffled_means, 25):+.3f}  '
              f'median {np.median(shuffled_means):+.3f}  '
              f'p75 {np.percentile(shuffled_means, 75):+.3f}  '
              f'max {shuffled_means.max():+.3f}')
        print(f'    actual percentile in null distribution : {dow_pct:.1%}')

    section('Chronological walk-forward — 3-fold')
    wf_mean, wf_min, wf_list = walk_forward(tr_baseline, n_folds=3)
    print(f'    mean fold Sharpe : {wf_mean:+.2f}')
    print(f'    min  fold Sharpe : {wf_min:+.2f}')

    section('MEF diagnostic — does month-end show stronger gross?')
    mef_diag = mef_diagnostic(tr_unc, COST_BPS_DEFAULT)
    mef_gap = mef_diag.get('gap_gross_bps', 0.0)

    section('KILL CRITERIA — Phase 2')
    cost_stress_mean = cs.get(KC_COST_STRESS_BP, {}).get('mean_bps', float('-inf'))
    pass_p2 = kill_criteria_check(
        stats_baseline, rb_baseline,
        dir_null_gap_bps=dir_null_gap,
        dow_shuffle_pct=dow_pct,
        wf_mean_sh=wf_mean, wf_min_sh=wf_min,
        cost_stress_mean_bps=cost_stress_mean,
        mef_gap_bps=mef_gap,
    )

    section('VERDICT')
    if pass_p2:
        print('  Phase 2 PASS. Candidate for Phase 3 cross-pair check '
              '(EURJPY / GBPJPY).')
    else:
        print('  Phase 2 REJECT. See kill-criteria detail above.')
    print('  Data caveat: full sample is 2022-10 -> present (~3.6y, W3+W4 era '
          'only). W1/W2 regime test infeasible — Eightcap USDJPY M5 history '
          'doesn\'t go pre-2022.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
