# FX safe-haven — JPY-long during equity stress regimes

**Status**: Phase 2 complete 2026-05-18
**Verdict**: REJECT — mechanism partially works (2020 COVID stress Sharpe +1.39, just below +1.5 bar) but catastrophically breaks in rate-divergence regimes (2022 Sharpe −0.91). The Fed-BoJ rate divergence inverted the classical JPY-haven property during the very kind of equity-bear regime a book hedge must cover. Null-check direction-gap −0.55 (long-side profits at same triggers) confirms the regime structure does not generally favor the short JPY-cross direction in modern data.

## Why this exists

`short_tsmom` (rejected 2026-05-18) confirmed lesson #34 of RESEARCH_NOTES: **equity-index shorts are structurally broken as a book hedge in the QE era.** The conditions that look like "bear regime" select for buy-the-dip EV. So the hedge cannot come from another equity exposure.

This experiment tries a different asset class: **JPY-long via JPY-cross shorts** during equity stress regimes. The mechanism — carry-trade unwind in stress — is structurally orthogonal to "fight central-bank policy" because JPY's appreciation in stress is exactly the unwinding of leveraged carry positions held by global investors.

## Thesis (mechanism)

1. **JPY funds global carry trades.** Decades of near-zero Japanese rates → leveraged long-AUD/long-NZD/long-USD short-JPY positions held by global macro. Total positioning is estimated at several hundred billion notional.
2. **Stress events trigger forced unwinds.** When equity vol spikes, AUDJPY/NZDJPY/USDJPY positions get margin-called or risk-reduced. The unwinding flow itself drives JPY higher (and crosses lower).
3. **The unwind is concentrated and fast.** Historical examples: 2008 (AUDJPY −34% peak-to-trough in 4 months), 2015 China devaluation (AUDJPY −15% in 8 weeks), 2020 COVID (AUDJPY −20% in 2 weeks), Aug 2024 carry-shock (AUDJPY −12% in 2 weeks). These are exactly the windows where an all-long-equity book bleeds the most.
4. **In calm regimes, carry decay is the cost of insurance.** AUDJPY in normal times grinds higher on carry differential and risk-on flows. A short-bias hedge will bleed −5 to −15 bp/day in those regimes (this is the insurance premium).
5. **Different mechanism than tsmom-short.** Trigger is regime-detection (equity-vol or equity-drawdown), not price-momentum on the FX pair itself. So the QE-era "buy-the-dip on equities" pattern doesn't directly hurt us — we're not trading equity-momentum, we're trading carry-unwind flow.

## Key reference

- Brunnermeier, Nagel, Pedersen (2008) "Carry Trades and Currency Crashes" — carry crashes co-occur with funding-liquidity shocks
- Spitznagel, "Safe Haven" (2021) — insurance-asset framework
- Repo prior: `experiments/short_tsmom/short_tsmom.md` REJECT — lesson #34 motivating this experiment

## Signal math

```
For each day t:
  Compute SPX500 regime signal (from prior-day close):
    spx_dd_60d[t]  = spx_close[t-1] / max(spx_close[t-60..t-1]) - 1
    spx_rvol_20[t] = std(spx_returns[t-20..t-1]) * sqrt(252)
    spx_sma_50[t]  = mean(spx_close[t-50..t-1])

  Stress regime triggers (test variants):
    V1: spx_dd_60d < -0.05
    V2: spx_rvol_20 > median(spx_rvol_20[full sample]) * 1.5
    V3: spx_close[t-1] < spx_sma_50 (simple downtrend)
    V4: V1 OR V2 (union of stress signals)

  Position management on FX pair:
    If stress regime active and flat: SHORT next-day open, vol-target 10%.
    If stress regime cleared and short: FLAT at next-day open.
    Adverse-move stop: position closed if open_pnl < -8% (rare for FX D1).
    Time stop: max hold 90 days.

  Cost: 1 bp RT per trade (FX CFD typical).
```

## Why retail-accessible

- AUDJPY/NZDJPY/USDJPY all tradeable on Eightcap (56 FX pairs available).
- D1 timeframe — no microstructure, no execution sensitivity.
- Position sizing in lot terms is trivial on MT5.
- The "smart money" version of this trade is buying USDJPY puts in low-vol regimes. Retail can't easily do that; CFD short is the proxy.

## Universe

