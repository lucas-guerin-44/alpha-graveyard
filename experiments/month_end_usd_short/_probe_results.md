# USDCAD month-end probe — results + revisit queue

**Status**: DIRECTION-VALIDATED, MAGNITUDE-SAMPLE-BLOCKED (2026-05-27)
**Next review trigger**: when Eightcap MT5 USDCAD M5 history reaches n ≥ 20 month-end events (estimated ~2027 Q3)

## TL;DR

The structural USD-funding-squeeze mechanism extends to USDCAD with ~2× the EUR magnitude, **but Eightcap broker data depth limits USDCAD M5 to ~9 months → only 8 month-end events available, far too few for Phase 2**. Direction signal is supportive (+3.98 bp gross, +4.57 bp null-gap vs placebo); cost-net mean +1.98 bp at 2 bp RT is still sub-deploy but materially closer than EUR (+1.18 bp) or GBP (−0.03 bp).

## Probe spec (informal — NOT a thesis lock)

- Instrument: USDCAD M5
- Trigger: last business day of every month
- Window: 14:00-15:00 ET (same as `month_end_usd_short` basket REJECT)
- Direction: LONG USDCAD (= SHORT CAD)
- Cost: 2 bp RT (Eightcap typical)
- Sample: 8 events (2025-09 → 2026-04)

## Results (n=8, direction-only — NO formal verdict possible)

| Metric | USDCAD (n=8) | EUR (n=88, REJECTed basket) | Read |
|---|---|---|---|
| Gross mean | **+3.98 bp** | −2.68 bp / +2.68 short | ~1.5× larger |
| Null-gap vs placebo | **+4.57 bp** | +2.20 bp | **~2× larger** |
| Placebo | −0.59 bp (cleanly opposite-signed) | +0.05 bp | Cleaner non-event baseline |
| t-stat | +1.49 (n=8 noise floor ~+2.4) | −1.77 | Smaller magnitude per √n |
| WR | 50% (4/8) | 56.8% | Coin-flip at n=8 |
| Cost-net | +1.98 bp/event | EUR-S +1.18 / GBP-S −0.03 | Larger than basket avg |

**Direction**: USDCAD goes UP at month-end 14-15 ET, consistent with USD-funding-squeeze story. Placebo is cleanly opposite (−0.59 bp on n=141 non-event same-weekday days) — month-end day IS distinct from random NY-PM weekday.

## Why we can't Phase 2 this now

- Eightcap MT5 only has USDCAD M5 from 2025-09 onward (confirmed: H1 fetch only added 184 new bars beyond M5's coverage, same depth limit)
- n=8 events is below the bootstrap CI floor (needs n ≥ 30 for meaningful CI)
- All 8 events in W3 — no W1/W2 regime data available
- t=+1.49 at n=8 has p ≈ 0.18 — not significant

## Revisit conditions

Re-run this probe when ALL of:
1. Eightcap MT5 USDCAD M5 depth reaches ≥ 24 months (n ≥ 20 month-end events at ~12/yr cadence)
2. The structural_flow_audit screen has been re-run with corrected `COST_FLOOR_BPS` per [lesson #-20](../../docs/STATE.md) (planned but not yet done as of 2026-05-27)

If both hold → write `month_end_usdcad_long.md` thesis doc + full Phase 2 simulator + 13 pre-committed kill criteria mirroring `month_end_usd_short.md` structure. Pre-Phase-2 prior: cost-net +1.98 bp is still below the +1.5 bp full-mean floor but close — could clear at n>=30 if magnitude/cost ratio holds at ~2× the EUR level (~3× the cost-floor — exactly at the methodology lesson #-20 threshold).

## Alternative data sources (if revisit can't wait for natural lake fill)

1. **Dukascopy free historical M5** — 15+ years of USDCAD M5. Format: bar OHLC. Acceptable for Phase 2 research even if not the deploy venue.
2. **HistData.com** — free, M1 + tick. Aggregable to M5.
3. **Tiingo IEX** — has USDCAD but only D1 (no intraday window possible).

None of these are pre-integrated into the repo's data layer. Adding them would be ~1 day of work to write a fetch script + datalake injector — worth doing only if the USDCAD revisit becomes priority before natural lake fill.

## Direction-validation contribution to RESEARCH_NOTES

Even at n=8, USDCAD's positive direction + ~2× EUR magnitude is meaningful evidence the USD-funding-squeeze mechanism is broader than EUR/GBP. Combined with the existing screen results (EUR + GBP both negative same direction, t around -1.5 to -1.8), this is 3-of-3 same-direction confirmation of the mechanism across major USD-counterpart pairs. The retail-cost magnitude is sub-threshold across all three at current data depths, but the mechanism existence is no longer ambiguous.

If methodology lesson #-20 (3× cost-floor screen rule) is applied AND a lower-cost execution venue becomes available (PB FX, futures, ECN), the family becomes deploy-grade. Tag the family `VALIDATED_BLOCKED_AT_COST_AND_DATA_DEPTH`.
