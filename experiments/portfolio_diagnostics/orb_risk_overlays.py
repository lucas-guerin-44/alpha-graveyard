#!/usr/bin/env python3
"""
orb_dax risk-overlay sweep: keep the signal, shrink the bad regimes.

Baseline = current deploy (GER40 M5, OR=30, T+180 LONG-only, 1pt cost).

Overlays tested (single + combined):
  A. Vol-target sizing — scale position by target_vol / current_vol (clipped)
  B. Long-term SMA trend filter — only fire when prior_close > SMA_N
  C. Daily loss limit — flat for the rest of the day after first loser
  D. Realized-vol filter — skip days where 20d realized vol > P_q

For each variant, report:
  Sharpe (vol-adjusted return space), MDD, Calmar, total return ($10k account
  at 1% risk-per-trade vol-sized), trades, worst single trade, % trades skipped.

The point: which overlay improves Calmar (return / |MDD|) the most without
gutting absolute return?
"""
from __future__ import annotations

import os
import sys
import importlib

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'orb'))


ACCOUNT = 10_000.0
RISK_PCT = 0.01
TARGET_VOL_ANN = 0.15   # 15% annualized for underlying vol target


def section(t: str) -> None:
    print(f"\n{'=' * 92}\n  {t}\n{'=' * 92}")


def annual_sharpe(r: np.ndarray, bpy: int = 252) -> float:
    r = r[np.isfinite(r)]
    if r.size < 2:
        return 0.0
    s = r.std(ddof=1)
    return 0.0 if s == 0 else float(r.mean() / s * np.sqrt(bpy))


# --- load baseline orb_dax + daily price series --------------------------

def load_orb_baseline():
    os.environ['ORB_SYMBOL'] = 'GER40'
    os.environ['ORB_SESSION'] = 'EU'
    import orb_demo
    importlib.reload(orb_demo)
    bars = orb_demo.load_m5('GER40')
    daily_idx = pd.Index(sorted(set(bars.index.date)))
    bias = pd.Series(1, index=daily_idx, dtype=int)
    bar_ret, trades = orb_demo.simulate_orb(
        bars, or_minutes=30, entry_cutoff_min=180, tod_exit_minutes=180,
        trend_filter=bias, cost_points=1.0,
    )
    # Daily close = last bar of each session day in UTC
    daily_close = bars['close'].groupby(bars.index.date).last()
    daily_close.index = pd.to_datetime(daily_close.index)
    return bars, bar_ret, trades, daily_close


def daily_realized_vol(daily_close: pd.Series, window: int = 20) -> pd.Series:
    ret = daily_close.pct_change()
    return ret.rolling(window).std(ddof=1) * np.sqrt(252)  # annualized


def sma(daily_close: pd.Series, n: int) -> pd.Series:
    return daily_close.rolling(n).mean()


# --- overlay-aware PnL builder ------------------------------------------

