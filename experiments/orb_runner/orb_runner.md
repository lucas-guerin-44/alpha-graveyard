# GER40 ORB — partial-exit "runner" overlay (let a sliver ride the trend day)

**Status**: Phase 2, 2026-06-05. Overlay on the DEPLOYED `orb` GER40 T+180 LONG-only
strat (`experiments/_live/orb/`). Not a standalone strategy — a modification to the *exit*.

**Verdict: REJECT (2026-06-05).** The runner is Sharpe-, CAGR- and holdout-negative
with negligible convexity gain. The post-T+180 drift on the deployed session is
*negative* (as orb.md's TOD sweep predicted), so keeping a sliver past the clock is a
net drag. The base is **already** a +5.5-skew lottery-ticket profile (WR 20%, PF 1.25)
— the T+180 winners already *are* the trend days; there is no untapped right tail for a
runner to harvest. Null check: gated ≈ ungated (the trend gate adds nothing on a
risk-adjusted basis). Pre-committed conditions [1], [3], [4] all FAIL.

---

## Phase 2 results (2026-06-05) — GER40 DEPLOY session (Berlin 06:00-14:30, the live TZ-shifted window)

> **Session note**: the deployed GER40 ORB trades the TZ-fix shifted session
> (Berlin 06:00-14:30; orb.md banner 2026-05-28), NOT 09:00-17:30. Reproducing the
> deployed +0.76/+0.93 *requires* that window. The repo's `ger40_asymmetry.py` is
> hardcoded to `ORB_SESSION=EU` (09:00-17:30) and so reports LONG-only full Sh **−0.17**
> — it no longer matches the deployed config post-tz-fix. Flagged, not fixed here.

Base reproduction (this demo, DEPLOY session, extended data to 2026-05): full Sh
**+0.87**, HO **+0.83**, MDD −8.55%, 1453 trades, WR 20%, PF 1.25, **skew +5.51** — a
faithful match to orb.md's +0.76/+0.93/−7.8% (slightly higher on the extended window).

| Variant | Full Sh | HO Sh | CAGR | MDD | skew | max win | runner-leg sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| **base** (T+180 LONG-only) | **+0.87** | **+0.83** | +4.31% | −8.55% | +5.51 | +5.57% | — |
| gated runner (bank .75) | +0.85 | +0.80 | +4.27% | −8.45% | +5.82 | +5.90% | **−0.19%** (186 days) |
| ungated runner (null) | +0.85 | +0.74 | +4.28% | −8.35% | +5.79 | +5.90% | **−0.16%** (301 days) |

Bank-fraction sweep (gated): bank .50 → Sh +0.82, bank .75 → +0.85, bank .90 → +0.86
(monotone: *less* runner = better → the runner is a drag). Runner-exit sweep (close /
T+240 / T+300): +0.85 / +0.78 / +0.82 (holding longer is worse). All consistent.

**Scorecard vs pre-committed conditions:**

- [1] holdout not degraded — **FAIL** (+0.80 < +0.83).
- [2] Sharpe guard (≥ base − 0.05) — PASS (+0.85 vs +0.87), but only because the runner
  is *small*; it never helps.
- [3] convexity real (CAGR & skew & maxW all up) — **FAIL** (CAGR down; skew/maxW up
  only trivially: +5.51→+5.82, +5.57→+5.90).
- [4] NULL: gated beats ungated — **FAIL** (Sh tie +0.85; CAGR tie). The trend gate
  picks marginally better *per-day* runner days (runner-leg WR 55.4% vs 49.2%) but the
  kept days are still net-negative and too few to matter.
- [5] MDD < 25% — PASS (−8.45%).

### Mechanistic interpretation — why the runner can't help here

1. **No untapped right tail.** The base is already a convex, low-win-rate breakout:
   WR 20%, PF 1.25, **trade-PnL skew +5.51**. Most trades stop out small (−0.40% avg);
   a few T+180 exits run to +5%+. The T+180 exit is *already* the trend-day harvester —
   the big winners in the base ARE the days that trended into midday. There is no
   separate "trend day" the fixed clock leaves on the table for a runner to catch.
2. **Post-T+180 drift is negative.** orb.md's TOD sweep (T+180 +0.58 > T+240 +0.52 >
   EOD +0.38) said extending past the clock loses on average. The runner-leg sums confirm
   it directly: **−0.19% (gated) / −0.16% (ungated)** total over 7 years. Holding into
   the US open (the deploy session ends 14:30 Berlin, right as US futures ramp) gives
   back more than it captures.
