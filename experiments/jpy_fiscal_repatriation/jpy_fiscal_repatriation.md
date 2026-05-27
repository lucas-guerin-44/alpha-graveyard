# JPY March fiscal-year-end repatriation (USDJPY seasonal)

**Status (2026-05-26)**: Phase 0 ABORT → **REJECT**. Phase 2 not built.

**Verdict**: **REJECT (decisive, Phase 0 magnitude gate AND direction-inverted).**
SHORT USDJPY Feb 15 → Mar 28 over 8 fiscal years (2019-2026, USDJPY D1
Yahoo): gross mean **-150.2 bps/yr**, net mean **-191.7 bps/yr** (post 0.7
bps spread + ~40 bps swap drag), hit rate **4/8 = 50%** (below 5/8 floor),
W3 (2023+) gross mean **-73 bps** (below 0 floor). **The thesis direction
is sign-inverted in modern data**: LONG USDJPY in the same window has
gross mean **+150 bps**, net **+190 bps** (positive carry tailwind) —
but driven by 3 outlier years (2021/2022/2026), 50% hit rate, NOT a
deployable inversion.

Phase 0 gate fired cleanly on all 4 criteria. Pre-flagged red flag #5
("front-running compresses the timing") was empirically correct, AND
stronger than predicted: front-running has *inverted* the Feb 15 → Mar
28 window, not just compressed it. The Goh et al. 2013 academic prior
(+1.2% March JPY mean on 1986-2010 sample) does not survive on 2019-
2026 modern-regime data.

## Phase 0 results (USDJPY D1 Yahoo, FY 2019-2026, _phase0_magnitude_check.py)

Per-year:

| FY | entry | exit | entry_px | exit_px | gross_bps | net_bps |
|---:|---|---|---:|---:|---:|---:|
| 2019 | 02-15 | 03-28 | 110.54 | 110.49 | **+4** | -37 |
| 2020 | 02-17 | 03-27 | 109.79 | 109.11 | **+62** | +21 |
| 2021 | 02-15 | 03-26 | 105.06 | 109.18 | **-392** | -433 |
| 2022 | 02-15 | 03-28 | 115.54 | 122.27 | **-583** | -624 |
| 2023 | 02-15 | 03-28 | 132.99 | 131.23 | **+132** | +91 |
| 2024 | 02-15 | 03-28 | 150.54 | 151.29 | **-49** | -92 |
| 2025 | 02-17 | 03-28 | 152.02 | 150.85 | **+77** | +36 |
| 2026 | 02-16 | 03-27 | 152.78 | 159.70 | **-453** | -495 |

**Phase 0 gates** (all binding, all FAIL):

| Gate | Result | Pre-commit | Pass? |
|---|---:|---|---|
| Gross mean | **-150 bps** | ≥ +80 bps | FAIL |
| Net mean | **-192 bps** | ≥ +20 bps | FAIL |
| Hit rate | **4/8 (50%)** | ≥ 5/7 (71%) | FAIL |
| W3 (2023+) gross | **-73 bps** | > 0 | FAIL |

Direction null check: **mechanism is sign-inverted**. LONG USDJPY same window
has gross mean +150 / net +190 bps — but driven by outliers (2021 +392,
2022 +583, 2026 +453), 50% hit rate, NOT deployable as a recovered-inverse
strategy.

## Mechanistic interpretation

1. **Front-running has fully inverted the seasonal, not just compressed
   it.** Red flag #5 was the right prior but underestimated the magnitude.
   Modern macro-fund front-running of the FY-end mechanical flow appears
   to happen *before* Feb 15 (presumably January), so the Feb 15 → Mar 28
   window now captures the *unwind* of the front-running (LONG USDJPY
   direction) rather than the underlying corporate-AR conversion flow.
   The mechanical flow is real but its price signature has been moved
   forward into a window the thesis doesn't cover.

2. **Three large outlier years (2021, 2022, 2026) drive the negative
   mean and the LONG-direction outliers.** In each of these years
   USDJPY had a substantial multi-month rally that swamped the seasonal
   window. 2021 (+392 LONG) was the post-COVID Fed-vs-BoJ divergence
   onset; 2022 (+583 LONG) was the aggressive Fed-hike-vs-BoJ-YCC
   divergence (USDJPY 115 → 122 in 6 weeks); 2026 (+453 LONG) was a
   similar acceleration in Q1. These are NOT one-off events — they
   reflect the post-2013 BoJ regime that the Goh et al. (1986-2010)
   academic prior pre-dates.

