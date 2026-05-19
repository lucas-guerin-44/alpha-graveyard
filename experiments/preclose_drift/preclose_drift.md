# Pre-Close MOC-Imbalance Drift — SPX500 / NDX100 (US session)

**Status**: Phase 2 complete 2026-05-12.

**Verdict**:

| Instrument | Verdict | Baseline Sh | Holdout Sh | Dir-gap | MDD | Trades |
|---|---|---|---|---|---|---|
| SPX500 | **REJECT** (no signal) | −2.60 | −2.72 | +0.17 | −21% | 1,031 |
| NDX100 | **REJECT** (signal too thin) | −0.41 | **+0.57** | **+0.74** | −7% | 1,027 |

**Headline**: The Cushing-Madhavan / Bogousslavsky-Muravyev MOC-imbalance drift does survive as a *directional signal* on NDX100 (fade-gap +0.74, 2023-2026 holdout Sharpe +0.57) but the gross edge is fully consumed by 1pt CFD round-trip cost on a 5-10 min hold. SPX500 shows no directional content at all (cont/fade both lose identically) — too broad / too crowded a basket for the NYSE MOC imbalance to leak through cleanly at M5. The thesis is sound mechanistically but **not extractable on retail M5 CFD execution**.

Combined with the prior DAX pre-auction REJECT (sign-inverted), three venues across three microstructures rule out retail M5 pre-close drift as a deployment candidate. The mechanism is real on cash equities at higher frequency (sub-minute) per the literature; retail M5 latency + CFD spread are the binding constraints.

---

## Phase 2 results — SPX500 (REJECT)

M5, RTH 09:30-16:00 ET, 146,054 bars, 1,884 trading days.

**Baseline (cont, LB=20min, entry=T-10, thr=0.25, last-bar exit, cost=1pt)**:

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | −2.60 | FAIL |
| Max DD | −21.1% | PASS (just) |
| Trades | 1,031 (2.72/wk) | PASS |
| WR / PF | 31.2% / 0.46 | FAIL |
| Avg win / loss | +0.062% / −0.062% | — |

**Regime breakdown**: −2.38 / −3.48 / −2.72 — **3/3 regime fail**, monotonically bad.

**Lookback sweep**: LB=10 −3.45, 20 −2.60, 30 −2.55, 60 −1.91. Longer lookback marginally less bad but never positive.

**Threshold sweep**: thr=0.0 −4.51, 0.25 −2.60, 0.5 −1.48, 1.0 −0.51. Tighter filter linearly removes noise drag, never clears zero.

**Cost sensitivity**: 0.5pt −1.28, 1.0pt −2.60, 2.0pt −4.90, 3.0pt −6.65 — linear in cost. Cost-zero extrapolated Sharpe ≈ +0.04. **Gross signal is flat**, the live result is dominated by friction.

**Null-check**: cont −2.60, fade −2.77, gap +0.17 (FAIL +0.30 floor). Both directions lose equally — pure noise trading.

**Long/short split**: LONG −1.86, SHORT −1.82 — perfectly symmetric losses. No tradeable side.

**Mechanistic read on SPX failure**: the S&P 500 is split across NYSE (~85% by weight) and Nasdaq (~15%, dominated by tech mega-caps). The NYSE OII publication flags imbalance for NYSE-listed names; SPX cash and the CFD reflect the *combined* cross-venue close. The combined signal is much noisier than a pure-NYSE basket would be, and tech mega-cap MOC flow at Nasdaq partially offsets NYSE-side imbalance — washing out the directional drift.

Additionally SPX is the single most-arbed index in the world. The 15:50-16:00 imbalance window has had >15 years of HFT arbitrage at sub-second latency. Whatever drift survives at retail M5 granularity is small enough to be drowned by 1pt CFD spread. **REJECT, tombstone.**

---

## Phase 2 results — NDX100 (REJECT — signal real, too thin for CFD execution)

M5, RTH 09:30-16:00 ET, 146,245 bars, 1,885 trading days.

**Baseline (cont, LB=20min, entry=T-10, thr=0.25, last-bar exit, cost=1pt)**:

| Metric | Value | vs threshold |
|---|---|---|
| Sharpe | −0.41 | FAIL |
| Max DD | −6.80% | PASS |
| Trades | 1,027 (2.71/wk) | PASS |
| WR / PF | 45.6% / 0.89 | FAIL |
| Avg win / loss | +0.074% / −0.069% | — |

**Regime breakdown**:

| Window | Sharpe | Trades |
|---|---|---|
| 2019-2020 pre/COVID | −0.90 | 261 |
| 2021-2022 vol | −1.08 | 283 |
| **2023-2026 holdout** | **+0.57** | **483** |

