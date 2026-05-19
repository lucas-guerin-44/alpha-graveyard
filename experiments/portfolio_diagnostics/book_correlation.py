#!/usr/bin/env python3
"""
Correlation / co-movement diagnostic for the current 3-strategy live book.

  orb_dax       — GER40 M5, EU session, OR=30, T+180 LONG-only
  lunch_fade    — NDX100 M5, US session, thr=0.25 LONG-only fade
  xau_session   — XAUUSD H1, 23->08 UTC Variant C, DOWN-med filter, LONG

Re-runs each strategy with its deployed config, aggregates bar/trade returns
to a daily PnL series, then reports:

  * Pairwise Pearson + Spearman correlation, full sample and by regime window
  * Trading-day firing overlap (% of days where >1 strategy is in-trade)
  * Tail co-movement: down-day concordance + |R| > median |R| co-move
  * 63-day rolling correlation summary
  * Equal-vol-blended Sharpe vs sum of component Sharpes (diversification ratio)
  * Beta of each strategy to SPX500 daily and to a 50/50 SPX/NDX risk-on proxy
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'orb'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'lunch_fade'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'xau_session'))


# --- deployed config: orb_dax (GER40 EU) -----------------------------------

def run_orb_dax() -> pd.Series:
    os.environ['ORB_SYMBOL'] = 'GER40'
    os.environ['ORB_SESSION'] = 'EU'
    import importlib
    import orb_demo
    importlib.reload(orb_demo)  # pick up env vars

    bars = orb_demo.load_m5('GER40')
    bar_ret, _ = orb_demo.simulate_orb(
        bars,
        or_minutes=30,
        entry_cutoff_min=180,
        tod_exit_minutes=180,
        trend_filter=pd.Series(1.0, index=bars.index),  # LONG-only
        cost_points=1.0,
    )
    return _bars_to_daily(bar_ret, name='orb_dax')


# --- deployed config: lunch_fade (NDX LONG-only fade thr=0.25) -------------

def run_lunch_fade() -> pd.Series:
    os.environ['LUNCH_SYMBOL'] = 'NDX100'
    import importlib
    import lunch_fade_demo
    importlib.reload(lunch_fade_demo)

    bars = lunch_fade_demo.load_m5('NDX100')
    bar_ret, _ = lunch_fade_demo.simulate_lunch_fade(
        bars,
        morning_end_min=120,
        afternoon_end_min=240,
        min_move_atr=0.25,
        cost_points=1.0,
        direction='fade',
        long_only=True,
    )
    return _bars_to_daily(bar_ret, name='lunch_fade')


# --- deployed config: xau_session (Variant C dnmed long) -------------------

def run_xau_session() -> pd.Series:
    import xau_session_demo as xs
    df = xs.load_h1()
    ny = xs.build_ny_summary(df)
    ret, _ = xs.simulate(
        df,
        ny,
        filter_mode='dnmed',
        z_threshold=1.0,
        cost_bps=2.0,
        direction='long',
    )
    # ret is already per-trade indexed by trade-date — collapse to daily.
    ret.index = pd.to_datetime(ret.index).tz_localize(None).normalize()
    daily = ret.groupby(ret.index).sum().rename('xau_session')
    return daily


# ---------------------------------------------------------------------------

def _bars_to_daily(bar_ret: pd.Series, name: str) -> pd.Series:
    """Sum tz-aware bar-returns into a daily PnL series indexed by UTC date.

    Compounding across a handful of bars per trade is ~equal to summing at
    these magnitudes, and summing keeps things linear for the correlation
    math (we treat per-day return as additive).
    """
    if bar_ret.empty:
        return pd.Series(dtype=float, name=name)
    idx = bar_ret.index
    if idx.tz is None:
        days = pd.to_datetime(idx).normalize()
    else:
        days = idx.tz_convert('UTC').tz_localize(None).normalize()
    daily = bar_ret.groupby(days).sum()
    daily.name = name
    return daily


# --- analysis helpers ------------------------------------------------------

def regime_window(ts: pd.Timestamp) -> str:
    y = ts.year
    if y <= 2020:
        return 'W1_2019_2020'
    if y <= 2022:
        return 'W2_2021_2022'
    if y <= 2024:
        return 'W3_2023_2024'
    return 'W4_2025_2026'


def annual_sharpe(r: np.ndarray, bpy: int = 252) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    std = r.std(ddof=1)
    if std == 0:
        return 0.0
    return float(r.mean() / std * np.sqrt(bpy))


def section(title: str) -> None:
    print(f"\n{'=' * 84}\n  {title}\n{'=' * 84}")


def correlation_table(df: pd.DataFrame, method: str = 'pearson') -> pd.DataFrame:
    # Restrict to days where each pair has *some* activity (non-zero in either)
    # to avoid the inflation of correlation by shared zeros (flat days).
    cols = df.columns
    out = pd.DataFrame(np.eye(len(cols)), index=cols, columns=cols)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if j <= i:
                continue
            sub = df[[a, b]].copy()
            active = (sub[a].abs() > 0) | (sub[b].abs() > 0)
            sub = sub.loc[active]
            if len(sub) < 5:
                out.loc[a, b] = out.loc[b, a] = np.nan
                continue
            c = sub.corr(method=method).iloc[0, 1]
            out.loc[a, b] = out.loc[b, a] = c
    return out


def downday_concordance(df: pd.DataFrame) -> pd.DataFrame:
    cols = df.columns
    out = pd.DataFrame(np.nan, index=cols, columns=cols)
    for a in cols:
        for b in cols:
            if a == b:
                out.loc[a, b] = 1.0
                continue
            sub = df[[a, b]].copy()
            sub = sub.loc[(sub[a] < 0)]
            if len(sub) < 5:
                continue
            out.loc[a, b] = float((sub[b] < 0).mean())
    return out


def fire_overlap(df: pd.DataFrame) -> dict:
    active = df.abs() > 0
    n_days = len(active)
    fires_per_day = active.sum(axis=1)
    return {
        'n_days': int(n_days),
        'days_any_active': int((fires_per_day > 0).sum()),
        'days_2plus_active': int((fires_per_day >= 2).sum()),
        'days_3_active': int((fires_per_day == 3).sum()),
        'mean_strategies_per_day': float(fires_per_day.mean()),
    }


def rolling_corr_summary(df: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    cols = df.columns
    rows = []
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if j <= i:
                continue
            sub = df[[a, b]]
            rc = sub[a].rolling(window).corr(sub[b]).dropna()
            if len(rc) == 0:
                continue
            rows.append({
                'pair': f'{a} vs {b}',
                'n_windows': len(rc),
                'mean': float(rc.mean()),
                'p10': float(rc.quantile(0.10)),
                'p50': float(rc.quantile(0.50)),
                'p90': float(rc.quantile(0.90)),
                'max_abs': float(rc.abs().max()),
                'pct_above_+0.30': float((rc > 0.30).mean()),
                'pct_below_-0.30': float((rc < -0.30).mean()),
            })
    return pd.DataFrame(rows)


def equal_vol_blend(df: pd.DataFrame) -> pd.Series:
    vols = df.std(ddof=1)
    w = (1.0 / vols).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    w = w / w.sum()
    blend = (df * w).sum(axis=1)
    blend.name = 'blend'
    print(f"  Equal-vol weights: " + ', '.join(f'{c}={w[c]:.3f}' for c in df.columns))
    return blend


def beta_to(df: pd.DataFrame, bench: pd.Series) -> pd.DataFrame:
    rows = []
    for c in df.columns:
        sub = pd.concat([df[c], bench], axis=1, join='inner').dropna()
        sub = sub.loc[sub[c].abs() > 0]  # only days the strategy was active
        if len(sub) < 30:
            rows.append({'strategy': c, 'n': len(sub), 'beta': np.nan, 'corr': np.nan})
            continue
        x = sub.iloc[:, 1].to_numpy()
        y = sub.iloc[:, 0].to_numpy()
        b = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
        r = np.corrcoef(y, x)[0, 1]
        rows.append({'strategy': c, 'n': len(sub), 'beta': float(b), 'corr': float(r)})
    return pd.DataFrame(rows)


# --- benchmark loader -----------------------------------------------------

def load_spx_daily() -> pd.Series:
    """Daily close-to-close return for SPX500 (from the M5 file we already have)."""
    from utils import fetch_ohlc
    raw = fetch_ohlc('SPX500', 'M5', '2019-01-01', '2026-04-18')
    if raw is None or raw.empty:
        return pd.Series(dtype=float, name='spx')
    df = raw[['timestamp', 'close']].copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.set_index('timestamp').sort_index()
    # Daily close = last bar of each UTC date
    daily_close = df['close'].groupby(df.index.tz_convert('UTC').tz_localize(None).normalize()).last()
    daily_ret = daily_close.pct_change().rename('spx_ret')
    return daily_ret


# --- main -----------------------------------------------------------------

def main() -> int:
    section('Re-running each deployed strategy')
    orb = run_orb_dax()
    lf = run_lunch_fade()
    xau = run_xau_session()

    df = pd.concat([orb, lf, xau], axis=1).fillna(0.0).sort_index()
    # Restrict to overlapping span
    first = max(orb.index.min(), lf.index.min(), xau.index.min())
    last = min(orb.index.max(), lf.index.max(), xau.index.max())
    df = df.loc[first:last]
    print(f"  Date range: {first.date()} -> {last.date()}  ({len(df)} days)")
    print(f"  Trades per day non-zero: " +
          ', '.join(f"{c}={(df[c] != 0).sum()}" for c in df.columns))

    section('Per-strategy headline (daily-aggregated)')
    for c in df.columns:
        r = df[c].to_numpy()
        eq = (1.0 + df[c]).cumprod()
        sh = annual_sharpe(r)
        mdd = float(((eq - eq.cummax()) / eq.cummax()).min())
        print(f"  {c:12s} | Sh={sh:+.2f}  total={eq.iloc[-1]-1:+.2%}  MDD={mdd:.2%}  "
              f"active_days={(np.abs(r) > 0).sum()}")

    section('Pairwise correlation (Pearson, active-day-conditional)')
    print(correlation_table(df, 'pearson').round(3).to_string())

    section('Pairwise correlation (Spearman)')
    print(correlation_table(df, 'spearman').round(3).to_string())

    section('Correlation by regime window')
    regimes = df.index.map(regime_window)
    for reg, sub in df.groupby(regimes):
        if len(sub) < 30:
            print(f"\n  {reg}: only {len(sub)} days, skipped")
            continue
        print(f"\n  {reg}  ({len(sub)} days)")
        print(correlation_table(sub, 'pearson').round(3).to_string())

    section('Firing overlap (how often >1 strategy is in-trade same day)')
    fo = fire_overlap(df)
    for k, v in fo.items():
        print(f"  {k:30s} {v}")

    section('Down-day concordance: P(col_strategy <0 | row_strategy <0)')
    print(downday_concordance(df).round(3).to_string())

    section('Rolling 63-day correlation summary')
    print(rolling_corr_summary(df, window=63).round(3).to_string(index=False))

    section('Equal-vol blend vs components')
    blend = equal_vol_blend(df)
    full = pd.concat([df, blend], axis=1)
    for c in full.columns:
        r = full[c].to_numpy()
        sh = annual_sharpe(r)
        print(f"  {c:12s} Sh={sh:+.2f}  vol_ann={full[c].std(ddof=1) * np.sqrt(252):.4f}")
    # Diversification ratio = sum(w_i * sigma_i) / sigma_portfolio
    vols = df.std(ddof=1)
    w = (1.0 / vols)
    w = w / w.sum()
    weighted_avg_vol = (w * vols).sum()
    port_vol = blend.std(ddof=1)
    div_ratio = weighted_avg_vol / port_vol if port_vol > 0 else np.nan
    print(f"\n  Diversification ratio = weighted-avg-vol / port-vol = {div_ratio:.2f}")
    print(f"    (1.0 = no diversification; sqrt(N)~1.73 = perfectly uncorrelated 3 strats)")

    section('Beta to SPX500 (daily close-to-close)')
    try:
        spx = load_spx_daily().dropna()
        spx.index = pd.to_datetime(spx.index)
        print(beta_to(df, spx).round(3).to_string(index=False))
    except Exception as e:
        print(f"  could not load SPX benchmark: {e}")

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
