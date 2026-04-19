# GER40 intraday z-score momentum — M5

**Status**: Phase 2 complete, 2026-04-19. **MARGINAL — do not deploy; tombstoned in favor of GER40 ORB T+180.**
**Verdict summary**: Mechanism confirmed. Fade-gap +0.82 (reversion -0.93 vs momentum -0.12) says DAX z-score stretches continue, not revert — matching the ORB fade-gap sign. BUT: baseline fails at 1pt cost (Sharpe -0.12). Costless Sharpe +0.41 would pass; cost-breakeven is ~0.7pt. **The ORB-boundary trigger is a structurally better entry signal than a 20-bar z-score on DAX** — same mechanism, stronger trigger.
**Parent insights (two):**
1. **orb_spx.md** — GER40 ORB baseline Sharpe +0.58 with T+180min exit, fade-gap +1.04 under 1:2 R:R. Directional momentum signal confirmed from ORB-boundary trigger. Edge lives in first 3 hours post-breakout.
2. **ndx_mean_reversion.md** (2026-04-19, same day) — proved that z-score stretches on NDX100 are weakly momentum-continuation, not reversion. Validated the z-score-trigger framework as a distinct, cleaner alternative to ORB boundaries.

**This experiment asks**: does the GER40 directional momentum edge generalize to a proper z-score-extension trigger (not the OR-boundary trigger), or is the edge ORB-boundary-specific?

If YES → the mechanism is "DAX intraday momentum continuation from stretched levels" — cleaner, lifts multiple entry-trigger variants.
If NO → the ORB mechanism depends specifically on the opening-range-break as the entry trigger, not a general stretch-continuation property of DAX.

## Thesis (mechanism)

Xetra's concentrated morning auction resolves overnight information into a clean directional impulse during the first 30-60 min. Unlike NDX100 (distributed US-session price discovery), DAX has a point-in-time resolution at open and a well-known "trend-day or not" pattern decided by 10:00-11:00 Berlin. Mechanistic hypotheses:

1. **Continuation after stretch**: M5 bars that print z ≥ 2.0 against a 20-bar rolling window typically do so because the stretch is part of an established intraday direction. In NDX, we saw that stretches drift weakly with direction; DAX's concentrated-open dynamic should make the continuation stronger.
2. **Morning auction bias**: the first ~3 hours of Xetra cash (09:00-12:00 Berlin) is the highest-information-content window. If the z-score fires during this window, directional continuation should be more reliable than if it fires mid-afternoon.
3. **No cross-Atlantic confound until 15:30 Berlin** (US cash open). Stretches triggered before 15:30 are purely EU-driven; stretches triggered after are mixed with US session open noise.

## Key reference

Same references as orb_spx.md (Crabel, Fisher, Zarattini/Aziz). The momentum-continuation literature is deep; the specific twist here is a z-score trigger applied to EU cash index CFDs at M5.

## Signal math

```
Parameters:
  WINDOW_BARS             = 20      (20 M5 bars = 100 min rolling window)
  Z_ENTRY                 = 2.0     (enter when |z| >= 2.0)
  Z_PROFIT                = 3.0     (TP when |z| >= 3.0 — stretch continues further)
  Z_STOP                  = 0.5     (stop when |z| <= 0.5 — reverted to mean)
  T_EXIT_MIN              = 180     (time exit after 180 min — matches GER40 ORB sweet spot)
  ENTRY_CUTOFF_MIN        = 300     (no new entries in last hour of session)
  EXIT_MIN_BEFORE_CLOSE   = 5       (flat by 17:25 Berlin)
  COST_POINTS_RT          = 1.0     (pessimistic retail CFD)

Per M5 RTH bar b (09:00-17:30 Europe/Berlin):

  mean_b = rolling_mean(close, WINDOW_BARS)  (within-day, resets per session)
  std_b  = rolling_std(close, WINDOW_BARS, ddof=1)
  z_b    = (close_b - mean_b) / std_b

  Entry (flat only, within ENTRY_CUTOFF_MIN of open):
    z_b >=  Z_ENTRY  -> LONG  at next bar open (ride the up-stretch)
    z_b <= -Z_ENTRY  -> SHORT at next bar open (ride the down-stretch)

  Exit (first of):
    |z_current|             >= Z_PROFIT     -> TP   (stretch extended — take profit)
    |z_current|             <= Z_STOP       -> STOP (reverted to mean — stretch failed)
    bars_since_entry * 5    >= T_EXIT_MIN   -> TIME (no resolution in window)
    minute_of_day           >= exit_cutoff  -> EOD
```

