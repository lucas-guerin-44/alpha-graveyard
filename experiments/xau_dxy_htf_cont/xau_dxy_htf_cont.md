# DXY-breakout → XAU inverse-continuation (H1/H4) — higher-TF price test

**Status (2026-06-01):** **REJECT at Phase 0.** No Phase 1 built. Tombstoned to
STATE_GRAVEYARD. (Prior was LOW; confirmed.)

**Verdict summary (2026-06-01):** REJECT. The LOW-prior red flags were correct —
the inverse-continuation is **just gold momentum** (own-momentum gate fails) and a
**W4 gold-bull artifact** (W3 negative). Real USDX, H1 corr −0.406 / H4 −0.408.

**Headline failures:**

1. **Below the magnitude floor.** Best signed cell is **+3.0 bp** (H1, k=6,
   mag70, h=12, t=+3.12); nothing reaches the **+5 bp** floor. The many
   statistically-significant H1 short-k cells (t=2-4) are all **+0.4 to +3.0 bp**
   — at or barely above the 2 bp RT cost, not a tradeable per-trade edge. (Sec 3)
2. **Own-momentum gate FAILS — it's gold momentum, not a DXY edge.** At H1
   (k=12, h=3) the DXY-direction forward spread is +3.5/**t+3.38 ONLY in the
   "gold already fell" tercile**; it's −0.5 and −1.0 (negative) in the flat and
   "gold rose" terciles. Hold gold's own prior move fixed and the DXY signal
   **vanishes/inverts**. At H4 the spread is **negative in all three terciles**
   (−4.8 / −3.1 / −1.9). This is `gold_trend` (#73) in a dollar costume. (Sec 4)
3. **W4-only — W3 actively loses.** W3 (2022-23, the persistent dollar-strength
   hiking regime — exactly where inverse-continuation *should* be strongest) is
   **negative across all horizons** (H1 h12 −3.4/**−3.36**; H4 h6 −3.9/−1.47).
   All positive signal is W4 (2024+ gold bull). Same **bullrun-isolation**
   confound as `xau_dxy_stall` / `xau_dxy_comove_fade` / `xau_asia_range`. (Sec 6)
4. **Direction null trivial.** Cont-minus-rev gap is mechanically 2× the (tiny,
   sub-bp) signed mean — no meaningful directional content at the mag70 cell. (Sec 5)

**Mechanistic interpretation:** a DXY H1/H4 breakout coincides with XAU having
already moved inversely; the apparent "continuation" is gold's own momentum
continuing, with **zero incremental information from the dollar leg** once gold's
prior move is conditioned out. Higher TF did not rescue the family — it made the
gold-beta confound *more* visible (the own-momentum gate is cleaner at H1/H4 than
the M5 stall framing allowed). The 2022-24 gold/real-rate decoupling shows up
directly as the negative W3.

**Family conclusion — DXY–XAU price family CLOSED.** Three independent price
angles now reject, all on the same two confounds (gold-beta/momentum +
W4-bull-isolation), across M5 / H1 / H4 with real USDX:
`xau_dxy_stall` (stall-reversal) · `xau_dxy_comove_fade` (co-move-reversion) ·
`xau_dxy_htf_cont` (HTF-continuation). Any future DXY-positioning XAU signal
needs a **non-price, lower-frequency trigger** (CFTC TFF positioning, 10Y real
rates, ETF flows) — not intraday/HTF CFD price.

## Origin

Third and final price-based angle on the DXY–XAU pair, after two intraday
rejects:
- `xau_dxy_stall` — momentum-stall *reversal* (REJECT; found DXY–XAU *continues*
  at M5 in the mechanism-strong cells, not reverts).
- `xau_dxy_comove_fade` — co-move-breakdown *reversion* (REJECT; real USDX, W4
  gold-bull artifact, sub-cost).

Both reversion framings died. The one price test never run: the *continuation*
that `xau_dxy_stall` actually pointed at, at a **higher timeframe** (H1/H4) where
the slower real-rate/dollar anchor that drives the inverse has time to act.

## Thesis (mechanism)

1. **DXY and XAU are structurally inversely correlated** via the real-rate /
   dollar-funding channel — a daily/weekly force, too slow to resolve on M5
   (that frequency mismatch is why the intraday angles failed).
2. **At H1/H4 a directional DXY breakout signals a dollar trend leg with
   real persistence** (macro flows, CB-FX, positioning build slowly).
3. **XAU continues in the inverse direction over the next few H1/H4 bars** as
   the real-rate channel transmits the dollar move into gold.
4. **Trade XAU inverse to the DXY breakout:** DXY breaks UP → SHORT XAU; DXY
   breaks DOWN → LONG XAU. XAU is the tradeable; USDX is read-only signal.

## The load-bearing gate (why this probably fails)

This is mechanically **"DXY momentum → XAU inverse momentum."** Because DXY and
XAU co-move inversely *contemporaneously*, a DXY breakout almost always coincides
with XAU having ALREADY moved the inverse way. So the real question is **not**
"does XAU continue after a DXY breakout" (it trivially might, via gold's own
momentum) but **"does the DXY breakout add forward predictive power BEYOND XAU's
own prior move?"** If, after conditioning on XAU's own prior-k return, the DXY
signal adds nothing, this is just `gold_trend` (XAU TSMOM = passive beta, already
REJECT #73) wearing a dollar costume.

## Key reference

- `xau_dxy_stall.md` (DXY–XAU continues, not reverts, at short horizons),
  `gold_trend.md` (XAU directional momentum = passive bull beta, fails B&H + null).
- Erb & Harvey (2006) — gold's dollar/real-rate beta.

## Signal math

For TF ∈ {H1, H4}, lookback `k` bars, forward `h` bars:
```
dxy_mom  = sign(log USDX[t] - log USDX[t-k])        # breakout direction
mag      = |log USDX[t] - log USDX[t-k]|            # bucket by pctile
xau_own  = log XAU[t] - log XAU[t-k]                # gold's OWN prior move
signal   = -dxy_mom                                 # inverse-continuation
fwd[h]   = signal * 1e4 * (XAU[t+h]/XAU[t] - 1)     # bps
```
Sweeps: TF {H1, H4}, k {6,12,24} (H1) / {3,6,12} (H4), mag-pctile {0,50,70},
h {1,2,3,6,12}.

**Own-momentum control:** within terciles of `xau_own`, split by `dxy_mom` sign
and measure forward XAU. The DXY effect = within-bucket (DXY-down minus DXY-up)
forward XAU spread. Must be > 0 and significant *inside* the buckets.

## Universe

- Trade leg: XAUUSD CFD (Eightcap, 2 bps RT research cost; deploy analog spot gold).
- Signal leg: USDX M5→H1/H4.
- Window: 2021-06-10 → 2026-06-01 (USDX coverage), tail-W2 / W3 / W4. W4 binding.

## Expected performance

If real, expect signed forward XAU mean +5 to +15 bps at H4 1-3 bar horizons
(larger per-trade than M5 given the holding period), decaying past ~24h. Cadence
modest (breakout events ~100-400/yr depending on mag filter).

## Fail conditions (pre-committed)

Phase 0 PASS (→ build Phase 1) requires **all**:

- **≥1 (TF, k, mag, h) cell**: signed mean **≥ +5 bps** (higher floor than M5 —
  holding cost/overnight swap at H4) AND **t ≥ +2.0** AND cell n ≥ 150.
- **Own-momentum gate (load-bearing):** within ALL THREE `xau_own` terciles, the
  DXY-direction forward-XAU spread is **≥ +3 bps AND t ≥ +1.8**. If the DXY
  effect lives only in the bucket where gold already moved (i.e. vanishes once
  gold's own momentum is held fixed) → REJECT, it's `gold_trend`.
- **Direction null-check:** inverse-continuation beats inverse-reversal (gap > 0).
- **Persists W3 AND W4** (not single-window; W4 = 2024+ binding).
- **Beats XAU buy-and-hold-inverse-to-DXY baseline** per #73 discipline (a
  signed-drift control: always-short-XAU-on-up-days style baseline).

If only some clear → MARGINAL, no Phase 1. If none → REJECT, tombstone.

## Why this might fail (red flags)

- **It's gold momentum in disguise** (the own-momentum gate is built to catch
  exactly this; `gold_trend` #73 already rejected XAU directional momentum).
- **Higher TF is MORE arbed** — daily/weekly DXY–XAU inverse is the most-watched
  macro relationship in the asset; no retail edge in "gold up when dollar down."
- **2022-24 gold/real-rate decoupling**: the macro anchor structurally weakened
  in the holdout (CB reserve buying overrode the TIPS channel) → W4 may invert.
- **Continuation ≠ persistence**: a DXY H1 breakout may already be exhausted by
  the time the bar closes (same arb logic as `cross_asset_lead_lag`).

## Phase 0 → Phase 1 plan

- [x] Phase 0 profile (`_profile_htf_cont.py`) — ran 2026-06-01, **REJECT**
- [ ] ~~Phase 1 simulator~~ — not built (own-momentum gate failed)
- [ ] ~~Phase 2-5 battery~~ — n/a

## Files

- `xau_dxy_htf_cont.md` — this doc
- `_profile_htf_cont.py` — Phase 0 higher-TF continuation profile
