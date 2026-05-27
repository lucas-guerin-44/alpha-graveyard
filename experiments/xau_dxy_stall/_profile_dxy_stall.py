"""XAUUSD DXY-stall contra-signal — Phase 0 profile.

Thesis: experiments/xau_dxy_stall/xau_dxy_stall.md (2026-05-27).

DXY synthetic index from EURUSD/USDJPY/GBPUSD M5 log-returns (83% of real DXY
weight). Detects 30-min HWM/LWM-stall events and measures XAU forward returns
at +30/+60/+90/+120 min, sign-mapped (HWM-stall → XAU LONG, LWM-stall → SHORT).

Comparisons:
  1. Real-stall forward XAU returns vs hour-matched random-bar baseline
  2. HWM-stall LONG mean vs LWM-stall SHORT mean (symmetry)
  3. Regime decomposition (W1-W4)
  4. Conditional splits: stall count N, time-of-day, prior DXY momentum strength,
     XAU prior direction
  5. Independence check vs deployed xau_session signal proxy
"""
import os, sys
from collections import defaultdict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# ---- config ----
DXY_WEIGHTS = {
    'EURUSD': -0.576,   # inverted
    'USDJPY': +0.136,
    'GBPUSD': -0.119,   # inverted
}
HWM_LOOKBACK_BARS = 6      # 30 min HWM window
STALL_N_VALUES = [3, 4, 5, 6, 8]   # how many bars must pass without new HWM
MAX_STALL_LAG_BARS = 12    # stall event only valid if HWM was within last 60 min
FWD_BARS = [6, 12, 18, 24]  # 30 / 60 / 90 / 120 min forward XAU returns


