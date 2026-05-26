# XAU LDN-AM FADE — Break-of-Structure + Retest, 07-10 UTC (M15)

**Status (2026-05-26):** Phase 2 COMPLETE — REJECT.
**Verdict:** **REJECT** — baseline FADE fails 7 of 10 pre-committed kill criteria. The session-transplant hypothesis is refuted.

## Verdict summary (2026-05-26)

Baseline FADE (07-10 UTC, M15, FADE, cost=0.20pt, n=1048 / 7.7y):

| Metric | Value | Threshold | Result |
|---|---|---|---|
| FULL Sharpe | **-0.25** | > +0.50 | **FAIL** |
| W1 2019-2020 Sh | +0.10 | > +0.20 | FAIL |
| W2 2021-2022 Sh | **-0.63** | > +0.20 | **FAIL** |
| W3 2023-2026 (holdout) Sh | -0.28 | > +0.00 | **FAIL** |
| MDD | -6.34% | < 15% | PASS |
| Trades | 1048 | >= 200 | PASS |
| Fade-gap (FADE − CONT) | +0.44 | > +0.30 | PASS — mechanism *direction* is correct |
| Cost-stress @ 0.40pt | -1.23 | > 0.00 | **FAIL** |
| Deflated Sh | -0.34 | > +0.20 | **FAIL** |
| Corr vs deployed NY-AM (per-day pnl) | **-0.07** | < +0.70 | PASS — would have been a good diversifier *if* it worked |

The fade-gap is positive (FADE +0.44 better than CONT), so the **direction** of the mechanism is the same as the deployed NY-AM strategy. But the **magnitude** is roughly zero gross and goes net-negative at deploy cost. The W2 2021-2022 Sh -0.63 alone is decisive: this is the regime where the deployed NY-AM strategy posts Sh +1.70. The mechanism is session-specific to NY-AM, not portable to LDN-AM.

ATR-floor variants (atr-3 through atr-10) all hit INSUFFICIENT_N (n < 200). Per CLAUDE.md "DO NOT aggregate 'best variant' across a sweep as if it's the strategy" — the baseline is the verdict. The atr-10 FADE Sh +0.68 / n=16 over 0.9y is a small-sample artefact (the +$10 ATR threshold is only reached post-mid-2025 in the post-Trump-tariff vol regime) and would not survive a pre-commit.

## Full results table

```
variant        dir       Sh     W1     W2     W3      MDD     n   WR%    PF   fgap  Sh@CS    dSh   corr verdict
baseline       CONT   -0.69  -0.82  -2.31  +0.04  -14.22%  1048 38.7% 0.83  -0.44  -1.29  -0.82    --  FAIL
baseline       FADE   -0.25  +0.10  -0.63  -0.28   -6.34%  1048 32.9% 0.93  +0.44  -1.23  -0.34  -0.07 FAIL
atr-3          CONT   +0.19  +0.57  +0.00  +0.10   -3.84%   172 48.3% 1.13  +0.33  +0.10  +0.02    --  INSUFFICIENT_N
atr-3          FADE   -0.15  +0.05  +0.00  -0.08   -4.86%   172 33.7% 0.91  -0.33  -0.31  -0.33  -0.08 INSUFFICIENT_N
atr-5          CONT   +0.14  +0.00  +0.00  +0.04   -3.84%    80 45.0% 1.14  +0.07  +0.11  -0.09    --  INSUFFICIENT_N
atr-5          FADE   +0.07  +0.00  +0.00  +0.06   -3.12%    80 27.5% 1.07  -0.07  +0.00  -0.12  -0.07 INSUFFICIENT_N
atr-7          CONT   +0.02  +0.00  +0.00  -0.46   -3.86%    37 32.4% 1.03  -0.22  +0.00  -0.30    --  INSUFFICIENT_N
atr-7          FADE   +0.24  +0.00  +0.00  +0.72   -1.35%    37 32.4% 1.40  +0.22  +0.21  +0.02  -0.10 INSUFFICIENT_N
atr-10         CONT   -0.64  +0.00  +0.00  +0.00   -3.97%    16 37.5% 0.64  -1.32  -0.66  -0.64    --  INSUFFICIENT_N
atr-10         FADE   +0.68  +0.00  +0.00  +0.00   -1.26%    16 31.2% 1.73  +1.32  +0.64  +0.68  -0.18 INSUFFICIENT_N
atr-5+adx-20   CONT   +0.08  +0.00  +0.00  -0.18   -4.45%    68 47.1% 1.08  +0.13  +0.05  -0.16    --  INSUFFICIENT_N
atr-5+adx-20   FADE   -0.05  +0.00  +0.00  -0.06   -2.77%    68 26.5% 0.95  -0.13  -0.11  -0.30  -0.08 INSUFFICIENT_N
```

