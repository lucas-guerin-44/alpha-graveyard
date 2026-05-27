# Retail-concentrated single-name CFD overshoot fade (1-3 day window)

**Status (2026-05-26)**: Phase 2 complete.

**Verdict**: **REJECT**. Baseline FADE Sharpe -0.26 (kill +0.30), MDD -71%
(kill 25%), W3 2023-2026 holdout Sharpe -1.07 (kill ≤0), direction-gap -0.10
(kill +0.30 — both FADE and CONT lose), walk-forward mean OOS Sh -1.37. The
mechanism shows W2-pass/W3-fail (Sh +1.30 / -1.07 split) — it worked in the
2021-2022 meme regime and inverted hard in 2023-2026. See **Phase 2 results**
section below for full mechanistic interpretation.

## Why this — the institutional-absence framing

This thesis is the first deliberate test of the project's reframing: **don't
chase where literature says drift exists** (institutions are already there and
arb it at sub-bp cost), **chase where institutional capital is structurally
absent or constrained**. The retail-concentrated single-name universe is the
cleanest example of structural institutional avoidance the broker offers.

The classical reads — `earnings_continuation_mag7` REJECT, `earnings_fade`
REJECT, `pead_midcap` PASS-research-but-CFD-swap-blocked — all tested
institutional-coverable universes (Mag7, broad mid-cap) where institutional
flow IS the trade. The retail-concentrated subset is a different population.

## Thesis (mechanism)

1. **Retail-concentration creates a 1-3 day institutional dead-zone.** On
   names where retail % of float is >25-40% (TSLA, NVDA, PLTR, COIN, MSTR,
   MARA, RIOT, GME, AMC, RDDT, SOFI, HOOD, etc.), institutional desks
   systematically under-trade the post-spike continuation/reversal window
   for three converging reasons — none of which is "headline squeeze risk
   per GME precedent" (a 3× historical event, not a structural mechanism):

   a. **Borrow-cost asymmetry.** When a retail-heavy name spikes, hard-to-
      borrow rates spike with it. Institutional shorts pay 20-200%
      annualized borrow on the spike days vs 0.25% on quiescent names.
      The math doesn't work for risk-adjusted fundamental-short capital.

   b. **Mandate / risk-budget exclusions.** Post-2021, most prime-broker
      LP letters and internal risk-committee mandates explicitly cap
      exposure to "high-retail-concentration single names" — not via a
      named-list (which would be a Reg-FD problem) but via float-turnover
      / option-OI / borrow-rate triggers that mechanically exclude the
      universe. The carve-out is reputational + operational, not statutory,
      so the constraint persists.

   c. **Time-horizon coverage gap.** Fundamental shorts work over weeks-
      months; intraday HFT works over seconds-minutes. The 1-3 day window
      post-spike falls in a coverage gap on retail-popular names because
      neither timeframe's institutional player will rationally allocate
      capacity to it. Multi-day swing capital exists at institutional
      scale but operates on broader universes where capacity > $50M is
      deployable.

2. **The flow that DOES happen during the dead-zone is retail-extension.**
   On a +5-15% spike day, retail concentration mechanically increases as
   non-retail holders (passive, fundamental) hold or trim; retail buys the
   news+social-driven continuation. Retail momentum extends 1-3 days past
   where fundamentals reverse, then mean-reverts when the news cycle dies
   and retail attention rotates.

3. **The 1-3 day window is sized to keep CFD swap drag bounded.** Eightcap
   long-stock-CFD swap is ~7% annualized = ~2 bp/day per side. 1-3 day hold
   = 2-6 bp swap drag per side, ~4-12 bp RT, well below the expected 50-150
   bp overshoot reversion magnitude. The 5+ day window (where `pead_midcap`
   was killed) is structurally avoided.

4. **The directional sign is FADE (short the spike).** The hypothesis is
   that retail-flow exhaustion produces multi-day mean-reversion, opposite
   the intraday-spike-continuation pattern that lesson #43 documented for
   US-index 0DTE-driven intraday MR. Distinct from lesson #43 because the
   1-3 day window is outside the 0DTE gamma decay window — the multi-day
   reversion is governed by retail flow exhaustion, not options positioning.

## Key references

- **Barber & Odean (2008), "All That Glitters: The Effect of Attention and
  News on the Buying Behavior of Individual and Institutional Investors",
  *Review of Financial Studies*.** Canonical retail-attention-driven buying
  effect; documents the post-attention-event reversal at multi-day horizon.
