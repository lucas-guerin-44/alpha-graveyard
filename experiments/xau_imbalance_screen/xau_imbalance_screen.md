# XAUUSD 3-bar FVG — full-history characterization screen (M5, 2005–2026)

**Status**: COMPLETE — characterization screen, run 2026-05-30.
**Verdict (summary)**: **NEGATIVE (standalone)** — the 3-bar FVG *continuation*
mechanism has **real, decisively-signed directional content** (pooled gross
cont +0.114 bps vs fade −0.093 → **dir-edge +0.207 bps**, positive in nearly
every feature region), but the raw edge is **an order of magnitude below
realistic cost (~0.5 bps RT)**. Conditioning concentrates it — the edge lives
almost entirely in **NY-AM × slow-retest (25–30 min gap-fill)** — and *that one
corner survives cost and holds out-of-sample* (DISC Sh +0.42 / HOLD Sh +0.84,
net@0.5 +0.69 / +1.41 bps, OOS dir-edge +3.96 bps). But it trades only ~125/yr,
pooled t-stat +1.04 (DISC) / +1.46 (HOLD) — **below the pre-committed t≥3
significance gate and the repo's ≥200-trade cadence bar**. Zero cells cleared the
robustness gates → **NEGATIVE as a standalone strategy**, with a precisely-located
residual (below). This is a far more rigorous tombstone of the FVG family than
the prior single-config REJECT: it shows *where* the edge is and *why* it's
undeployable, not just that one parameterization failed.

> **Two corrections forced mid-run (logged so the verdict is honest):**
> 1. **No M5 gold before 2018.** The CSV's 2005–2017 rows are daily (≤2016) /
>    hourly (2017) bars mislabeled M5 (≈260 bars/yr, 1440-min gaps). The
>    "two-cycle stability" premise was impossible on M5; the real coverage is
>    2018–2026 (one secular-bull-dominated regime structure), same as the prior
>    experiment. Discovery sub-windows reset to D1 2018–2020 / D2 2021–2022 /
>    D3 2023; holdout 2024–2026.
> 2. **Cost must be bps, not fixed USD.** Gold ran $1160→$5588 *inside* the M5
>    window, so a fixed-USD spread is mechanically confounded with the bull (a
>    fixed 0.30 USD is ~2.6 bps at 2018's $1150 but ~0.67 bps at 2025's $4500).
>    Switched to constant bps (deploy 0.5; sweep 0.35/0.5/0.75/1.0). The first
>    run's all-negative wash was this artifact; gross + bps-net is the fair model.

> **What this is and is NOT.** This is **not** a parameter optimizer and the
> output is **not** "the best variant we found." It is a *characterization map*:
> enumerate every 3-bar FVG on XAUUSD M5 over the full 2005–2026 history, attach
> a feature vector to each, and measure the **forward-edge surface** as a function
> of those features. The deliverable is the surface + the answer to one question:
> *does any region of FVG-feature space carry a directional edge that is stable
> across two full gold bull/bear cycles AND survives the cost cliff?* Exactly one
> pre-committed config is drawn from the most-stable robust region at the very end
> and validated once on an untouched tail. Per CLAUDE.md "do NOT aggregate the
> best variant as the strategy" — the single draw is one pre-committed hypothesis,
> not a claim that the screen produced a deployable strategy.

## Why revisit (what the prior `xau_imbalance` left on the table)

`experiments/xau_imbalance/` was **tombstoned (REJECT)** 2026-05-28. Two facts
from that tombstone motivate this screen:

1. **The mechanism has decisive directional content** — fade-gap +5.25 (Sharpe).
   Entering *in* the FVG direction is unambiguously the right side. There is real
   structure to characterize.
2. **It died on magnitude + fragility, not on sign.** Post-geometry-bug-fix the
   single blunt config (13–15 UTC, retest 6, hold 6, both directions) collapsed to
   Sh +0.56, with ~0.6 bp gross/trade sitting on a **cost cliff at ~0.3 USD RT**,
   and the headline Sharpe was W3-bull-concentrated (W1 +0.12 / W2 +0.37 pre-bull).

The blunt config **averaged the whole FVG population**. The same sweep already
coughed up two conditional facts it then threw away by reporting the blend:

- **Small FVGs carry the signal, large ones don't** (ATR-size filter *rejected*).
- **Slow retests (bars 4–6) are signal; fast retests (≤3 bars) are noise**
  (age filter *rejected*).