- **Primary**: NZDJPY D1, CADJPY D1 (already on disk)
- **Secondary**: AUDJPY (derive D1 from H1 file on disk), USDJPY (derive D1 from H1)
- Regime signal from SPX500 D1 (already on disk)
- Period: 2018-01 → 2026-04

## Expected performance (pre-committed)

| Metric | Expected range | Reason |
|---|---|---|
| Full-sample Sharpe | −0.3 to +0.5 | Insurance asset — bleed in bulls + spikes in stress |
| 2020-Q1 stress Sharpe | +1.5 to +4.0 | COVID carry-unwind was textbook |
| 2022 full-year Sharpe | −0.5 to +1.0 | Equities bear but USDJPY rallied on rate divergence — could go either way |
| 2024-2026 bull-drag | −0.5 to +0.5 | Big JPY weakening trend; expect drag |
| MDD | < 30% | Adverse-move stop limits per-trade |
| Trades | 30-80 | Low cadence by design |
| Correlation to book in stress windows | < −0.20 | Load-bearing — must inverse to book in bad windows |

## Fail conditions (pre-committed)

| Criterion | Bar |
|---|---|
| Full-sample Sharpe > −0.50 | Insurance can bleed but not collapse |
| MDD < 40% | Allowed to drawdown but not blow up |
| Trades ≥ 30 | Below this, signal is too rare to matter |
| **2020-Q1 stress Sharpe > +1.5** | **load-bearing** — the textbook event must work |
| **At least 2 of (V1/V2/V3/V4) PASS 2020-Q1 > +1.5** | **load-bearing** — mechanism robust across trigger choices |
| **Correlation to deployed book in 2020-Q1 < −0.20** | **load-bearing** — must be a real hedge |
| Direction null-gap (long vs short) > +0.30 | Confirms direction has content |

## Why this might fail (red flags)