- **Da, Engelberg, Gao (2011), "In Search of Attention", *Journal of
  Finance*.** Google Search Volume as proxy for retail attention; predicts
  short-term overpricing and subsequent reversal.
- **Internal**:
  - `experiments/_live/lunch_fade/lunch_fade.md` — same "institutional-
    absence creates retail-tradeable structure" framing in a different
    micro-context (institutional lunch break vs institutional mandate
    exclusion).
  - `experiments/earnings_continuation_mag7/earnings_continuation_mag7.md`
    — REJECT on the post-2022 Mag7 universe; this thesis tests whether
    the retail-concentrated subset (which Mag7 partly overlaps with for
    TSLA / NVDA) has different sign.
  - `experiments/pead_midcap/pead_midcap.md` — PASS at research, blocked
    at CFD swap due to 20-day hold; this thesis is the swap-binding-aware
    short-hold variant.

## Signal math — pre-commit pseudo-code

```
Parameters (≤ 7 hard cap):
  UNIVERSE              = [TSLA, NVDA, PLTR, COIN, MSTR, MARA, RIOT,
                           GME, AMC, RDDT, SOFI, HOOD]  (universe-fixed)
  SPIKE_THRESHOLD       = 0.05   (5% intraday move triggers entry)
  SPIKE_WINDOW_BARS     = 12     (12 × M5 = 1h spike-detection window)
  HOLD_DAYS             = 2      (target hold, time-exit at T+48h)
  STOP_PCT              = 0.05   (5% adverse move from entry = stop)
  COOLDOWN_DAYS         = 5      (no re-entry on same name within 5d)
  COST_BPS_DEFAULT      = 30     (estimated spread + 2 days of long-side
                                   CFD swap; calibrated to actual Eightcap
                                   per-name in Phase 0)

Per ticker, per M5 bar t:
  spike_pct[t] = (close[t] - close[t-SPIKE_WINDOW_BARS]) / close[t-SPIKE_WINDOW_BARS]

  if (flat on this ticker) AND
     (spike_pct[t] > SPIKE_THRESHOLD) AND
     (no entry on this ticker in past COOLDOWN_DAYS):

    ENTRY: SHORT at close[t]    (FADE — primary hypothesis)
    stop_px      = entry_px * (1 + STOP_PCT)
    time_exit_ts = entry_ts + HOLD_DAYS * 24h

  Exit on FIRST of:
    - stop hit
    - time exit
    - 50% retracement of the spike (target hit, optional sweep)

  cost_per_trade = spread (per-name varies) + (HOLD_DAYS × daily_swap × 2)
  net_ret = direction * (exit_px - entry_px) / entry_px - cost_per_trade
```

Free param count: 6 (THRESHOLD, WINDOW, HOLD, STOP, COOLDOWN, COST) — under the
7-cap. UNIVERSE is universe-fixed, not a free param.

Direction null-check: run CONTINUATION (LONG the spike) on the same
trigger as the primary null. If continuation outperforms fade by more than
the fade-gap threshold, the mechanism is sign-inverted — most likely meaning
0DTE-style retail momentum extends multi-day on these names too (lesson #43
generalizes further than expected).

## Why retail-accessible

- **Eightcap MT5 single-name CFD universe** carries most of the candidate
  tickers (verify per-name in Phase 0: `mt5_fetch.py --list-symbols
  --match TSLA,NVDA,PLTR,COIN,MSTR,MARA,RIOT,GME,AMC,RDDT,SOFI,HOOD`).
- **Capacity moat is the binding feature**: at $5k-$50k notional per trade,
  a single retail position has zero squeeze-risk-of-the-trade footprint;
  at $5M+ notional the same trade has career-risk implications for the PM.
  The capacity moat is the structural defense against the strategy being
  arbed at scale.
- **No specialized infra**: MT5 EA with per-ticker trigger-monitor + cooldown
  state, standard execution. Universe of ~12 tickers monitored in parallel.
- **Operationally retail-native**: Eightcap retail single-stock CFD is the
  exact venue this mechanism predicts the inefficiency lives in (since the
  primary inefficiency source is the lack of institutional CFD-retail
  participation — institutions trade these names via prime brokerage cash
  equity or options, not retail CFDs).

