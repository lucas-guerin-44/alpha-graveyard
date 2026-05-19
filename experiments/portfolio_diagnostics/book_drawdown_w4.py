#!/usr/bin/env python3
"""
Combined-book drawdown under 1%-risk-per-trade sizing + W4 drill-down.

Sizing convention:
  1R = mean absolute loser-pct per strategy (its natural per-trade risk unit)
  Risk per trade = 1% of current equity (compounded)
  -> scaled trade return = (trade_pct / one_R_pct) * 0.01

Account = $10,000. Three strategies share the same account; each fires
independently with its 1% sizing on its own active days.

Reports:
  * Combined equity curve, peak DD, worst-N drawdown periods
  * Drawdown decomposition: which strategy was draining on bad days
  * 'Three-strategy concurrent' day stats
  * W4 (2025-26) lunch_fade vs xau_session drill-down:
      - scatter / top shared-active days
      - regression on EURUSD daily change (USD-direction proxy)
      - residual correlation after stripping USD beta
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
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'lunch_fade'))
sys.path.insert(0, os.path.join(_EXPERIMENTS, 'xau_session'))


ACCOUNT = 10_000.0
RISK_PCT = 0.01  # 1% of equity per trade at 1R adverse move


def section(t: str) -> None:
    print(f"\n{'=' * 88}\n  {t}\n{'=' * 88}")


# --- per-strategy trade extraction with deployed config --------------------

def trades_orb_dax() -> pd.DataFrame:
    os.environ['ORB_SYMBOL'] = 'GER40'
    os.environ['ORB_SESSION'] = 'EU'
    import orb_demo
    importlib.reload(orb_demo)
    bars = orb_demo.load_m5('GER40')
    # trend_filter must be keyed by datetime.date (see orb_demo main()).
    daily_idx = pd.Index(sorted(set(bars.index.date)))
    long_only_bias = pd.Series(1, index=daily_idx, dtype=int)
    _, trades = orb_demo.simulate_orb(
        bars,
        or_minutes=30, entry_cutoff_min=180, tod_exit_minutes=180,
        trend_filter=long_only_bias,
        cost_points=1.0,
    )
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(trades)
    df['exit_dt'] = pd.to_datetime(df['exit_ts']).dt.tz_convert('UTC').dt.tz_localize(None).dt.normalize()
    df['strategy'] = 'orb_dax'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


def trades_lunch_fade() -> pd.DataFrame:
    os.environ['LUNCH_SYMBOL'] = 'NDX100'
    import lunch_fade_demo
    importlib.reload(lunch_fade_demo)
    bars = lunch_fade_demo.load_m5('NDX100')
    _, trades = lunch_fade_demo.simulate_lunch_fade(
        bars, morning_end_min=120, afternoon_end_min=240,
        min_move_atr=0.25, cost_points=1.0,
        direction='fade', long_only=True,
    )
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(trades)
    df['exit_dt'] = pd.to_datetime(df['exit_ts']).dt.tz_convert('UTC').dt.tz_localize(None).dt.normalize()
    df['strategy'] = 'lunch_fade'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


def trades_xau_session() -> pd.DataFrame:
    import xau_session_demo as xs
    df_bars = xs.load_h1()
    ny = xs.build_ny_summary(df_bars)
    _, trades = xs.simulate(
        df_bars, ny, filter_mode='dnmed', z_threshold=1.0,
        cost_bps=2.0, direction='long',
    )
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame(trades)
    df['exit_dt'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.normalize() \
        if pd.to_datetime(df['date']).dt.tz is not None else pd.to_datetime(df['date']).dt.normalize()
    df['pnl_pct'] = df['net_pct']
    df['strategy'] = 'xau_session'
    return df[['strategy', 'exit_dt', 'pnl_pct']]


# --- 1R-sizing -------------------------------------------------------------

def compute_one_R(trades: pd.DataFrame) -> float:
    """1R = stdev of trade returns (vol-targeted sizing).

    Using mean-loser as 1R mis-sizes strategies with hard stops (ORB clips
    losers tightly => artificially small 1R => excessive leverage). Stdev
    captures the full trade-return distribution including occasional large
    losses from gaps/slippage and is the standard fixed-fractional risk unit.
    """
    return float(trades['pnl_pct'].std(ddof=1))


def scaled_daily_pnl(all_trades: pd.DataFrame, one_R: dict, account: float = ACCOUNT,
                     risk_pct: float = RISK_PCT) -> pd.DataFrame:
    """Compounded $-PnL: each trade earns equity_t * risk_pct * (trade_pct / 1R)."""
    all_trades = all_trades.sort_values('exit_dt').reset_index(drop=True)
    # Compute R-multiple per trade
    all_trades['R'] = all_trades.apply(
        lambda r: r['pnl_pct'] / one_R[r['strategy']], axis=1)
    # Walk forward with compounded equity
    equity = account
    pnl_rows = []
    eq_rows = []
    # Aggregate by date so that same-day trades use same opening equity
    for dt, group in all_trades.groupby('exit_dt', sort=True):
        day_total_R_pct = 0.0
        per_strat = {'orb_dax': 0.0, 'lunch_fade': 0.0, 'xau_session': 0.0}
        for _, r in group.iterrows():
            day_total_R_pct += risk_pct * r['R']
            per_strat[r['strategy']] += equity * risk_pct * r['R']
        pnl_today = equity * day_total_R_pct
        equity = equity + pnl_today
        pnl_rows.append({'date': dt, **per_strat, 'total_pnl': pnl_today})
        eq_rows.append({'date': dt, 'equity': equity})
    pnl_df = pd.DataFrame(pnl_rows).set_index('date')
    eq_df = pd.DataFrame(eq_rows).set_index('date')
    return pnl_df.join(eq_df)


def drawdown_stats(eq: pd.Series, top_n: int = 5) -> dict:
    peak = eq.cummax()
    dd = (eq - peak) / peak
    # Find drawdown episodes
    in_dd = dd < -0.005  # 0.5% threshold
    episodes = []
    start = None
    for i, (t, flag) in enumerate(in_dd.items()):
        if flag and start is None:
            start = t
        elif not flag and start is not None:
            sub = dd.loc[start:t]
            trough = sub.idxmin()
            episodes.append({
                'start': start, 'trough': trough, 'recover': t,
                'depth_pct': float(sub.min() * 100),
                'depth_dollar': float((eq.loc[trough] - peak.loc[start])),
                'duration_days': (t - start).days,
            })
            start = None
    if start is not None:
        sub = dd.loc[start:]
        trough = sub.idxmin()
        episodes.append({
            'start': start, 'trough': trough, 'recover': None,
            'depth_pct': float(sub.min() * 100),
            'depth_dollar': float(eq.loc[trough] - peak.loc[start]),
            'duration_days': (eq.index[-1] - start).days,
        })
    episodes = sorted(episodes, key=lambda e: e['depth_pct'])[:top_n]
    return {
        'max_dd_pct': float(dd.min() * 100),
        'max_dd_dollar': float((eq - peak).min()),
        'final_equity': float(eq.iloc[-1]),
        'total_return_pct': float((eq.iloc[-1] / eq.iloc[0] - 1) * 100),
        'episodes': episodes,
    }


# --- USD proxy -------------------------------------------------------------

def load_eurusd_daily_change() -> pd.Series:
    path = os.path.join(_ROOT, 'ohlc_data', 'EURUSD_D1.csv')
    df = pd.read_csv(path, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_localize(None).dt.normalize()
    df = df.sort_values('timestamp').set_index('timestamp')
    ret = df['close'].pct_change().rename('eurusd_ret')
    # USD-up proxy = -EURUSD ret
    return (-ret).rename('usd_up')


# --- W4 drill-down ---------------------------------------------------------

def w4_drill(pnl_df: pd.DataFrame, eurusd_usd_up: pd.Series) -> None:
    w4 = pnl_df.loc['2025-01-01':].copy()
    print(f"  W4 window: {w4.index.min().date()} -> {w4.index.max().date()} ({len(w4)} days)")

    # Restrict to days where lunch_fade and xau_session both active
    both_active = (w4['lunch_fade'] != 0) & (w4['xau_session'] != 0)
    sub = w4.loc[both_active, ['lunch_fade', 'xau_session']]
    print(f"  Days with BOTH lunch_fade & xau_session active in W4: {len(sub)}")
    if len(sub) < 5:
        print("  Too few co-active days for meaningful analysis. Showing all W4 days instead.")
        sub_all = w4[['lunch_fade', 'xau_session']]
        any_active = (sub_all['lunch_fade'] != 0) | (sub_all['xau_session'] != 0)
        sub = sub_all.loc[any_active]
        print(f"  Days with EITHER active: {len(sub)}")
    if len(sub) >= 3:
        c = sub.corr().iloc[0, 1]
        print(f"  Pearson corr (co-active or either-active days, dollar PnL): {c:+.3f}")

    # Top shared days
    print(f"\n  Top contributing shared days (|lunch_fade| + |xau_session|):")
    sub2 = sub.copy()
    sub2['combined_abs'] = sub2['lunch_fade'].abs() + sub2['xau_session'].abs()
    print(sub2.sort_values('combined_abs', ascending=False).head(10).round(2).to_string())

    # USD residual: regress each on EURUSD-USD-up, then correlate residuals
    merged = sub.join(eurusd_usd_up, how='left').dropna()
    if len(merged) < 10:
        print("\n  Not enough USD-overlap days for residual analysis.")
        return
    print(f"\n  USD-proxy days available: {len(merged)}")

    def beta_and_resid(y, x):
        x_mean, y_mean = x.mean(), y.mean()
        b = ((x - x_mean) * (y - y_mean)).sum() / ((x - x_mean) ** 2).sum()
        a = y_mean - b * x_mean
        resid = y - (a + b * x)
        return b, resid

    b_lf, res_lf = beta_and_resid(merged['lunch_fade'], merged['usd_up'])
    b_xau, res_xau = beta_and_resid(merged['xau_session'], merged['usd_up'])

    print(f"\n  USD-up beta (W4 co-active days):")
    print(f"    lunch_fade  $-PnL beta to USD-up = {b_lf:+.2f}   (per 1 unit USD-up move)")
    print(f"    xau_session $-PnL beta to USD-up = {b_xau:+.2f}")

    raw_corr = merged[['lunch_fade', 'xau_session']].corr().iloc[0, 1]
    res_corr = np.corrcoef(res_lf, res_xau)[0, 1]
    print(f"\n  Raw correlation (W4 co-active):       {raw_corr:+.3f}")
    print(f"  USD-stripped residual correlation:     {res_corr:+.3f}")
    print(f"  Share of co-variance explained by USD: {1 - res_corr**2 / max(raw_corr**2, 1e-9):.1%}"
          if raw_corr != 0 else "")

    # Sanity: same regression on full W1-W3 window
    pre_w4 = pnl_df.loc[:'2024-12-31'].copy()
    bo = (pre_w4['lunch_fade'] != 0) & (pre_w4['xau_session'] != 0)
    pre = pre_w4.loc[bo, ['lunch_fade', 'xau_session']].join(eurusd_usd_up, how='left').dropna()
    if len(pre) >= 10:
        b_lf2, res_lf2 = beta_and_resid(pre['lunch_fade'], pre['usd_up'])
        b_xau2, res_xau2 = beta_and_resid(pre['xau_session'], pre['usd_up'])
        raw2 = pre[['lunch_fade', 'xau_session']].corr().iloc[0, 1]
        res2 = np.corrcoef(res_lf2, res_xau2)[0, 1]
        print(f"\n  Pre-W4 (2019-2024) comparison ({len(pre)} co-active days):")
        print(f"    USD betas: lf={b_lf2:+.2f}, xau={b_xau2:+.2f}")
        print(f"    Raw corr={raw2:+.3f}  | residual corr={res2:+.3f}")


# --- main ------------------------------------------------------------------

def main() -> int:
    section('Loading deployed trades from each strategy')
    t_orb = trades_orb_dax()
    t_lf = trades_lunch_fade()
    t_xau = trades_xau_session()
    print(f"  orb_dax     trades: {len(t_orb)}")
    print(f"  lunch_fade  trades: {len(t_lf)}")
    print(f"  xau_session trades: {len(t_xau)}")

    all_trades = pd.concat([t_orb, t_lf, t_xau], ignore_index=True)

    section('Per-strategy 1R (stdev of trade returns — vol-targeted sizing)')
    one_R = {}
    for s, df in all_trades.groupby('strategy'):
        one_R[s] = compute_one_R(df)
        losers = df.loc[df['pnl_pct'] < 0, 'pnl_pct']
        winners = df.loc[df['pnl_pct'] > 0, 'pnl_pct']
        worst = df['pnl_pct'].min()
        print(f"  {s:12s} | n={len(df)}  1R(stdev)={one_R[s]*100:.3f}%  "
              f"avg_win={winners.mean()*100:+.3f}%  avg_loss={losers.mean()*100:+.3f}%  "
              f"worst={worst*100:+.3f}%  WR={(df['pnl_pct']>0).mean()*100:.1f}%")
        # Worst trade in R-multiple terms
        worst_R = worst / one_R[s]
        print(f"               worst trade in R-multiples = {worst_R:.2f}R "
              f"(=> ${ACCOUNT*RISK_PCT*abs(worst_R):,.0f} loss at 1% risk)")

    section(f'Combined book: $-PnL @ ${ACCOUNT:.0f} account, {RISK_PCT*100:.1f}% risk/trade (compounded)')
    pnl_df = scaled_daily_pnl(all_trades, one_R)
    print(f"  Trading days with at least one trade: {len(pnl_df)}")
    print(f"  Date range: {pnl_df.index.min().date()} -> {pnl_df.index.max().date()}")

    eq = pnl_df['equity']
    stats = drawdown_stats(eq, top_n=5)
    print(f"\n  Final equity:      ${stats['final_equity']:>10,.2f}")
    print(f"  Total return:      {stats['total_return_pct']:>10.2f}%")
    print(f"  PEAK drawdown:     {stats['max_dd_pct']:>10.2f}%  (${stats['max_dd_dollar']:,.2f})")

    print(f"\n  Worst 5 drawdown episodes:")
    print(f"  {'start':<12} {'trough':<12} {'recover':<12} {'depth%':>8} {'depth$':>10} {'days':>6}")
    for ep in stats['episodes']:
        rec = ep['recover'].date() if ep['recover'] is not None else 'open'
        print(f"  {str(ep['start'].date()):<12} {str(ep['trough'].date()):<12} {str(rec):<12} "
              f"{ep['depth_pct']:>8.2f} {ep['depth_dollar']:>10,.2f} {ep['duration_days']:>6}")

    section('Drawdown attribution on worst-trough days')
    # For each top episode, show contribution by strategy from start..trough
    for ep in stats['episodes'][:3]:
        s, tr = ep['start'], ep['trough']
        sub = pnl_df.loc[s:tr]
        contrib = sub[['orb_dax', 'lunch_fade', 'xau_session']].sum()
        print(f"\n  Episode {s.date()} -> {tr.date()} (depth {ep['depth_pct']:.2f}%):")
        for c, v in contrib.items():
            n = (sub[c] != 0).sum()
            print(f"    {c:12s} ${v:>10,.2f}   (active {n} days)")

    section('Concurrent-trade-day stats')
    active = (pnl_df[['orb_dax','lunch_fade','xau_session']] != 0).sum(axis=1)
    for k in (1, 2, 3):
        days = (active == k).sum()
        avg_pnl = pnl_df.loc[active == k, 'total_pnl'].mean()
        avg_abs = pnl_df.loc[active == k, 'total_pnl'].abs().mean()
        worst = pnl_df.loc[active == k, 'total_pnl'].min()
        print(f"  {k}-strategy days: n={days:4d}  mean_pnl=${avg_pnl:>8.2f}  "
              f"mean|pnl|=${avg_abs:>8.2f}  worst=${worst:>9.2f}")

    section('W4 drill-down: lunch_fade <-> xau_session, USD beta strip')
    eurusd_up = load_eurusd_daily_change()
    w4_drill(pnl_df, eurusd_up)

    section('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