3. **BoJ regime change post-Abenomics overwhelms the seasonal.**
   Over the 2019-2026 sample, USDJPY rallied from ~110 to ~152 — a
   ~5.5%/yr nominal drift. A random 6-week window over the period
   expects ~+60 bps from drift alone. The SHORT-USDJPY thesis was
   effectively fighting that structural drift, which removed any
   seasonal alpha it might have had. **Academic seasonality with
   pre-Abenomics support is regime-fragile on USDJPY in the post-2013
   structural-divergence era.**

4. **The direction-asymmetric swap cost amplifies the failure.** SHORT
   USDJPY over 30 business days pays ~42 bps swap drag (negative carry).
   LONG USDJPY earns ~42 bps swap tailwind. The 84 bps swing in cost
   economics matters when the expected gross is 80-150 bps. The thesis
   was bet on the wrong side of carry AND the wrong side of regime
   drift simultaneously.

5. **Not Phase 2 cycles saved — methodology lesson confirmed.** The
   Phase 0 magnitude gate (per revised Lesson A) fired exactly as
   designed. Building the full Phase 2 simulator on this would have
   produced the same REJECT with more decimals. Phase 0 gate is doing
   real work in saving research bandwidth.

## Lessons for the project

- **Academic-seasonality priors are regime-fragile on FX.** Goh et al.
  (2013) +1.2% March JPY mean on 1986-2010 data is **fully inverted**
  on 2019-2026. Joins lesson #1 (FX 2015-2026 is a graveyard for
  non-momentum factors) with a sharper variant: even *mechanical-flow*
  seasonals from regulator-mandated calendar anchors can invert under
  regime change. The mechanism may still operate; its price signature
  has migrated.
- **Front-running can invert, not just compress, calendar-anchored
  mechanical-flow signatures.** Pre-2013 academic priors assumed
  front-running compressed timing within the window. Modern data shows
  front-running can move the price signature *outside* the window
  entirely, leaving the residual window dominated by unwind-flow in
  the opposite direction.
- **Multi-week-hold direction-asymmetric swap is a binding cost item
  on FX.** SHORT vs LONG USDJPY over 6 weeks has an 84 bps cost
  difference from swap alone. Any FX thesis with hold > 5 days must
  pre-commit direction-aware swap modeling per `pre_fomc_drift` lesson
  AND `pead_midcap` lesson #59 (the CFD-swap-ceiling family extended
  to multi-week FX).

## Files

- `jpy_fiscal_repatriation.md` — this doc
- `_phase0_magnitude_check.py` — Phase 0 binding diagnostic (kept for
  reproducibility)
- Data: `ohlc_data/USDJPY_D1.csv` (Yahoo, fetched 2026-05-26, 2185 bars
  2018-01-01 → 2026-05-25)

---

## Pre-run scaffold (kept below for context — superseded by Phase 0 result above)

**Project context**: this is the project's first **multi-week seasonal**
strategy and the second Asian-leaning addition after `usdjpy_tokyo_fix`.
Different shape than anything else in the book — fits in the
"different timeframe, different mechanism family" diversification slot.

## Why this — institutional mechanical flow at a regulator-mandated anchor

The Japanese fiscal year ends **March 31**. Japanese corporates (especially
exporters) and life insurers must report year-end balance sheets in JPY
terms. The accounting cycle forces **mechanical USD-to-JPY conversion of
foreign-earnings receivables** in the 4-6 weeks leading up to March 31.
This is the largest single seasonal flow in USDJPY and is **not arbitrary
positioning — it is regulator-mandated accounting flow**.

The flow is:
- **Corporates**: Toyota, Sony, Honda, etc. earn USD from foreign sales.
  At fiscal year-end they convert booked-USD-AR into JPY for the annual
  consolidated report. Aggregate flow: ~$30-50B of USD-selling spread
  across Feb-Mar.
- **Life insurers**: rebalance JGB-vs-foreign-bond portfolios. If foreign
  bonds outperformed during the fiscal year (typical when USDJPY rallies),
  they lighten foreign-bond books at FY-end to bank gains in JPY terms.
  Aggregate flow: ~$20-30B JPY-buying.
