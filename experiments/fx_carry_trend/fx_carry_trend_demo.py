#!/usr/bin/env python3
"""
FX Carry + Trend demo -- Asness-style "Value & Momentum Everywhere".

Pure-carry was a loser in 2015-2026 (-29%, Sharpe -0.38); the losers were
"stuck long carry while spot craters" cases (EURNOK, USDZAR, NZDCAD).
Hypothesis: a simple 63-day trend confirmation filter removes those bad
episodes by only taking the carry trade when price momentum agrees.

Signal:
    carry_pct   = rate_base - rate_quote
    trend_sign  = sign(log-return over 63 days)
    combined    = +1 if carry > +0.5% and trend_sign > 0
                  -1 if carry < -0.5% and trend_sign < 0
                   0 otherwise

Sizing/mechanics are identical to the pure-carry demo (monthly rebalance,
60d vol target 15% ann., equal risk across non-zero pairs, gross cap 2.0,
6 bps per unit turnover, $100K start).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS = os.path.dirname(HERE)
ROOT = os.path.dirname(EXPERIMENTS)
ENGINE = os.path.abspath(os.path.join(ROOT, "..", "backtesting-engine-2.0"))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(EXPERIMENTS, "fx_carry"))  # sibling for fx_carry_demo
sys.path.insert(0, os.path.join(EXPERIMENTS, "xs_momentum"))  # sibling for xs_momentum_validation

# Reuse helpers from the pure-carry demo without modifying it.
from fx_carry_demo import (  # noqa: E402
    FX_PAIRS,
    CURRENCIES,
    TIMEFRAME,
    START_DATE,
    END_DATE,
    RATES_DIR,
    SIGNAL_THRESHOLD_PCT,
    REBAL_BARS,
    VOL_LOOKBACK_BARS,
    VOL_TARGET_ANN,
    BARS_PER_YEAR,
    GROSS_CAP,
    ROUNDTRIP_BPS,
    load_fx,
    load_rate,
    parse_pair,
    section,
    max_drawdown,
    annualized_sharpe,
)
from xs_momentum_validation import (  # noqa: E402
    load_data as xs_load_data,
    run_xs_momentum,
    UNIVERSE as XS_UNIVERSE,
    COSTS_BY_SYMBOL as XS_COSTS,
)


# ---------------------------------------------------------------------------
# Local config -- trend lookback in trading days (3 months).
# ---------------------------------------------------------------------------

TREND_LOOKBACK_BARS = 63

# Pure-carry baseline numbers (for side-by-side comparison at the end).
PURE_CARRY_RETURN = -0.2941
PURE_CARRY_SHARPE = -0.38
PURE_CARRY_MAXDD = -0.3981
PURE_CARRY_CORR_DAILY = 0.29
PURE_CARRY_CORR_MONTHLY = 0.24

STARTING_CAPITAL = 100_000.0


def main() -> int:
    section("Loading FX data")
    fx_frames: dict[str, pd.DataFrame] = {}
    for p in FX_PAIRS:
        df = load_fx(p)
        if df is None or len(df) < 300:
            if df is not None:
                print(f"  {p:<8s} skipped ({len(df)} bars)")
            continue
        fx_frames[p] = df
        print(f"  {p:<8s} {len(df):>5,} bars  "
              f"{df.index[0].date()} -> {df.index[-1].date()}")
    print(f"\n  {len(fx_frames)}/{len(FX_PAIRS)} pairs loaded")

    section("Loading interest-rate series")
    rates_raw: dict[str, pd.Series] = {}
    for c in CURRENCIES:
        s = load_rate(c)
        if s is None or s.empty:
            continue
        rates_raw[c] = s
        print(f"  {c:<3s}  {len(s):>5,} rows  "
              f"{s.index[0].date()} -> {s.index[-1].date()}  "
              f"last={s.iloc[-1]:.4f}%")
    missing_ccy = [c for c in CURRENCIES if c not in rates_raw]
    if missing_ccy:
        print(f"\n  WARNING: missing rate series for {missing_ccy} -- "
              f"any pair requiring these will be skipped from sizing.")

    # ------------------------------------------------------------------
    # Common daily index (business days) and aligned price/rate panels.
    # ------------------------------------------------------------------
    bidx_naive = pd.bdate_range(
        start=pd.Timestamp(START_DATE), end=pd.Timestamp(END_DATE)
    )
    bidx = bidx_naive.tz_localize("UTC")

    closes = pd.DataFrame(index=bidx, columns=list(fx_frames.keys()), dtype=float)
    for p, df in fx_frames.items():
        s = df["close"].reindex(bidx, method=None).ffill()
        closes[p] = s

    rates = pd.DataFrame(index=bidx, columns=list(rates_raw.keys()), dtype=float)
    for c, s in rates_raw.items():
        r = s.reindex(bidx_naive, method="ffill")
        r.index = bidx
        rates[c] = r
    rates = rates.ffill()

    # ------------------------------------------------------------------
    # Signal construction: carry-only, trend-only, combined.
    # ------------------------------------------------------------------
    section("Signal construction (carry + trend)")

    # 63-day log-return trend per pair.
    log_close = np.log(closes)
    trend_ret = log_close - log_close.shift(TREND_LOOKBACK_BARS)
    trend_sign = np.sign(trend_ret).fillna(0.0)

    pair_carry_sig: dict[str, pd.Series] = {}
    pair_trend_sign: dict[str, pd.Series] = {}
    pair_combined: dict[str, pd.Series] = {}
    pair_carry_val: dict[str, pd.Series] = {}

    skipped_pairs: list[str] = []
    for p in closes.columns:
        base, quote = parse_pair(p)
        if base not in rates.columns or quote not in rates.columns:
            skipped_pairs.append(p)
            continue
        carry = rates[base] - rates[quote]
        pair_carry_val[p] = carry

        carry_sig = pd.Series(0, index=bidx, dtype=int)
        carry_sig[carry > SIGNAL_THRESHOLD_PCT] = 1
        carry_sig[carry < -SIGNAL_THRESHOLD_PCT] = -1
        pair_carry_sig[p] = carry_sig

        ts = trend_sign[p].astype(int)
        pair_trend_sign[p] = ts

        # Combined: agreement between nonzero carry_sig and matching trend_sign.
        combined = pd.Series(0, index=bidx, dtype=int)
        combined[(carry_sig == 1) & (ts > 0)] = 1
        combined[(carry_sig == -1) & (ts < 0)] = -1
        pair_combined[p] = combined

    if skipped_pairs:
        print(f"  Skipped pairs (missing a rate series): {skipped_pairs}")
    active_pairs = list(pair_combined.keys())
    print(f"  Active pairs: {len(active_pairs)}")
    print(f"  Trend lookback: {TREND_LOOKBACK_BARS} trading days (~3m)")
    print(f"  Carry threshold: +/-{SIGNAL_THRESHOLD_PCT:.2f}% differential")

    # ------------------------------------------------------------------
    # Daily returns and rolling vol.
    # ------------------------------------------------------------------
    rets = closes[active_pairs].pct_change().fillna(0.0)
    daily_vol = rets.rolling(
        VOL_LOOKBACK_BARS, min_periods=VOL_LOOKBACK_BARS // 2
    ).std(ddof=1)
    ann_vol = daily_vol * np.sqrt(BARS_PER_YEAR)

    # ------------------------------------------------------------------
    # P&L simulation.
    # ------------------------------------------------------------------
    n_bars = len(bidx)
    weights = np.zeros(len(active_pairs))
    equity = np.empty(n_bars)
    equity[0] = 1.0
    daily_returns = np.zeros(n_bars)
    pair_pnl = np.zeros(len(active_pairs))
    turnover_events: list[float] = []
    n_rebals = 0

    # Need enough history for BOTH vol estimate and trend lookback.
    first_valid = max(VOL_LOOKBACK_BARS, TREND_LOOKBACK_BARS)
    first_rebal = first_valid

    rets_arr = rets.to_numpy()
    annvol_arr = ann_vol.to_numpy()
    combined_arr = pd.DataFrame(
        {p: pair_combined[p] for p in active_pairs}
    ).to_numpy()
    carry_sig_arr = pd.DataFrame(
        {p: pair_carry_sig[p] for p in active_pairs}
    ).to_numpy()
    trend_sign_arr = pd.DataFrame(
        {p: pair_trend_sign[p] for p in active_pairs}
    ).to_numpy()

    # Disagreement tracking per pair: among rebalance events where carry_sig
    # was non-zero, how often did trend disagree and zero-out the combined
    # signal?
    carry_live_count = np.zeros(len(active_pairs), dtype=int)
    disagree_count = np.zeros(len(active_pairs), dtype=int)

    rebal_dates: list[pd.Timestamp] = []
    for t in range(n_bars):
        if t > 0:
            r = rets_arr[t]
            r = np.where(np.isfinite(r), r, 0.0)
            port_ret = float(np.dot(weights, r))
            equity[t] = equity[t - 1] * (1.0 + port_ret)
            daily_returns[t] = port_ret
            pair_pnl += weights * r

        is_rebal = (
            t >= first_rebal and (t - first_rebal) % REBAL_BARS == 0
        )
        if not is_rebal:
            continue

        # Track disagreement at this rebalance.
        cs_t = carry_sig_arr[t]
        ts_t = trend_sign_arr[t]
        live_carry = cs_t != 0
        carry_live_count += live_carry.astype(int)
        # Disagree = carry has signal but combined is 0.
        cmb_t = combined_arr[t]
        disagree = live_carry & (cmb_t == 0)
        disagree_count += disagree.astype(int)

        sig_t = cmb_t.astype(float)
        vol_t = annvol_arr[t]
        live = (sig_t != 0) & np.isfinite(vol_t) & (vol_t > 1e-6)
        if not live.any():
            new_weights = np.zeros_like(weights)
        else:
            n_live = int(live.sum())
            base_w = np.where(
                live,
                sig_t * (VOL_TARGET_ANN / np.where(vol_t > 0, vol_t, np.nan))
                / n_live,
                0.0,
            )
            base_w = np.where(np.isfinite(base_w), base_w, 0.0)
            gross = float(np.sum(np.abs(base_w)))
            if gross > GROSS_CAP and gross > 0:
                base_w = base_w * (GROSS_CAP / gross)
            new_weights = base_w

        dw = new_weights - weights
        turnover = float(np.sum(np.abs(dw)))
        turnover_events.append(turnover)

        cost = turnover * (ROUNDTRIP_BPS * 1e-4)
        equity[t] *= (1.0 - cost)
        daily_returns[t] -= cost

        weights = new_weights
        n_rebals += 1
        rebal_dates.append(bidx[t])

    # ------------------------------------------------------------------
    # Standalone metrics.
    # ------------------------------------------------------------------
    section("Carry+Trend standalone performance")
    total_ret = float(equity[-1] / equity[0] - 1.0)
    sharpe = annualized_sharpe(daily_returns)
    mdd = max_drawdown(equity)
    years = (bidx[-1] - bidx[0]).days / 365.25
    cagr = (equity[-1] / equity[0]) ** (1.0 / max(years, 1e-9)) - 1.0
    calmar = (cagr / abs(mdd)) if mdd != 0 else 0.0

    final_equity = STARTING_CAPITAL * equity[-1]
    print(f"  Period          : {bidx[0].date()} -> {bidx[-1].date()}  ({years:.2f}y)")
    print(f"  Starting capital: ${STARTING_CAPITAL:,.0f}")
    print(f"  Ending equity   : ${final_equity:,.0f}")
    print(f"  Total return    : {total_ret * 100:+.2f}%")
    print(f"  CAGR            : {cagr * 100:+.2f}%")
    print(f"  Sharpe (252)    : {sharpe:.4f}")
    print(f"  Max DD          : {mdd * 100:+.2f}%")
    print(f"  Calmar          : {calmar:.3f}")
    print(f"  Rebalances      : {n_rebals}")
    if turnover_events:
        print(f"  Avg turnover    : {np.mean(turnover_events):.4f}  "
              f"(sum |dw| per rebal)")

    # ------------------------------------------------------------------
    # Per-pair P&L.
    # ------------------------------------------------------------------
    section("Per-pair P&L contribution (sorted)")
    contribs = sorted(
        [(p, pair_pnl[i]) for i, p in enumerate(active_pairs)],
        key=lambda x: -x[1],
    )
    print(f"  {'Pair':<8s} {'Contribution':>14s}")
    print("  " + "-" * 25)
    for p, c in contribs:
        print(f"  {p:<8s} {c * 100:>+13.2f}%")

    # ------------------------------------------------------------------
    # Signal-disagreement rate per pair.
    # ------------------------------------------------------------------
    section("Signal-disagreement rate (trend filtered carry out)")
    print("  Among rebalance dates where |carry| > threshold, the fraction")
    print("  where trend disagreed and the combined signal was forced to 0.")
    print()
    rows = []
    for i, p in enumerate(active_pairs):
        n_carry = int(carry_live_count[i])
        n_dis = int(disagree_count[i])
        frac = (n_dis / n_carry) if n_carry > 0 else 0.0
        rows.append((p, n_carry, n_dis, frac))
    rows.sort(key=lambda x: -x[3])
    print(f"  {'Pair':<8s} {'CarryOn':>8s} {'Filtered':>9s} {'Frac':>8s}")
    print("  " + "-" * 40)
    for p, nc, nd, f in rows:
        print(f"  {p:<8s} {nc:>8d} {nd:>9d} {f * 100:>7.1f}%")

    # ------------------------------------------------------------------
    # Signal coverage (post-filter).
    # ------------------------------------------------------------------
    section("Combined-signal coverage (fraction of days non-zero, post-filter)")
    frac_rows = []
    for p in active_pairs:
        s = pair_combined[p].iloc[first_rebal:]
        frac = float((s != 0).mean())
        frac_rows.append((p, frac))
    frac_rows.sort(key=lambda x: -x[1])
    print(f"  {'Pair':<8s} {'Frac non-zero':>14s}")
    print("  " + "-" * 25)
    for p, f in frac_rows:
        print(f"  {p:<8s} {f * 100:>13.2f}%")

    # ------------------------------------------------------------------
    # Correlation with XS-mom.
    # ------------------------------------------------------------------
    section("Correlation with XS-momentum strategy")
    print("  Loading XS-mom universe for cross-strategy comparison...")
    xs_frames: dict[str, pd.DataFrame] = {}
    for sym in XS_UNIVERSE:
        df = xs_load_data(sym, START_DATE, END_DATE)
        if df is None or len(df) < 400:
            continue
        xs_frames[sym] = df
    print(f"    Loaded {len(xs_frames)} XS-mom instruments.")
    print("  Running XS-mom (lookback=189, skip=42, rebal=63, top_k=5, bottom_k=0)...")
    xs_res = run_xs_momentum(
        xs_frames,
        start_date=START_DATE,
        end_date=END_DATE,
        lookback_bars=189,
        skip_bars=42,
        rebalance_bars=63,
        top_k=5,
        bottom_k=0,
        starting_cash=STARTING_CAPITAL,
        costs_bps=XS_COSTS,
    )
    xs_idx = xs_res["index"]
    xs_ret = pd.Series(xs_res["daily_returns"], index=xs_idx, name="xs_mom")
    ct_ret = pd.Series(daily_returns, index=bidx, name="carry_trend")

    aligned = pd.concat([ct_ret, xs_ret], axis=1, join="inner").dropna()

    def _trim(s: pd.Series) -> pd.Series:
        nz = np.flatnonzero(s.to_numpy())
        return s.iloc[nz[0]:] if nz.size else s

    ct_live = _trim(aligned["carry_trend"])
    xs_live = _trim(aligned["xs_mom"])
    live_start = max(ct_live.index[0], xs_live.index[0])
    both = aligned.loc[live_start:]
    print(f"  Overlap window  : {both.index[0].date()} -> {both.index[-1].date()}  "
          f"({len(both)} bars)")

    if len(both) < 30:
        print("  WARNING: very short overlap; correlation unreliable.")
    corr_daily = float(both["carry_trend"].corr(both["xs_mom"]))
    monthly = (1.0 + both).resample("ME").prod() - 1.0
    corr_monthly = float(monthly["carry_trend"].corr(monthly["xs_mom"]))

    print(f"  Corr (daily)    : {corr_daily:+.4f}")
    print(f"  Corr (monthly)  : {corr_monthly:+.4f}")

    # ------------------------------------------------------------------
    # Comparison block: pure carry vs carry+trend.
    # ------------------------------------------------------------------
    section("Pure Carry vs Carry+Trend")
    print(f"  {'':<22s} {'Pure Carry':>12s}   {'Carry+Trend':>12s}")
    print("  " + "-" * 52)
    print(f"  {'Return':<22s} {PURE_CARRY_RETURN * 100:>11.2f}%  "
          f"{total_ret * 100:>11.2f}%")
    print(f"  {'Sharpe':<22s} {PURE_CARRY_SHARPE:>12.2f}   {sharpe:>12.2f}")
    print(f"  {'Max DD':<22s} {PURE_CARRY_MAXDD * 100:>11.2f}%  "
          f"{mdd * 100:>11.2f}%")
    print(f"  {'Corr daily vs XS-mom':<22s} {PURE_CARRY_CORR_DAILY:>12.2f}   "
          f"{corr_daily:>12.2f}")
    print(f"  {'Corr monthly':<22s} {PURE_CARRY_CORR_MONTHLY:>12.2f}   "
          f"{corr_monthly:>12.2f}")

    # ------------------------------------------------------------------
    # Verdict.
    # ------------------------------------------------------------------
    section("Verdict")
    best_abs = max(abs(corr_daily), abs(corr_monthly))
    low_corr = best_abs < 0.3
    if sharpe <= 0:
        verdict = "REJECT  (Sharpe <= 0; trend filter did not rescue carry)"
    elif low_corr and sharpe > 0.4:
        verdict = "KEEP    (corr < 0.3 AND Sharpe > 0.4 -> add to blend)"
    elif low_corr and 0 < sharpe <= 0.4:
        verdict = ("MAYBE   (corr < 0.3 AND 0 < Sharpe <= 0.4 -- small "
                   "positive edge, uncorrelated)")
    elif sharpe > 0.4:
        verdict = (f"BORDERLINE (Sharpe {sharpe:.2f} > 0.4 but corr "
                   f"{best_abs:.2f} >= 0.3 -- limited diversification)")
    else:
        verdict = (f"WEAK    (Sharpe {sharpe:.2f}, corr {best_abs:.2f} -- "
                   f"does not clear either bar cleanly)")
    print(f"  {verdict}")
    print()
    print(f"  Standalone Sharpe target (>0.4): "
          f"{'MET' if sharpe > 0.4 else 'MISSED'}  (actual {sharpe:.2f})")
    print(f"  Correlation target (<0.3):       "
          f"{'MET' if best_abs < 0.3 else 'MISSED'}  (max |rho| {best_abs:.2f})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