**Note the inversion of TP/STOP logic** vs the NDX MR experiment: here, further stretch is the TP (we want continuation); reversion to mean is the stop (the thesis is wrong on this trade).

## Universe

GER40 M5, RTH 09:00-17:30 Europe/Berlin, 2019-01-02 → 2026-04-17. Data at `ohlc_data/GER40_M5.csv` (470,230 bars).

## Expected performance

Given GER40 ORB T+180 produced Sharpe +0.58 with fade-gap +1.04, and this is the same underlying momentum mechanism with a different trigger:
- Full-sample Sharpe **+0.3 to +0.7** after 1pt cost.
- Trade cadence **2-6 per week** (z ≥ 2.0 is less frequent than ORB breakouts).
- WR **40-55%** (momentum strategies are typically low-to-medium WR with large winners).
- PF **1.1-1.5**.
- MDD **10-18%**.

Live haircut target: 0.15-0.35.

**If the mechanism is real and not ORB-boundary-specific**: fade-gap (momentum minus reversion direction) should be **≥ +0.5 Sharpe**, matching GER40 ORB's +1.04 fade-gap magnitude.

**If the mechanism is ORB-specific**: z-score momentum may still be positive but weaker than the ORB version, and the fade-gap would be smaller.

## Fail conditions (pre-committed)

Phase 2 kills if:
- Full-period Sharpe < 0.30 after 1pt RT cost.
- Max DD > 25%.
- Trade count < 150 over 7.3 years (z-score trigger is rarer than ORB).
- PF < 1.05.
- **Fade-gap test**: the reversion variant (enter AGAINST stretch) should LOSE by ≥ 0.3 Sharpe. If reversion and momentum are equally profitable / unprofitable, directional content is missing.

Phase 4 kills if Sharpe positive in ≤ 1 of 3 regime windows. Holdout 2023-2026 is the critical one.

## Why this might fail (red flags)

1. **DAX closes half the day during European lunch** (11:30-13:30 Berlin historically, though Xetra continuous is 09:00-17:30 now). Low-volume midday bars could generate spurious z-score triggers that don't reflect real directional flow.
2. **Post-15:30 Berlin (US cash open) is mixed-regime.** Stretches triggered then may be cross-Atlantic noise, not DAX-specific momentum. Might need to truncate entry cutoff to 13:30 or 15:00.
3. **The 3pt spread on GER40 CFD is realistic at some brokers.** 1pt is optimistic. Cost sweep must show positive Sharpe at 2pt minimum.
4. **Sample is ~470K bars** but trade count will be ~1,500-3,000. Thin when split across 3 regimes.

## Phase 1 → 2 plan

- [x] **Phase 1 thesis (this doc).**
- [x] **Phase 2 — baseline demo.**
- [x] **Phase 2b — variant sweeps** z_entry / T_exit / z_profit / window / entry_cutoff.
- [x] **Phase 2c — reversion null check** (corrected logic after initial off-by-mirror).
- [x] **Phase 2d — regime breakdown** 2019-2020 / 2021-2022 / 2023-2026.
- [x] **Phase 2e — entry-time truncation** 180/240/300/390/480 min.
- [x] **Phase 2f — cost sensitivity** 0 / 0.5 / 1 / 1.5 / 2 / 3pt RT.