- **Pension funds (GPIF, KKR)**: quarterly rebalance includes a March
  bias toward JPY assets for FY reporting.

Total estimated mechanical USD→JPY flow: **~$50-80B over the Feb-Mar
window**, concentrated in the final 3 weeks. That's a sizable share of
USDJPY's ~$1.2T daily volume aggregated over the window.

This thesis is the cleanest "specific named institutional flow at a
mechanical anchor" candidate proposed this session — the flow source is
named, the timing is regulator-mandated, and the direction is unambiguous.

## Why this isn't already arbed to zero

Two reasons institutional capital doesn't fully arb the flow:

1. **The flow IS institutional**. Macro hedge funds front-run it in
   February, but the *mechanical underlying flow* (corporate AR
   conversion + life-insurer rebalancing) is real-money, not arb-
   deflectable. Front-runners can compress the timing of the move (i.e.,
   the JPY rally may happen mid-February rather than late-March in
   front-run years), but they cannot eliminate it because the
   regulator-mandated flow will transact regardless of price.

2. **2022-2024 BoJ intervention era distorts the price signal but
   reinforces the directional bias**. BoJ intervention episodes are
   *also* SHORT-USDJPY direction (BoJ sells dollars to defend JPY).
   When intervention coincides with the seasonal window, the directional
   alignment is doubled. When intervention happens outside the seasonal
   window, it doesn't compete with the thesis.

## Differentiator from existing FX experiments

| Strategy | Mechanism | Timeframe | Vessel | Verdict |
|---|---|---|---|---|
| `fx_session` (rejected) | Intraday USD-bid at 23 UTC | Intraday | EUR/USD, USD/JPY, AUD/USD | INSTITUTIONAL-ONLY |
| `fx_carry` (rejected) | XS carry on G10 | Daily | Multi-pair | 2015-2026 graveyard |
| `pre_fomc_drift` (rejected) | FX-side of US-macro flow | 24h pre-event | EUR/USD | REJECT (W4 dead) |
| `pre_ecb_drift_eurusd` (rejected) | FX-side of EU-policy event | 24h pre-event | EUR/USD | REJECT (kill criteria) |
| `cfd_wed_rollover_eurusd` (rejected) | Retail-CFD weekly rollover | Same-day | EUR/USD | REJECT (no magnitude) |
| `usdjpy_tokyo_fix` (Phase 1 sibling) | Tokyo fix flow | 20-min window | USD/JPY | TBD |
| **`jpy_fiscal_repatriation` (this)** | **Mechanical FY-end AR conversion** | **4-6 week seasonal** | **USD/JPY** | **TBD** |

No prior FX thesis in the repo targets multi-week mechanical flow on a
regulator-mandated calendar anchor. This is structurally novel.

## Thesis (mechanism)

1. **Japanese fiscal year ends March 31, mandated by Japanese corporate
   law and tax code.** All publicly-listed Japanese corporates,
   insurance companies, and pension funds report consolidated results
   on this calendar. ~95% of TSE-listed Japanese companies use March
   31 fiscal year-end (vs ~5% on other dates).

2. **Foreign-earnings translation forces USD→JPY conversion of accumulated
   USD-denominated assets and AR** in the run-up to FY-end. For a Toyota
   with $20B annual USD revenue, even a modest 10-20% conversion before
   year-end = $2-4B JPY-buying.

3. **Life insurer FY-end rebalancing favors JPY-side assets** when
   foreign-bond books have appreciated during the year. 2024-2025 saw
   significant foreign-bond gains for Japanese life insurers (rising
   Western yields = capital losses, but BoJ-relative yield differential
   was a net positive for hedged holdings). FY-end rebalancing in 2025
   showed material JPY-buying flow.

4. **The seasonal concentrates Feb 15 - Mar 31** (last 6 weeks of fiscal
   year). Empirical academic studies on JPY seasonality (Goh, Jiang,
   Tu 2013; Asness, Moskowitz, Pedersen 2013 currency seasonality
   chapter) document a **late-February JPY strength signature** that
   has held in 18 of the last 25 years (72% hit rate).

5. **The trade**: SHORT USDJPY (= LONG JPY) from a single entry around
   Feb 15 to a single exit around Mar 28 (3 trading days before FY-end
   to avoid year-end-day volatility). One trade per year, 4-6 week hold.

6. **Why retail-tradeable**: simple calendar-anchored entry/exit, no
   intraday timing skill required, low monitoring (one position per year),
   trivial EA implementation.

