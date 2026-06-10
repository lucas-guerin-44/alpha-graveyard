# XAUUSD intraday mean-reversion — regime-gated, high-cadence screen (M5, 2018–2026)

**Status**: COMPLETE — characterization screen, run 2026-05-30.
**Verdict (summary)**: **NEGATIVE — and the trend-gate mechanism is REFUTED.**
Intraday reversion exists but is the *same* ~0.2 bps sub-cost edge as the FVG
family via a different mechanism (pooled gross +0.232 bps @ h=6, net −0.268 @
0.5 bps). The core thesis — "fade works on range/low-ER bars, fails on trending
bars" — **failed its monotonicity test**: the most-ranging bucket (ER1) is the
*worst* (net −0.24 to −0.75), no ER gradient. So the gate doesn't rescue it.
0 of 56 cells robust. The only OOS-persistent corner is again **NY session**
(`thr2.5|NYPM`: disc net +0.70 → **holdout +1.89 bps, Sh +1.01**) but at 178/yr,
t<2 — sub-cadence and sub-significance, the *identical* signature to the FVG
screen's NY-AM corner. **Two independent intraday mechanisms (continuation,
reversion) → same verdict: XAU M5 is efficient to ~0.2–0.3 bps; no high-cadence
edge clears the spread.** This closes the frequent-XAU intraday question.

> **What this is.** A gross-first characterization screen (same engine family as
> `xau_imbalance_screen`) asking one question: **does fading intraday price
> extension on XAU M5 clear cost (~0.5 bps RT), at high cadence, when gated by an
> intraday trend/range regime?** Not a parameter optimizer — the deliverable is
> the reversion-edge surface vs (extension magnitude × trend regime × session),
> and whether any frequent cell clears the cost + significance + cross-regime
> gates. One pre-committed cell is drawn and validated on the untouched 2024–2026
> tail, then confirmed on SPX500/NDX100 (the other tight-spread CFDs).

## Motivation — why this specific shape (and why it's not in the graveyard)

The XAU intraday reject pile (12 experiments) is consistent and instructive:

- **Momentum/continuation is dead or sub-cost** — FVG continuation ~0.2 bps
  (`xau_imbalance_screen`, #90), `xau_break_retest` has a *negative* fade-gap
  (continuation points the wrong way), ORB is DAX-only (`xau_ldn_orb_m1`),
  `xau_asia_range` is a bull-run rider.
- **Naïve fading gets run over** — `xau_ldn_am_fade` REJECT: "LDN-AM is a
  directional-drift window; fades get run over by LBMA flow." *Unconditional*
  mean-reversion bleeds in the trending windows.
- **The only robust XAU edge is the low-frequency overnight drift**
  (`xau_session` live; `xau_session_v2_ffr_gated` Sh +1.11) — directional,
  ~39/yr, the opposite of high-cadence.

The gap: **every fade tried so far was pattern-conditional (break-retest, FVG)
or single-session (LDN-AM), and none gated on a trend/range regime.** The
recurring failure mode — "fades run over by trend/LBMA flow" — is *precisely*
what a regime gate is designed to avoid. The thesis is therefore not "fade XAU
intraday" (tombstoned) but: **fade intraday extension ONLY on range/low-trend
bars, sit out trending regimes.** That combination — XAU's tight spread (~0.35
bps, the repo's cheapest) + high cadence + an explicit trend gate — is the one
frequent-XAU shape not yet tested.

## Mechanism (falsifiable)

1. On a **range/low-trend** intraday regime, order-flow imbalances that stretch
   price away from a short-term anchor are absorbed by two-sided liquidity and
   **revert** to the anchor within minutes — a microstructure reversion, not a
   directional view.
2. On a **trending** regime (LBMA directional flow, macro impulse, bull-trend
   day), the same stretch is the *start* of a move, not an overshoot — fading it
   loses. This is the documented `xau_ldn_am_fade` failure.
3. Therefore the reversion edge should be **monotone in the trend gate**: strong
   in low-efficiency-ratio bars, zero/negative in high-ER bars. If it is *not*
   monotone (fades work equally in trends), the "edge" is something else and
   suspect.

## Signal math (frozen for the screen — characterization, not exits)

```
Rolling anchor over LOOKBACK=24 M5 bars (2h):
  mean_t  = rolling mean(close, 24)
  std_t   = rolling std(close, 24)
  z_t     = (close_t - mean_t) / std_t            # extension in sigmas
  ER_t    = |close_t - close_{t-24}| / sum_{k} |close_{t-k+1}-close_{t-k}|
            (Kaufman efficiency ratio, 24-bar; ~0 = ranging, ~1 = trending)
  atr_bps = rolling std of M5 returns(24) * 1e4   # vol regime

Extension EVENT at bar t: |z_t| >= THR and |z_{t-1}| < THR  (fresh crossing).
Fade entry at t+1 open, opposite the stretch sign.
Forward FADE return at horizon h bars:
  fade_ret_h = -sign(z_t) * (close_{t+h} - open_{t+1}) / open_{t+1}
Horizons reported: h ∈ {1, 3, 6, 12} bars (5/15/30/60 min). Primary h = 6.
Gap guard: skip the event if the t+1..t+h span crosses a >10-min bar gap.
Cost: bps RT applied once (entry+exit). Deploy 0.5; sweep 0.35/0.5/0.75/1.0.
```

Pure forward-return characterization avoids exit-parameter confounds. THR swept
{1.0, 1.5, 2.0, 2.5}. No free params are "tuned" — the surface is reported across
all of them and the pre-committed selection rule picks one.

## Features attached to every event

| Feature | Buckets |
|---|---|
| `session` (UTC) | ASIA 22–06, LDN 06–12, NYAM 12–16, NYPM 16–21 |
| `z_bucket` (|z| at event) | discovery quartiles |
| **`er_bucket`** (trend gate) | discovery quintiles ER1 (ranging) … ER5 (trending) |
| `vol_bucket` (ATR%) | discovery quintiles |
| `hour` | 0–23 (marginal only) |

## Discovery / holdout (pre-committed)

- **DISCOVERY = 2018–2023**; sub-windows D1 2018–2020 / D2 2021–2022 / D3 2023.
- **HOLDOUT = 2024–2026** — untouched until the single-cell validation.
- **Cross-instrument confirm** = SPX500 + NDX100 M5 (same bps cost ≈ 0.5/1.4
  bps): re-run the XAU-selected regime cell; report whether it ports.
- Bucket thresholds computed on XAU discovery, applied to holdout & (rescaled
  per-instrument z/ER, which are unit-free) cross-instrument.

## Pre-committed gates (DO NOT REVISE AFTER RUN)

A cell (over the `THR × er_bucket × session` grid, primary horizon h=6) is
**robust** iff, on DISCOVERY:

1. total `n ≥ 300` AND **cadence ≥ 150 events/yr** (the high-cadence requirement —
   a low-frequency reversion cell defeats the purpose);
2. per-sub-window `n ≥ 60` in all three;
3. `mean_net @ 0.50 bps > 0` in all three sub-windows;
4. pooled `t-stat @ 0.50 bps ≥ 3.0`;
5. **monotonicity check**: the reversion edge must be higher in low-ER than
   high-ER buckets (gate-consistency; logged, not auto-failing, but a non-monotone
   "edge" is flagged as suspect per mechanism point 3).

Single draw = robust cell maximizing the **minimum per-sub-window Sharpe @ 0.50**.

## Holdout + cross-instrument pass bars

- HOLDOUT 2024–2026: `Sharpe @ 0.50 > +0.30` AND `mean_net @ 0.50 > 0`.
- Cross-instrument: the same regime cell is **positive net** on ≥1 of SPX/NDX at
  its own cost (informative — ports = generic microstructure; XAU-only = metal-
  specific, still deployable but flagged).

## Fail condition

Zero robust cells → **NEGATIVE**: high-cadence XAU intraday MR has no
cost-survivable, cross-regime edge even under a trend gate. Combined with the
existing reject pile, that closes the frequent-XAU intraday question with a
mechanism-level reason (and is a valid deliverable).

## Expected outcomes (pre-run priors)

- **~50% NEGATIVE** — reversion edge in low-ER cells is real but < 0.5 bps, same
  sub-cost story as FVG; or the trend gate shrinks cadence below the bar.
- **~35% a low-ER cell survives** — fading high-z stretches on ranging bars
  clears cost at decent cadence; monotone in ER (clean mechanism). The most
  likely "win" shape.
- **~15% it ports cross-instrument** — generic intraday MR microstructure on
  tight-spread CFDs; strongest outcome, low corr to the overnight-drift book.

## Files

- `xau_intraday_mr.md` — this doc.
- `xau_intraday_mr_demo.py` — enumerator + reversion surface + gates + holdout +
  cross-instrument confirm.
- Data: `ohlc_data/{XAUUSD,SPX500,NDX100}_M5.csv`.

---

## Results (run 2026-05-30, 559,942 XAU M5 bars 2018-01 → 2026-05)

150,243 fresh extension events across THR {1.0,1.5,2.0,2.5}; discovery 105,328 /
holdout 44,915. Cadence is *not* the constraint — 17,555 events/yr pooled.

### Pooled reversion edge by horizon (DISCOVERY, net @ 0.50 bps)

| horizon | n | gross_bps | net_bps | t-stat | WR |
|---|---:|---:|---:|---:|---:|
| 1 (5m) | 105,328 | +0.126 | −0.374 | −13.9 | 48.9% |
| 3 (15m) | 105,328 | +0.149 | −0.351 | −9.6 | 50.0% |
| **6 (30m)** | 105,328 | **+0.232** | **−0.268** | −5.6 | 50.6% |
| 12 (60m) | 105,328 | +0.262 | −0.238 | −3.7 | 51.2% |

Reversion edge grows with horizon (microstructure overshoot decays slowly) but
caps at ~0.26 bps gross — **half the 0.5 bps cost**. WR ~50% = no directional
content beyond the tiny mean. Same magnitude as FVG continuation (+0.21 bps).

### Trend-gate surface — the refutation (ER × |z|, net mean_bps @ 0.50, h=6)

| | z1 | z2 | z3 | z4 |
|---|---:|---:|---:|---:|
| **ER1 (most ranging)** | −0.24 | −0.75 | −0.41 | −0.11 |
| ER2 | −0.14 | −0.33 | −0.20 | −0.11 |
| ER3 | −0.28 | −0.15 | −0.17 | **+0.11** |
| ER4 | −0.27 | −0.43 | −0.56 | −0.39 |
| ER5 (most trending) | −0.24 | −0.34 | −0.06 | −0.13 |

**Mechanism prediction (monotone: ranging > trending) is false.** ER1 is the
*worst* row, not the best; no ER gradient exists. The 24-bar efficiency ratio
does not isolate a "mean-reverting microstructure" regime on XAU M5. The one
positive cell (ER3·z4, +0.11) is isolated noise. **The gate that was the entire
novelty of this thesis adds nothing.**

### Marginals (net @ 0.50, h=6) — only NY-afternoon is positive

| feature | best bucket | gross | net | t-stat |
|---|---|---:|---:|---:|
| session | **NYPM (16–21 UTC)** | +0.634 | **+0.134** | +1.2 |
| vol | V5 (highest) | +0.513 | +0.013 | +0.1 |
| |z| | z4 (most extended) | +0.356 | −0.144 | −1.3 |
| THR | 2.5 | +0.277 | −0.223 | −1.2 |

Only NY-afternoon clears cost on net, and only at t≈1.2 (insignificant).

### Cell grid — 56 cells, 0 robust

- n≥300 & cadence≥150/yr: 55/56. All-3-windows-positive: **2**. **ROBUST: 0.**
- `thr2.5|NYPM` (n=1066, 178/yr): net +0.703, Sh +0.51, **t +1.24 < 3** → fail.
- `ER3|NYAM` (n=4415, 736/yr): net +0.500, Sh +0.60, min-window +0.02, t +1.48 → fail.

### Holdout (info — near-miss, not a draw)

`thr2.5|NYPM` on untouched 2024–2026: n=456, **net +1.886 bps @ 0.50, Sh +1.01,
t +1.76**. Strengthens OOS (like every NY corner in these screens) but 178/yr and
t<2 — not deployable, and defeats the "multiple times a day" goal anyway.

Cross-instrument SPX/NDX confirm not run (no robust XAU cell to port).

## Mechanistic interpretation

1. **Reversion is real but micro (~0.2 bps), same as continuation.** Two
   orthogonal intraday mechanisms — FVG continuation (#90) and z-extension
   reversion (here) — independently land on a +0.2 bps gross edge that loses to
   the 0.5 bps spread. This is strong evidence that **XAU M5 is efficient to
   ~0.2–0.3 bps**: whatever direction you slice it, the per-bar predictable
   component is below retail cost. The tight spread is real but the edge is
   smaller still.
2. **The trend gate doesn't exist (at this definition).** The headline novelty —
   fade only on ranging bars — is refuted by a flat, non-monotone ER surface.
   Pre-committed discipline: this is NOT an invitation to hunt for an alternative
   gate definition that happens to work in-sample (that's the curve-fit failure
   mode); the thesis predicted ER-monotonicity and it failed.
3. **The residual is NY-session, mechanism-agnostic, sub-cadence.** Both screens'
   only OOS-persistent corner is a NY-session cell at ~125–180/yr and t<2. The
   honest read: there is a faint NY-session XAU intraday edge (~0.7–1.9 bps on the
   most-extended events) that survives OOS but is far too infrequent and
   statistically thin to trade. It is the same residual from two angles, not two
   findings.

## M15 addendum (probe, 2026-05-30) — reversion inverts to momentum

Re-ran the identical engine on XAUUSD **M15** (gap-guard scaled to 25 min;
47,626 events) to test whether a coarser bar rescues the cost ratio. It does the
opposite: pooled fade-return is **+0.016 bps @ 15 min and goes NEGATIVE at longer
horizons (−0.362 @ 90 min, −0.265 @ 180 min)**, NYAM strongly negative (−1.5 bps
gross). At M15 resolution a 2σ extension is a genuine directional impulse, not a
microstructure overshoot — so **fading loses and the move tends to continue.**
The negative reversion = a positive *momentum/continuation* signal at M15+. This
(a) kills the "use M15 to beat the spread" idea — the edge sign flips, not just
the magnitude — and (b) points directly at the trend/momentum family as the
regime where XAU's predictable component actually lives. Reversion is an M5-only,
sub-cost, <30-min phenomenon; momentum takes over by M15.

## Verdict & recommendation

- **NEGATIVE** (0 robust cells; trend-gate mechanism refuted).
- **Closes the high-cadence XAU intraday question** raised this session: tight
  spread notwithstanding, neither continuation nor reversion produces a
  cost-clearing, cross-regime, high-cadence edge. The frequent-trading XAU
  ambition is not supported by the data at retail M5 cost.
- **Do not pursue an alternative trend-gate** on XAU (curve-fit risk). If the
  high-cadence idea is still wanted, the only honest next move is a *different
  instrument* (SPX/NDX intraday MR as its own screen, not as a port of a
  non-existent XAU cell) — but the priors from the XAU graveyard are not
  encouraging. Recommend shelving the frequent-XAU thread.