Cost sweep on baseline FADE: 0.10pt Sh +0.24 / 0.20pt -0.25 / 0.40pt -1.23 / 0.80pt -3.19. The strategy needs cost ≤ ~0.07pt to break even at baseline — Eightcap XAU's median real spread (deployed strategy spread audit C3 in xau_break_retest_m15.md) is 0.20-0.30pt, so the cost-survivable regime is **not realistic**.

Hour-of-entry breakdown for baseline FADE: hour 07 UTC −0.70bp (n=382), hour 08 UTC +0.25bp (n=382), hour 09 UTC −0.39bp (n=284) — no consistent fade signal across the window.

## Mechanistic interpretation (why the transplant failed)

1. **LDN-AM is a directional window, not a fade window.** The deployed `xau_session` strategy already captures positive drift through ~08 UTC; the residual drift bleeds into 07-10 UTC and punishes fade entries against it. This is the obverse of the NY-AM finding — NY-AM has *no* systematic intraday drift on XAU (per the deployed strategy's C1 cross-session control: `in-session vs off-sessions Δ Sh > +1.7`), which is precisely what makes the fade work there. The MM re-anchoring mechanism needs an absence-of-drift environment to clear; LDN-AM has too much directional pressure.

2. **LME AM auction (10:30 UTC) leaks into the entry window.** Pre-auction one-way real-money pressure between 09:00-10:00 UTC dominates the break-retest dynamic. A fade entry 30-60 min before the fix gets run over by the auction-flow accumulation, which is the opposite of NY-AM where the same break-retest mechanic is left to mean-revert without an end-of-window scheduled-flow event.

3. **The XAG hint did not transplant.** The XAG `_xag_deep_dive.py` Test 4 LDN-AM result was a **zero-cost gross** number — it was a mechanism screen, not a deployable Sharpe. Without an XAG net-of-cost baseline showing the mechanism actually clears any cost level, "XAU has tighter cost so it'll pass" was an unsupported jump. The right pre-commit would have been: *only* transplant XAG findings that have positive zero-cost Sharpe in **all** of W1/W2/W3 — that wasn't checked.

4. **What the W1/W2/W3 numbers say about session-portability.** W1 +0.10 (early-2018-2020 lower-0DTE / lower-Tokyo regime) is the only window that comes close to neutrality; W2 -0.63 (2021-2022 inflation-vol regime) is decisively negative; W3 -0.28 (post-2023 holdout) is also negative. There is no regime where this works. Compare to deployed NY-AM FADE: W1 +1.50 / W2 +1.70 / W3 +1.36 (all decisive). The asymmetry of session-portability is total.

5. **Diversification was not the issue.** The trade-by-trade correlation with deployed NY-AM (-0.07 over 1372 shared days) shows that *if* a LDN-AM strategy had worked, it would have been a near-zero-correlated complement. The REJECT is not redundancy-driven; it is signal-absence-driven.

## Lesson for the corpus

Session-portability **on the same instrument** is not free, even when the mechanism is intraday-microstructure rather than fundamental. Lesson #-3 already established the cross-instrument case (Asian-session-handoff XAU +1.23 / BTC +0.64 / WTI -0.58 W4). This experiment adds the cross-session-same-instrument case: NY-AM FADE Sh +1.49 → LDN-AM FADE Sh -0.25 on the same XAU M15 simulator. The mechanism is asymmetric across both axes (instrument × session), not just one.

Operational rule going forward: before transplanting an intraday-microstructure strategy to a second session window on the same instrument, **explicitly check the off-session-vs-in-session control (lesson C1 from xau_break_retest_m15 Phase 3) for the candidate window**. If the candidate window doesn't show the same in-session > off-sessions Δ Sh > +0.50 that the deployed window does, do not bother running the full Phase 2.

## Files

- `xau_ldn_am_fade.md` — this doc (verdict updated 2026-05-26)
- `xau_ldn_am_fade_demo.py` — demo simulator (reuses parent's engine)

## Original pre-committed thesis follows below (preserved unchanged)

---

## Thesis (mechanism)

This is a session-transplant of the deployed `xau_break_retest_m15` (NY-AM 13-15 UTC FADE on XAU M15, Sh +1.49 / W1+W2+W3 all positive) onto a **second daily window: London AM 07-10 UTC**.

The reason this transplant is worth running — and not auto-killed by lesson #-3 (Asian-session-handoff is not auto-transferable across instruments) — is the inverse direction of generalisation: we are holding the *instrument* fixed (XAU, where the mechanism is already validated) and varying the *session window*. The bet is on the **mechanism being session-portable on the same instrument**, not on the asset class porting at a fixed session.

1. **Mechanism**: BoS+retest FADE captures market-maker re-anchoring at recently broken structural levels — fresh swing breaks during a liquidity-thin window get faded back by passive book replenishment. The deployed NY-AM verdict shows the fade is mechanistically dominant on XAU; what we're testing is whether the same re-anchoring mechanic plays out in the LDN-AM window.

2. **Why LDN-AM 07-10 UTC**: LME silver/gold fixings (10:30 / 15:00 UTC London) bracket this window. The 07-10 UTC slot is *between* Asian-cash settlement (00 UTC fix) and the AM LME fixing — directional Tokyo-overnight flow is exhausting but the auction-driven LDN-AM real-money flow has not yet imprinted. That gap should favour fade-retracements over continuation.

3. **Empirical hint (XAG transplant test)**: `break_retest_universal/_xag_deep_dive.py` Test 4 surveyed 6 session windows on XAG zero-cost; LDN-AM 07-10 UTC FADE was a positive-Sharpe finding on silver with W1/W2/W3 stability — but XAG's ~10 bp RT spread at Eightcap eats the gross. **XAU's ~0.20 pt cost is ~0.7 bp at $2900 = ~14× more cost-survivable**, so an XAG-gross edge that washes in net should clear on XAU.

4. **Cadence multiplier**: if it passes, XAU now runs FADE in two daily sessions (LDN-AM + NY-AM). Doubling cadence on a *validated mechanism family* is the deploy thesis — not finding a new edge, but extending a known edge to a second window on the same instrument.

5. **Correlation concern**: the two sessions are 4-6 hours apart on the same instrument. A common-driver (e.g. dollar-index intraday trend bleeding into both) could push trade-by-trade correlation > +0.7, in which case the second session has no diversification value even on a Sharpe pass. Correlation vs deployed NY-AM book is a binding tombstone criterion (see kill criteria §).

## Key reference

- `experiments/_live/xau_break_retest_m15/xau_break_retest_m15.md` — companion strategy, NY-AM 13-15 UTC FADE, deployed 2026-05-25, full pipeline including C1 cross-session control, C2 block-bootstrap, C3 spread audit, C4 macro-release calendar
- `experiments/break_retest_universal/_xag_deep_dive.py` Test 4 — the cross-session screen on XAG that surfaced LDN-AM 07-10 UTC FADE as a candidate window
- [[xau_break_retest_m15]] — direct parent

## Signal math

Direct reuse of `simulate_break_retest_m15` from `experiments/_live/xau_break_retest_m15/xau_break_retest_m15_demo.py`. Only the session window changes.

```
session_start_utc = 7
session_end_utc   = 10
entry_cutoff_utc  = 10
swing_lookback    = 16 M15 bars (4h)
retest_window     = 3 M15 bars (45 min)
retest_tol_atr    = 0.30
stop_atr_mult     = 1.20
time_exit_bars    = 6 (90 min)
direction         = FADE (primary), CONTINUATION (null check)
cost_points       = 0.20 default; sweep 0.10 / 0.20 / 0.40 / 0.80
```

## Why retail-accessible

XAUUSD CFD with Eightcap (Pepperstone / IC Markets equivalents). 0.20 pt cost model matches deployed NY-AM strategy. Single MT5 EA can run both windows.

## Universe

XAUUSD only. No cross-asset extension at this phase.

## Expected performance (pre-committed point estimates)

The LDN-AM window will likely **underperform** NY-AM because the post-Tokyo Tokyo→LDN handoff is a known directional-drift period (xau_session deploys against drift in that family). But fade should still work if the mechanism is portable:

- FADE Sharpe **+0.50 to +1.00** (50-66% of NY-AM's +1.49)
- 50-90 trades/year (NY-AM session is 2h; LDN-AM is 3h → expect ~50% more trades per session, partially offset by lower break-frequency in early LDN)
- MDD < 10%
- WR ~37%, PF ~1.5

## Fail conditions (PRE-COMMITTED — these are written before the backtest runs)

These mirror the deployed `xau_break_retest_m15` Phase 2 grid, with one tightening (correlation tombstone) and one loosening (full Sharpe bar dropped from +1.0 to +0.50 because LDN-AM is the secondary session and we already have the NY-AM workhorse).

| # | Criterion | Threshold | Direction |
|---|---|---|---|
| 1 | Baseline FADE Sharpe (full sample, 0.20 pt) | > +0.50 | binding |
| 2 | W1 2019-2020 FADE Sharpe | > +0.20 | binding |
| 3 | W2 2021-2022 FADE Sharpe | > +0.20 | binding |
| 4 | W3 2023-2026 (holdout) FADE Sharpe | > +0.00 | binding |
| 5 | Max DD | < 15% | binding |
| 6 | Trade count | >= 200 | binding (else INSUFFICIENT_N) |
| 7 | Fade-gap (Sh_fade − Sh_cont) | > +0.30 | binding (else direction ambiguous) |
| 8 | Cost-stress @ 0.40 pt: FADE Sharpe | > 0.00 | binding |
| 9 | Deflated Sharpe (6-variant haircut) | > +0.20 | binding |
| 10 | **Trade-by-trade correlation vs deployed NY-AM book** | **< +0.70** | **binding — tombstone if violated** |

If criterion #10 fails on a Sharpe pass: the strategy is REJECT-by-redundancy. The mechanism is real but offers no portfolio benefit beyond the deployed NY-AM book.

If FADE fails but CONTINUATION passes with fade-gap reversed: the mechanism flips sign between sessions — REJECT (lesson #-3 / venue-of-mechanism failure).

If both directions lose: no signal in this window — REJECT.

## Why this might fail (red flags)

1. **LDN-AM is a directional-drift window, not a mean-reversion window**. The deployed `xau_session` strategy collects the Asian-session positive drift through 08 UTC. If part of that drift continues into 07-10 UTC, fade against an upward bias loses systematically.

2. **LME AM auction (10:30 UTC) one-way order flow** can reach the market 30-60 min in advance. If real-money sets directional bias before the fix, fade entries 30 min before the fix lose.

3. **Holiday-thin liquidity** on LDN-AM is more variable than NY-AM (LDN bank holidays — May Day, Jubilee, etc — drag the session into a pseudo-Asian regime where the retest mechanic fails entirely).

4. **High correlation with deployed NY-AM book**. Same-instrument same-mechanism strategies tend to capture the same intraday volatility regime; the diversification benefit may not survive criterion #10.

## Phase 2 plan

- [ ] Write demo reusing `simulate_break_retest_m15` from the deployed sibling
- [ ] Run baseline + 5 ATR-floor variants × 2 directions, mirroring deployed pipeline
- [ ] Regime breakdown W1/W2/W3
- [ ] Cost sweep 0.10/0.20/0.40/0.80
- [ ] Direction null check (CONT vs FADE)
- [ ] Trade-by-trade correlation vs deployed NY-AM book (Pearson on net_ret per shared trading-day-aggregate)
- [ ] Update this doc with results + verdict
- [ ] Update `docs/STATE.md` YAML block

## Files

- `xau_ldn_am_fade.md` — this doc
- `xau_ldn_am_fade_demo.py` — demo simulator (reuses parent's engine)

## Results

(to be filled in after the run)