## Phase 2 result — MARGINAL (mechanism confirmed, trigger inferior to ORB)

Ran on GER40 M5, 2019-01-02 → 2026-04-17, RTH 09:00-17:30 Europe/Berlin (188,895 bars, 1,853 trading days).

### Baseline (window=20, z_entry=2.0, z_profit=3.0, z_stop=0.5, T=180min, cost=1pt)

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | **−0.12** | FAIL (need > +0.30) |
| CAGR | −1.09% | — |
| Max DD | −20.58% | PASS (< 25%) |
| Trades | 4,175 (11.0/week) | PASS |
| Win rate | 36.7% | — |
| Profit factor | 0.98 | FAIL (need ≥ 1.05) |
| Avg win | +0.253% | — |
| Avg loss | −0.149% | — |
| Exit mix | STOP 3,702 / TP 439 / TOD 34 | Stop-at-z=0.5 dominates — most trades revert past entry before hitting TP |

### Null check (reversion variant — enter AGAINST stretch, TP on mean-reversion, stop on further stretch)

| Variant | Sharpe | WR | PF | Avg win | Avg loss |
|---|---|---|---|---|---|
| **Momentum** (thesis) | **−0.12** | 36.7% | 0.98 | +0.253% | −0.149% |
| **Reversion** (null) | **−0.93** | 61.1% | 0.88 | +0.141% | −0.251% |
| **Fade-gap** | **+0.82** | — | — | — | — |

**Mechanism confirmed.** Fade-gap +0.82 is well above the +0.30 bar — momentum-on-z-score has real directional content on DAX, opposite to NDX where reversion-on-z-score was the less-bad direction (-0.28 fade-gap). The DAX / NDX dichotomy is consistent across triggers.

### Regime breakdown (baseline)

| Window | Sharpe | MDD | Trades | WR |
|---|---|---|---|---|
| 2019-2020 pre/COVID | −0.11 | −14% | 1,120 | 36.5% |
| 2021-2022 vol | −0.17 | −11% | 1,171 | 37.5% |
| 2023-2026 holdout | −0.09 | −16% | 1,884 | 36.3% |

**3/3 regimes mildly negative at 1pt cost.** Tight distribution (−0.09 to −0.17) — no regime is the problem; it's a uniform cost-friction issue.

### Variant sweep — z_entry

| z_entry | Sharpe | MDD | Trades | WR | PF |
|---|---|---|---|---|---|
| **1.5** | **+0.11** | −19% | 5,995 | 34.0% | 1.01 |
| 2.0 | −0.12 | −21% | 4,175 | 36.7% | 0.98 |
| 2.5 | −0.00 | −14% | 2,204 | 39.3% | 0.99 |
| 3.0 | −0.23 | −9% | 753 | 42.0% | 0.93 |

z_entry=1.5 scrapes positive (+0.11) with the most trades. Not deploy-worthy but consistent with "lower threshold finds more signal but with noisier fires".

### Variant sweep — T_exit, z_profit, window, entry_cutoff (summary)