## Universe

- **Research universe** (primary, 12 names): TSLA, NVDA, PLTR, COIN, MSTR,
  MARA, RIOT, GME, AMC, RDDT, SOFI, HOOD.
  - Selection rationale: high retail-concentration (>25% retail float share
    per public estimates from public 13F/short-interest data); CFD-tradeable
    on Eightcap; M5 history available 2019+ (most names; some like RDDT
    only post-IPO 2024).
  - Selection bias note: these names are *currently* retail-popular. A
    walk-forward variant should hold this universe FIXED across the entire
    sample, not roll the universe forward by retail-concentration
    measurement. Universe-rolling would bias the result.
- **Research timeframe**: M5 (entry trigger), 1-3 day hold.
- **Data path**:
  - Primary: Eightcap MT5 M5 (verify per-name in Phase 0).
  - Fallback: Tiingo/Yahoo cash-equity M5/M15 for names where Eightcap CFD
    history is too thin; flag CFD-vs-cash basis mismatch as a separate
    risk for those names.
- **Deployment target**: same Eightcap MT5 single-name CFDs.

## Expected performance (point estimates, pre-run)

Honest priors:
- **Cost-zero gross Sharpe expectation**: +0.50 to +1.20. The mechanism
  has good theoretical support (Barber & Odean documented the multi-day
  reversion) but the post-2022 0DTE-gamma confound (lesson #43) is the
  binding falsification risk. If gross Sh < +0.30, the mechanism doesn't
  exist on this universe in this regime.
- **Net Sharpe after realistic cost (30bp RT)**: +0.20 to +0.60. Deploy
  bar is +0.30 net after the realistic cost.
- **Trade cadence**: 12 names × ~10-30 spikes/yr/name × cooldown filter
  = 50-150 trades/yr basket. Above the 200-trade floor over 4+ year window.
- **Win rate**: 50-58%. Multi-day fade strategies typically don't have
  high WR; the edge comes from average winners > average losers ratio.
- **MDD**: -15% to -25% basket-level. Single-name spikes can extend further
  than the stop, and the universe is correlated (crypto-proxies move
  together; meme-names move together). Pre-commit MDD ceiling at 25%.

## Fail conditions (pre-committed, BEFORE running Phase 2)

Phase 2 KILL if ANY at 30bp RT cost:

1. **Full-sample basket Sharpe ≤ +0.30** (net of cost).
2. **W3 (2023-2026 holdout) basket Sharpe ≤ +0.00** — modern regime must
   not be negative. (Note: 4-window split available if family-extension
   to the macro_drift convention is preferred; default to 3-window per
   CLAUDE.md convention.)
3. **Direction null-gap (FADE − CONT Sharpe) < +0.30**. The load-bearing
   pre-commit. If CONTINUATION wins (i.e., the spike continues multi-day),
   lesson #43 generalizes to multi-day on retail-popular names — different
   mechanism than this thesis, REJECT.
4. **Basket MDD > 25%** on the full sample.
5. **Per-name diagnostic**: at least 6 of 12 names individually positive
   on Sharpe (cost-zero). If only 1-2 names carry the entire basket signal,
   the mechanism is name-specific not universe-mechanism.
6. **Trade count < 100** basket-aggregate over the full sample.
7. **Cost-stress at 60bp RT** (worst-case wider spread on illiquid CFD
   names like GME, AMC): basket Sharpe still > 0.
8. **Walk-forward 3-fold OOS Sharpe**: mean ≥ +0.20 AND min ≥ -0.10.
9. **CFD-swap stress**: at +30% relative to baseline swap assumption
   (modeled as 40bp RT instead of 30bp), basket Sharpe still > 0. Lesson
   #59 binding.

PASS only if ALL of (1)-(9) hold for the FADE direction.

## Why this might fail (red flags)

1. **Lesson #43 generalizes to multi-day.** The post-2022 0DTE-amplification
   pattern may extend beyond the intraday horizon if retail-flow-on-spike
   self-reinforces for 2-3 days before exhausting. In that case CONTINUATION
   wins at 1-3 day horizon (especially on crypto-proxies in W3 holdout
   where MSTR/COIN exhibited strong multi-day momentum). The direction
   null-check is the binding test.

2. **Universe is selection-biased post-hoc.** The 12-name list is biased
   by *current* retail-popularity knowledge; in 2019-2021 the actual
   retail-popular set was different (no RDDT, no MSTR was retail-popular
   pre-2024). The fixed-universe walk-forward is the diagnostic; a strong
   in-sample result that doesn't survive walk-forward is universe-selection
   overfitting.

3. **The universe is mechanically correlated.** Crypto-proxies (COIN,
   MSTR, MARA, RIOT, HOOD, GME-when-NFTs) move together on BTC moves;
   meme-names (GME, AMC, RDDT) move together on retail-sentiment cycles.
   Basket MDD could spike if 5+ names trigger SHORT on the same day. Pre-
   commit MDD ceiling is the protection.

4. **Borrow-rate asymmetry could prevent execution.** The thesis assumes
   the trade can be entered; on the names where the mechanism is
   strongest (hardest-to-borrow), the actual Eightcap CFD SHORT-availability
   may be restricted or carry punitive financing. Phase 0 must verify
   short-side execution for each name.

5. **CFD-vs-cash-equity basis on overnight gap.** Eightcap CFD pricing on
   single names tracks cash equity intraday but can have basis drift
   overnight. The 2-day hold spans 1-2 overnight gaps; basis drift could
   add per-trade noise of 10-30 bps that's invisible in cash-equity research
   data. Real-tape audit Phase 4 prerequisite.

6. **News-cycle decay regime change.** The "retail attention exhausts in
   1-3 days" assumption was supported by 2019-2022 social-media cycles;
   post-2024 short-form video (TikTok/Reels) may extend retail attention
   half-life to 5-10 days, breaking the time-window. W3 holdout breakdown
   is the diagnostic — if W1+W2 strong and W3 negative, mechanism is
   decayed-by-attention-regime, REJECT.

## Phase 2 results (2026-05-26)

### Phase 0 finding: universe shrinks to 7 of 12

Eightcap MT5 carries **TSLA, NVDA, PLTR, COIN, MSTR, HOOD, RDDT**. The other
five thesis-listed names (**MARA, RIOT, GME, AMC, SOFI**) are not on the
broker — the most extreme retail-concentration names (the GME/AMC/MARA cluster
that the thesis treated as the strongest expression of the mechanism) are
unavailable. This means even a PASS would have run on a partially-de-fanged
universe; not a kill condition, but a meaningful reduction in the mechanism's
expression.

Data spans (M5):
- TSLA / NVDA / HOOD: 2021-09 → 2026-05 (~4.6y)
- PLTR: 2021-12 → 2026-05
- COIN / RDDT: 2024-03 → 2026-05 (~2.2y)
- MSTR: 2024-10 → 2026-05 (~1.6y)

### Headline numbers (baseline FADE, 7-name basket, 30bp RT cost)

| Metric                | Value     | Kill threshold | Result |
| --------------------- | --------- | -------------- | ------ |
| Net Sharpe            | -0.26     | ≥ +0.30        | FAIL   |
| Max DD                | -70.89%   | < 25%          | FAIL   |
| Trades                | 126       | ≥ 100          | PASS   |
| W3 2023-2026 Sharpe   | -1.07     | > 0            | FAIL   |
| Direction gap (F − C) | -0.10     | ≥ +0.30        | FAIL   |
| Cost-stress 60bp Sh   | -0.52     | > 0            | FAIL   |
| WF mean OOS Sh        | -1.37     | ≥ +0.20        | FAIL   |
| WF min  OOS Sh        | -2.31     | ≥ -0.10        | FAIL   |
| Positive names (gross)| 4/7       | ≥ 4            | PASS   |

### Regime breakdown — the load-bearing finding

| Regime                | n   | Sh     | MDD     | WR    |
| --------------------- | --- | ------ | ------- | ----- |
| W1 2019-2020 pre/COVID | 0  | —      | —       | —     |
| W2 2021-2022 vol      | 35  | +1.30  | -23.03% | 48.6% |
| W3 2023-2026 holdout  | 91  | -1.07  | -68.93% | 37.4% |

The mechanism existed cleanly in W2 (Sh +1.30, MDD -23%, near deploy-bar) and
inverted hard in W3. This is the canonical regime-decay shape: an effect
that worked when the population behaviour matched the thesis is now being
arbed or has structurally changed.

### Direction null-check

| Direction    | n   | Sh     | MDD     |
| ------------ | --- | ------ | ------- |
| FADE (short) | 126 | -0.26  | -70.89% |
| CONT (long)  | 127 | -0.16  | -60.19% |

**Both lose.** Direction-gap = -0.10. No directional content in the signal —
the 5%/1h spike trigger is not selecting a population with multi-day
predictable behaviour in either direction at 30bp cost. (Cost-zero gross
Sharpe is also flat: +0.00.)

### Per-name diagnostic

| Ticker | n  | Sh net | Sh gross | WR    |
| ------ | -- | ------ | -------- | ----- |
| TSLA   | 12 | +0.39  | +0.47    | 50.0% |
| NVDA   |  8 | -0.05  | +0.03    | 25.0% |
| PLTR   | 21 | -0.48  | -0.36    | 23.8% |
| COIN   | 16 | -0.39  | -0.25    | 31.2% |
| MSTR   | 19 | -0.13  | +0.04    | 52.6% |
| HOOD   | 29 | +0.29  | +0.41    | 51.7% |
| RDDT   | 21 | -0.96  | -0.77    | 38.1% |

4 of 7 cross zero on gross Sharpe; only TSLA and HOOD are convincingly
positive net of cost. The "universe-wide mechanism" framing is not supported.
TSLA/HOOD positive + PLTR/COIN/RDDT decisively negative looks more like
two-name luck than a structural effect.

### Variant sweeps

- **SPIKE_THRESHOLD**: monotone *more negative* as the threshold widens from 3%
  to 6% — fewer/cleaner triggers don't improve the edge. At very high thresholds
  (≥8%) Sharpe approaches zero only because n falls to 16-23 and the sample is
  too small to be informative.
- **HOLD_DAYS**: hd=5 (cost=40bp) Sh +0.14 is the best variant — counterintuitively
  the *longer* hold helps. Suggests if there is any edge it lives beyond the
  thesis's 1-3 day window. Consistent with red flag #6 (retail-attention half-life
  extending in the TikTok era).
