# Safe-haven risk-off tail-hedge — Phase 1/2 thesis

**Status**: Phase 1/2, 2026-05-29. The cross-asset (#2) sibling of `ndx_trend_day` — same NDX risk-off
trigger, expressed through a **different-axis vessel** (gold / JPY / CHF) for genuine book-diversification.
**Verdict (2026-05-29): REJECT — cross-asset safe-haven hedges are regime-broken post-2022.**
- **XAU** (long): Sh −0.23, **placebo FAIL** (+1.22 bp on risk-off vs +1.70 bp normal — gold does *worse*); W1 −1.75 / W2 −0.70 = rate-shock-regime failure.
- **USDJPY** (long JPY): Sh **−2.77**, placebo FAIL — long-JPY-on-risk-off *loses* across all regimes. Post-2022 the Fed/BoJ rate differential overrode JPY's haven role. **Re-confirms lesson #35 decisively.**
- **USDCHF** (long CHF): tail-sign *correct* (placebo +0.66 bp, corr→book +0.05, **+0.44 bp on book's worst days**) but standalone-negative (Sh −0.60) + thin (n=228, no W1) → **not deployable** (a net-losing hedge with a tiny worst-day payoff).

**Conclusion:** express the equity-risk-off tail-hedge via the *equity instrument itself* (`ndx_trend_day`
continuation), NOT cross-asset havens — gold/JPY are regime-broken, CHF too weak/thin. Validates the deployed
`ndx_trend_day` as the right tail-tool. See RESEARCH_NOTES lesson #89.

## Thesis (mechanism)

1. The book's worst days are US-equity **risk-off** sessions (sharp down + vol spike). On those days capital
   flees to **safe havens** — gold (XAU), JPY (USDJPY ↓), CHF (USDCHF ↓).
2. So: use the **same trigger** that `ndx_trend_day` shorts on — an NDX **down-vol-expansion** morning — but
   instead of shorting NDX, go **long the safe-haven** for the rest of the session. Different *instrument/axis*
   (cross-asset flight-to-safety, not intraday equity momentum) → should be book-anti-correlated.
3. **Early-commit** (lesson #88): enter at 10:30 ET as the risk-off is underway, hold to 16:00 — positioned
   *during* the flight, not confirming it late. On the book's worst (persistent-risk-off) days the haven keeps
   rallying → tail-CONVEX; the haven's bad case (equity recovers intraday) coincides with the book's *good* days.

## Signal math

```
Trigger (NDX100 M5, ET): OR=09:30-10:30. or_range_pct > median(trailing-20d)  AND  thrust = (OR_close-OR_open) < 0   ⇒ RISK-OFF day.
On triggered days, enter the safe-haven at 10:30 ET, exit 16:00 ET:
   XAU   : LONG   (dir +1)
   USDJPY: SHORT  (dir -1, = long JPY)
   USDCHF: SHORT  (dir -1, = long CHF)
ret = dir*(SH_close - SH_1030)/SH_1030 - cost.   cost: XAU 2bp / FX ~1bp.
```

## Universe / why retail-accessible

NDX100 (trigger) + XAUUSD / USDJPY / USDCHF (Eightcap, all cached). Test all three; pick the best-complementing
(XAU risks redundancy with `xau_session`; JPY/CHF add a new asset the book barely has).

## Expected performance (prior)

Unknown — the safe-haven↔equity link is **regime-unstable** (gold sold off *with* equities in the 2022
fast-hike regime). Honest prior: it may only work in flight-to-safety regimes, not rate-shock ones. Sh −0.2 to
+0.6. The bar is tail-complement, not standalone.

## Fail conditions (pre-committed — FROZEN)

1. Sharpe ≤ +0.30 after cost.
2. MDD ≥ 25%.
3. W3 holdout ≤ 0 (regime check; flag if it's a single-regime artifact).
4. Trades < 80.
5. **Placebo**: safe-haven mean return on triggered (risk-off) days minus on non-triggered days ≤ 0 (if the haven moves the same regardless, the risk-off trigger has no content).
6. **Tail-complement (load-bearing, lesson #88)**: FAIL if corr to book > +0.10 **or** mean return on book's worst-decile days ≤ 0. (Gold vessel also: corr to `xau_session` < +0.5, else redundant.)

PROCEED only if standalone (1-5) AND complement (6). Report per-vessel + corr to existing book legs.

## Why this might fail

- Gold-equity correlation flips positive in rate-shock regimes (2022) → the hedge fails exactly when rates drive the selloff.
- XAU may be redundant with the deployed `xau_session`.
- Late-ish entry (10:30, after the open move) may miss the bulk of the flight — early-commit caveat.

## Files

`safe_haven_riskoff_demo.py` (NDX trigger → 3-vessel sim + regime + placebo + tail-complement vs book).