Holdout is the strongest regime — consistent with literature that closing-auction volume has tripled since 2010 and continued to grow post-COVID, intensifying the imbalance-window flow. But two of three windows are negative, so a Phase-4 kill is in play even at baseline.

**Cost sensitivity**: 0.5pt −0.02, 1.0pt −0.41, 2.0pt −1.20, 3.0pt −1.96. Linear, cost-zero extrapolation Sharpe ≈ +0.36. **Gross signal is real and ~0.4 Sharpe**; CFD cost halves and ultimately consumes it.

**Null-check**: cont −0.41, fade −1.16, gap **+0.74** (PASS +0.30 floor). Clean directional content. Both lose absolutely, but cont loses by less — same shape as the NDX100 ORB result (directional signal exists, magnitude too thin).

### Fine threshold + dir-gap

| thr | Sh_cont | Sh_fade | dir-gap | trades | MDD |
|---|---|---|---|---|---|
| 0.00 | −1.01 | −1.37 | +0.36 | 1,836 | −12.0% |
| 0.25 | −0.41 | −1.16 | **+0.74** | 1,027 | −6.8% |
| 0.50 | −0.38 | −0.50 | +0.12 | 488 | −4.9% |
| 0.75 | −0.25 | −0.29 | +0.04 | 261 | −3.2% |
| **1.00** | **+0.07** | −0.40 | +0.47 | 134 | −2.1% |
| 1.25 | +0.16 | −0.35 | +0.51 | 72 | −1.2% |
| 1.50 | +0.18 | −0.30 | +0.47 | 41 | −1.2% |
| 2.00 | +0.41 | −0.48 | +0.89 | 18 | −0.4% |

U-shape in dir-gap: strong at thr=0.25 (large sample), collapses at thr=0.5-0.75 (mid-range noise dominates), rebuilds at thr≥1.0 (high-conviction outlier days). **No cell satisfies the Phase 2 trade floor (≥200) AND Sharpe>0.30 simultaneously**: thr=0.5 has 488 trades but Sh −0.38; thr=1.0 jumps to Sh +0.07 but only 134 trades. Statistical power evaporates at the threshold required to clear cost.

### High-threshold regime split (thr=1.0)

| Window | Sharpe | Trades |
|---|---|---|
| 2019-2020 | −0.57 | 42 |
| 2021-2022 | +0.79 | 31 |
| 2023-2026 | +0.61 | 61 |

Two strong post-2020 regimes but 31-61 trades per window is insufficient statistical power to call this a robust edge. With <100 trades the standard error on Sharpe is ~0.5-0.7 — the +0.61 holdout estimate is consistent with anything from −0.1 to +1.3 at 95% confidence. Not deployable.

### LB × thr grid (continuation Sharpe, cost=1pt)

|       | thr=0.25 | thr=0.50 | thr=0.75 | thr=1.00 | thr=1.25 | thr=1.50 |
|---|---|---|---|---|---|---|
| LB=20m | −0.41 | −0.38 | −0.25 | +0.07 | +0.16 | +0.18 |
| LB=30m | −0.40 | −0.21 | +0.19 | −0.10 | −0.20 | −0.15 |
| LB=60m | −0.41 | +0.33 | −0.14 | +0.55 | −0.03 | −0.36 |

Scattered positives (LB=60 / thr=1.0 +0.55, LB=60 / thr=0.5 +0.33) but **18-cell grid → 6 positive cells is consistent with selection bias at this sample size**. The LB=20m row monotonically improves with threshold; the LB=30m and LB=60m rows are erratic. No coherent pattern that would survive out-of-sample selection.

### Long/short split @ thr=1.0

- LONG-only: 53 trades, Sh −0.02
- SHORT-only: 81 trades, Sh +0.17

Slight short skew but n=53/81 is too thin. No deployable asymmetry.

**Mechanistic read on NDX**: NDX100 is Nasdaq-listed concentrated (100 names, all on Nasdaq), so Nasdaq Closing Cross + NOII publication signal aligns cleanly with the CFD basket — explaining why dir-gap is real (+0.74) when SPX's was not (+0.17). The mechanism is intact. But:

1. **Net edge after cost ≈ 4-5 bps gross / day-on-trade × ~50% cost = 2-3 bps net.** Below detection threshold at 1k-trade sample.
2. **HFT arbitrage compresses retail M5 entry.** First-tick to indicative-imbalance reaction at colocated firms is sub-millisecond. By the time an M5-bar-close decision propagates to a market-order fill at 15:55, most of the displaceable price has already moved.
3. **Mega-cap concentration risk.** Top 10 names are ~50% of NDX100. On any given day, the index-MOC-flow direction may be dominated by 1-2 mega-cap rebalances, making the "signal" highly idiosyncratic per day.