def build_pnl(trades: list[dict],
              daily_close: pd.Series,
              one_R: float,
              overlay_size: pd.Series | None = None,
              overlay_skip: pd.Series | None = None,
              daily_loss_limit: bool = False,
              ) -> tuple[pd.Series, dict]:
    """
    Returns a daily $-PnL series and metadata.

    overlay_size: daily series of position multipliers (e.g. vol-target). Looked
                  up by entry-date prior-day.
    overlay_skip: daily series of bool (True = skip trade on this date).
    daily_loss_limit: if True, skip trade if a prior trade today already lost.

    Sizing: $ PnL per trade = equity_t * RISK_PCT * (pnl_pct / one_R) * scale
    """
    trade_df = pd.DataFrame(trades).copy()
    if len(trade_df) == 0:
        return pd.Series(dtype=float), {'trades_fired': 0, 'trades_skipped': 0}
    trade_df['date'] = pd.to_datetime(trade_df['date']).dt.normalize()
    trade_df = trade_df.sort_values(['date', 'entry_ts']).reset_index(drop=True)

    skipped = 0
    fired = 0
    equity = ACCOUNT
    rows = []
    for d, g in trade_df.groupby('date', sort=True):
        # Use prior-day's vol / SMA to avoid lookahead
        prior_d = daily_close.index[daily_close.index.searchsorted(d) - 1] \
            if d in daily_close.index else d
        scale = 1.0
        if overlay_size is not None:
            try:
                v = overlay_size.loc[prior_d]
                if pd.notna(v):
                    scale = float(v)
            except KeyError:
                scale = 1.0
        skip_day = False
        if overlay_skip is not None:
            try:
                sk = overlay_skip.loc[prior_d]
                if pd.notna(sk) and bool(sk):
                    skip_day = True
            except KeyError:
                skip_day = False

        day_pnl = 0.0
        day_loser_hit = False
        for _, r in g.iterrows():
            if skip_day:
                skipped += 1
                continue
            if daily_loss_limit and day_loser_hit:
                skipped += 1
                continue
            R = r['pnl_pct'] / one_R
            trade_pnl = equity * RISK_PCT * R * scale
            day_pnl += trade_pnl
            fired += 1
            if r['pnl_pct'] < 0:
                day_loser_hit = True
        equity += day_pnl
        rows.append({'date': d, 'pnl': day_pnl, 'equity': equity})
    out = pd.DataFrame(rows).set_index('date')
    return out, {'trades_fired': fired, 'trades_skipped': skipped}


def metrics(pnl_df: pd.DataFrame) -> dict:
    if len(pnl_df) == 0:
        return {}
    eq = pnl_df['equity']
    daily_ret = pnl_df['pnl'] / eq.shift(1).fillna(ACCOUNT)
    sh = annual_sharpe(daily_ret.to_numpy())
    peak = eq.cummax()
    dd = (eq - peak) / peak
    mdd = float(dd.min())
    tot = float(eq.iloc[-1] / ACCOUNT - 1)
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (1 + tot) ** (1 / max(years, 1e-9)) - 1
    return {
        'final_equity': float(eq.iloc[-1]),
        'total_return': tot,
        'cagr': cagr,
        'sharpe': sh,
        'mdd': mdd,
        'calmar': cagr / abs(mdd) if mdd < 0 else float('inf'),
        'worst_day': float(pnl_df['pnl'].min()),
        'best_day': float(pnl_df['pnl'].max()),
    }


def print_row(label: str, m: dict, info: dict, baseline: dict | None = None) -> None:
    delta_str = ''
    if baseline:
        d_ret = (m['total_return'] - baseline['total_return']) * 100
        d_mdd = (m['mdd'] - baseline['mdd']) * 100  # less negative = improvement
        d_calmar = m['calmar'] - baseline['calmar']
        delta_str = f"  | d_ret {d_ret:+5.1f}pp  d_MDD {d_mdd:+5.2f}pp  d_Calmar {d_calmar:+5.2f}"
    print(f"  {label:<32s}  "
          f"Sh={m['sharpe']:+.2f}  "
          f"CAGR={m['cagr']*100:+5.1f}%  "
          f"MDD={m['mdd']*100:+6.2f}%  "
          f"Calmar={m['calmar']:.2f}  "
          f"final=${m['final_equity']:>7,.0f}  "
          f"fired={info['trades_fired']:>4d} skipped={info['trades_skipped']:>4d}"
          f"{delta_str}")


# --- main ---------------------------------------------------------------