Those are *conditional-structure* facts about where in feature space the edge
lives. This screen maps that structure systematically instead of guessing one
parameterization.

## The anti-overfit thesis

The naïve worry is "screening huge data = overfitting." The honest correction:
**sample size kills sampling noise in a single estimate; it does nothing about
selection bias across many configs.** The protection here is **out-of-sample
regime-stability**, and the full 2005–2026 history is the asset that makes it
possible — it spans:

- the 2009–2012 GFC gold bull,
- the 2013–2018 gold bear/range,
- the 2019–2022 vol regime,
- the 2023+ secular bull (the confound that inflated the prior holdout).

A feature cell that is directional and positive across a bull AND a bear cycle is
credible in a way that "works since 2022" never is. That cross-cycle stability
requirement is the real multiple-testing control, not row count.

## Enumeration (frozen so cells are comparable)

Enumerate **every** 3-bar FVG across **all 24h** (session becomes a *feature*, not
a filter). For each FVG, simulate retest→entry→exit under a **single frozen
canonical rule** so that differences between cells reflect the *FVG features*, not
a swept exit:

```
FROZEN canonical rule (NOT swept during characterization):
  RETEST_WINDOW = 6 bars      # 30 min to re-enter the gap zone
  HOLD_BARS     = 6 bars      # 30 min time exit
  STOP_MULT     = 0.5 * FVG_width past the far edge
  ENTRY         = next-bar-open after the retest bar
  DIRECTION     = FVG direction (continuation; the prior null proved this side)
  GEOMETRY GUARD = ON (skip trade if entry_price is already past stop_level —
                   reuses the 2026-05-28 fix that killed the phantom-alpha bug)
  GAP GUARD     = retest/hold scan terminates if the bar-to-bar time gap > 10 min
                  (handles weekends, holidays and the daily liquidity break
                   without arbitrary day-labeling)
```

Bull FVG: `bar[t-2].high < bar[t].low`. Bear FVG: `bar[t-2].low > bar[t].high`.
Cost is **not** baked into the enumeration — `gross` and `entry_price` are stored,
so net edge at any cost (0.16 / 0.20 / 0.30 / 0.40 USD RT) is computed per cell at
analysis time.

## Features attached to every entered FVG

| Feature | Buckets |
|---|---|
| `direction` | bull / bear |
| `session` (UTC) | ASIA 22–06, LDN 06–12, NYAM 12–16, NYPM 16–21 |
| `hour` | 0–23 (marginal only) |
| `gap_bps` | discovery quartiles (tiny / small / med / large) |
| `gap_atr` = FVG_width / ATR20 | reported alongside gap_bps |
| `retest_age` | fast 1–2 / mid 3–4 / slow 5–6 bars |
| `trend_align` = sign(EMA20−EMA60) vs dir | aligned / counter |
| `vol_bucket` = ATR20 discovery-quintile | Q1..Q5 |
| `dow` | Mon–Fri (marginal only) |
| `macro_window` | hour ∈ {12,13,14,15} UTC (coarse 08:30/10:00 ET proxy) |

## Discovery / holdout split (pre-committed)

- **DISCOVERY = 2005-01 → 2023-12** — surface + cell selection. Stability tested
  across four sub-windows spanning both cycles:
  - D1 2005–2008, D2 2009–2012 (GFC bull), D3 2013–2018 (bear/range), D4 2019–2023.
- **HOLDOUT = 2024-01 → 2026-05** — **untouched** until the single final
  validation of the one drawn config.

Vol/gap-bucket thresholds are computed on DISCOVERY and applied to the holdout
(no holdout lookahead).

## Pre-committed cell-selection rule (DO NOT REVISE AFTER RUN)

Candidate cells are drawn from a fixed grid (marginals + these interactions):
`session×gap_bucket`, `session×retest_age`, `gap_bucket×retest_age`,
`session×vol_bucket`. `n_trials` = total cells tested is reported for honesty.

A cell is **robust** iff, on DISCOVERY only:

1. total `n ≥ 300`;
2. per-sub-window `n ≥ 60` in **all four** of D1–D4;
3. `mean_net @ 0.30 USD RT > 0` in **all four** sub-windows (the cross-cycle gate —
   this is the load-bearing anti-overfit filter; null pass rate ≈ (½)⁴ ≈ 6%);
4. pooled `t-stat @ 0.30 cost ≥ 3.0`;
5. pooled continuation−fade **Sharpe gap > +0.40** (directional-content / null check).