3. **The gate has weak but insufficient content.** It does select better runner days
   (55.4% vs 49.2% leg WR) — it isn't pure noise — but the edge is too small to overcome
   the negative base-drift, and concentrating into 186 days *underperforms* an
   indiscriminate sliver on Sharpe. Selection < diversification here.

**Lesson**: a "let a sliver run" overlay can only add value when the base exit leaves
right-tail on the table. A base that is *already* high-positive-skew (fixed time/asym-stop
breakout) has no spare tail — the runner just buys negative-expectancy post-exit drift.
This generalizes: check base trade-PnL skew BEFORE proposing a runner; high skew ⇒ the
exit already harvests the tail ⇒ runner is redundant-to-harmful.

---

## Thesis (mechanism)

The deployed GER40 ORB cuts every trade at a fixed **T+180min** clock. That clock is
the validated average optimum (TOD sweep: T+180 Sh +0.58 > T+240 +0.52 > EOD +0.38,
`orb.md`). But a fixed time-stop is a blunt instrument: it closes winners and losers at
the *same wall-clock time* regardless of whether that specific day is still trending.

Proposal — **bank the bulk, keep a sliver**:

1. At T+180, close `BANK_FRACTION` (e.g. 75%) of the position. This **secures the
   "normal" validated gain** — the entry→T+180 P&L is byte-identical to the deployed
   strat, so the modification cannot touch the core edge.
2. On days that look like **trend days at the T+180 mark**, leave the remaining
   `(1−BANK_FRACTION)` running to the cash close (still stop-protected at OR-low).
   On non-trend days, fully exit at T+180 exactly as today.
3. Genuine trend days set their high/low in the last hour ~60-65% of the time
   (Crabel 1990; cited in `orb.md` thesis). A fixed T+180 exit structurally misses
   that tail. The runner buys convex exposure to it for a small, pre-banked cost.

The incremental P&L of the overlay per gated day is exactly
`(1−BANK_FRACTION) × (exit_return from T+180 → close)`. Everything else is the
deployed strat untouched.

## Key reference

- Crabel (1990), *Day Trading with Short Term Price Patterns and ORB* — trend-day
  extreme-near-close statistic; the tail this overlay targets.
