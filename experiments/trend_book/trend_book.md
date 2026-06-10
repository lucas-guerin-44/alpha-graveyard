# Trend-following book — Eightcap-deployable diversified TSMOM

**Status**: COMPLETE — steps 1-2 done, 2026-05-30. **Verdict: NEGATIVE** — a
canonical 12-1 TSMOM does not clear the deploy bar on the Eightcap-tradeable
universe, and the per-sleeve diagnosis shows the deployable universe is stripped
of exactly the instruments that make trend-following work (bonds above all). Step 3
(fresh thesis) not recommended on this universe — see verdict below.
**Plan**: (1) scope the Eightcap-tradeable + swap-survivable universe [DONE below];
(2) revisit `tsmom` (24-instr long-only, Sh 0.40 / holdout 1.14) on that universe
with real swap modelled + correlation vs the current live book — its only prior
blocker (+0.69 corr with the now-retired `xs_momentum`) is moot; (3) eventually a
fresh L/S trend thesis if the revisit motivates it.

**Why trend, why now.** Trend-following holds for weeks → spread/slippage is a
rounding error (the constraint that killed the intraday/HF threads this session).
The edge is breadth + patience, not speed — the part of the field retail can
actually compete in. TSMOM is the longest-documented cross-asset anomaly (AQR
"Century of Evidence"; Moskowitz-Ooi-Pedersen 2012). Repo lessons: single-
instrument trend is fragile/one-regime (`gold_trend` REJECT #73, `btc_trend`
real-OOS −0.32); the edge lives in **diversification across low-correlated
trending markets**, and the binding constraint is the **tradeable + swap-
survivable** universe (`treasury_trend`/`softs_ensemble` blocked at broker).

## Step 1 — Universe scope (live Eightcap MT5 probe, 2026-05-30)

Source: `_scope_probe.py` against the live terminal (847 symbols, Eightcap-Demo).
Authoritative for tradeability (`trade_mode`) and financing (`swap_long/short`).
Annual % validated vs the #86 softs probe (COCOA/COFFEE/COTTON/CORN/WHEAT match
≤0.5%). **For long-only TSMOM only `swap_long` (annL%) binds.**

### Deployable for LONG-ONLY trend (FULL trade, long financing > −12%/yr)

| Class | Instruments (broker name) | annL% range | Note |
|---|---|---|---|
| **FX majors** | EURUSD GBPUSD USDJPY USDCHF USDCAD AUDUSD NZDUSD | −2.5 … +1.9 | swap-light, some +carry |
| **FX exotic** | AUDNZD NZDCAD GBPNZD AUDCAD CADJPY NZDJPY EURGBP EURNOK USDZAR | −7.3 … +1.4 | USDZAR −7.3 worst |
| **Index** | SPX500 NDX100 GER40 UK100 FRA40 JPN225 HK50 | −6.0 … +2.2 | funding drag; JPN −2.8 cheapest, FRA40 +2.2 |
| **Metals** | XAUUSD(−6.5) XAGUSD(−8.5) XPDUSD(−7.8) [XPTUSD −10.2 borderline] | −6.5 … −10.2 | meaningful long drag |
| **Softs** | COCOA(−0.1) COFFEE(+0.1) LDSUGAR(−0.3) WHEAT(−11.6) | ≈0 … −11.6 | cocoa/coffee/sugar ≈ FREE |
| **Country ETF** | EWZ (−6.8, INT_CURR) | −6.8 | only EWZ survives |

### Excluded — swap-dead or not tradeable