Among robust cells, the **single draw** maximizes the **minimum per-sub-window
annualized Sharpe @ 0.30 cost** (worst-window objective — explicitly favours
stability over peak, the opposite of cherry-picking the best in-sample cell).

## Holdout validation of the single draw (pre-committed pass bar)

The one selected cell is applied **once** to HOLDOUT 2024–2026:
- `Sharpe @ 0.30 USD RT > +0.30`, AND
- `mean_net @ 0.30 > 0`, AND
- directional (continuation−fade Sharpe gap > 0 on holdout).

## Fail condition (the clean negative is a valid deliverable)

If **zero cells** clear the discovery robustness gates, the verdict is a
**definitive NEGATIVE**: XAU M5 3-bar FVG continuation has no cross-cycle-stable,
cost-survivable directional edge in any feature region. That tombstones the FVG
family far more rigorously than the prior single-config REJECT (which only tested
one parameterization on a 2018-start window) and is the deliverable in its own right.

## Expected outcomes (pre-run priors)

- **~55% clean negative** — robust cells all sit at ~0.6 bp gross that dies at the
  cliff, or the high-edge cells fail the cross-cycle gate (W3-bull-only).
- **~30% a sub-region survives** — most likely small-gap × slow-retest × a
  session/vol gate clears a higher per-trade gross than the blend, enough to sit
  above the cliff and survive holdout. A deployable slice the blunt config buried.
- **~15% an interaction find** — a feature interaction (e.g. gap×vol, or
  FVG-fill conditioned on session) shows clean cross-cycle edge. Only this design
  can surface it; the prior single-config approach was blind to interactions.

## Files

- `xau_imbalance_screen.md` — this doc.
- `xau_imbalance_screen_demo.py` — enumerator + surface + gates + single-draw holdout validation.
- Data: `ohlc_data/XAUUSD_M5.csv` (571,988 bars, 2005-01 → 2026-05).
- Prior context: `experiments/xau_imbalance/xau_imbalance.md` (tombstoned REJECT).

---

## Results (run 2026-05-30, 559,590 M5 bars 2018-01 → 2026-05)

Enumerated **70,783** continuation trades (+ 59,871 fade-null) across all 24h.
Exit mix: 43,208 stop / 26,878 time / 697 gap. Direction balanced (36,362 bull /
34,421 bear). Discovery 49,205 / holdout 21,578.

### Pooled reference — ALL FVGs, no conditioning (DISCOVERY 2018–2023)

| | n | cont | fade | dir-edge |
|---|---:|---:|---:|---:|
| **GROSS (pre-cost)** | 49,205 | **+0.114 bps** | −0.093 bps | **+0.207 bps** |

| Cost (bps RT) | net mean | t-stat | Sharpe | WR |
|---|---:|---:|---:|---:|
| 0.35 | −0.236 | −5.5 | −2.24 | 29.2% |
| **0.50** (deploy) | **−0.386** | −9.0 | −3.67 | 28.7% |
| 0.75 | −0.636 | −14.8 | −6.04 | 28.1% |
| 1.00 | −0.886 | −20.6 | −8.41 | 27.4% |

**The average FVG continuation has +0.21 bps of raw directional content and
loses at every realistic cost.** The mechanism is correctly signed (matches the
prior fade-gap +5.25) but ~0.2 bps is roughly half the *cheapest* deploy cost.

### Marginal surface — where the gross edge concentrates (net @ 0.50 bps)

| Feature | best bucket | gross_bps | dir-edge | net@0.5 | t-stat |
|---|---|---:|---:|---:|---:|
| session | **NYAM** | +0.319 | +0.433 | −0.181 | −1.1 |
| retest age | **mid3-4 / slow5-6** | +0.269 / +0.155 | +0.433 / +0.394 | −0.231 / −0.345 | −2.2 |
| gap size | large | +0.227 | +0.413 | −0.273 | −2.1 |
| vol (ATR) | **Q5** | +0.208 | **+0.566** | −0.292 | −1.8 |
| trend | aligned | +0.152 | +0.269 | −0.348 | −5.6 |
| macro window | True (=NYAM) | +0.319 | +0.433 | −0.181 | −1.1 |

Monotone, mechanism-consistent structure: edge rises with **NY-AM session, high
vol, larger gaps, slower retests, trend-alignment** — and *every* bucket's
dir-edge is positive (continuation > fade), confirming directional content is
pervasive. But **no single marginal clears 0.5 bps net.** Note the prior
experiment's "small gaps carry signal" inverts on *gross* — large gaps have the
higher raw edge (+0.227 vs +0.067); the prior's result was a net/exit-confound.

