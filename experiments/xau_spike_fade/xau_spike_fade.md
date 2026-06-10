# xau_spike_fade — XAUUSD M5 spike-resolution characterization

**Status:** Phase 0 screen — CLOSED 2026-06-03
**Verdict:** **REJECT** as a tradeable fade. The anecdote is real but it is a
**base-rate illusion**: spikes *do* retrace ~70% of the time within an hour, but
**normal candles retrace MORE (~87%)** — bigger moves resolve *less*, not more.
Net reversion is ~0 and the fade loses money at any realistic spread.
Confirms lesson #91 (XAU M5 is microstructure-efficient to ~0.2-0.3 bps) from a
third orthogonal angle (single-bar ATR-spike overshoot). Negative result is the
deliverable; not promoted.

## Results (2026-06-03 — `xau_spike_fade_screen.py`, 557,386 M5 bars 2018-06-08..2026-06-01)

**Headline — does a spike "come back down"? (X=2·ATR, within K=12 bars / 1h, retrace ≥50% of the spike)**

| dir | n | resolve% | normal-candle base rate | **EDGE** | net-reversion$ @1h | medCont (further-ext before retrace) |
|---|---|---|---|---|---|---|
| UP-spike   | 3,900 | 67.6% | 86.7% | **−19.2pp** | −0.34 (t −3.0, *continues up*) | 0.83× spike size |
| DOWN-spike | 4,288 | 71.2% | 87.7% | **−16.5pp** | +0.38 (t +2.5, weak revert) | 0.80× spike size |