## Capacity moat

Multi-week swing position on USDJPY is large enough that institutional
macro funds DO trade it. But they trade it in size that **cannot fully
absorb the underlying mechanical flow**. The capacity argument is:

- Total mechanical flow: ~$50-80B / 6 weeks = $1-2B/day average
  USD-selling.
- Macro-fund total USDJPY trading capacity (across all macro funds): ~$5-10B
  net positioning capacity in any direction at any time.
- The macro-fund position is *part of the price formation*, not a
  *counter-flow*. They go SHORT USDJPY alongside the corporates,
  reinforcing the move.

The price level moves to where the mechanical flow meets resistance —
that "resistance" includes BoJ-side speculators going LONG-USDJPY on
carry, but the **net direction is SHORT-USDJPY-favoring** because the
mechanical flow is asymmetric (USD-selling, no balancing USD-buying
of equivalent mandate).

Retail can ride this with zero capacity impact at $5k-$500k notional.

## Key references

- **Asness, Moskowitz, Pedersen (2013), "Value and Momentum Everywhere",
  *Journal of Finance*.** Currency seasonality chapter documents G10
  fiscal-year-end seasonality effects.
- **Goh, Jiang, Tu (2013), "Calendar Effects in Currency Markets",
  *Pacific-Basin Finance Journal*.** Specific JPY March-end seasonality
  documented: 1986-2010 sample showed mean JPY return of +1.2% in
  March vs -0.1% other months.
- **BIS Triennial Central Bank Survey** — confirms Japanese corporates
  + life insurers are top-5 USDJPY net-flow contributors during Feb-Mar.
- **Bank of Japan "Tankan" survey** — quarterly corporate hedging
  intentions data; March-quarter Tankan shows the biggest gap between
  USD-AR-holding corporates and active-hedging behavior.
- **Internal**:
  - `experiments/_live/xau_session/xau_session.md` — Asian-session
    structural-flow template.
  - `experiments/_live/macro_drift/macro_drift.md` — calendar-event
    drift template (different timeframe, similar mechanical-flow framing).
  - `docs/RESEARCH_NOTES.md` lesson #5 — multi-day-hold CFD swap-cost
    binding consideration (lesson #59 cousin: applies here as a binding
    cost item).
  - `docs/RESEARCH_NOTES.md` Lesson A revised — capacity moat insufficient
    without magnitude check.

## Signal math — pre-commit pseudo-code

```
Parameters (≤ 4):
  ENTRY_DAY             = 'Feb 15'  (calendar anchor; first valid trading
                                     day on or after this date)
  EXIT_DAY              = 'Mar 28'  (calendar anchor; last trading day
                                     before T-3 ahead of fiscal year-end,
                                     to avoid March 31 day-of volatility)
  COST_BPS_SPREAD       = 1.0       (Eightcap USDJPY ~1 pip RT)
  COST_BPS_SWAP_DAILY   = 1.4       (SHORT USDJPY negative carry: Fed-BoJ
                                     differential ~5% annualized / 360 days
                                     = ~1.4 bps/day = ~58 bps over 42-day hold)

Each year y in sample (2019-2025; partial 2026 if data permits):

  entry_date = first business day ≥ Feb 15 of year y
  exit_date  = last business day ≤ Mar 28 of year y
  hold_days  = business days between entry and exit (typically ~30 days)

  entry_px = USDJPY close at entry_date
  exit_px  = USDJPY close at exit_date

  # SHORT USDJPY (= LONG JPY) for the full window
  gross_pct = (entry_px - exit_px) / entry_px * 100
  net_pct   = gross_pct - COST_BPS_SPREAD/100 - (hold_days * COST_BPS_SWAP_DAILY/100)
```

Free param count: 2 free (ENTRY_DAY, EXIT_DAY); 2 fixed-by-broker (COSTs).
Well under 7-cap.

Direction null-check: same window/cost, opposite direction (LONG USDJPY).
This is the load-bearing null — if LONG also wins, the result is general
USDJPY drift over the period, not specifically the FY-end mechanical
flow.

Robustness null #2: same window-length on **non-FY-end periods**. Run
the same 6-week SHORT-USDJPY window centered on June, September, December
quarter-ends. If those quarter-ends show similar effect, the mechanism
is **generic quarter-end flow**, not **specifically March FY-end** —
which would be a different (and weaker) thesis.