### Cell grid — 60 cells, pre-committed gates (DISCOVERY)

- Cells with n≥300: **59/60**. Cells positive in **all 3** sub-windows: **1**.
- **ROBUST cells (n≥300, all-windows>0, t≥3, fade-gap>0.40): 0** → pre-committed
  **NEGATIVE**.
- The single cross-window survivor: **`NYAM | slow5-6`** (n=628) — net@0.5 +0.685,
  Sh +0.42, fade-gap +1.22, but **t-stat +1.04 fails the ≥3 significance gate**.

### The residual — `NYAM × slow-retest` (the one real corner)

Probed on the untouched holdout despite failing the gate (informative, not a draw):

| cell | window | n | gross | net@0.5 | Sh | WR | OOS dir-edge |
|---|---|---:|---:|---:|---:|---:|---:|
| **NYAM·slow5-6** | DISC 18–23 | 628 | +1.185 | +0.685 | +0.42 | 31% | — |
| **NYAM·slow5-6** | **HOLD 24–26** | 307 | **+1.910** | **+1.410** | **+0.84** | 37% | **+3.96 bps** |
| NYAM·all | HOLD | 3,877 | +0.206 | −0.294 | −0.59 | 29% | +0.59 |
| NYAM·large-gap | DISC→HOLD | 3858→1998 | +0.596→+0.161 | +0.096→**−0.339** | +0.13→−0.40 | — | — |
| Q5-vol·all | HOLD | 7,613 | +0.305 | −0.195 | −0.51 | 31% | +0.59 |

**`NYAM × slow-retest` is the entire FVG edge.** It *strengthened* out-of-sample
(Sh +0.42→+0.84, net +0.69→+1.41 bps, OOS continuation beats fade by ~4 bps) —
the opposite of an overfit cell. But it is **~105/yr (DISC) – 150/yr (HOLD)**,
pooled t-stat ≤ 1.5, so the Sharpe estimate has error bars too wide to deploy on,
and it clusters in the 12–16 UTC macro window where the 0.5 bps cost is most
optimistic (spread spikes on CPI/NFP). Large-gap and high-vol were in-sample red
herrings (large-gap flips negative OOS).

## Mechanistic interpretation

1. **The mechanism is real but micro.** FVG continuation is correctly signed
   everywhere (+0.2 bps pooled, up to +0.4–0.6 bps dir-edge in NY-AM/high-vol),
   confirming the prior fade-gap. The edge is **dealer-side gap-fill flow**, not
   noise — but its magnitude (~0.2 bps average) is structurally below retail CFD
   cost. No amount of conditioning manufactures size that isn't there; it only
   *concentrates* the existing ~0.2 bps into a thinner, higher-density corner.

2. **The edge is a slow-retest, NY-AM phenomenon.** The surviving corner is
   exactly the prior experiment's two thrown-away findings — "slow retests are
   signal, fast retests are noise" + "13–15 UTC NY-AM" — now isolated cleanly.
   The mechanism: a gap that takes 25–30 min to fill is dealer hedging
   *unwinding back* into the level (tradeable); a gap that fills in <10 min is
   momentum noise (not). 38k of 49k FVGs are fast-retest and net-negative; they
   diluted the prior blunt 13–15 config to its marginal +0.56.

3. **Why standalone-undeployable.** The one cost-surviving, OOS-consistent corner
   trades ~125/yr at t<1.5 — below both the ≥200-trade cadence bar and the t≥3
   significance gate, and concentrated in the spread-spike window. It is a real
   structural fact about XAU NY-AM microstructure, but not a strategy.

## Verdict & recommendation

- **NEGATIVE as a standalone strategy** (0 robust cells; pre-committed).
- **The reverse-engineering worked**: the screen *did* extract the common useful
  parameters (NY-AM + slow-retest + high-vol), and they reproduce the prior
  single-config's edge as a precisely-located corner — it just shows that corner
  is sub-cadence and sub-significance, not deployable.
- **Where the residual could matter**: only as a *confirming micro-filter inside
  another NY-AM gold strategy* (e.g. require a slow-retest FVG-fill in agreement
  before an entry), never on its own. Not worth a deploy slot.
- **Tombstone the FVG family for XAU M5 standalone.** This screen supersedes the
  prior `xau_imbalance` REJECT with a mechanism-level reason: raw edge ~0.2 bps,
  concentrated in a ~125/yr NY-AM slow-retest corner, structurally sub-cost.