**REJECT.** Real mechanism, real directional content, but not extractable at retail M5 + CFD-cost execution.

---

## Cross-instrument synthesis

| Venue | Imbalance publication | Mechanism viability | Result |
|---|---|---|---|
| NYSE (SPX) | OII at 15:50 ET, 10-min lead-time | Mechanism present but diluted by Nasdaq-listed weight + crowded arb | REJECT (dir-gap +0.17) |
| Nasdaq (NDX) | NOII at 15:50 ET, 10-min lead-time | Mechanism clean (basket = exchange constituents), edge too thin | REJECT (dir-gap +0.74, Sh below floor) |
| Xetra (DAX) | No public imbalance during continuous trading | Different mechanism (auction-call only) → tombstoned sign-inverted | REJECT (dir-gap −0.33, see `dax/pre_auction.md`) |

**Key insight**: the canonical Cushing-Madhavan effect requires *both* (a) public imbalance publication during continuous trading **and** (b) an instrument whose constituents are concentrated on that one venue. NDX100 satisfies (a) and (b) cleanly; SPX500 fails (b); DAX fails (a). NDX is therefore the strongest setup of the three — and it still fails at M5 CFD execution.

**Implication**: pre-close MOC drift is **not a viable retail-M5-CFD strategy on any of the three major venues**. To extract this edge would require either (i) cash-equity execution with commission ~0.1-0.5 bps (Zarattini-style), (ii) sub-minute bars + colocation, or (iii) a different mechanism (e.g., a focused single-stock NOII-imbalance fade rather than index-wide drift).

---

## Lessons captured

- **DAX rejection did not rule out the US thesis.** Xetra has no public OII feed during continuous trading, so the mechanism cannot operate there. The retest on NYSE + Nasdaq venues was warranted, and produced a more nuanced result (signal exists on NDX, absorbed by costs).
- **Threshold sweeps with very tight filters look better than they are.** thr=2.0 with 18 trades produced Sh +0.41 — meaningless. Always cross-check trade count against Phase 2 floor before celebrating a positive cell.
- **dir-gap U-shape is a fingerprint of "real signal absorbed by friction".** When dir-gap is positive at low threshold (lots of noisy trades), drops to ~0 in the mid-range, then rebuilds at high threshold (few high-conviction outliers), the mechanism is real but the gross edge per trade is too small to outrun cost on the broad sample. NDX100 ORB had the same shape; this is now seen twice.
- **Cost-zero Sharpe extrapolation is the right diagnostic** for distinguishing "no edge" (SPX, cost-zero ≈ 0) from "edge eaten by cost" (NDX, cost-zero ≈ +0.36). The latter still rejects on retail CFD but tells a different mechanistic story.
- **Mega-cap concentration is a hidden enemy on NDX-style baskets.** Top-10 weight ~50%, so single-name rebalance flow drives the per-day MOC signal more than aggregate flow does. Signal is idiosyncratic per-day → high sample noise.

---

## Files

- Thesis: `experiments/preclose_drift/preclose_drift.md` (this file).
- Demo: `experiments/preclose_drift/preclose_drift_demo.py` — env-var `PRECLOSE_SYMBOL` (default SPX500). Baseline + LB/entry/thr/cost sweeps + null-check + long/short split.
- Refinement: `experiments/preclose_drift/preclose_drift_refine.py` — fine threshold sweep with cont vs fade columns, regime breakdown of high-threshold variant, LB×thr grid.
- Data: `ohlc_data/SPX500_M5.csv`, `ohlc_data/NDX100_M5.csv`.
- Run commands:
  - `venv/Scripts/python.exe experiments/preclose_drift/preclose_drift_demo.py`
  - `PRECLOSE_SYMBOL=NDX100 venv/Scripts/python.exe experiments/preclose_drift/preclose_drift_demo.py`
  - `PRECLOSE_SYMBOL=NDX100 venv/Scripts/python.exe experiments/preclose_drift/preclose_drift_refine.py`

## References

- Cushing, D., & Madhavan, A. (2000). "Stock returns and trading at the close." *Journal of Financial Markets* 3(1), 45-67.
- Bogousslavsky, V., & Muravyev, D. (2023). "Who Trades at the Close? Implications for Price Discovery and Liquidity." *Review of Financial Studies* 36(11).
- Hu, J., Jo, K., Wang, J., & Xie, Y. (2023). "Closing Auction Trades and Returns." Working paper.