All sweeps produced Sharpe in the range **−0.28 to +0.14**. Best point: `window=60` (Sharpe +0.11, but only 249 trades over 7.3y — too sparse). Best early-cutoff: `cutoff=180min` (Sharpe +0.01, i.e., flat — late-session entries are not the problem, they're actually slightly better than morning-only).

No single parameter flips the strategy convincingly positive. The signal is real but the noise-to-cost ratio is borderline.

### Cost sensitivity (the decisive table)

| Cost | Sharpe |
|---|---|
| 0.0pt | **+0.41** |
| 0.5pt | +0.14 |
| 1.0pt | −0.12 |
| 1.5pt | −0.37 |
| 2.0pt | −0.63 |
| 3.0pt | −1.14 |

**Cost-breakeven ~0.7pt.** Survives only at tight retail-CFD pricing (IC Markets/Pepperstone 0.5-0.8pt typical). At any wider broker or at the 1pt default assumption, the strategy loses.

### Comparison vs GER40 ORB T+180 (the incumbent)

| Strategy | Baseline Sharpe (1pt) | Costless Sharpe | Fade-gap | MDD | Holdout Sh |
|---|---|---|---|---|---|
| **ORB T+180** (orb_spx.md) | **+0.58** | ~+0.85 | +1.04 | −12% | **+0.55** |
| **z-score momentum** (this) | −0.12 | +0.41 | +0.82 | −21% | −0.09 |

The ORB-boundary trigger is strictly better than z-score momentum on DAX:
- 2× better absolute Sharpe at 1pt cost
- Better fade-gap magnitude (stronger signal content)
- Lower MDD
- Positive vs negative holdout

### Mechanistic interpretation

The OR-boundary is a **structurally informative price level** on DAX, not just a convenient z-score proxy. Reasons:

1. **Xetra auction-resolution effect**: the first-30-min high/low of cash session is a real pool of stop-orders and pending limit-fills. Breaking it triggers actual flow (stop-runs, momentum-chasers, delta-hedgers). A rolling z-score at ±2σ does not correspond to any particular flow-level — it's a statistical construct.
2. **Day-trader anchor bias**: many DAX day-traders explicitly watch the 09:00-09:30 Berlin range. Price closing outside that range generates coordinated follow-through that a pure-statistical z-score can't capture.
3. **Z-score extremes are more frequent than OR breakouts but less information-dense per fire.** 4,175 z-score trades vs 2,831 ORB trades for the same sample → z-score fires ~50% more often but with individually weaker signal content.

This is consistent with the NDX100 comparison: on NDX there is no comparable structural level (no concentrated opening auction), and both triggers fail.

### Kill decision

Per pre-committed Phase 2 criteria:
- Sharpe > 0.30 → **FAIL** (−0.12)
- Max DD < 25% → PASS (−21%)
- Trades ≥ 150 → PASS (4,175)
- PF ≥ 1.05 → **FAIL** (0.98)
- Fade-gap ≥ +0.30 → **PASS STRONGLY** (+0.82)

**3 of 5 pass (including the critical fade-gap), 2 of 5 fail (absolute Sharpe and PF).** Verdict: **MARGINAL**. Real mechanism, weaker trigger than the ORB-boundary. Tombstone in favor of the incumbent GER40 ORB T+180 deploy candidate. Do not deploy.

### Lessons captured

- **"Same mechanism, different trigger" is a valid research path** — it distinguishes "the mechanism is real and general" from "the specific setup is what works". Here it told us the DAX momentum mechanism IS general (fade-gap +0.82 with a generic z-score trigger), but the OR-boundary is a *better-calibrated trigger* for the same mechanism.
- **Fade-gap being positive is necessary but not sufficient** for a deployable strategy. DAX z-score momentum has +0.82 fade-gap — strong directional content — but the signal-to-cost ratio is too thin to profit at 1pt RT. Direction ≠ magnitude.
- **The null-check TP/stop logic must be a clean mirror of the baseline.** Initial run had an asymmetric reverse-mode that produced a misleading +0.18 fade-gap; fixing to a clean mirror (reversion TP on |z|<=z_stop, stop on |z|>=z_profit) gave the real +0.82. Document for CLAUDE.md.
- **Costless Sharpe +0.41 is a useful diagnostic.** It separates "signal exists but friction kills it" (this case) from "no signal at all" (the NDX MR case, costless Sharpe −0.21). Different problems, different next-steps.

## Files

- Thesis: `experiments/dax_zscore_momentum/dax_zscore_momentum.md` (this file).
- Demo: `experiments/dax_zscore_momentum/dax_zscore_momentum_demo.py`.
- Data: `ohlc_data/GER40_M5.csv`.
- Run: `venv/Scripts/python.exe experiments/dax_zscore_momentum/dax_zscore_momentum_demo.py`
