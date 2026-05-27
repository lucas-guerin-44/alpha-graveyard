"""Phase 0 magnitude check for post_fomc_amateur_fade.

Per thesis (post_fomc_amateur_fade.md §"Phase 0 magnitude check"):

  Compute simple mean of FADE-direction gross_bps on the full ~56-event
  FOMC sample with SPIKE_FLOOR_BPS = 10. Phase 0 floor is +5 bps gross
  mean. If below, ABORT to REJECT without running Phase 2.

  Mechanism: at FOMC announce (14:00 ET) measure NDX100 first-15min
  signed spike. Fade direction = -sign(spike). Gross fade return =
  fade_direction * (px_60 - px_15) / px_15 * 10000 bps.

Also reports:
  - CONT direction for diagnostic comparison (Phase 2 null-check preview)
  - SPIKE_FLOOR sweep (5/10/15/20) to size the operating envelope
  - Per-regime W1/W2/W3 breakdown so we see early if it's a pre-2020 artifact

Run (Windows venv):
  venv/Scripts/python.exe experiments/post_fomc_amateur_fade/_phase0_magnitude_check.py
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

# Re-use the macro_drift calendar loader & timezone helpers.
_MACRO_DIR = os.path.join(_ROOT, 'experiments', '_live', 'macro_drift')
sys.path.insert(0, _MACRO_DIR)
from _profile_fomc_drift import load_calendar, load_m5  # type: ignore

NDX_M5_PATH = os.path.join(_ROOT, 'ohlc_data', 'NDX100_M5.csv')

SPIKE_FLOOR_BPS = 10.0
PHASE0_FLOOR_BPS = 5.0
FIRST_REACTION_MIN = 15
HOLD_MIN = 45  # T+15 -> T+60


def label_regime(year: int) -> str:
    """3-window regime split per CLAUDE.md convention."""
    if year <= 2020:
        return 'W1'  # 2019-2020 pre/COVID
    if year <= 2022:
        return 'W2'  # 2021-2022 vol
    return 'W3'      # 2023-2026 holdout


def bar_close(bars: pd.DataFrame, target_utc: pd.Timestamp,
              tolerance_min: int = 10) -> float | None:
    """Close of the M5 bar nearest target_utc within tolerance."""
    delta = (bars['timestamp'] - target_utc).abs()
    idx = int(delta.values.argmin())
    if delta.iloc[idx] > pd.Timedelta(minutes=tolerance_min):
        return None
    return float(bars.iloc[idx]['close'])


def build_events(cal: pd.DataFrame, m5: pd.DataFrame) -> pd.DataFrame:
    """For every FOMC event, snap px_0/px_15/px_60 and compute spike/forward."""
    ts_arr = m5['timestamp'].values
    rows = []
    for _, r in cal.iterrows():
        t0 = r['announce_utc']
        t15 = t0 + pd.Timedelta(minutes=FIRST_REACTION_MIN)
        t60 = t0 + pd.Timedelta(minutes=FIRST_REACTION_MIN + HOLD_MIN)
        px0 = bar_close(m5, t0)
        px15 = bar_close(m5, t15)
        px60 = bar_close(m5, t60)
        if px0 is None or px15 is None or px60 is None:
            continue
        spike_bps = (px15 - px0) / px0 * 10000
        forward_bps = (px60 - px15) / px15 * 10000  # raw move T+15 -> T+60
        rows.append({
            'date': r['date'],
            'regime': label_regime(r['date'].year),
            'announce_utc': t0,
            'px0': px0, 'px15': px15, 'px60': px60,
            'spike_bps': spike_bps,
            'forward_bps': forward_bps,
        })
    return pd.DataFrame(rows)


def fade_gross_bps(ev: pd.DataFrame, floor: float) -> pd.Series:
    """FADE direction gross bps per event after SPIKE_FLOOR filter."""
    keep = ev['spike_bps'].abs() >= floor
    sub = ev.loc[keep].copy()
    sub['fade_bps'] = -np.sign(sub['spike_bps']) * sub['forward_bps']
    return sub


def cont_gross_bps(ev: pd.DataFrame, floor: float) -> pd.Series:
    keep = ev['spike_bps'].abs() >= floor
    sub = ev.loc[keep].copy()
    sub['cont_bps'] = np.sign(sub['spike_bps']) * sub['forward_bps']
    return sub


def summarize(label: str, series: pd.Series) -> dict:
    n = int(len(series))
    if n == 0:
        print(f'  [{label}] no events'); return {}
    mean = float(series.mean())
    std = float(series.std(ddof=1)) if n > 1 else 0.0
    t = mean / (std / np.sqrt(n)) if std > 0 else 0.0
    wr = float((series > 0).mean())
    print(f'  [{label:<22}] n={n:>3}  mean {mean:+7.2f} bps  std {std:6.2f}  '
          f't {t:+5.2f}  wr {wr*100:5.1f}%')
    return {'n': n, 'mean': mean, 'std': std, 't': t, 'wr': wr}


def section(t: str) -> None:
    print(f'\n{"=" * 92}\n  {t}\n{"=" * 92}\n')


def main() -> None:
    section('post_fomc_amateur_fade — Phase 0 magnitude check (NDX100 M5)')
    cal = load_calendar()
    print(f'  FOMC events (historical) : {len(cal)}')

    m5 = load_m5(NDX_M5_PATH)
    print(f'  NDX M5 bars              : {len(m5):,}  '
          f'({m5["timestamp"].min()} -> {m5["timestamp"].max()})')

    ev = build_events(cal, m5)
    print(f'  Events with full M5 cov. : {len(ev)}')

    section('Headline: FADE direction mean @ SPIKE_FLOOR=10 bps (binding floor +5 bps)')
    fade10 = fade_gross_bps(ev, SPIKE_FLOOR_BPS)
    fade_metrics = summarize('FADE  floor=10', fade10['fade_bps'])
    cont10 = cont_gross_bps(ev, SPIKE_FLOOR_BPS)
    summarize('CONT  floor=10 (null)', cont10['cont_bps'])

    section('SPIKE_FLOOR sweep — FADE direction')
    for fl in (5, 10, 15, 20, 30):
        summarize(f'FADE  floor={fl:>2}',
                  fade_gross_bps(ev, fl)['fade_bps'])

    section('SPIKE_FLOOR sweep — CONT direction (null)')
    for fl in (5, 10, 15, 20, 30):
        summarize(f'CONT  floor={fl:>2}',
                  cont_gross_bps(ev, fl)['cont_bps'])

    section('Per-regime breakdown @ SPIKE_FLOOR=10  (FADE direction)')
    for reg in ('W1', 'W2', 'W3'):
        sub = fade10[fade10['regime'] == reg]
        summarize(f'FADE  {reg}', sub['fade_bps'])

    section('Per-regime breakdown @ SPIKE_FLOOR=10  (CONT direction)')
    for reg in ('W1', 'W2', 'W3'):
        sub = cont10[cont10['regime'] == reg]
        summarize(f'CONT  {reg}', sub['cont_bps'])

    section('Spike-distribution context (sanity)')
    print(f'  |spike| median  : {ev["spike_bps"].abs().median():.1f} bps')
    print(f'  |spike| mean    : {ev["spike_bps"].abs().mean():.1f} bps')
    print(f'  |spike| p25/p75 : {ev["spike_bps"].abs().quantile(0.25):.1f} / '
          f'{ev["spike_bps"].abs().quantile(0.75):.1f} bps')
    print(f'  events |spike|>=10 : {int((ev["spike_bps"].abs()>=10).sum())} / {len(ev)}')

    section('Phase 0 verdict')
    if not fade_metrics:
        print('  ABORT — no events survived M5 coverage filter.')
        return
    mean = fade_metrics['mean']
    print(f'  FADE mean @ floor=10  : {mean:+.2f} bps')
    print(f'  Phase 0 floor          : +{PHASE0_FLOOR_BPS:.2f} bps')
    if mean >= PHASE0_FLOOR_BPS:
        print(f'  VERDICT                : PASS -> proceed to Phase 2 sweep build.')
    else:
        print(f'  VERDICT                : ABORT -> REJECT (mechanism magnitude too small)')
        print(f'                           Tombstone with "0DTE-era post-event flow is')
        print(f'                           faster than 60min" methodology lesson.')


if __name__ == '__main__':
    main()
