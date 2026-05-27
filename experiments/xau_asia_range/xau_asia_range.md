# XAUUSD Asia-range level interaction — REJECT (Phase 1, bullrun confound)

**Status (2026-05-27):** **REJECT.** Phase 1 simulator ran clean kill-criteria
battery; best variant D_asym = 6/8. The two failures are load-bearing.

| variant | Sh full | Sh W4 | MDD | n | fade-gap | WF-deg | Sh@4bp | bull-gap | score |
|---|---|---|---|---|---|---|---|---|---|
| A_baseline | -0.27 | -0.11 | 36.3% | 3771 | +1.36 | +0.02 | -1.21 | -0.43 | 3/8 |
| B_first | -0.30 | -0.11 | 32.8% | 2533 | +0.98 | -0.27 | -1.09 | -0.05 | 3/8 |
| C_lon | +0.01 | +0.47 | 23.6% | 2436 | +1.54 | -0.11 | -0.75 | -0.13 | 3/8 |
| **D_asym** | **+0.50** | **+1.24** | **11.9%** | 1377 | +2.29 | -0.32 | **-0.15** | **+0.14** | 6/8 |

**Load-bearing failures (both on the best variant D_asym):**

1. **Bullrun-isolation gap +0.14** vs +0.30 bar. London-session-range control
   variant (range 11-19 UTC, same width, same trade rule) shows W4 Sharpe +1.10 —
   essentially identical to Asia-range W4 +1.24. The W4 alpha is the gold
   bullrun expressing through any 8h-range-breakout filter, not Asian-session
   microstructure. Pre-W4 regimes (W1-W3) are noise (sh -0.09 to +0.07).
2. **Cost-stress fail @ 4bp** (Sh -0.15). Even at 2bp Eightcap-Raw realistic,
   per-trade gross is only ~3.5 bps — cost-cliff is right at deploy.

**Robustness check (WICK_MIN_FRAC=0.10, require touch wick ≥ 10% of range
beyond level)**: D_asym bullrun-gap flips to **-0.39** (London W4 +1.36
*beats* Asia W4 +0.96). Pattern is fragile to a single-parameter change —
strong evidence the apparent edge is regime-bullrun, not structural.

**Methodological win**: bullrun-isolation control was pre-committed and built
into the Phase 1 simulator from the start (vs xau_session retrofit). Detected
the regime confound in one pass and avoided the Phase 2-5 sunk cost.

**Why Phase 0 looked so good and Phase 1 didn't:** Phase 0 measured per-touch
forward return *unconditional on regime*. W4 dominated the FULL average
(continuation +5.2 bps t=+3.87 in W4 alone, near-zero W1-W3). When the same
W4 amplification appears in the London-session-range control, the signal is
revealed as a bullrun rider, not microstructure.

**Original discretionary thesis**: user observed "price retests and bounces
off Asia-range high/low" → fade direction. Phase 0 flipped sign (data showed
continuation). Phase 1 showed even the corrected direction doesn't isolate
Asia microstructure. Best read of the user's discretionary edge: they're
correctly reading short-horizon noise around the level (the 5-15min wicks
that bounce) but the 1-4h EV is trend-following the bullrun.

**This strategy is NOT deployed.** Tombstoned to STATE_GRAVEYARD.

## Origin

Surfaced from a discretionary observation by the user: the high and low of
XAUUSD's price range during 00:00-08:00 CET ("Asian session") tend to act as
S/R during the subsequent London/NY hours, with price retesting and bouncing
around them. User's discretionary read was *fade* (mean revert off the
extremes); Phase 0 profiling revealed the opposite is the dominant signal.

CET window 00-08 = UTC 23-07 (winter) / UTC 22-06 (summer). Phase 0 anchored
on UTC 23-07 as the primary 8h range definition and confirmed 6h (01-07) and
7h (00-07) variants produce similar shape.

## Phase 0 finding (2026-05-27)

Across 2,036 trading days 2018-04-30, 9,744 real-level touch events captured
during the 07-21 UTC post-range window, **the forward-return bias after a
touch is continuation, not fade.**

### Headline FULL 2018-2026

| direction | touch type | n | fwd 240m mean | t | placebo 240m | placebo t |
|---|---|---|---|---|---|---|
| high-touch (price continues UP) | 5,123 | +1.8 bps | **+2.69** | -0.3 bps | -0.53 |
| low-touch (price continues DOWN) | 4,621 | -1.8 bps | **-2.27** | +1.4 bps | +2.31 |

Mirror-symmetric in real levels (continuation), opposite-shape on placebo
(mean reversion after extension by 1x range-width). Real levels carry
information; the placebo confirms it's not just "price drifts after a big move".