## Why retail-accessible

- **USDJPY M5/H1/D1 CFD on Eightcap** confirmed tradeable; spread 1 pip
  RT at quote 145-160 = ~0.62-0.69 bps RT.
- **One position per year, 4-6 week hold**: trivial EA — calendar-
  anchored entry on Feb 15-ish, time-exit on Mar 28-ish. No intraday
  signal logic, no per-event triggering.
- **Capacity moat**: institutional macro funds ARE in this trade, but
  the flow is mechanical and not fully arb-able. Retail at $5k-$500k
  has zero capacity impact.
- **Swap cost is material but bounded**: ~58 bps swap drag over the
  full hold vs expected 80-200 bps gross. Net 22-142 bps per trade.
  This is the binding cost item; the magnitude check in Phase 0 must
  net the swap explicitly.

## Universe

- **Primary instrument**: USDJPY (D1 sufficient given 4-6 week hold;
  use M5/M1 only for entry/exit precision around the anchor dates).
- **Research history**: needs to cover ≥ 6 Februaries (2020-2025) plus
  ideally 2019 and pre-2019 for regime comparison.
  - 2019-2025 = 7 fiscal years of data
  - n=7 is **statistically thin** by Phase 2 standards (typical n ≥ 50
    floor); the kill criteria below are adjusted for the small-n regime.
- **Universe expansion (Phase 3 if PASS)**:
  - **Cross-pair check**: EURJPY, GBPJPY, AUDJPY (same mechanism on
    JPY-cross-rates). Should all show similar JPY-buying signature.
  - **Calendar-control**: same 6-week period on non-Japanese-FY-end
    quarter dates (June/Sep/Dec end). Should be flat — if positive,
    the mechanism is generic quarter-end-rebalance, not FY-specific.
- **Deployment target**: Eightcap MT5 USDJPY CFD, single calendar EA
  with magic number distinct from other JPY trades (e.g., `usdjpy_tokyo_fix`
  if both deploy).

## Expected performance (pre-run, with Phase 0 magnitude floor)

**Phase 0 magnitude check (binding before Phase 2 expansion)** per Lesson A:

Compute the simple gross mean and net (post-swap) mean across the 7
historical years (2019-2025 fiscal-year cycles). 
- **Phase 0 magnitude floor: gross mean ≥ +80 bps per year** AND
  **net mean ≥ +20 bps per year**. The gross threshold is academic-prior-
  consistent (Goh et al. found ~+120 bps March JPY return historically);
  the net threshold requires positive expectancy after swap.
- If gross < +80 bps OR net < +20 bps → REJECT before Phase 2 expansion.
  Document the methodology lesson: "mechanical-flow seasonality is dead
  in modern regime" or "swap cost eats seasonal gross."

**Hit rate check** (binding before Phase 2 expansion):
- Phase 0 requires **≥ 5 of 7 years positive** (71% hit rate). Below 5/7
  the win rate is at coin-flip and any positive mean is single-year-driven.

If Phase 0 passes:
- **Per-year gross**: +80 to +250 bps (historical academic range; varies
  by year regime).
- **Per-year net** (post-swap, ~58 bps drag): +22 to +192 bps.
- **Trade cadence**: **1 trade per year**. Extremely low. This is the
  category-novel part of the thesis — most deployed strategies are
  intraday/event-driven; this is a once-a-year seasonal.
- **Sharpe**: not meaningfully computable on n=7. Use **per-year return
  series mean / std** as the diagnostic instead of annualized Sharpe.
  Expected: mean +60 to +120 bps, std +80 to +120 bps, ratio ~+0.6 to
  +1.2 unconditional.
- **MDD**: worst-year loss expected -50 to -120 bps. Pre-commit single-
  year drawdown ceiling at -200 bps (= a single "bad" year stops out
  the strategy for that year, not for all years).

## Fail conditions (pre-committed, BEFORE running Phase 2)

Phase 0 ABORT (before any further sweeps):
- **Gross mean < +80 bps/yr** on 7-year sample → REJECT
- **Net mean < +20 bps/yr** post-swap → REJECT (mechanism alive but
  swap-cost-blocked, similar to `pead_midcap`)
- **Hit rate < 5/7 years positive** → REJECT (single-year-driven)
- **W3 (2023-2025, n=3) mean ≤ +0 bps** → REJECT per Lesson A regime-
  persistence requirement (modern regime cannot be negative even if
  full-sample is positive)

