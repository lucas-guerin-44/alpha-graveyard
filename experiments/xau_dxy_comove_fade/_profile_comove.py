"""XAU/DXY co-movement fade — Phase 0 profile.

Thesis: experiments/xau_dxy_comove_fade/xau_dxy_comove_fade.md (2026-06-01).

Real USDX M5 (MT5) vs XAUUSD M5. A "co-move event" = XAU and USDX move the SAME
direction over a window W (breaking their structural inverse) with both legs
large. Fade-XAU rule (dollar-anchored): signal = -sign(r_usdx) (both up -> short
XAU, both down -> long XAU). Measure forward XAU returns sign-mapped.

Comparisons:
  1. Sanity: daily + rolling XAU/USDX correlation (expect strongly negative)
  2. Event counts by (W, theta) -> cadence
  3. Signed forward XAU return after co-move events, by (W, theta, horizon)
  4. Hour-of-day-matched control applying the SAME fade rule on non-event bars
     -> real-minus-control delta (isolates the breakdown contribution)
  5. Symmetry: both-up SHORT vs both-down LONG
  6. Direction null-check: continuation rule (+sign(r_usdx)) must lose to fade
  7. Leg attribution: raw fwd XAU vs raw fwd USDX after events (which leg reverts?)
  8. Regime decomposition (W2-partial / W3 / W4)
  9. Verdict vs pre-committed Phase 0 criteria
"""
import os, sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXPERIMENTS = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_EXPERIMENTS)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(_ROOT, '..', 'backtesting-engine-2.0')))

from data import fetch_ohlc

# ---- config ----
START_DATE = "2021-06-10"   # USDX M5 coverage start
END_DATE = "2026-06-01"
W_VALUES = [3, 6, 12]            # co-move window: 15 / 30 / 60 min
THETA_PCTILES = [50, 70, 85]     # both-leg magnitude floor (pctile of |W-bar ret|)
FWD_BARS = [6, 12, 18, 24]       # 30 / 60 / 90 / 120 min forward
MIN_CELL = 30


def section(title):
    print(f"\n{'='*80}\n{title}\n{'='*80}")


def t_of(arr):
    arr = arr[np.isfinite(arr)]
    if len(arr) < 5:
        return 0.0, np.nan, 0
    m = arr.mean()
    s = arr.std(ddof=1)
    if s == 0:
        return m, np.nan, len(arr)
    return m, m / (s / np.sqrt(len(arr))), len(arr)


# ---------------------------------------------------------------------------
# Load + align
# ---------------------------------------------------------------------------
print("Loading M5 series (XAUUSD, USDX) ...")
xau = fetch_ohlc("XAUUSD", "M5", START_DATE, END_DATE)
usdx = fetch_ohlc("USDX", "M5", START_DATE, END_DATE)


def prep(d, name):
    d = d[['timestamp', 'close']].copy()
    d['timestamp'] = pd.to_datetime(d['timestamp'], utc=True)
    return d.rename(columns={'close': name})


xau = prep(xau, 'xau')
usdx = prep(usdx, 'usdx')
df = xau.merge(usdx, on='timestamp', how='inner').dropna()
df = df[df['timestamp'] >= pd.Timestamp(START_DATE, tz='UTC')]
df = df.sort_values('timestamp').reset_index(drop=True)

print(f"Aligned M5 bars: {len(df):,}")
print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

df['hour'] = df['timestamp'].dt.hour
df['year'] = df['timestamp'].dt.year


def regime_of(y):
    if y < 2020:
        return 'W1'
    if y < 2022:
        return 'W2'   # 2021 H2 only (USDX starts 2021-06)
    if y < 2024:
        return 'W3'   # 2022-2023
    return 'W4'        # 2024-2026 (binding holdout)


df['regime'] = df['year'].apply(regime_of)

# ---- numpy arrays for inner loop ----
log_xau = np.log(df['xau'].values.astype(np.float64))
log_usdx = np.log(df['usdx'].values.astype(np.float64))
xau_arr = df['xau'].values.astype(np.float64)
usdx_arr = df['usdx'].values.astype(np.float64)
hour_arr = df['hour'].values
regime_arr = df['regime'].values
n = len(df)
years = (df['timestamp'].max() - df['timestamp'].min()) / np.timedelta64(1, 'D') / 365.25


