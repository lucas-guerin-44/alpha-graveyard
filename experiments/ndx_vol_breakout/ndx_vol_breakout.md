# NDX100 direction-agnostic vol-breakout — Phase 1/2 thesis

**Status**: Phase 1/2, 2026-05-29. The *purer* long-gamma sibling of the deployed `ndx_trend_day`
(removes direction risk). Aimed at the same corr-gap (#3) — a leg that thrives on volatile days.
**Verdict (2026-05-29): REJECT for the tail-hedge purpose.** Standalone-positive (Sh +0.71, dir-gap +1.69,
gap-guard clean Δ+0.00) but **fails the tail-complement decisively**: corr→book **+0.389** and **−33.6 bp on
the book's worst-decile days** (it *amplifies* drawdowns, the opposite of `ndx_trend_day`'s +14.4 bp). Despite
−0.34 corr to `lunch_fade`, it is positively book-correlated and tail-concave.

**Why (the reusable finding):** entry *timing* flips the tail-sign. `ndx_trend_day` commits at 10:30 (thrust) →
already positioned before the extension → rides the big one-way day (tail-convex). This breakout waits for the
range to break → on the worst days (extend-then-reverse whipsaws, which *are* the book's worst days) it enters
the extension late and eats the reversal → tail-concave. Same mechanism family, opposite tail behavior. Confirms
`ndx_trend_day`'s early-commit is load-bearing, not luck. Anti-corr to one leg ≠ tail-complementary; the
worst-day-profit test is the real gate. See RESEARCH_NOTES (entry-timing/tail-sign lesson).

## Thesis (mechanism)

1. `ndx_trend_day` commits at 10:30 in the *opening-range-close direction* (thrust). Its weakness: a day that
   looks up at 10:30 but **reverses** — it's long the wrong way.
2. A **direction-agnostic opening-range breakout** sidesteps that: after the OR forms (09:30-10:30), enter when
   price **breaks** the OR — long above `OR_high`, short below `OR_low`, **whichever side breaks first** — and
   hold to the close. The market picks the direction; we ride whichever way the volatile day actually goes.
3. Vol-expansion gate (range >> its own trailing norm) selects the days likely to break-and-trend (0DTE
   short-gamma amplifies one-way moves post-2022, same regime force that pays `ndx_trend_day`).
4. This is closer to a **long-gamma / straddle proxy**: it should be *more tail-convex* than `ndx_trend_day`
   (captures big reversal days too) — at the cost of false-breakout whipsaw on wide-but-choppy days.

## Signal math (gap-aware fill — lesson #81/#83 baked in)

```
RTH NDX100 M5. OR = 09:30-10:30 ET. or_hi/or_lo/or_open, or_range_pct = (or_hi-or_lo)/or_open.
vol_gate = or_range_pct > EXP_MULT * median(trailing-20d or_range_pct, shifted)   # relative, lesson #63
After 10:30, first bar that breaks:
  high >= or_hi -> LONG ; entry = (bar_open > or_hi) ? bar_open : or_hi   # GAP-AWARE: if it gaps through, fill at open
  low  <= or_lo -> SHORT; entry = (bar_open < or_lo) ? bar_open : or_lo
hold to cash close 16:00. ret = dir*(close-entry)/entry - cost. No break => flat.
```

## Why retail-accessible / universe

NDX100 CFD, M5, US RTH — same vessel as `lunch_fade`/`ndx_trend_day` so tail-complementarity is measured
directly. Cost 0.8 bp, sweep. (Tradeable live as stop-entry orders at OR_hi / OR_lo.)

## Expected performance (prior — honestly REJECT-leaning)

Naive both-sides ORB loses to friction (false-breakout whipsaw); the user flagged it's the trickier one.
The novel elements are the **vol-expansion gate** + **direction-agnosticism** + the post-2022 regime. Point
estimate Sh −0.2 to +0.6. The bar is the **tail-complement**, not standalone stardom — and whether it beats
`ndx_trend_day` on *reversal* days.

## Fail conditions (pre-committed — FROZEN BEFORE THE RUN)

1. Sharpe ≤ +0.30 after cost.
2. MDD ≥ 25%.
3. < 3/3 regimes positive (W1/W2/W3); **W3 holdout ≤ 0** is binding (W1-neg acceptable only if mechanism-explained like `ndx_trend_day`).
4. Trades < 100.
5. **Null-check**: break-continuation minus break-FADE dir-gap ≤ +0.30 (if fading the break wins, breaks mean-revert here — no continuation content).
6. **Tail-complement (load-bearing)**: FAIL if corr to `lunch_fade` > +0.20 **or** mean return on book's worst-decile days ≤ 0.
7. **Gap-through guard (lesson #83)**: report % of entries that are gap-fills; if removing the level-fill (forcing open-fill) collapses Sharpe, the edge was phantom → REJECT.

PROCEED only if 1-5 pass AND 6 passes AND 7 clean. Also report **corr to `ndx_trend_day`** + relative
performance on reversal days (the reason this variant exists).

## Why this might fail (red flags)

- False-breakout whipsaw on wide-but-choppy days is the classic ORB killer.
- Level-based entry → phantom-fill bug risk (mitigated by the gap-aware fill from line 1).
- May just be a noisier `ndx_trend_day` (high corr to it, no added tail-capture) → then it's redundant, not complementary.

## Files

`ndx_vol_breakout_demo.py` (sim + regime + null + cost + gap-guard + tail-complement vs book + corr-to-ndx_trend_day).