def load_m5(symbol):
    path = os.path.join(_ROOT, 'ohlc_data', f'{symbol}_M5.csv')
    df = pd.read_csv(path, parse_dates=['timestamp'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df[df['timestamp'] >= pd.Timestamp('2018-01-01', tz='UTC')].copy()
    df = df.reset_index(drop=True)
    return df[['timestamp', 'open', 'high', 'low', 'close']]


print("Loading M5 series ...")
eu = load_m5('EURUSD').rename(columns={'close': 'eu_close'})
uj = load_m5('USDJPY').rename(columns={'close': 'uj_close'})
gu = load_m5('GBPUSD').rename(columns={'close': 'gu_close'})
xau = load_m5('XAUUSD').rename(columns={'close': 'xau_close'})

# Align all four series by timestamp inner-join
df = eu[['timestamp', 'eu_close']].merge(
    uj[['timestamp', 'uj_close']], on='timestamp', how='inner'
).merge(
    gu[['timestamp', 'gu_close']], on='timestamp', how='inner'
).merge(
    xau[['timestamp', 'xau_close']], on='timestamp', how='inner'
)

print(f"Aligned bars: {len(df):,}")
print(f"Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")

# Build synthetic DXY = exp(sum(w_i * log(price_i))) — multiplicative composite
df['log_dxy'] = (
    DXY_WEIGHTS['EURUSD'] * np.log(df['eu_close'])
    + DXY_WEIGHTS['USDJPY'] * np.log(df['uj_close'])
    + DXY_WEIGHTS['GBPUSD'] * np.log(df['gu_close'])
)
df['dxy'] = np.exp(df['log_dxy'])
df['hour'] = df['timestamp'].dt.hour
df['dow'] = df['timestamp'].dt.day_name()
df['year'] = df['timestamp'].dt.year

def regime_of(y):
    if y < 2020: return 'W1'
    if y < 2022: return 'W2'
    if y < 2024: return 'W3'
    return 'W4'
df['regime'] = df['year'].apply(regime_of)

# Sanity check: synthetic-DXY daily-return correlation with XAU daily-return
daily = df.set_index('timestamp').resample('1D').last().dropna()
dxy_daily_ret = daily['dxy'].pct_change()
xau_daily_ret = daily['xau_close'].pct_change()
corr = dxy_daily_ret.corr(xau_daily_ret)
print(f"\nSanity: synthetic-DXY vs XAU daily-return corr = {corr:+.3f} "
      f"(expect -0.5 to -0.85)")

# ---- numpy arrays for inner loop ----
ts = df['timestamp'].values
dxy_arr = df['dxy'].values.astype(np.float64)
xau_arr = df['xau_close'].values.astype(np.float64)
hour_arr = df['hour'].values
regime_arr = df['regime'].values
n = len(df)

# ---- HWM / LWM detection ----
# HWM(t) = max(dxy[t-LOOKBACK+1 .. t]); a new HWM at t means dxy[t] == HWM(t)
# Vectorized: use a rolling max
print("\nDetecting DXY HWM/LWM ...")
dxy_ser = pd.Series(dxy_arr)
hwm = dxy_ser.rolling(HWM_LOOKBACK_BARS, min_periods=1).max().values
lwm = dxy_ser.rolling(HWM_LOOKBACK_BARS, min_periods=1).min().values
is_new_hwm = dxy_arr >= hwm - 1e-10  # at HWM
is_new_lwm = dxy_arr <= lwm + 1e-10  # at LWM


def detect_stall(is_new_extreme, stall_n):
    """Stall event at bar t if:
      - The last bar with is_new_extreme=True was at bar t-stall_n (or earlier
        but within MAX_STALL_LAG_BARS)
      - Bars t-stall_n+1 .. t had no new extreme.
      - More precisely: bar t IS a stall event iff
          (count of False since last True) == stall_n
        and (last True was within MAX_STALL_LAG_BARS of t).
    Implementation: at each bar, compute "bars since last True".
    """
    n = len(is_new_extreme)
    out = np.zeros(n, dtype=bool)
    last_true = -10**6
    for i in range(n):
        if is_new_extreme[i]:
            last_true = i
        elif (i - last_true) == stall_n and (i - last_true) <= MAX_STALL_LAG_BARS:
            out[i] = True
    return out


# ---- forward XAU returns ----
def forward_ret(local_arr, fb_list):
    """Vectorized: for each i, return xau[i+fb]/xau[i] - 1 for each fb."""
    out = {}
    for fb in fb_list:
        shifted = np.concatenate([local_arr[fb:], np.full(fb, np.nan)])
        out[fb] = (shifted - local_arr) / local_arr * 10000.0  # bps
    return out


fwd_xau = forward_ret(xau_arr, FWD_BARS)


def t_of(arr):
    arr = arr[np.isfinite(arr)]
    if len(arr) < 5: return 0.0, np.nan
    m = arr.mean()
    s = arr.std(ddof=1)
    if s == 0: return 0.0, np.nan
    return m, m / (s / np.sqrt(len(arr)))


def section(title):
    print(f"\n{'='*78}\n{title}\n{'='*78}")


# ---- 1. Per-stall-N event counts ----
section("1. Stall-event counts by N (across 2018-2026 aligned bars)")
print(f"  {'N':>3s} {'HWM-stalls':>12s} {'LWM-stalls':>12s}  trades/yr (combined)")
years = (df['timestamp'].max() - df['timestamp'].min()) / np.timedelta64(1, 'D') / 365.25
stall_events = {}
for sN in STALL_N_VALUES:
    h = detect_stall(is_new_hwm, sN)
    l = detect_stall(is_new_lwm, sN)
    nh = int(h.sum())
    nl = int(l.sum())
    print(f"  {sN:>3d} {nh:>12d} {nl:>12d}  {(nh+nl)/years:>5.0f}")
    stall_events[sN] = (h, l)


# ---- 2. Forward XAU returns by stall N, signed (HWM=long, LWM=short) ----
section("2. Signed forward XAU returns after DXY stall (HWM-stall LONG, LWM-stall SHORT)")
print(f"  {'N':>3s} {'kind':>5s} {'n':>6s}  " + "  ".join([f"{'mean/t '+str(fb*5)+'m':>14s}" for fb in FWD_BARS]))
for sN in STALL_N_VALUES:
    h, l = stall_events[sN]
    for kind, mask, sign in [('HWM', h, +1), ('LWM', l, -1)]:
        idxs = np.where(mask)[0]
        if len(idxs) < 20: continue
        parts = []
        for fb in FWD_BARS:
            vals = sign * fwd_xau[fb][idxs]
            m, t = t_of(vals)
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
        print(f"  {sN:>3d} {kind:>5s} {len(idxs):>6d}  " + "  ".join([f"{p:>14s}" for p in parts]))


# ---- 3. Time-of-day matched baseline: random non-stall bars ----
section("3. Hour-of-day matched random-bar baseline (1000 samples / hour distribution)")
# Build hour-distribution of stall events for each N, then sample non-stall bars matching that distribution.
print(f"  {'N':>3s} {'kind':>5s} {'n_real':>7s} {'n_base':>7s}  " +
      "  ".join([f"{'real-base 30m':>14s}", f"{'real-base 60m':>14s}",
                 f"{'real-base 90m':>14s}"]))
for sN in STALL_N_VALUES:
    h, l = stall_events[sN]
    for kind, mask, sign in [('HWM', h, +1), ('LWM', l, -1)]:
        idxs = np.where(mask)[0]
        if len(idxs) < 50: continue
        # Hour distribution of real stalls
        hour_dist = pd.Series(hour_arr[idxs]).value_counts(normalize=True)
        # Non-stall pool
        not_stall = ~mask
        # Sample baseline: for each hour bin, draw len(hour_dist[h] * len(idxs)) non-stall bars
        rng = np.random.default_rng(seed=42)
        baseline_idxs = []
        for hr, frac in hour_dist.items():
            n_draw = int(frac * len(idxs))
            pool = np.where(not_stall & (hour_arr == hr))[0]
            if len(pool) == 0 or n_draw == 0: continue
            pick = rng.choice(pool, size=min(n_draw, len(pool)), replace=False)
            baseline_idxs.extend(pick.tolist())
        baseline_idxs = np.array(baseline_idxs)
        parts = []
        for fb in [6, 12, 18]:  # 30/60/90 min
            real_vals = sign * fwd_xau[fb][idxs]
            base_vals = sign * fwd_xau[fb][baseline_idxs]
            real_m = real_vals[np.isfinite(real_vals)].mean()
            base_m = base_vals[np.isfinite(base_vals)].mean()
            delta = real_m - base_m
            # bootstrap t-stat: difference of means / pooled SE
            ra = real_vals[np.isfinite(real_vals)]
            ba = base_vals[np.isfinite(base_vals)]
            if len(ra) < 5 or len(ba) < 5:
                parts.append(f"{'-':>14s}")
                continue
            se = np.sqrt(ra.var(ddof=1)/len(ra) + ba.var(ddof=1)/len(ba))
            t = delta / se if se > 0 else 0
            parts.append(f"{delta:>+6.1f}/{t:>+5.2f}")
        print(f"  {sN:>3d} {kind:>5s} {len(idxs):>7d} {len(baseline_idxs):>7d}  " +
              "  ".join([f"{p:>14s}" for p in parts]))


# ---- 4. Per-regime breakdown for the best N (use N=5 as middle) ----
section("4. Regime decomposition (N=5, both HWM-stall and LWM-stall, signed)")
sN = 5
h, l = stall_events[sN]
print(f"  {'kind':>5s} {'regime':>6s} {'n':>6s}  " +
      "  ".join([f"{'mean/t '+str(fb*5)+'m':>14s}" for fb in FWD_BARS]))
for kind, mask, sign in [('HWM', h, +1), ('LWM', l, -1)]:
    for reg in ['W1', 'W2', 'W3', 'W4']:
        idxs = np.where(mask & (regime_arr == reg))[0]
        if len(idxs) < 20: continue
        parts = []
        for fb in FWD_BARS:
            vals = sign * fwd_xau[fb][idxs]
            m, t = t_of(vals)
            parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
        print(f"  {kind:>5s} {reg:>6s} {len(idxs):>6d}  " + "  ".join([f"{p:>14s}" for p in parts]))


# ---- 5. Time-of-day decomposition for N=5 ----
section("5. Time-of-day decomposition (N=5, signed, fwd 60m)")
print(f"  {'kind':>5s} {'hr':>3s} {'n':>5s} {'mean':>7s} {'t':>6s}")
for kind, mask, sign in [('HWM', h, +1), ('LWM', l, -1)]:
    for hr in range(24):
        idxs = np.where(mask & (hour_arr == hr))[0]
        if len(idxs) < 30: continue
        vals = sign * fwd_xau[12][idxs]
        m, t = t_of(vals)
        if abs(t) >= 1.5:
            mk = '  <<<' if abs(t) >= 2.0 else ''
            print(f"  {kind:>5s} {hr:>3d} {len(idxs):>5d} {m:>+6.1f}bp {t:>+5.2f}{mk}")


# ---- 6. DXY momentum-strength before stall ----
section("6. Conditional on prior DXY momentum strength (N=5, fwd 60m)")
print("  Bucket DXY 30-min return into prior to stall: large up (>+0.10%), small up, small dn, large dn (<-0.10%)")
# DXY 30min return = log_dxy[t] - log_dxy[t-6]
log_dxy = df['log_dxy'].values
dxy_30m_ret = np.full(n, np.nan)
dxy_30m_ret[6:] = (log_dxy[6:] - log_dxy[:-6]) * 100  # in %
for kind, mask, sign in [('HWM', h, +1), ('LWM', l, -1)]:
    idxs = np.where(mask)[0]
    if len(idxs) < 50: continue
    prior_ret = dxy_30m_ret[idxs]
    fwd60 = sign * fwd_xau[12][idxs]
    # for HWM-stall, expect prior_ret > 0 (DXY ran up); for LWM-stall, prior_ret < 0
    print(f"\n  {kind}-stall, prior DXY 30m-ret bucket:")
    bins = [(-np.inf, -0.10), (-0.10, -0.03), (-0.03, +0.03), (+0.03, +0.10), (+0.10, np.inf)]
    labels = ['<-0.10', '-0.10..-0.03', '-0.03..+0.03', '+0.03..+0.10', '>+0.10']
    for (lo, hi), lab in zip(bins, labels):
        bucket = (prior_ret >= lo) & (prior_ret < hi)
        if bucket.sum() < 20: continue
        vals = fwd60[bucket]
        m, t = t_of(vals)
        print(f"    {lab:>16s}  n={int(bucket.sum()):>5d}  mean={m:>+6.1f}bp  t={t:>+5.2f}")


# ---- 7. Combined HWM+LWM-signed table for headline verdict ----
section("7. Headline (combined HWM+LWM signed, by N)")
print(f"  {'N':>3s} {'n':>6s}  " + "  ".join([f"{'mean/t '+str(fb*5)+'m':>14s}" for fb in FWD_BARS]))
for sN in STALL_N_VALUES:
    h, l = stall_events[sN]
    all_signed = []
    for fb in FWD_BARS:
        a = +1 * fwd_xau[fb][h]
        b = -1 * fwd_xau[fb][l]
        all_signed.append(np.concatenate([a, b]))
    n_total = len(all_signed[0])
    parts = []
    for arr in all_signed:
        m, t = t_of(arr)
        parts.append(f"{m:>+6.1f}/{t:>+5.2f}")
    print(f"  {sN:>3d} {n_total:>6d}  " + "  ".join([f"{p:>14s}" for p in parts]))


# ---- 8. Verdict ----
section("8. Phase 0 pass criteria")
print("""
Pass criteria for Phase 1 commit:
  - At least one (kind, N, horizon) cell has mean >= +3 bps signed AND t >= +2.0
    AND real-vs-baseline delta >= +1.5 bps with t >= +1.8.
  - Symmetric: HWM-stall LONG and LWM-stall SHORT both positive, within 50% mag.
  - Persists across W3 AND W4 (post-2022) — not 2018-2021-only.
  - Cell n >= 200 (cadence floor).

If any cell clears all four: write Phase 1 simulator.
If only some clear, document the marginal case in thesis doc and STATE.md
  as MARGINAL — Phase 1 not built without strong signal.
If none clear: REJECT at Phase 0, tombstone to graveyard.
""")