### Regime decomposition — this is a W4 strategy

| regime | high-touch 240m | t | low-touch 240m | t |
|---|---|---|---|---|
| W1 2018-19 | +0.5 | +0.43 | -1.1 | -0.85 |
| W2 2020-21 | -0.3 | -0.20 | -2.4 | -1.43 |
| W3 2022-23 | +1.0 | +0.79 | -1.2 | -0.91 |
| **W4 2024-26** | **+5.2** | **+3.87** | -2.4 | -1.26 |

Pre-2024 the signal is weak/inconsistent. W4 amplifies — same shape as
`xau_session`, same likely driver (post-institutionalization Asian flow
discipline). This is a **W4-binding strategy** per the BTC W4-floor lesson.

### Best conditional cells (W3+W4, asymmetric across directions)

| cell | n | fwd 240m | t |
|---|---|---|---|
| LONG: high-touch + 1st touch + London-UP | 437 | +6.3 bps | +3.27 |
| SHORT: low-touch + 3rd+ touch + London-DOWN | 648 | -6.0 bps | -2.51 |
| (also strong) high-touch + prior-NY DOWN (FULL, not W3+W4) | 2,099 | +4.6 bps | +4.47 |

Asymmetry note: long side wants *first-touch* (Asian buyers absorb first lows,
sellers chase first highs); short side wants *persistent-touch* (3rd+ low
suggests Asian buyers capitulated and Western selling extends). Could be a
genuine flow-asymmetry mechanism or data-mining artifact. Phase 1 will tell.

## Thesis (mechanism)

1. **Asian session prints the day's reference range.** OTC desks and Asian
   physical/central-bank flow establish liquidity zones during 23-07 UTC.
   These zones become the next day's reference for Western desks.
2. **Western desks (London open onward) test these levels.** A touch of
   range-high is the market probing whether Asian sellers will defend the
   level; a touch of range-low is probing Asian buyers.
3. **Post-2022 institutionalization amplifies follow-through.** As Asian
   sovereign / ETF / family-office flows scaled post-Russia sanctions
   (W4 2024-26), the level-defense becomes weaker relative to
   trend-continuation. The "bounce" the user observes discretionarily is real
   short-horizon noise; the 1-4h drift is continuation.
4. **London-open direction signals which side will win.** When London opens
   UP and tests range-high → buyer dominance confirmed → continuation up. When
   London opens DOWN and re-tests range-low → seller dominance confirmed →
   continuation down.

## Key reference

No direct paper on Asia-range S/R for gold. Conceptually adjacent to:
- Lehmann & Modest 1994 ("Trading costs, liquidity, and asset returns")
- Anolick et al 2020 ("Time-zone effects in FX market microstructure")
- Internal: this repo's [[xau_session]] confirmed Asian-session-specific
  structural flow on XAUUSD; this thesis tests whether the same flow leaves
  a level-imprint, not just a directional drift.

## Signal math (Phase 1 simulator)

```
For each trade-date D (UTC):
  range_bars = M5 bars where (timestamp.hour in {23, 0..6}) and timestamp.trade_date == D
  range_high = max(high) over range_bars
  range_low  = min(low) over range_bars
  range_size_bps = (range_high - range_low) / mid * 10000

  prior_NY_dir = sign(NY close - NY open) where NY = D-1 13:00-21:00 UTC
  lon_open_dir = sign(close at D 07:25 UTC - open at D 07:00 UTC)

  For each M5 bar B in (D 07:00 UTC .. D 20:55 UTC):
    if (bar B's high >= range_high) and (bar B-1 high < range_high):
      record HIGH-TOUCH event at B, touch_num = next-in-day count
    if (bar B's low  <= range_low ) and (bar B-1 low  > range_low ):
      record LOW-TOUCH event at B, touch_num = next-in-day count
```

Trade rules (per variant; baseline = simplest):

```
On HIGH-TOUCH event (if not already in a position):
  if variant allows: enter LONG at touch-bar close
  exit: time-based, T_HOLD minutes after entry, or 21:00 UTC cap
  cost: 2 bps RT applied at exit

On LOW-TOUCH event (if not already in a position):
  if variant allows: enter SHORT at touch-bar close
  exit / cost: same
```

Variants:

- **A — baseline**: every touch, both directions, all touch numbers (no filter)
- **B — first-touch only**: touch_num == 1 (per direction per day)
- **C — London-confirmation**: long if lon_open_dir == UP, short if DOWN
- **D — asymmetric pre-committed**: LONG if (high-touch and touch_num==1 and lon_open=UP); SHORT if (low-touch and touch_num>=3 and lon_open=DOWN)

