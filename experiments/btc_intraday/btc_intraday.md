# BTCUSD intraday session structure — Phase 0 scoping

**Status (2026-05-16 — Phase 1 simulator run):** **MARGINAL.**
3 of 7 pre-committed kill criteria pass. The binding criterion
(2025-2026 net Sharpe > +0.30) clears at **+0.64**, and fade-gap
(+1.72) + cost-robustness (Sh +0.58 at 10bp) both clear. Three
calibration criteria fail (full-W4 Sh +0.83 vs +1.0, MDD −35.7% vs
−20% on FULL — but W4-only MDD is −7.3%, trades/yr 47.8 vs 50). One
substantive criterion fails: **2026 mean trade return −0.258% vs
pre-commit +0.02%**.

The 2026 failure has bear-regime context: 2026Q1 was a −26% BTC
drawdown with intraday MDD −35%. The strategy's W4 MDD of −7.3% in
the same window actually protected capital better than spot. But
2025Q4 had similar BTC drawdown (−24.9%) and the strategy gave Sh
+1.27 — so 2026Q1's −4.85 Sh is not fully explained by "long-bias
in bear regime". Something about 2026Q1 is materially different
(possibly a regime decay overlay, possibly idiosyncratic noise on
n=14 trades).

Pre-commit discipline: the 2026-individual-quarter criterion was
written specifically to catch this kind of failure. It triggered.
The honest verdict is MARGINAL with a clear Phase 2 prescription —
either a regime-detector overlay (pause in sharp BTC drawdowns) as
a NEW thesis with NEW pre-commits, or accept this as KEEP_FOR_REFERENCE.

## Origin