# ---------------------------------------------------------------------------
# 1. Sanity: correlation
# ---------------------------------------------------------------------------
section("1. Sanity: XAU vs USDX correlation (expect strongly negative)")
daily = df.set_index('timestamp').resample('1D').last().dropna()
dxret = np.log(daily['usdx']).diff()
gxret = np.log(daily['xau']).diff()
print(f"  Daily log-return corr  = {gxret.corr(dxret):+.3f}   (textbook -0.5..-0.8)")
# M5 contemporaneous
m5x = np.diff(log_xau)
m5d = np.diff(log_usdx)
print(f"  M5  log-return corr    = {np.corrcoef(m5x, m5d)[0,1]:+.3f}")
# rolling 1-day (288 bar) correlation distribution
roll = pd.Series(m5x).rolling(288).corr(pd.Series(m5d))
print(f"  Rolling 1d M5 corr: median={roll.median():+.3f}  "
      f"p10={roll.quantile(.10):+.3f}  p90={roll.quantile(.90):+.3f}  "
      f"frac>0 (inverse broke)={np.mean(roll.dropna() > 0):.2%}")


# ---------------------------------------------------------------------------
# Precompute W-bar returns (bps) and forward returns (bps)
# ---------------------------------------------------------------------------
def wbar_ret(logp, W):
    out = np.full(len(logp), np.nan)
    out[W:] = (logp[W:] - logp[:-W]) * 1e4
    return out


def fwd_ret(local_arr, fb_list):
    out = {}
    for fb in fb_list:
        shifted = np.concatenate([local_arr[fb:], np.full(fb, np.nan)])
        out[fb] = (shifted - local_arr) / local_arr * 1e4
    return out


fwd_xau = fwd_ret(xau_arr, FWD_BARS)
fwd_usdx = fwd_ret(usdx_arr, FWD_BARS)


def build_events(W, theta_pct):
    """Return (event_mask, sign_usdx) for co-move (sign-agree + both-large) events."""
    rx = wbar_ret(log_xau, W)
    rd = wbar_ret(log_usdx, W)
    sx = np.sign(rx)
    sd = np.sign(rd)
    thx = np.nanpercentile(np.abs(rx), theta_pct)
    thd = np.nanpercentile(np.abs(rd), theta_pct)
    comove = (sx == sd) & (sx != 0)
    large = (np.abs(rx) >= thx) & (np.abs(rd) >= thd)
    ev = comove & large & np.isfinite(rx) & np.isfinite(rd)
    return ev, sd, rx, rd


# ---------------------------------------------------------------------------
# 2. Event counts
# ---------------------------------------------------------------------------
section("2. Co-move event counts by (W, theta-pctile)")
print(f"  {'W':>3s} {'theta%':>7s} {'n_events':>9s} {'events/yr':>10s} "
      f"{'both-up':>8s} {'both-dn':>8s}")
for W in W_VALUES:
    for th in THETA_PCTILES:
        ev, sd, rx, rd = build_events(W, th)
        idx = np.where(ev)[0]
        nup = int(np.sum(sd[idx] > 0))
        ndn = int(np.sum(sd[idx] < 0))
        print(f"  {W:>3d} {th:>7d} {len(idx):>9d} {len(idx)/years:>10.0f} "
              f"{nup:>8d} {ndn:>8d}")


# ---------------------------------------------------------------------------
# 3. Signed forward XAU return after events (fade rule -sign(r_usdx))
# ---------------------------------------------------------------------------
section("3. Signed fwd XAU after co-move (FADE: signal=-sign(r_usdx)), mean/t by horizon")
print(f"  {'W':>3s} {'th%':>4s} {'n':>6s}  " +
      "  ".join([f"{str(fb*5)+'m':>13s}" for fb in FWD_BARS]))