T_HOLD: 240 min (= 48 M5 bars, matches Phase 0 best horizon).

## Universe / cadence / cost

- **Symbol**: XAUUSD on Eightcap (live verified all-in cost ~1.9 bps RT,
  see `xau_session.md` § Eightcap spread verification 2026-05-16).
- **Cost model**: 2 bps RT realistic; 4 bps stress; 6 bps cliff.
- **Cadence (FULL 2018-2026)**:
  - Variant A: ~9,744 events / 2,036 days = 4.8/day = ~1,210/year
  - Variant B: 1st-touches only ~2,798 = ~350/year
  - Variant D (LONG bucket only): 437 in W3+W4 = ~80/year deploy frequency,
    plus SHORT bucket ~80/year = ~160/year total

## Pre-committed kill criteria (Phase 1)

Phase 1 simulator runs all 4 variants through these bars. Cost = 2 bps RT.

- **Sharpe FULL > +0.30** (research bar after cost)
- **Sharpe W4 > +0.50** (binding constraint per [[BTC W4-floor lesson]])
- **MDD FULL < 15%**
- **Trade count ≥ 200** cumulative over backtest window
- **Continuation-vs-fade gap > +0.40**: run the same simulator with reversed
  direction (long on low-touch, short on high-touch). Continuation-direction
  Sharpe must beat fade-direction Sharpe by ≥ +0.40, else the level isn't
  doing directional work.
- **Walk-forward mean degradation < 0.50** across 5 rolling 3y-IS / 2y-OOS
  splits.
- **Cost-stress passes at 4 bps RT** (still positive Sharpe).
- **DOW concentration < 50%** in any single weekday.
- **Bullrun-isolation control**: run identical simulator on a translated
  range window (e.g. London-session range 09-13 UTC; same width-of-range
  logic, same trade rule). The Asia-range Sharpe must exceed the control
  by ≥ +0.30 in W4. If the control is as strong, the W4 result is
  attributable to the bullrun + general level-respect, not Asian-session
  microstructure specifically.

If a variant passes ≥ 7-of-9 kill criteria, it advances to Phase 2/3
(bootstrap CI, sign-flip permutation, deflated Sharpe, block-bootstrap
regime CI, MC slippage stress) — same structure as `xau_session`.

## Why this might fail (red flags)

- **W4 = bullrun confound** (biggest risk). XAUUSD rose ~125% W4. Any
  long-biased breakout strategy makes money in a strong uptrend trivially.
  The bullrun-control variant is critical; without it the W4 number is
  uninformative.
- **Discretionary thesis was fade; data says continuation** — possibility we
  measured wrong (e.g., touch definition too liberal, 240m horizon too long).
  Robustness check: shorter holds (60m, 120m) should show the same sign or
  the result is suspect.
- **Asymmetric long/short rules in Variant D** are post-hoc fit to Phase 0.
  Real test is whether Variant A or B passes — Variant D is a candidate, not
  a defended primary.
- **Cost: per-trade gross of +6 bps at 240m on best bucket** has ~33% cost
  haircut at 2 bps RT. Tighter than `xau_session`'s 5x net-to-cost ratio.
- **Touch definition arbitrariness**: required wick to exceed level. Phase 1
  should test wick-extension filter (touch only counts if `high - r_high >=
  0.1 * r_size`) to rule out micro-noise crossings.

## Phase 1 → Phase 2 plan

- [x] Phase 0 profile (`_profile_asia_range.py`) — DONE 2026-05-27
- [ ] Phase 1 simulator (`xau_asia_range_demo.py`) with variants A/B/C/D,
      fade-direction null-check, regime breakdown, walk-forward, cost stress,
      DOW concentration, and bullrun-isolation control (London-session range
      variant)
- [ ] If any variant passes ≥7/9 kill criteria: Phase 2 (bootstrap CI,
      sign-flip permutation, deflated Sharpe with n_trials=8 since 4 variants
      × 2 hold lengths)
- [ ] Phase 3: block-bootstrap per-regime CI, MC slippage at +2bp / +4bp
- [ ] Phase 4: retrospective forward-holdout (truncate to ≤2024, retest 2025-26)
- [ ] Phase 5: MT5 EA build (if all prior phases pass)

## Files

- `xau_asia_range.md` — this doc
- `_profile_asia_range.py` — Phase 0 level-interaction profile, placebo
  comparison, conditional splits, regime decomposition
- `xau_asia_range_demo.py` — Phase 1 simulator (next)