- `experiments/_live/ndx_trend_day/` — repo's own vol/range-expansion trend-day gate
  (relative-to-trailing-norm, pre-committed `EXP_MULT=1.0`; lesson #63 "relative not
  absolute"). The gate here is the intraday analog.

## Signal math

```
Deployed base: GER40 EU session, OR=30min, entry_cutoff=180, stop=OR_low (1.0x),
               T+180 exit, LONG-only, cost=1pt RT.

Overlay, evaluated at the bar where the T+180 clock fires (LONG context):
  hi, lo   = running day high/low through this bar (incl. OR window)
  rng      = hi - lo
  gate = (rng >= K_RANGE * or_width)                 # range has extended past OR  [K_RANGE=2.0]
         AND ((close - lo) / rng >= NEAR_HIGH)        # closing near the day's high [NEAR_HIGH=0.70]
         AND (close > entry_px)                       # trade still in profit

  if gate:  bank BANK_FRACTION at this bar's close; keep (1-BANK_FRACTION) running
            to cash-close (or OR-low stop, whichever first).
  else:     full exit at this bar's close (== deployed behavior).

Pre-committed params (FROZEN before run): BANK_FRACTION=0.75, K_RANGE=2.0,
NEAR_HIGH=0.70, runner exit = cash-close (no trailing-stop tuning in v1).
Cost: runner's separate exit leg adds no extra cost in the proportional spread model
(total in-notional == out-notional whether split or not).
```

## Why retail-accessible

Pure exit-logic change on an already-deployed MT5 EA. One partial-close order at the
T+180 mark; the runner is the existing position with a reduced lot. No new data, no
new instrument.

## Universe

GER40 CFD, M5, EU session (Berlin 09:00-17:30 cash; deployed on the GMT+3 shifted
session per the TZ-fix). 2019-01-02 → 2026-05-29. LONG-only.

## Expected performance (prior)

The overlay's expected *Sharpe* contribution is **slightly negative** — the average
post-T+180 drift is negative (TOD sweep). What it can add is **right-tail convexity**:
higher max-winner, positive skew, possibly higher CAGR, at a small Sharpe cost. Point
estimate: full Sharpe within ±0.05 of the +0.76 base; CAGR +0 to +1.5pp; skew up.
Honestly a likely **MARGINAL / REJECT on Sharpe**, kept only if convexity is real AND
the gate beats an ungated runner.

## Fail conditions (pre-committed — FROZEN BEFORE THE RUN)

The bar is "does this improve the DEPLOYED strat", not standalone Sharpe.

1. **Holdout guard**: 2023-2026 holdout Sharpe must NOT drop below the base T+180
   LONG-only holdout. If the runner degrades the holdout → REJECT.
2. **Sharpe guard**: full-sample Sharpe ≥ base − 0.05 (no material Sharpe loss).
3. **Convexity must be real**: gated-runner CAGR > base CAGR AND trade-PnL skew up
   AND max-winner up. If it costs Sharpe and buys no convexity → REJECT.
4. **Null check (load-bearing)**: the gated runner must beat the **ungated** runner
   (keep the sliver on *every* day, no trend gate) on full + holdout Sharpe/CAGR.
   If the gate adds nothing over an indiscriminate runner, it has no trend-day
   content — it's just buying DAX drift exposure (the un-run "long-to-close every
   day" benchmark flagged in `orb.md`). → REJECT the gate.
5. MDD must not exceed the 25% Phase-2 ceiling (base is −7.8%; lots of headroom, but
   the runner rides into the US open which can reverse hard).

Outcome map: PASS (adopt) needs 1-4 all green. MARGINAL = convexity real but Sharpe
down (a CAGR-vs-Sharpe tradeoff for the user to choose). REJECT otherwise.

## Why this might fail (red flags)

1. **Average post-T+180 drift is negative** — the runner swims against the measured
   current; the gate has to do real work to flip it.
2. **US-open reversal** — the runner holds into 15:30 Berlin when the US opens and
   routinely reverses the European morning trend. "Morning showed momentum" does not
   protect against an afternoon US-led fade.
3. **Thin gated subsample** — trend days are ~15-20% of days; the LONG-only book is
   ~1,440 trades over 7y, so the gated set may be ~250-350 trades, ~80-110/regime.
   Weak power for the extension decision specifically.
4. **Overfit surface** — BANK_FRACTION, K_RANGE, NEAR_HIGH, runner-exit = 4 knobs on
   an exit structure; the repo's #1 failure mode (NDX100). Mitigation: one frozen
   config, judged on holdout + null, sweeps reported but not cherry-picked.

## Phase 1 → 2 plan

- [x] Reproduce deployed base (T+180 LONG-only) — +0.87 / HO +0.83 on DEPLOY session ✓.
- [x] Gated runner (frozen config) — full + regime + holdout. → slightly worse on all.
- [x] Ungated runner (null check) — gate forced on every day. → gated ≈ ungated (gate inert).
- [x] BANK_FRACTION sweep (0.5 / 0.75 / 0.9) — monotone: less runner = better.
- [x] Runner-exit sweep (close / T+240 / T+300) — holding longer is worse.
- [x] Convexity stats: skew +5.51→+5.82, runner-leg sum NEGATIVE (−0.19%).
- [x] Verdict (REJECT) + graveyard block + lesson #98.

## Files

- Thesis: this file.
- Demo: `experiments/orb_runner/orb_runner_demo.py`.
- Base strat: `experiments/_live/orb/` (deployed GER40 T+180 LONG-only).
- Data: `ohlc_data/GER40_M5.csv`.
- Run: `ORB_SYMBOL=GER40 ORB_SESSION=EU venv/Scripts/python.exe experiments/orb_runner/orb_runner_demo.py`