def main() -> int:
    section('Loading orb_dax baseline')
    bars, bar_ret, trades, daily_close = load_orb_baseline()
    print(f"  bars: {len(bars):,}  trades: {len(trades)}  "
          f"daily range: {daily_close.index.min().date()} -> {daily_close.index.max().date()}")

    # 1R = stdev of pct_returns (vol-targeted unit)
    trade_pcts = np.array([t['pnl_pct'] for t in trades])
    one_R = float(trade_pcts.std(ddof=1))
    print(f"  1R (trade-return stdev): {one_R*100:.3f}%")

    rvol_20 = daily_realized_vol(daily_close, 20)
    sma_200 = sma(daily_close, 200)
    sma_50 = sma(daily_close, 50)

    section('Baseline (no overlay)')
    pnl_base, info_base = build_pnl(trades, daily_close, one_R)
    m_base = metrics(pnl_base)
    print_row('baseline', m_base, info_base)

    section('Overlay A: vol-target sizing (size = TARGET_VOL / realized_vol)')
    # Scale = target_vol / current_vol, clipped [0.25, 2.0]
    for clip_hi, label in [(2.0, 'clip [0.25, 2.0]'), (1.5, 'clip [0.25, 1.5]'), (1.0, 'clip [0.25, 1.0]')]:
        scale = (TARGET_VOL_ANN / rvol_20).clip(0.25, clip_hi)
        pnl, info = build_pnl(trades, daily_close, one_R, overlay_size=scale)
        m = metrics(pnl)
        print_row(f'voltgt 15% {label}', m, info, m_base)

    section('Overlay B: long-term SMA trend filter')
    for n in (50, 100, 200):
        sma_n = sma(daily_close, n)
        # Skip when prior_close < SMA_N (i.e., long-term downtrend)
        skip = (daily_close < sma_n)
        pnl, info = build_pnl(trades, daily_close, one_R, overlay_skip=skip)
        m = metrics(pnl)
        print_row(f'SMA-{n} regime (skip below)', m, info, m_base)

    section('Overlay C: daily-loss-limit (flat after first loss of the day)')
    pnl, info = build_pnl(trades, daily_close, one_R, daily_loss_limit=True)
    m = metrics(pnl)
    print_row('daily-loss-limit', m, info, m_base)

    section('Overlay D: skip high-vol days (rvol > p_q)')
    for q in (0.75, 0.85, 0.90, 0.95):
        thresh = rvol_20.quantile(q)
        skip = rvol_20 > thresh
        pnl, info = build_pnl(trades, daily_close, one_R, overlay_skip=skip)
        m = metrics(pnl)
        print_row(f'skip rvol > p{int(q*100)} (={thresh*100:.0f}% ann)', m, info, m_base)

    section('Combinations')
    # Vol-target + SMA-200 + daily-loss-limit
    scale = (TARGET_VOL_ANN / rvol_20).clip(0.25, 1.5)
    skip200 = (daily_close < sma_200)

    pnl, info = build_pnl(trades, daily_close, one_R,
                          overlay_size=scale, overlay_skip=skip200)
    m = metrics(pnl); print_row('voltgt + SMA-200', m, info, m_base)

    pnl, info = build_pnl(trades, daily_close, one_R,
                          overlay_size=scale, daily_loss_limit=True)
    m = metrics(pnl); print_row('voltgt + daily-loss-limit', m, info, m_base)

    pnl, info = build_pnl(trades, daily_close, one_R,
                          overlay_size=scale, overlay_skip=skip200,
                          daily_loss_limit=True)
    m = metrics(pnl); print_row('voltgt + SMA-200 + DLL', m, info, m_base)

    section('Drawdown profile comparison (vol-target [0.25,1.5] vs baseline)')
    scale = (TARGET_VOL_ANN / rvol_20).clip(0.25, 1.5)
    pnl_v, _ = build_pnl(trades, daily_close, one_R, overlay_size=scale)
    for name, pnl in [('baseline', pnl_base), ('voltgt-1.5', pnl_v)]:
        eq = pnl['equity']
        peak = eq.cummax()
        dd = (eq - peak) / peak
        in_dd = dd < -0.005
        episodes = []
        st = None
        for t, f in in_dd.items():
            if f and st is None:
                st = t
            elif not f and st is not None:
                sub = dd.loc[st:t]
                episodes.append((sub.min(), st, sub.idxmin(), t, (t - st).days))
                st = None
        episodes = sorted(episodes, key=lambda x: x[0])[:3]
        print(f"\n  {name}: top-3 drawdowns")
        for depth, s, tr, rec, days in episodes:
            print(f"    {s.date()} -> trough {tr.date()} -> rec {rec.date()}  "
                  f"depth {depth*100:+.2f}%  days {days}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