Phase 2 KILL (if Phase 0 passes) at 1 bp spread + 1.4 bp/day swap:
1. **Direction null-gap (SHORT − LONG mean) ≥ +50 bps/yr**. The load-
   bearing pre-commit on small-n data — if LONG-direction is also
   positive of similar magnitude, the result is general-USDJPY-drift
   not FY-specific flow.
2. **Calendar-control null** (same window-length on June/Sep/Dec quarter-
   ends): mean per-year ≤ +30 bps net (i.e., FY-end window meaningfully
   outperforms other quarter-ends by ≥ +50 bps).
3. **Single-year drawdown** ≤ -200 bps (any individual year worse than
   -200 bps gross is a regime-fail).
4. **Cost-stress at 2x swap** (worst-case BoJ-Fed rate differential
   widening, ~3 bps/day swap = 126 bps drag): net mean per-year still
   > 0.
5. **ENTRY_DAY sensitivity**: shifting entry ±5 business days should
   not move mean by more than ±20 bps (otherwise the result is calibrated
   to a specific date). Sweep Feb 10 / 15 / 20 / 25 / Mar 1 as entry.
6. **EXIT_DAY sensitivity**: shifting exit ±3 business days should not
   collapse the mean. Sweep Mar 25 / 27 / 28 / 29 / 31. Mar 31 entry
   itself (intraday) may show inverted direction as the unwind ends.

PASS only if Phase 0 floor + all of (1)-(6) hold.

## Why this might fail (red flags)

1. **n=7 is statistically thin.** Any conclusions on n=7 have wide
   CIs — a single bad year (e.g., 2024 with BoJ intervention noise)
   could flip the mean from +120 bps to +30 bps. **Pre-commit the
   small-n caveat: if Phase 2 passes, this is a "MARGINAL" verdict
   pending 3-5 more years of forward live data**, not an immediate
   deploy-grade PASS. Same standard as `pre_boj_drift` watch-list.

2. **2022-2024 BoJ intervention era confounds the price signal.**
   Sep-Oct 2022 intervention drove USDJPY -10% in days; Apr-May 2024
   intervention drove USDJPY -5% over weeks; Jul 2024 again. The 2022,
   2024 entries in the sample have intervention-noise that swamps the
   FY-end-flow signature. **Diagnose**: split sample by intervention-
   year vs non-intervention-year; if intervention years drive the
   positive mean, the mechanism is intervention-aligned not
   FY-end-flow.

3. **Carry-cost asymmetry tips the trade.** SHORT-USDJPY pays
   ~1.4 bps/day swap = 58 bps over 6 weeks. If the seasonal gross is
   only +60-80 bps in modern regime (which the W3 data may show), the
   net is just barely positive. Sensitive to small changes in BoJ-Fed
   rate spread. Pre-commit: if BoJ raises and Fed cuts to where the
   rate-diff narrows to <200 bps, the strategy's economics change
   materially — re-evaluate deploy continuation.

4. **Academic literature priors are 1986-2010 based.** The Goh et al.
   +1.2% March JPY mean was on pre-Abenomics, pre-YCC, pre-intervention-
   era data. Post-2013 BoJ regime fundamentally changed the JPY-rate
   structure. Post-2022 era is even more divergent. Phase 0 hit-rate
   check on the 2019-2025 window is the binding diagnostic.