cells = []  # (W, th, fb, mean, t, n, idx, sign)
for W in W_VALUES:
    for th in THETA_PCTILES:
        ev, sd, rx, rd = build_events(W, th)
        idx = np.where(ev)[0]
        if len(idx) < MIN_CELL:
            continue
        signal = -sd[idx]   # fade dollar direction
        parts = []
        for fb in FWD_BARS:
            vals = signal * fwd_xau[fb][idx]
            m, t, nn = t_of(vals)
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
            cells.append((W, th, fb, m, t, nn))
        print(f"  {W:>3d} {th:>4d} {len(idx):>6d}  " +
              "  ".join([f"{p:>13s}" for p in parts]))


# ---------------------------------------------------------------------------
# 4. Hour-matched control applying the SAME fade rule on non-event bars
# ---------------------------------------------------------------------------
section("4. Real-minus-control delta (control = same -sign(r_usdx) fade on hour-matched NON-event bars)")
print(f"  {'W':>3s} {'th%':>4s} {'n_real':>7s} {'n_ctrl':>7s}  " +
      "  ".join([f"{'d '+str(fb*5)+'m':>13s}" for fb in [6, 12, 18]]))
rng = np.random.default_rng(42)
for W in W_VALUES:
    for th in THETA_PCTILES:
        ev, sd, rx, rd = build_events(W, th)
        idx = np.where(ev)[0]
        if len(idx) < 50:
            continue
        # control pool: not an event, but r_usdx defined (so sign exists)
        valid = np.isfinite(rd) & np.isfinite(rx)
        not_ev = valid & ~ev
        hour_dist = pd.Series(hour_arr[idx]).value_counts(normalize=True)
        ctrl_idx = []
        for hr, frac in hour_dist.items():
            n_draw = int(frac * len(idx))
            pool = np.where(not_ev & (hour_arr == hr))[0]
            if len(pool) == 0 or n_draw == 0:
                continue
            ctrl_idx.extend(rng.choice(pool, size=min(n_draw, len(pool)),
                                       replace=False).tolist())
        ctrl_idx = np.array(ctrl_idx)
        parts = []
        for fb in [6, 12, 18]:
            real = (-sd[idx]) * fwd_xau[fb][idx]
            ctrl = (-sd[ctrl_idx]) * fwd_xau[fb][ctrl_idx]
            ra = real[np.isfinite(real)]
            ca = ctrl[np.isfinite(ctrl)]
            if len(ra) < 5 or len(ca) < 5:
                parts.append(f"{'-':>13s}")
                continue
            delta = ra.mean() - ca.mean()
            se = np.sqrt(ra.var(ddof=1)/len(ra) + ca.var(ddof=1)/len(ca))
            t = delta/se if se > 0 else 0.0
            parts.append(f"{delta:>+6.1f}/{t:>+5.2f}")
        print(f"  {W:>3d} {th:>4d} {len(idx):>7d} {len(ctrl_idx):>7d}  " +
              "  ".join([f"{p:>13s}" for p in parts]))


# ---------------------------------------------------------------------------
# 5. Symmetry: both-up SHORT-XAU vs both-down LONG-XAU
# ---------------------------------------------------------------------------
section("5. Symmetry (W=6): both-up SHORT-XAU vs both-down LONG-XAU, signed fwd, mean/t")
W = 6
print(f"  {'th%':>4s} {'side':>8s} {'n':>6s}  " +
      "  ".join([f"{str(fb*5)+'m':>13s}" for fb in FWD_BARS]))
for th in THETA_PCTILES:
    ev, sd, rx, rd = build_events(W, th)
    for side, smask, sign in [('both-up', sd > 0, -1), ('both-dn', sd < 0, +1)]:
        idx = np.where(ev & smask)[0]
        if len(idx) < MIN_CELL:
            continue
        parts = []
        for fb in FWD_BARS:
            vals = sign * fwd_xau[fb][idx]
            m, t, _ = t_of(vals)
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
        print(f"  {th:>4d} {side:>8s} {len(idx):>6d}  " +
              "  ".join([f"{p:>13s}" for p in parts]))