- **The raw resolve % is high (matches the user's eye) but it is LOWER than for ordinary 0.5–1.0·ATR candles.** A large 5-min draw retracing half of itself is pure regression-to-mean of noise; the bigger the move, the *more* momentum it carries and the *less* it resolves (edge worsens monotonically: X=1.5 → −14/−12pp, X=3 → −28/−24pp, X=4 → −30/−29pp).
- **Asymmetry (mechanistic, but sub-cost):** up-spikes show net *continuation* (netRev −0.34, t −3.0 — gold is bid, "greed runs"); down-spikes show weak *reversion* (netRev +0.38, t +2.5 — dips get bought). Real but tiny on a $2,000–$4,000 instrument.
- **Continuation-first kills the fade even when it "eventually resolves":** the median spike extends another **~0.8× its own size further** before any retrace — you're stopped out first.

**Fade expectancy (X=2, short up-spikes / long down-spikes, TP=50% retrace, SL=extreme+0.5·ATR, 12-bar time-stop):**

| cost RT ($) | up-spike avg$ | up WR / PF | down-spike avg$ | down WR / PF |
|---|---|---|---|---|
| 0.00 (gross) | +0.004 | 38.9% / 1.01 | +0.025 | 41.8% / 1.03 |
| **0.30** (realistic XAU) | −0.296 | 38.3% / 0.68 | −0.275 | 41.4% / 0.75 |

Breakeven cost ≈ **$0.00–0.02** — i.e. zero edge before spread; dead on arrival. And spreads *widen* on exactly the fast bars we'd fade.

**Robustness:** no rescue. Regime (18-20 / 21-22 / 23-26): resolve% flat ~67–71%, netRev$ ≈ 0 every window. Session (UTC): Asia/EU netRev slightly + (t<1.5), US −; nothing significant. 3-bar burst variant: same shape (down-burst netRev +0.24 t+4.1 @1h, but < $0.30 cost).

### Mechanistic interpretation — why the anecdote feels true but isn't tradeable

1. **Base-rate illusion.** You notice spikes resolving and don't notice that *every* candle resolves at least as often. The salient ~70% is below the ~87% unconditional rate — conditioning on "spike" makes retrace *less* likely, not more.
2. **Survivorship in memory.** The spikes that ran away (continuation) don't get remembered as "spikes that should have come back"; the ones that retraced confirm the prior.
3. **Continuation-first.** Even the spikes that do resolve typically extend ~0.8× further first → a naïve fade is stopped before the retrace.
4. **Efficiency.** Net per-bar predictable component is ~0.2–0.3 bps < spread — the same wall hit by `xau_intraday_mr` (z-extension MR) and `xau_imbalance_screen` (FVG continuation). Three opposite-signed mechanisms all bottom out at sub-spread ⇒ XAU M5 is efficient at this scale (lesson #91, now #97).

## Question (user-posed)

XAUUSD M5 shows frequent violent candles ("spikes"). Anecdotally most of them
"resolve and come back down" — an imbalance/overshoot that retraces. **Of M5
bars that move ≥ X·ATR(14) in one bar, what % actually retrace?** And — the part
that decides tradability — is that retrace rate *above the base rate you'd get by
chance*, and does a mechanical fade have positive expectancy net of the XAU spread?

## Thesis (mechanism)

1. **Liquidity-vacuum overshoot.** A fast M5 displacement on gold often runs a
   thin book / stop cascade past fair value, leaving a temporary imbalance that
   passive liquidity refills → partial retrace.
2. **News-impulse double-count.** Macro/USD headline ticks spike XAU, then the
   first impulse is faded as the move is re-priced more slowly.
3. **Wick-noise regression.** A large bar is, mechanically, a large draw from the
   5-min return distribution; ANY large draw partially retraces by mean-reversion
   of noise alone. **This is the null we must beat** — the headline "% resolve"
   number is dominated by this and is not, by itself, evidence of an edge.

## Key reference

Lehmann (1990) "Fads, martingales, and market efficiency"; Avellaneda &
Lee (2010) stat-arb reversion; intraday "overshoot-and-fade" microstructure
(Bouchaud et al., square-root impact + relaxation).

## Signal math (screen)

```
ATR = Wilder ATR(14) on M5
move_t      = close[t] - close[t-1]              # 1-bar displacement
spike       = |move_t| >= X * ATR[t-1]  AND  bar t contiguous with t-1 (dt==5m)
dir         = sign(move_t)                        # +1 up-spike, -1 down-spike
size        = |move_t|
# resolution within K contiguous forward bars:
rev_excursion  = (close[t] - min(low[t+1..t+K]))  for up   (back-down distance)
              or (max(high[t+1..t+K]) - close[t])  for down
resolved_F  = rev_excursion >= F * size           # F in {0.5, 1.0}
cont_excursion = max(high[t+1..t+K]) - close[t]    for up (further-extension)
fwd_ret_against = -dir * (close[t+K] - close[t])   # >0 == net reverted
```

Swept: X ∈ {1.5, 2, 3, 4}; K ∈ {3,6,12,24,48} bars (15m→4h); F ∈ {0.5, 1.0}.
Secondary trigger: 3-bar cumulative displacement burst (same machinery).

## Why retail-accessible

XAUUSD is the user's live instrument (Eightcap). Pure M5 OHLC, no L2 needed.
Cost is the only gate — see expectancy sweep.

## Universe

XAUUSD M5, 2018-06-08 → 2026-06-01 (true intraday start; daily-mislabelled bars
before that excluded). All 23h trading; weekends dropped; cross-gap windows censored.

## What would make this worth pursuing (pre-committed)

This is a screen, not a pass/reject strategy backtest. Promote to a full
`xau_spike_fade` Phase-2 strategy ONLY if ALL of:

- **Edge over base rate** ≥ +8pp: P(resolve | spike) − P(resolve | normal candle)
  at the headline (X=2, K=12, F=0.5). If spikes retrace no more than normal
  candles, the anecdote is pure regression-to-mean → STOP.
- **Net signed reversion** statistically real: mean fwd_ret_against > 0 with
  |t| > 3 at X≥2.
- **Fade expectancy positive net of cost**: mechanical fade (enter at close[t]
  against spike, 50% target, stop beyond spike extreme, K-bar time stop) shows
  positive expectancy at **0.30 spread RT** and breakeven cost ≥ 0.40.
- **Not one-sided / not one-regime**: holds for both up- and down-spikes and in
  the 2023-2026 window, not just COVID-era 2020.

## Why this might fail (red flags)

- The 50%-retrace headline will be high (~70-85%) by noise alone → looks great,
  means nothing without the base-rate diff and the net-return / expectancy legs.
- Continuation-first: spike extends another +1 ATR before retracing → stops you
  out even though it "eventually resolves". The cont_excursion column tests this.
- Gold spike clusters are news (NFP/CPI/FOMC) — fading the first impulse is
  exactly when tail risk is worst; survivorship in the median hides the tail.
- Spread on a fast bar widens 3-5× — the 0.30 RT assumption is optimistic during
  the very spikes we want to fade.

## Files

- `xau_spike_fade_screen.py` — characterization + base-rate null + fade expectancy
- `xau_spike_fade.md` — this doc