1. **2022 was an inverse case.** USDJPY went UP during the equity bear because of US/JP rate divergence (Fed hiked, BoJ didn't). The textbook "JPY rallies in bear" assumption broke. If V4 keeps us short USDJPY during 2022, we lose money in an equity bear regime — which would invalidate the whole insurance thesis.
2. **2024-2026 JPY weakening trend (USDJPY 150+).** Any short-JPY-cross bias will bleed in this regime because the secular trend is JPY-down regardless of equity action.
3. **Single-event 2020 sample.** With only one clean COVID-style stress in the window, the 2020-Q1 Sharpe is N=1. Could easily be a fluke.
4. **NZDJPY vs AUDJPY vs USDJPY are correlated but not identical.** If only one of three works, mechanism is suspect.

## Phase 1 → Phase 2 plan

- [x] Read short_tsmom REJECT + RESEARCH_NOTES lesson #34
- [x] Confirm FX data on disk (NZDJPY, CADJPY D1; AUDJPY/USDJPY H1)
- [ ] Build demo with 4 regime triggers × 2-4 pairs
- [ ] Baseline run with V4 (union) trigger
- [ ] Stress-window decomposition: 2020-Q1, 2022, 2024-2026
- [ ] Cost sweep
- [ ] Null check: long-side same trigger (must underperform)
- [ ] Cross-strategy correlation to deployed book in stress windows
- [ ] Update verdict

## Files

- Thesis: this doc
- Demo: `experiments/fx_safe_haven/fx_safe_haven_demo.py`

## Phase 2 results (2026-05-18)

Universe used: NZDJPY D1, CADJPY D1 (full coverage 2018-2026). AUDJPY/USDJPY D1 datalake coverage too short for the full sample, so portfolio equal-weight ran effectively on NZDJPY + CADJPY backbone with the recent-period add-ons.

### Per-instrument baseline (V4 trigger, short pair = long JPY)
| Pair | Sharpe | Total | MDD | Trades | WR |
|---|---|---|---|---|---|
| NZDJPY | −0.43 | −22.94% | −29.79% | 39 | 33.3% |
| CADJPY | −0.23 | −14.64% | −25.11% | 39 | 43.6% |
| AUDJPY | (short coverage) | | | 0 | — |
| USDJPY | +0.07 | +0.67% | −5.52% | 12 | 41.7% |
| **PORTFOLIO** | **−0.32** | **−9.28%** | **−14.19%** | 90 | 38.9% |

### Regime breakdown (portfolio)
| Window | Sharpe | Total | Active days |
|---|---|---|---|
| W1 2018-2019 | −0.46 | −2.20% | 122 |
| **>> 2020 stress (COVID, Feb 19 → Apr 30)** | **+1.39** | +3.38% | 45 |
| W2 2020 full | +0.42 | +2.31% | 114 |
| W3 2021 | −1.20 | −0.66% | 6 |
| **W4 2022 (equity bear)** | **−0.91** | **−4.91%** | 201 |
| W5 2023-2024 | −0.77 | −3.80% | 59 |
| W6 2025-2026 | −0.03 | −0.23% | 50 |

### 2020-Q1 robustness across trigger choices
| Trigger variant | 2020-Q1 Sharpe |
|---|---|
| V1 SPX drawdown > 5% | +1.39 |
| V2 SPX rvol spike | +0.74 |
| V3 SPX < SMA-50 | +1.48 |
| V4 V1 OR V2 (baseline) | +1.39 |

3 of 4 variants exceed +1.0 in COVID — the mechanism is robust to trigger choice IN THAT REGIME.

### Null check (V4 trigger, long pair = short JPY)
| | Sharpe | Total |
|---|---|---|
| V4 short (baseline) | −0.32 | −9.28% |
| V4 long (null check) | **+0.24** | **+6.20%** |

Direction-gap = −0.55. The long-pair direction profits at the same triggers. Same QE-era pattern as short_tsmom (lesson #34): the "looks like risk-off" conditions in 2018-2026 are dominated by structural JPY-down trend driven by rate divergence + secular BoJ policy stance.

### Cost sensitivity
Sharpe goes from −0.31 (cost-zero) to −0.35 (5 bp RT). Cost is NOT the binding factor; this is a directional-signal failure, not a friction failure.

### Kill criteria
| Criterion | Bar | Result | |
|---|---|---|---|
| Full-sample Sharpe > −0.50 | ≥ | −0.32 | PASS |
| MDD < 40% | ≥ | −14.19% | PASS |
| Trades ≥ 30 | ≥ | 90 | PASS |
| **2020-Q1 stress Sharpe > +1.5** | **load-bearing** | **+1.39** | **FAIL (narrow miss)** |
| **2 of 4 triggers PASS 2020-Q1 > +1.5** | **load-bearing** | **0 of 4** | **FAIL** |
| 2022 stress Sharpe > 0 (bonus) | ≥ | −0.91 | FAIL |
| **Direction null-gap > +0.30** | **load-bearing** | **−0.55** | **FAIL** |
| 2024-2026 drag > −0.50 | ≥ | −0.36 | PASS |

## Mechanistic interpretation — why this fails

The thesis assumed the classical pre-2022 pattern: equity stress → carry unwind → JPY appreciates. This held for COVID. But in 2018-2026 the regime structure is bimodal:

1. **Liquidity-shock stress (COVID 2020)**: classical pattern holds, JPY rallies, short carry-pair wins.
2. **Rate-divergence stress (2022)**: Fed hikes aggressively while BoJ stays at zero/negative rates. The widening rate differential overwhelms the carry-unwind flow. AUDJPY/NZDJPY/USDJPY all RALLY during the equity bear. Short carry-pair loses ~5% in the year the book most needed protection.
3. **Calm regimes (2021, 2025-2026)**: JPY weakens secularly on the rate-policy difference. Even with no equity stress to trigger entries, every entry that DOES fire bleeds against the JPY-down trend.

So the regime-detection signal (SPX-based) doesn't distinguish liquidity-shock from rate-divergence stress. Both look like "equity drawdown + vol spike". Mechanism works for one, fails for the other.

The same null-check pattern as short_tsmom: at exactly the SPX-stress conditions, the LONG direction in JPY-crosses is profitable. The QE-era macro regime has SPX-stress correlated with JPY-down, not JPY-up — the opposite of the pre-2022 textbook.

## Cross-experiment lesson (logged to RESEARCH_NOTES.md)

**JPY-haven property is regime-conditional, NOT structural.** Two stress regimes in 2018-2026 produced opposite JPY behaviors: COVID 2020 (JPY rallied, classical) vs 2022 bear (JPY collapsed, anti-classical). A safe-haven hedge based on simple equity-stress detection cannot distinguish these and will catastrophically misfire in the rate-divergence regime. **Implication**: any "safe-haven" thesis in 2018+ data MUST condition on the rate-policy state, not just equity-vol state.

## Files

- Thesis: this doc
- Demo: `experiments/fx_safe_haven/fx_safe_haven_demo.py`