# ---------------------------------------------------------------------------
# 6. Direction null-check: continuation (+sign) must lose to fade (-sign)
# ---------------------------------------------------------------------------
section("6. Direction null-check (W=6): FADE (-sign) vs CONTINUE (+sign), signed fwd 60m mean/t")
W = 6
print(f"  {'th%':>4s} {'n':>6s}  {'FADE 60m':>15s}  {'CONTINUE 60m':>15s}  {'gap(fade-cont)':>15s}")
for th in THETA_PCTILES:
    ev, sd, rx, rd = build_events(W, th)
    idx = np.where(ev)[0]
    if len(idx) < MIN_CELL:
        continue
    fade = (-sd[idx]) * fwd_xau[12][idx]
    cont = (+sd[idx]) * fwd_xau[12][idx]
    mf, tf, _ = t_of(fade)
    mc, tc, _ = t_of(cont)
    print(f"  {th:>4d} {len(idx):>6d}  {mf:>+7.1f}/{tf:>+5.2f}  "
          f"{mc:>+7.1f}/{tc:>+5.2f}  {mf-mc:>+8.1f}")


# ---------------------------------------------------------------------------
# 7. Leg attribution: which leg reverts? raw fwd XAU vs raw fwd USDX
# ---------------------------------------------------------------------------
section("7. Leg attribution (W=6, th=70): raw fwd of each leg, sign-mapped to 'reversion of the co-move'")
W, th = 6, 70
ev, sd, rx, rd = build_events(W, th)
idx = np.where(ev)[0]
print(f"  events n={len(idx)}.  Sign convention: reversion = move OPPOSITE the co-move direction.")
print(f"  {'horizon':>8s}  {'XAU revert mean/t':>22s}  {'USDX revert mean/t':>22s}")
for fb in FWD_BARS:
    xau_rev = (-sd[idx]) * fwd_xau[fb][idx]      # XAU reverts the co-move
    usdx_rev = (-sd[idx]) * fwd_usdx[fb][idx]    # USDX reverts the co-move
    mx, tx, _ = t_of(xau_rev)
    md, tdd, _ = t_of(usdx_rev)
    print(f"  {fb*5:>6d}m  {mx:>+9.1f}/{tx:>+6.2f}        {md:>+9.1f}/{tdd:>+6.2f}")


# ---------------------------------------------------------------------------
# 8. Regime decomposition
# ---------------------------------------------------------------------------
section("8. Regime decomposition (W=6, th=70, FADE signed fwd) — W4 binding")
W, th = 6, 70
ev, sd, rx, rd = build_events(W, th)
print(f"  {'regime':>6s} {'n':>6s}  " +
      "  ".join([f"{str(fb*5)+'m':>13s}" for fb in FWD_BARS]))
for reg in ['W2', 'W3', 'W4']:
    idx = np.where(ev & (regime_arr == reg))[0]
    if len(idx) < 10:
        print(f"  {reg:>6s} {len(idx):>6d}  (thin)")
        continue
    parts = []
    for fb in FWD_BARS:
        vals = (-sd[idx]) * fwd_xau[fb][idx]
        m, t, _ = t_of(vals)
        parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
    print(f"  {reg:>6s} {len(idx):>6d}  " + "  ".join([f"{p:>13s}" for p in parts]))


# ---------------------------------------------------------------------------
# 9. Verdict
# ---------------------------------------------------------------------------
section("9. Phase 0 pass criteria (pre-committed)")
print("""
PASS (-> build Phase 1) requires ALL of:
  - >=1 (W, theta, horizon) cell: signed mean >= +3 bps AND t >= +2.0   [Sec 3]
  - real-minus-control delta >= +1.5 bps, t >= +1.8                     [Sec 4]
  - symmetry: both-up & both-down both positive, within +-50% mag       [Sec 5]
  - FADE beats CONTINUE (direction gap > 0)                             [Sec 6]
  - persists W3 AND W4 (not single-window)                              [Sec 8]
  - cell n >= 200 (cadence)                                             [Sec 2/3]

Best signed cells (mean>=+3, t>=+2.0, n>=200):""")
good = [(W, th, fb, m, t, nn) for (W, th, fb, m, t, nn) in cells
        if m >= 3.0 and t >= 2.0 and nn >= 200]
if good:
    for (W, th, fb, m, t, nn) in sorted(good, key=lambda x: -x[4]):
        print(f"    W={W} th={th} {fb*5}m: mean={m:+.1f}bp t={t:+.2f} n={nn}")
else:
    print("    NONE — no cell clears mean>=+3 & t>=+2.0 & n>=200.")