- **STOP_PCT**: barbell — 3% (+0.10) and 15% (+0.12) marginally positive, 5-10%
  decisively negative. Characteristic of an MR strategy hitting trend extensions
  — the middle stops give back exactly the bounce that justifies the trade.
- **COOLDOWN_DAYS**: cd=10 (+0.20) is the best variant; over-trading during
  clustered-spike weeks is the dominant cost.

None of these variants would clear the +0.30 kill bar even at zero cost.

### Mechanistic interpretation — why it failed

1. **The W2→W3 sign inversion is the headline.** In 2021-2022 the meme-stock
   archetype (GME-driven retail mania, weekly social-media-driven spike
   cycles) produced a 1-3 day exhaustion-and-fade pattern; Sh +1.30 in that
   window is real. In 2023-2026 the same trigger fires into a *different*
   population — the 0DTE-options-driven institutional gamma flow that lesson
   #43 documents for intraday MR. On these single names the multi-day
   reversal pattern has been arbed away (or absorbed into the options
   market) and what remains is two-way noise around random spikes.

2. **The "institutional-absence" framing was wrong for this specific
   inefficiency.** The thesis argued institutions structurally avoid the
   1-3 day window on retail-popular names. The Phase 2 evidence is that
   *something* (gamma desks? long-vol ETF rebalancing? prop CFD
   market-makers?) is now filling that window — the absence the thesis
   relied on no longer exists in 2023-2026.