Daily-frequency BTC research thread is closed: `btc_trend` (retired,
walk-forward FAIL), `btc_weekend` (REJECT on full-sample MDD), `btc_volbreak`
(REJECT one-window-wonder). All three converged on a single structural
insight: **BTC institutionalization (CME futures volume scaling Q4-2021 →
spot ETF Q1-2024) creates a phase transition that DEGRADES slow-trend
mechanisms and ACTIVATES microstructure-asymmetry mechanisms** (see STATE.md
cross-experiment pattern #-1, mirror-image driver).

Intraday BTC is the unexplored frontier. The mirror-image rule predicts that
intraday microstructure mechanisms should ACTIVATE post-2022 (W3/W4
amplification), which directly satisfies the BTC W4-floor deploy-discipline
rule (RESEARCH_NOTES #31). This Phase 0 follows the `xau_session` template:
pure structural exploration first, mechanism-commitment second.

## Phase 0 methodology

Data: BTCUSD M5 from datalake (`/api/query`), 2018-01-01 → 2026-05-15,
~716k rows. Aggregated to H1 in-process (open-high-low-close of consecutive
M5 bars within each hour-bucket UTC).

Three diagnostics, in this order:

1. **Hour-of-day mean H1 return** across FULL 2018-2026 and W1-W4 regime
   windows (matching the BTC framework: W1 2018-19, W2 2020-21, W3 2022-23,
   W4 2024-26). Surfaces structurally-active hours.
2. **DOW slice** of the same hour-of-day profile. BTC is 24/7 — Sat/Sun
   behavior is structural, not a gap. Key question: do Sun-evening reopen
   hours dominate the signal, or is there a hour-of-UTC effect that
   persists across all DOWs?
3. **Session aggregate cumulative drift** for Asia (00-08 UTC) / Europe
   (08-14 UTC) / US (14-21 UTC) / Late (21-24 UTC). Same framework as
   `xau_session.md`, lets us compare BTC's session structure to gold.

## Pre-committed Phase 0 → Phase 1 gating criteria

Before this exploration is run, pre-commit on what counts as a "go" signal:

- **W4 (2024-2026) hour-of-day t-stat > +2 OR < -2** on at least one
  hour-of-UTC bucket. The BTC W4-floor lesson is binding — a structurally
  active hour that only existed pre-2022 is not deployable.
- **DOW-conditional concentration < 70%** in any single weekday. If the
  effect lives entirely on (e.g.) Sunday-open, it's a weekend-reopen
  artifact, not a hour-of-day structural mechanism. Sundays may still be
  the single best day — but the signal must persist across at least
  3 weekdays.
- **Cross-regime sign consistency**: if W4 active-hour is positive
  (continuation), at least one of W2/W3 must also be same-signed. If signs
  flip between W2/W3/W4, the mechanism is regime-conditional drift, not a
  structural session pattern → reject this thesis family, propose a regime
  detector instead.

If Phase 0 passes all three criteria, write the Phase 1 thesis tomorrow
with pre-committed kill criteria. If it fails, tombstone the thesis with
the negative result documented and propose a different intraday angle
(CME-handoff ORB, liquidation-cascade fade, etc. from the menu).

## Phase 0 findings (hour-of-day profile, BTCUSD M5→H1 2018→2026-04)

Data: 704,136 BTCUSD M5 bars 2018-01-01 → 2026-04-30 (datalake refreshed
2026-05-16). Aggregated to 59,029 H1 bars in-process. Profile script:
`_profile_btc_hod.py`.

### Headline: Hour-00 UTC (Tokyo/HK/SGP open) drifts UP, consistently

| window | hour-00 mean | n | t-stat |
|---|---|---|---|
| FULL 2018→2026-04 | **+0.0627%** | 2,278 | **+4.39** |
| W1 2018-2019 | +0.0737% | 309 | +1.44 |
| W2 2020-2021 | +0.1133% | 455 | +3.68 |
| W3 2022-2023 | +0.0138% | 699 | +0.60 |
| W4 2024 → 2026-04 | +0.0637% | **815** | **+3.84** |

Hour 00 UTC (00:00-01:00 UTC = 09:00 Tokyo / 08:00 HK / 09:00 Singapore /
03:00-04:00 NY EST) shows consistent positive drift across all 4 regime
windows (same sign throughout — W3 is weakest at t=+0.60 but still
positive). W4 is t=+3.66, satisfying the binding W4-floor rule. Cost-zero
Sharpe of a single-hour long at the FULL period ≈ +1.54 annualized
(mean/std × √(24×365 / 24) = √365).

**This is the BTC analog of the `xau_session` hour-00 finding.** Same UTC
hour, same Tokyo/HK opening window, different mechanism (XAU = physical
demand and central-bank flow; BTC = Asian retail and prop leverage), same
direction (positive). Two assets independently surfacing structural
Tokyo/HK-open drift is a sturdy cross-product corroboration that the
mechanism is real.

### Secondary signal hour-12 UTC LOST SIGNIFICANCE on full data

With the 9 extra months of W4 data, hour-12 UTC dropped from W4 t=+2.42
(initial pull) to t=+1.84 — below the +2.0 threshold. Initial Phase 0
secondary candidate is REJECTED. Hour-00 UTC is the only deployable
entry point.

### Session aggregate cumulative drift

| session | FULL | W1 | W2 | W3 | W4 |
|---|---|---|---|---|---|
| Asia 00-07 UTC | +0.014% | -0.026% | -0.043% | -0.000% | **+0.119%** |
| Europe 08-13 UTC | +0.063% | -0.038% | +0.137% | +0.052% | +0.076% |
| US 14-20 UTC | +0.081% | +0.163% | +0.221% | -0.059% | +0.067% |
| Late 21-23 UTC | -0.004% | -0.089% | +0.058% | +0.029% | -0.046% |

**The Asia 00-07 UTC W4 row is the load-bearing observation: +0.119%
cumulative vs negative-to-zero in W1/W2/W3.** This is the institutionalization
mirror-image driver in action — pre-2022 the Asia session was a noisy/dormant
window for BTC; post-2022 it is the strongest single-session signal.
Consistent with the `lunch_fade` post-2022 amplification on NDX (different
asset, different hour, same regime-change driver).

US session was the dominant W1/W2 driver and has DECAYED to mild positive
in W3/W4 — the same continuous-flow-smoothing institutionalization effect
that retired `btc_trend`. Asia ACTIVATES, US DECAYS.

### Day-of-week persistence

DOW slice on hour-00 UTC (bps mean):

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|
| +1.15 | +11.14 | +4.35 | +8.13 | +9.29 | +1.76 | +1.72 |

Hour-00 signal is concentrated on Tue/Thu/Fri (+8 to +11bp) and weaker on
Mon and weekend days (+1-2bp). Max DOW share = 31% of total absolute
signal — well below the 70% concentration threshold. The mechanism is a
structural session-handoff pattern, not a single-DOW artifact.

The Sat/Sun and Mon weakness is consistent with the Asia desks being
quieter on actual weekends and the Mon morning being a re-engagement
session rather than a continuation session (related to but distinct from
`btc_weekend`'s Sun→Mon mechanism).

### Negative-drift hours (for completeness)

- Hour 02-04 UTC mildly negative across W1/W2/W3 (mid-Asia post the open
  flow, before EU comes in — same shape as XAU)
- Hour 23 UTC and Hour 06 UTC W1 t < -2 isolated — not regime-persistent
- No hour has t < -2 in W4

The hour-02-04 mid-Asia weakness is the same pattern xau_session surfaced.
A Tokyo-open long that exits at 01:00 UTC sidesteps this; a Variant-C
overnight-to-London hold has to absorb it.

### Phase 0 → Phase 1 gating-criteria check

| criterion | result | pass? |
|---|---|---|
| W4 t > \|2\| on at least one hour | hr 00 t=+3.66, hr 12 t=+2.42 | **PASS** |
| DOW max-share < 70% on the hot hour | hr 00 max share 31%, hr 12 max share 36% | **PASS** |
| Sign consistency W2/W3/W4 same as W4 | hr 00: 2/2 same-sign; hr 12: 1/2 same-sign | **PASS** |

All three criteria cleared. Phase 0 is a PASS; the thesis space is
deploy-viable in principle. Cost is the binding question — addressed below.

## Phase 0b findings (filter sweep + W4-recent floor check, `_profile_btc_filters.py`)

The single-hour Phase 0 signal is cost-binding at retail BTC CFD spreads
(mean +0.063% vs ~10 bps RT = net −0.04%/trade). Phase 0b tests four
confirmation filters and a hold-window sweep.

### Filter A — prior-24h magnitude (|prior-24h zscore| > k)

| k | trades | tpy | mean | Sharpe | net | W4 mean |
|---|---|---|---|---|---|---|
| 0.5 | 1140 | 146 | +0.0828% | +1.50 | −0.0172% | +0.1088% |
| 1.0 | 586 | 75 | **+0.1084%** | +1.20 | **+0.0084%** ✓ | **+0.1770%** |
| 1.5 | 315 | 40 | +0.1033% | +0.74 | +0.0033% ✓ | +0.1559% |
| 2.0 | 168 | 22 | +0.1800% | +0.80 | +0.0800% ✓ | +0.2250% |

`k=1.0` is the sweet spot: ~75 trades/yr, cost-clears by a hair,
**W4 mean +0.177%** (3× the unfiltered W4 mean). But W3 sign-flips to
−0.032% on the filtered subset.

### Filter B — prior-NY direction is essentially symmetric

Prior-NY UP: mean +0.053% / Sh +1.13. Prior-NY DOWN: mean +0.059% / Sh +1.14.
**No directional asymmetry.** The Tokyo-open drift is not conditional on the
sign of the prior US session — disconfirms the "Asian fade-of-Western-selling"
hypothesis. The mechanism is sign-agnostic w.r.t. prior NY.

### Filter C — day-of-week slice

| DOW | n | mean | t | Sh | W4 mean |
|---|---|---|---|---|---|
| Mon | 237 | +0.013% | +0.35 | +0.16 | +0.009% |
| **Tue** | 398 | +0.072% | **+2.46** | +0.89 | +0.080% |
| Wed | 392 | +0.053% | +1.67 | +0.61 | +0.114% |
| **Thu** | 394 | +0.070% | **+2.26** | +0.82 | +0.044% |
| **Fri** | 395 | **+0.095%** | **+2.81** | +1.02 | +0.166% |
| Sat | 232 | +0.022% | +0.73 | +0.35 | +0.053% |
| Sun | 230 | +0.016% | +0.49 | +0.23 | −0.020% |

Signal concentrates **Tue/Thu/Fri** (t > +2.0 on all three). Weekend
days (Sat/Sun) and Mon are essentially zero. Friday hour-00 W4 mean
+0.166% is the single strongest cell in the entire DOW×regime grid.

### Best combo — DOW ∈ {Tue,Thu,Fri} × |prior-24h zscore| > k

| k | trades | tpy | mean | Sh | W4 mean | net | W3 mean |
|---|---|---|---|---|---|---|---|
| 0.0 | 1177 | 150 | +0.080% | +1.56 | +0.097% | −0.020% | +0.017% |
| **0.5** | **669** | **85** | **+0.106%** | **+1.41** | **+0.139%** | **+0.006%** ✓ | **−0.040%** |
| 1.0 | 358 | 46 | +0.105% | +0.87 | +0.169% | +0.005% ✓ | −0.094% |
| 1.5 | 190 | 24 | +0.077% | +0.40 | +0.132% | −0.023% | −0.130% |
| 2.0 | 102 | 13 | +0.151% | +0.49 | +0.198% | +0.051% ✓ | −0.101% |

`k=0.5` is the natural Phase 1 candidate: 85 trades/yr, mean +0.106%
just clears cost, W4 mean +0.139%, Sh +1.41. But **W3 sign is −0.040%
in every filtered bucket** — strict sign-consistency fails on the
2022-2023 bear-market regime.

### Hold-window sweep (entry 00:00 UTC, exit 00:00 + N hours)

| N | n | mean | std | Sh | W4 mean | net |
|---|---|---|---|---|---|---|
| 1h | 2681 | +0.068% | 1.82% | +0.71 | +0.049% | −0.032% |
| **2h** | 2681 | **+0.090%** | 1.91% | **+0.90** | +0.055% | **−0.010%** |
| 3h | 2681 | +0.064% | 2.05% | +0.60 | +0.033% | −0.036% |
| 5h | 2681 | +0.041% | 2.27% | +0.35 | +0.041% | −0.059% |
| 7h | 2681 | +0.024% | 2.33% | +0.20 | +0.054% | −0.076% |
| 9h | 2681 | +0.034% | 2.46% | +0.26 | +0.063% | −0.066% |
| 12h | 2681 | +0.050% | 2.60% | +0.36 | +0.098% | −0.050% |

**Optimal hold is 2 hours** — Sh peaks at +0.90, mean peaks at +0.090%.
Longer holds DEGRADE the signal (drift dissipates after the first 2
hours of Asian trading). This forecloses the `xau_session`-style
Variant B/C path: widening the hold window does NOT amortize cost over
more drift on BTC; it gives back signal to noise. The mechanism is
narrowly time-bounded.

### W4 internal trajectory (quarterly Sharpe)

| Quarter | n | mean | Sharpe |
|---|---|---|---|
| 2024Q1 | 87 | +0.007% | +0.22 |
| **2024Q2** | 88 | **+0.124%** | **+7.02** |
| 2024Q3 | 89 | +0.112% | +3.11 |
| 2024Q4 | 86 | +0.086% | +3.23 |
| 2025Q1 | 86 | +0.076% | +2.95 |
| 2025Q2 | 88 | +0.037% | +1.75 |
| 2025Q3 | 89 | +0.056% | +2.77 |
| 2025Q4 | 87 | +0.097% | +5.06 |
| **2026Q1** | 86 | **+0.002%** | +0.07 |
| **2026Q2** | 29 | **−0.007%** | −0.48 |

Peak: 2024Q2 (Asian retail surge into spot-ETF launch). Steady decay
through 2025. **2026Q1-Q2 essentially zero** (n=115 combined).
Recent-6-months / full-W4 ratio = 0.70 → STABLE-DECAYING. The mechanism
may be in the late-cycle phase of post-2022 institutionalization
activation — Asian flow is now smooth enough that the discrete hour-00
opening tick is no longer the structural inefficiency it was.

### W4-recent floor check (the killer table)

| slice | n | mean | Sh | net |
|---|---|---|---|---|
| 2024 only (raw) | 350 | +0.082% | +2.91 | −0.018% |
| **2025-2026 only (raw)** | **465** | **+0.050%** | +2.28 | **−0.050%** |
| FULL W4 (raw) | 815 | +0.064% | +2.57 | −0.036% |

With the Phase-0b best filter (DOW ∈ {Tue,Thu,Fri} ∧ \|z\|>1.0):

| slice | n | mean | Sh | net |
|---|---|---|---|---|
| 2024 only | 56 | +0.258% | +5.24 | **+0.158% ✓** |
| **2025-2026 only** | **72** | **+0.100%** | +2.35 | **−0.0004% (=cost)** |
| FULL W4 | 128 | +0.169% | +3.70 | +0.069% ✓ |

The filter math that gives full-W4 a +0.069%/trade net edge is paid for
**entirely by the 2024 slice**. The 2025-2026 slice gives back almost
all the edge to spread; net is essentially zero (+0.0004% favorable, but
within sampling noise of cost-breakeven).

This is the same shape as `btc_volbreak`'s W2-only-driven full-sample
pass (RESEARCH_NOTES #30 / W4-floor binding rule): a strong full-window
pass that is concentrated in one sub-window and decaying.

## Cost-binding diagnosis (revised)

At 10 bps RT BTC CFD spread:
- **Unfiltered hour-00** mean +0.063% net −0.037%/trade (cost-binding)
- **Filtered (best combo, k=1.0)** full-W4 net +0.069%/trade — clears, but
- **Filtered (best combo, k=1.0)** 2025-2026 net **+0.0004%/trade** — at cost-breakeven exactly
- **Hold-window** doesn't help (2h optimal, longer holds degrade)
- **Direction filter** doesn't help (sign-agnostic)
- **Magnitude + DOW combo** helps but the 2026Q1-Q2 quarters give it back

The two remaining cost-reduction paths are (a) execution-quality model
(passive limit at the bar open vs market-order — could shave 3-5 bps if
realistic given BTC volatility) and (b) sub-hour finer entry timing
(e.g. the 00:00-00:10 UTC sub-bucket might carry more of the signal
than the broader 00:00-01:00 H1).

## Candidate Phase 1 theses (after Phase 0b)

Phase 0b shrinks the option space substantially. Hold-window sweep
foreclosed Variants B/C/D (longer-hold versions). Hour-12 secondary
foreclosed (lost significance on full data). What survives:

### Variant E — "Filtered Tokyo open 2h-hold" (only remaining live variant)

- **Trigger**: every Tue/Thu/Fri UTC at 23:55 IF |prior-24h zscore| > 1.0
- **Entry**: long BTCUSD at 00:00 UTC
- **Exit**: 02:00 UTC (2-hour hold — optimal from sweep)
- **Cadence**: ~46 trades/year (best-combo k=1.0; can tighten to k=0.5 → 85/yr)
- **Expected gross (FULL-W4)**: +0.169% per trade, Sh +3.70 — clears 10bp RT
- **Expected gross (2025-2026 only)**: +0.100% per trade — cost-breakeven
- **Cost-clearance**: marginal. Forward-looking expectation may decay further
  through 2026 given the W4-internal trajectory (Q1 2026 +0.002%, Q2 -0.007%)
- **Phase 1 binding kill criterion**: 2025-2026 sub-slice net Sharpe must be
  > +0.30 after honest cost. If it isn't, MARGINAL → KEEP_FOR_REFERENCE

## Phase 0c — sub-hour M5 profile (run 2026-05-16, third iteration)

Question tested: is the +0.063% hour-00 H1 drift front-loaded in the
first 5-15 minutes (Asia pile-in at the bar open), or evenly distributed?
Script: `_profile_btc_subhour.py`.

### Per-M5-bucket within 00:00-01:00 UTC (FULL 2018→2026-04, n=28,575)

| minute | n | mean (bps) | t | cum (bps) |
|---|---|---|---|---|
| 00 | 2255 | +0.39 | +0.88 | +0.39 |
| 05 | 2384 | +0.47 | +1.05 | +0.86 |
| 10 | 2386 | +0.53 | +1.20 | +1.40 |
| 15 | 2396 | +0.36 | +0.72 | +1.75 |
| **20** | 2397 | **+0.92** | **+2.02** | +2.68 |
| 25 | 2397 | +0.33 | +0.79 | +3.01 |
| 30 | 2394 | +0.83 | +1.86 | +3.84 |
| **35** | 2392 | **+1.02** | **+2.43** | +4.86 |
| 40 | 2393 | +0.32 | +0.54 | +5.17 |
| 45 | 2394 | +0.82 | +1.85 | +5.99 |
| **50** | 2394 | +0.75 | **+2.10** | +6.75 |
| 55 | 2393 | +0.15 | +0.37 | +6.89 |

**Drift is evenly distributed.** The three statistically-significant M5
buckets (minutes 20, 35, 50) are spread across the entire hour, not
clustered at the open. The "Asia pile-in at the bar open"
front-loading hypothesis is DISCONFIRMED.

### Cumulative drift through the hour vs cost

| exit | cum FULL | cum W4 | net vs 10bp RT |
|---|---|---|---|
| 00:15 | +1.40 | +0.91 | −8.60 bps |
| 00:30 | +3.01 | +1.21 | −6.99 bps |
| 00:45 | +5.17 | +2.84 | −4.83 bps |
| **00:60** | **+6.89** | **+6.82** | **−3.11 bps** |

At NO sub-hour exit does the cumulative drift clear 10bp RT cost.
Tighter entry/exit captures LESS drift for the same cost. **Sub-hour
finer entry resolution does not improve the cost calculus** — Phase 0c
hypothesis is closed.

## All remaining cost-reduction levers are now foreclosed

| lever | result |
|---|---|
| Hold-window (1-12h) | 2h optimal; longer degrades |
| Tighter entry (sub-hour) | Captures less drift for same cost |
| Multi-trade compounding | Doubles cost, captures same total |
| Direction conditional | Sign-agnostic |
| Magnitude filter | Helps on FULL-W4, gives back in 2025-2026 |
| DOW filter (Tue/Thu/Fri) | Helps on FULL-W4, gives back in 2025-2026 |
| Best combo (DOW × \|z\|>1.0) | Same shape as above |

**The deploy decision is now binary on Eightcap's actual M1 spread
during 00-07 UTC.** All in-research levers are exhausted.

## Phase 0c #1 — Eightcap M1 spread verification (DONE 2026-05-16)

Pulled 23,001 M1 bars for BTCUSD from Eightcap MT5 (2026-04-15 →
2026-04-30). Script: `_profile_btc_spread.py`. M1 H-L in bps of close is
the conservative proxy for RT cost on a market-order-at-the-bar (true
inside spread is tighter).

### Per-hour M1 H-L summary (bps of close)

| hour (UTC) | n | p25 | median | p75 | p90 | mean |
|---|---|---|---|---|---|---|
| **00 (entry)** | 960 | 3.2 | **5.1** | 7.5 | 11.0 | 6.1 |
| 01 | 960 | 3.8 | 5.5 | 8.7 | 12.7 | 7.0 |
| 02 | 960 | 3.1 | 4.8 | 7.3 | 10.7 | 5.8 |
| 03 | 960 | 4.1 | 6.1 | 9.1 | 12.4 | 7.2 |
| 04 | 958 | 3.8 | 5.6 | 8.3 | 11.7 | 6.5 |
| 05 | 955 | 3.5 | 5.5 | 8.5 | 12.1 | 6.7 |
| 06 | 960 | 3.3 | 4.9 | 7.3 | 9.7 | 5.7 |
| 07 | 960 | 2.9 | 4.5 | 6.7 | 9.2 | 5.2 |
| (US 16-18) | 960 | 6.0-6.6 | 8.2-9.8 | 12.3-13.6 | 16.7-19.3 | 10.0-10.6 |

### Session aggregates

| session | n | p25 | **median** | p75 | p90 | mean |
|---|---|---|---|---|---|---|
| **Asia 00-07 UTC (deploy)** | 7,673 | 3.4 | **5.3** | 7.8 | 11.3 | 6.3 |
| Europe 08-13 UTC | 5,760 | 3.2 | 4.9 | 7.2 | 10.5 | 5.8 |
| US 14-20 UTC | 6,704 | 4.8 | 7.5 | 11.1 | 15.4 | 8.7 |
| Late 21-23 UTC | 2,864 | 4.0 | 6.3 | 9.3 | 12.9 | 7.3 |

### Entry minute (00:00 UTC sharp)

| n | p25 | median | p75 | p90 | mean |
|---|---|---|---|---|---|
| 16 | 3.1 | **4.3** | 5.4 | 7.1 | 4.5 |

### Verdict

**Median M1 H-L during 00-07 UTC = 5.3 bps RT** — comfortably below the
7-bp "clean Phase 1 PASS" threshold. Even the p75 (7.8 bps) is at the
top of the MARGINAL band, and 90% of bars are < 11.3 bps.

The Asian session is the QUIETEST window — tighter than European 08-13
and US 14-20 by 20-50%. This is fortunate: the deploy window is the
broker's lowest-spread window for BTCUSD.

### Caveats

- Sample is 15 days (2026-04-15 to 2026-04-30) — single recent period.
  Volatile periods (e.g., FOMC days, sharp BTC moves) will show wider
  spreads. The W4-internal decay coincides with calming BTC vol so this
  may not generalize across regimes; the Phase 1 simulator should sweep
  cost from 3 bps (best case) to 10 bps (conservative) to characterize
  the cost-sensitivity curve.
- M1 H-L overestimates true inside spread. A passive limit-at-the-bar-open
  execution model would fill closer to the inside; the realistic average
  is probably 60-80% of the M1 H-L proxy. So 5.3 bps median may translate
  to ~3.5-4 bps actual RT cost.
- This is point-in-time. Phase 1 should re-verify spread before deploy
  via a fresh M1 pull at the time of deploy.

## Phase 0c #2 — Cross-product hour-00 on ETH/SOL (deferred, lower priority)

xau_session's cross-product check already confirmed the hour-00 effect
appears on gold/FX/crypto (not equity risk-on). A direct ETH/SOL check
would tie BTC's direction to a multi-crypto pattern. Useful enrichment
but not deploy-binary; deferred until after Phase 1 simulator lands.

## Why this thesis is structurally different from anything in the book

- **Asset**: BTCUSD. Live book is GER40 (orb_dax) and NDX100 (lunch_fade).
  Correlation with both expected to be low (crypto vs traditional
  equity-index intraday).
- **Mechanism family**: session-handoff microstructure. Same family as
  `xau_session` (which also shows hour-00 UTC drift, different mechanism)
  and `lunch_fade` (different hour, also a session-handoff effect). Different
  family from any daily-frequency strategy.
- **Time-of-day**: 00:00 UTC = 03:00 NY EST. Live book is EU-morning
  (orb_dax 09:00 Berlin) and US-lunch (lunch_fade 11:30-13:30 ET). Three
  non-overlapping time windows would diversify execution risk and remove
  contention for VPS resources.
- **Institutionalization side**: ACTIVATION. The W4 amplification of the
  Asian-session effect (Asia +0.119% W4 vs -0.04% W1/W2 average) aligns
  with lunch_fade and btc_weekend's mirror-image driver. The mechanism
  benefits from the *same* post-2022 market-structure maturation that
  retired `btc_trend`.

## Phase 1 simulator results (2026-05-16)

Script: `btc_intraday_demo.py`. Numpy-indexed simulator, 393 entries
over 8.33 years, ~48 trades/yr post-filter.

### Baseline (Variant E, long-only, 2h hold, 5 bps RT)

| metric | value |
|---|---|
| n trades | 393 |
| trades/yr | 47.8 |
| mean per trade | +0.254% (gross +0.304%, cost 5bp) |
| std per trade | 2.43% |
| Sharpe (annualized) | **+0.72** |
| MDD (compounding equity, full sizing) | −35.7% |
| Win rate | 52% |

### Hold-window sub-sweep

| hold | Sharpe | mean | std | MDD |
|---|---|---|---|---|
| 1h | +0.55 | +0.160% | 2.00% | −24.9% |
| **2h (baseline)** | **+0.72** | **+0.254%** | **2.43%** | **−35.7%** |
| 3h | +0.64 | +0.294% | 3.16% | −45.4% |
| 4h | +0.44 | +0.224% | 3.56% | −43.4% |

2h confirms as the Sharpe-optimal hold, matching Phase 0b.

### Regime breakdown

| window | n | Sharpe | mean | MDD |
|---|---|---|---|---|
| W1 2018-2019 | 84 | +0.85 | +0.503% | −35.7% |
| W2 2020-2021 | 90 | **+1.41** | +0.458% | −5.3% |
| W3 2022-2023 | 89 | +0.05 | +0.018% | −19.3% |
| **W4 2024-2026** | 130 | +0.83 | +0.112% | **−7.3%** |

W4 standalone MDD of −7.3% is the deploy-relevant number. The −35.7%
full-sample MDD is dominated by W1 2018-2019 (pre-institutionalization
era where the mechanism hadn't fully activated).

### W4 sub-slices (binding test)

| slice | n | Sharpe | mean | MDD |
|---|---|---|---|---|
| W4-2024 | 59 | +1.04 | +0.166% | −7.2% |
| **W4-2025-26 (BINDING)** | **71** | **+0.64** | +0.068% | −7.2% |
| W4-2025 | 51 | **+1.89** | +0.195% | −3.4% |
| **W4-2026** | **20** | **−2.71** | **−0.258%** | −7.1% |

W4-2025-26 clears the +0.30 Sharpe bar at +0.64. But the 2025 alone is
spectacular (+1.89) and 2026 alone is catastrophic (−2.71) — the average
masks bimodal behavior.

### Cost sensitivity (RT bps)

| cost | full Sh | full mean | W4 Sh | 2025-26 Sh | 2025-26 mean |
|---|---|---|---|---|---|
| 3 bps | +0.78 | +0.274% | +0.98 | +0.83 | +0.088% |
| **5 bps** (verified Eightcap) | +0.72 | +0.254% | **+0.83** | **+0.64** | **+0.068%** |
| 7 bps | +0.66 | +0.234% | +0.68 | +0.45 | +0.048% |
| 10 bps | +0.58 | +0.204% | +0.46 | +0.17 | +0.018% |

Cost-insensitive — strategy remains positive at all 4 cost levels.
Even the conservative 10 bps assumption gives 2025-26 Sh +0.17.

### W4 quarterly trajectory

| quarter | n | mean | Sharpe |
|---|---|---|---|
| 2024Q1 | 18 | +0.311% | +1.96 |
| 2024Q2 | 12 | +0.357% | +5.70 |
| 2024Q3 | 11 | +0.572% | +2.78 |
| **2024Q4** | 18 | **−0.353%** | **−2.15** |
| 2025Q1 | 13 | +0.051% | +0.40 |
| 2025Q2 | 13 | +0.335% | +3.51 |
| 2025Q3 | 12 | +0.292% | +3.77 |
| 2025Q4 | 13 | +0.110% | +1.27 |
| **2026Q1** | 14 | **−0.345%** | **−4.85** |
| 2026Q2 | 6 | −0.054% | −0.36 |

Pattern: 6 strongly-positive quarters, 2 strongly-negative, 2 modest.
The two negative quarters (2024Q4, 2026Q1) coincide with periods of
sharp BTC moves but not in a perfectly clean way (2025Q4 was also a
BTC −25% quarter and the strategy gave +1.27 Sh).

### Null check (direction-symmetric short variant)

- LONG Sh +0.72, mean +0.254%
- SHORT Sh −1.00, mean −0.354%
- **Fade-gap +1.72** (clean directional content; mechanism is real, not artifact)

### Bear-regime context (BTC daily returns)

| period | BTC return | BTC MDD | Strategy Sh | Strategy MDD |
|---|---|---|---|---|
| 2024Q4 | +51.5% | −13.7% | −2.15 | (small) |
| 2025Q1 | −15.1% | −25.7% | +0.40 | (small) |
| 2025Q4 | **−24.9%** | **−32.7%** | **+1.27** | (small) |
| **2026Q1** | **−26.0%** | **−35.2%** | **−4.85** | **−7.1%** |
| 2026Q2 | +11.0% | −3.5% | −0.36 | small |

The "long-bias fails in bear" hypothesis is **partly true but doesn't
fully explain 2026Q1**. 2025Q4 had similar drawdown shape and the
strategy gave +1.27. Something about 2026Q1 is materially different —
possibly the first signs of mechanism decay, possibly idiosyncratic
on n=14.

### Pre-committed kill criteria check

| # | criterion | actual | threshold | result |
|---|---|---|---|---|
| 1 | **2025-2026 net Sharpe** (BINDING) | **+0.64** | > +0.30 | **PASS** |
| 2 | 2026 mean trade return | −0.258% | > +0.02% | **FAIL** |
| 3 | Full-W4 Sharpe | +0.83 | > +1.0 | FAIL |
| 4 | MDD (FULL, compounding-equity) | −35.7% | > −20% | FAIL |
| 5 | Trades/yr | 47.8 | ≥ 50 | FAIL (rounding) |
| 6 | Fade-gap | +1.72 | > +0.40 | **PASS** |
| 7 | Cost-robustness (Sh at 10bp) | +0.58 | > 0 | **PASS** |

**3/7 PASS.** Binding criterion passes; substantive 2026 criterion fails;
remaining failures are calibration (MDD dominated by W1, trades/yr at
edge, Full-W4 Sharpe near threshold).

### Phase 1 verdict and forward options

**MARGINAL → KEEP_FOR_REFERENCE.** Pre-commit discipline: the 2026
quarter criterion was explicitly written to catch active decay; it
triggered. The W4-2025 quarters showed the mechanism alive and strong;
W4-2026 quarters say something has changed. Without more 2026 data
(Q2 in progress, n=6 so far), one cannot distinguish:

1. **2026Q1 is a one-off bear-regime artifact** — the mechanism will
   return to W4-2025 form in 2026Q2-Q4. Re-run Phase 1 then.
2. **2026Q1 is the start of permanent decay** — the Asian-open structural
   bid is being arbed out as institutional flow normalizes. KEEP_FOR_REFERENCE
   is the right verdict.

Two honest forward options:

- **Tombstone now** (KEEP_FOR_REFERENCE) — accept the pre-committed
  verdict as final. The mechanism is preserved as a negative-result
  reference; no live trades.
- **Wait + re-run on truly-OOS 2026Q2-Q3 data** — the pre-commits stand
  unchanged. If Phase 1 re-passes on the same kill criteria with fresh
  data, promote. If it fails again, tombstone. Set re-check for
  ~2026-08-15 (Q2-Q3 will have ~25-30 fresh trades, enough to settle the
  question).

### Why "add a regime-detector overlay" is NOT a valid forward option

A regime gate (pause when BTC 30-day return < −10%, or trade only above
200-day MA, etc.) designed AFTER observing the 2026Q1 failure is
goalpost-moving by another name. It is exactly the "optimized variant
wins in-sample" trap from CLAUDE.md, one meta-level up: instead of
picking the best filter parameter from a sweep, the variant being
"picked" is the schedule of when-to-trade-and-when-not-to, and the
information being used to pick it is the very observation that triggered
the kill criterion. A regime gate fit to retroactively skip 2026Q1
would look great on this backtest and have no honest OOS predictive
content.

The only methodologically-honest way to introduce a regime gate is:
either (a) pre-commit it in a separate NEW thesis BEFORE looking at
2026 performance under that gate, on a DIFFERENT instrument or
mechanism, OR (b) treat it as a portfolio-level risk-management rule
applied uniformly across all strategies in the live book, with the
threshold chosen on grounds unrelated to btc_intraday's performance.
Neither belongs in this thesis.

## Pre-committed Phase 1 kill criteria (post-Phase-0c)

Cost model: **5 bps RT baseline** (verified median on Eightcap 00-07 UTC),
sensitivity sweep at **3 / 5 / 7 / 10 bps**.

- **2025-2026 net Sharpe > +0.30** at 5 bps RT baseline (binding — the
  W4-internal decay means 2024 strong quarters cannot pay for forward
  expectation)
- **2026Q1 + 2026Q2 individual quarter mean trade return > +0.02%**
  at 5 bps RT (relaxed from +0.05% given the lower cost; still catches
  active-decay-to-zero)
- **Full-W4 Sharpe > +1.0** at 5 bps RT (filter math gives Sh +3.70 in
  Phase 0b — this is easily clearable)
- **MDD < 20%** on FULL
- **Trade count ≥ 50/yr** (best-combo k=0.5 gives 85/yr; k=1.0 gives 46/yr —
  at the edge)
- **Fade-gap > +0.40** vs symmetric short-direction variant (null check)
- **Walk-forward mean degradation < 0.5** across 5 rolling W4-internal splits
- **W3 sign**: drop the strict "all 4 regimes positive" requirement (W3
  fails on filtered buckets, consistent with 2022-2023 bear-market regime
  broadly being weak for Asian-buy-the-open across assets); require W2
  AND W4 both positive (mechanism active in bull regimes)
- **Cost sensitivity**: net Sharpe must remain > 0 at 10 bps RT (conservative
  case for volatile periods). At 3 bps RT the strategy should clearly thrive
  (Sh > +1.0); the sensitivity curve characterizes broker-risk exposure.
- **DOW concentration < 50%** in any single weekday in the filtered version
  (current 31% is comfortable)
- **Cross-product check**: hour-00 UTC effect must also hold on at least
  one of {XAUUSD, ETH, SOL} — corroborates "global Asian morning bid"
  vs BTC-specific artifact

## Files

- `btc_intraday.md` — this doc
- `_fetch_btc_m5.py` — pulls BTCUSD M5 from datalake in monthly chunks,
  saves to `ohlc_data/BTCUSD_M5.csv` (704k rows through 2026-04-30)
- `_profile_btc_hod.py` — aggregates M5→H1, runs hour-of-day + DOW slice
  + W1-W4 regime profile
- `_profile_btc_filters.py` — Phase 0b filter sweep: prior-24h magnitude,
  prior-NY magnitude/direction, DOW slice, magnitude×direction combos,
  hold-window sweep, W4 internal trajectory, best-combo gate, W4-recent
  floor check
- `_profile_btc_subhour.py` — Phase 0c sub-hour M5 profile within
  00:00-01:00 UTC; confirms drift is evenly distributed (not front-loaded)
- `_profile_btc_spread.py` — Phase 0c Eightcap M1 spread verification;
  median RT 5.3 bps during 00-07 UTC, well under the 7-bp pass threshold
- `btc_intraday_demo.py` — Phase 1 numpy simulator (Variant E baseline,
  hold sweep, regime breakdown, W4 sub-slices, cost sensitivity, null
  check, W4 quarterly trajectory, kill-criteria summary)