| Instrument | Reason |
|---|---|
| CORN (−17.6%), COTTON (−17.1%) | swap-dead for long (confirms #86) |
| NATGAS/XNGUSD (≈ −61%/yr) | contango roll, swap-dead |
| BTCUSD / ETHUSD (−20%/yr, INT_CURR) | crypto CFD financing brutal for long-only; **short side pays +5%** (relevant only for a L/S thesis) |
| EWJ (EWJUSD) | **CLOSE-ONLY** trade mode — cannot open |
| FXI, AUS200, SOYBEAN, WTI/XTIUSD/XBRUSD | NOT OFFERED on Eightcap |
| USOUSD/UKOUSD | offered & FULL, but probe annL% (+31%) is a units artifact — **swap sign/size needs manual verification before inclusion** |

### Scope takeaways

1. **FX is the swap-survivable backbone** — 16 tradeable crosses, mostly |swap|
   < 4%/yr with some positive carry. This is exactly what real trend books lean
   on, and it's the cleanest deployable diversification here.
2. **Cocoa/coffee/sugar are ~free-swap** trend candidates (but only 3 names;
   the rest of ags are swap-dead — re-confirms #86).
3. **Indices + metals are usable with a −3% to −10%/yr funding hurdle** — trend
   must clear financing; include but expect the drag to bite flat-trend years.
4. **Crypto is long-only-hostile (−20%/yr)** but **short-favourable (+5%)** — park
   for a potential L/S thesis (step 3), not the long-only revisit.
5. **Deployable long-only universe ≈ 30 names**: 16 FX + 7 index + 3–4 metals +
   3 softs + EWZ. A material, genuinely diversified set — bigger than the prior
   `tsmom` 24 once FX breadth is added, and all broker-confirmed.

## Step 2 — tsmom revisit (RESULTS, 2026-05-30)

`tsmom_revisit.py` — fully-vectorized (no per-bar/per-instrument hot loop; 30
instruments × 3,605 dates in 0.4s), no-leak (traded position = `position.shift(1)`;
momentum = `close.shift(21)/close.shift(252)`), per-instrument swap modelled on
both legs. 30/32 loaded (HK50 not in lake; COFFEE thin — Eightcap CFD is recent;
USDCAD/AUDUSD/NZDUSD backfilled via MT5 to 2015).

### Headline (EW portfolio, swap ON)

| Mode | full Sh | null-gap | B&H-gap | 2015-18 | 2019-20 | 2021-22 | 2023-26 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Long-only** | **+0.36** | +0.05 | **−0.42** | −0.13 | −0.48 | +0.28 | +1.31 |
| **Long/short** | **−0.21** | +0.28 | n/a | −0.47 | −1.39 | +0.07 | +0.69 |

- **Long-only fails the lesson-#73 B&H gate** (Sh +0.36 vs EW B&H +0.79) with
  null-gap +0.05 → it's a **long-risk-beta proxy**, not trend alpha. B&H harvests
  the same beta more cheaply.
- **Long/short is net-negative (−0.21)** — more directional content (null-gap
  +0.28, so the signal *is* real) but it loses money, devastated in the 2015-2020
  trend winter (2019-20 Sh −1.39) and only positive 2023-26.
- **Swap haircut −0.26 (long) / −0.32 (LS)**; even swap-OFF, LS is only +0.11.

### Per-sleeve diagnosis (why it fails)

| sleeve | n | long-only Sh | LS Sh | LS 2023-26 |
|---|---:|---:|---:|---:|
| **FX (scoped "backbone")** | 16 | +0.06 | **−0.33** | −0.17 |
| INDEX | 6 | +0.34 | +0.04 | +0.92 |
| METALS | 4 | +0.32 | −0.02 | +0.85 |
| SOFTS | 3 | +0.47 | +0.35 | +0.94 |

1. **FX trend is dead** (LS −0.33; the post-2015 central-bank vol-suppression
   drought). The swap-survivable backbone has no trend edge.
2. **Index/metals "trend" is long-beta, not timing** — long-only +0.3 but LS ≈ 0.
   The positive long-only Sharpe is the 2023-26 bull (LS_23-26 +0.9), not the
   signal. Strip the beta and there's nothing.
3. **Softs is the only faint real L/S signal (+0.35)** but it's 3 names and
   already rejected for Eightcap (#86). Not a book.
4. Everything concentrates in 2023-26 (the bull confound, repo-wide).

## Verdict

**NEGATIVE — canonical TSMOM is not deployable on the Eightcap CFD universe.**
Trend-following isn't wrong in general (it's one of the most robust anomalies);
the problem is **the deployable-on-Eightcap universe is stripped of trend's
essential diversifiers**: no bonds (the single biggest TSMOM contributor —
`treasury_trend` Sh 0.67 but no Eightcap CFD), no energy complex, grains
swap-dead. What survives — FX (dead trend), index/metals (long-beta only), 3 softs
(too thin) — cannot assemble a trend book. This is the trend analogue of #86
(an ensemble doesn't survive restriction to the tradeable subset when the edge
lived in the un-tradeable names) and extends #73 (single/thin retail-CFD trend
= one-regime beta).

**Step 3 (fresh L/S thesis) NOT recommended on this universe** — the per-sleeve
diagnosis shows no sleeve has a deployable, non-beta, non-bull-concentrated trend
edge to build on. The honest path to real trend exposure needs bonds + a broad
futures complex (IBKR/futures, not Eightcap CFD) — a structural broker decision,
not a strategy tweak. The `tsmom` research stays KEEP_FOR_REFERENCE; only its
*Eightcap deployability* is rejected here.

## Files
- `trend_book.md` — this doc.
- `_scope_probe.py` — live Eightcap tradeability + swap probe (re-runnable).
- `tsmom_revisit.py` — vectorized swap-modelled long-only + L/S revisit.
- `tsmom_revisit_daily.csv` — saved daily returns (for any future corr-vs-book).

## Files
- `trend_book.md` — this doc.
- `_scope_probe.py` — live Eightcap tradeability + swap probe (re-runnable).