3. **The basket MDD is the operational killer.** Even if the basket Sharpe
   were positive, -70% MDD is uninvestable. Pre-commit red flag #3 (correlated
   universe) fired exactly as warned: COIN/MSTR/HOOD move together on BTC
   flows; PLTR/RDDT move together on AI/social-sentiment cycles; on bad days
   5+ names hit the same SHORT signal and the basket draws down together.

4. **Phase 0 reduced the universe by 5/12 and removed the most retail-
   concentrated cluster.** Had MARA/RIOT/GME/AMC/SOFI been included, the
   mechanism's expression *might* have been stronger (those are the highest
   retail-% names), but it's equally plausible they'd have made the basket
   correlation worse and the MDD even larger. The broker's universe selection
   is a real constraint, not a fixable one.

5. **Lesson reinforces book convention**: don't deploy strategies whose
   PASS is concentrated in a single regime window. The 2021-2022 +1.30
   Sharpe is the kind of in-sample number that, if quoted without the W3
   negative, looks deployable. The regime split is the diagnostic that
   prevents the deploy mistake.

### Falsified red flags (which fired)

- **#1 (lesson #43 generalization)**: PARTIAL — CONT doesn't win either, but
  FADE doesn't beat CONT, so the directional content collapses entirely.
  Interpretation closer to "the signal has no edge" than "continuation wins".