5. **Front-running compresses the timing.** Macro funds know about
   FY-end repatriation. The actual price move may happen in early-mid
   February (when macro funds enter) rather than late-March (when
   corporates execute). If the move concentrates Feb 1-20 and reverses
   late-March (as corporates execute below front-running's mark), the
   Feb 15 entry may miss the move entirely. **Diagnostic**: window-shift
   sweep is the test.

6. **Yen-cross-rate confound on cross-pairs**. Phase 3 cross-pair check
   on EURJPY/GBPJPY/AUDJPY should show similar JPY-strengthening, NOT
   USDJPY-specific weakness. If only USDJPY shows the effect but
   EURJPY/GBPJPY don't, the trade is USD-specific (= maybe DXY-related)
   rather than JPY-fundamental.

7. **Holiday timing**. Japanese fiscal year-end can fall on a weekend,
   shifting effective last-trading-day to March 28 or 29 depending on
   year. US holidays in mid-February (Presidents' Day) shift effective
   entry by 1-2 days. Phase 2 must use business-day-conditional
   anchors, not strict calendar dates.

## Phase 1 → Phase 0 → Phase 2 plan (checkbox)

- [x] Read Lesson A revised (capacity moat + Phase 0 magnitude floor),
      lesson #5 / #59 (CFD-swap binding), `xau_session` thesis
      (Asian-flow template), `pre_boj_drift` (USDJPY watch-list pattern
      reference), academic priors (Goh et al. 2013, AMP 2013)
- [x] Write this thesis with pre-committed Phase 0 floor + kill criteria
- [ ] **Phase 0a (data check)**: verify USDJPY D1 + M5 coverage 2019-01-01
      → 2026-05-22 on `ohlc_data/USDJPY_M5.csv` or via datalake
- [ ] **Phase 0b (magnitude check)**: compute gross + net SHORT-USDJPY
      return for the 7 fiscal years (2019, 2020, 2021, 2022, 2023, 2024,
      2025). Compare to Phase 0 floors:
      - gross ≥ +80 bps mean
      - net ≥ +20 bps mean (post 1 bp spread + ~58 bps swap)
      - ≥ 5/7 years positive
      - 2023-2025 mean ≥ 0 (W3 regime persistence)
      - **If any Phase 0 floor fails → REJECT and tombstone WITHOUT
        running Phase 2 sweeps**
- [ ] If Phase 0 passes, build `jpy_fiscal_repatriation_demo.py`:
      - Calendar-anchored entry/exit
      - Cost model: explicit spread + per-day-swap accumulation
      - Direction null check (LONG vs SHORT)
      - Calendar-control null (June/Sep/Dec quarter-ends, same window length)
      - ENTRY/EXIT sensitivity sweeps
      - Hit-rate diagnostic per regime
      - Intervention-year vs non-intervention-year diagnostic
- [ ] Update this doc with results + verdict + mechanistic interpretation
- [ ] If MARGINAL (n=7 small-sample caveat dominant): watch-list per
      `pre_boj_drift` template; revisit in 2027 after the 2026 + 2027 FY
      cycles add to the sample
- [ ] If PASS: Phase 3 cross-pair check (EURJPY/GBPJPY/AUDJPY); if
      cross-pairs corroborate, deploy candidate
- [ ] If REJECT: tombstone — most likely failure mode is swap-cost-eats-
      seasonal (lesson #59 corroboration on FX) OR intervention-era-
      noise-dominates (BoJ regime confound)

## Files

- `jpy_fiscal_repatriation.md` — this doc
- `jpy_fiscal_repatriation_demo.py` — Phase 2 simulator (TBD; only
  built if Phase 0 passes)
- Data: `ohlc_data/USDJPY_M5.csv` or daily aggregate via datalake
- Calendar: no custom calendar needed; use Japanese fiscal year fixed
  March 31 anchor with business-day-conditional logic

## Open methodology questions for the agent

1. **Small-n verdict standard.** n=7 fiscal years is below the
   project's typical n ≥ 50 floor. If Phase 2 passes all kill criteria,
   the honest verdict is "MARGINAL pending more data", not "PASS deploy-
   ready". Follow the `pre_boj_drift` watch-list pattern: document the
   small-n caveat in the verdict line, add to watch-list table in
   STATE.md, revisit after 3+ more years accumulate.

2. **Intervention-year handling.** 2022 and 2024 had BoJ intervention
   that's directionally aligned (SHORT-USDJPY) with the thesis. **Do not
   drop intervention years from the sample** — that would be selection
   bias. Document the intervention-noise diagnostic separately. The
   correct treatment: include all years in the headline number, flag
   intervention-year-driven results in the interpretation.

3. **Window-length convention.** The Feb 15 → Mar 28 default is 6 weeks.
   Alternative: weekly or biweekly entries to spread swap cost. Sweep
   single-entry vs weekly-rebalance variants in Phase 2 if Phase 0
   passes. The deploy form should be the simpler one absent strong
   evidence for the more complex form.

4. **Currency-of-quote consideration.** USDJPY at quote 145 has slightly
   different bps-per-pip than at quote 160. Cost model uses 1 pip = 0.62
   bps at 160; verify across the historical range and use **average**
   bps cost (~0.70 bps RT spread) for the cost-stress sweep.