- **#3 (correlated universe)**: FIRED HARD — -70% MDD confirms.
- **#5 (CFD-vs-cash basis)**: not tested (no Phase 4 audit) but moot given
  the strategy is REJECT at Phase 2.
- **#6 (attention-regime change)**: PROBABLE — HOLD_DAYS=5 outperforming
  HOLD_DAYS=2 is consistent with retail-attention half-life extending past
  the thesis's 1-3 day window.

### What this teaches the project (cross-experiment lesson)

The "institutional-absence" framing is correct as a *theoretical lens* but
needs a sharper diagnostic before committing a thesis to Phase 2: not every
"institutionally-absent" 1-3 day window has retail-flow exhaustion as the
binding mechanism. On these names in this regime, the absence has been
filled by gamma/options flow that produces different (or null) directional
content. **Tombstoned with W2-existed/W3-decayed shape** — the next
"institutional-absence" thesis should pre-specify the diagnostic that
distinguishes "absence-with-MR-flow" from "absence-with-momentum-flow"
from "absence-with-no-flow".

## Phase 1 → Phase 2 plan (checkbox)

- [x] Read lesson #43, #45, #59, #-13, `lunch_fade` thesis (institutional-
      absence framing reference), `pead_midcap` thesis (swap-binding
      lesson), `earnings_continuation_mag7` (direction null-check pattern)
- [x] Write this thesis with pre-committed kill criteria
- [x] **Phase 0**: `mt5_fetch.py --list-symbols` — Eightcap MT5 carries 7/12
      (TSLA NVDA PLTR COIN MSTR HOOD RDDT); MARA RIOT GME AMC SOFI NOT
      available. Working universe reduced to 7.
- [x] **Phase 0**: pulled M5 history per name (datalake primary for the
      pre-existing 5; MT5 fetch for HOOD + RDDT injected to datalake).
- [x] Built `retail_overshoot_fade_demo.py` with numpy inner loop, per-name
      M5 spike-trigger + 2-day hold + stop + cooldown state machine.
- [x] Ran Phase 2: baseline FADE + null CONT + regime + cost-sweep + per-name
      diagnostic + walk-forward + swap-stress (all in single A-to-Z run).
- [x] Updated this doc with results + REJECT verdict + mechanistic interpretation.
- [x] **REJECTED** — tombstone. Red flags fired: #3 (correlated MDD), #6
      (attention-regime change probable from HOLD_DAYS sweep). Sign-inversion
      across W2/W3 is the load-bearing finding for the project's lesson book.

## Files

- `retail_overshoot_fade.md` — this doc
- `retail_overshoot_fade_demo.py` — Phase 2 simulator (TBD)
- `universe_meta.csv` — Phase 0 output (TBD)
- Data: Eightcap MT5 single-name CFD M5 per universe member; fallback
  Tiingo/Yahoo cash-equity M5 with CFD-basis-drift caveat noted in red flag #5.

## Open methodology questions for the agent

1. **3-window vs 4-window regime split**: CLAUDE.md default is 3-window
   (W1 2019-2020 / W2 2021-2022 / W3 2023-2026). The macro_drift family
   uses 4-window (W1/W2/W3/W4). For this thesis, 3-window is the default
   but 4-window may surface the W3 hiking-cycle / W4 post-hike split that
   matters for crypto-proxy names. Recommend running both as a diagnostic;
   primary verdict on 3-window per convention.

2. **Cooldown vs no-cooldown**: the cooldown prevents over-trading the
   same name during a multi-spike-week pattern (e.g., GME running 5 days
   in a row in Jan-2021). But it also caps trades during the windows
   when the mechanism is strongest. Test both and report the trade-off.

3. **Basket-level vs per-name verdict**: this thesis pre-commits on basket
   Sharpe + per-name diagnostic (≥6 of 12 names individually positive).
   If the basket PASSES but only via 2-3 names, the deploy form should
   be those 2-3 names not the basket. Document the breakdown in results.
