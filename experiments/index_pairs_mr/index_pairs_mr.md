# Cointegrated index/metal pair spread-MR — REJECT

**Status**: COMPLETE 2026-05-30. **Verdict: REJECT.** The one Eightcap-native
non-structural family left untested (market-neutral spread reversion) — and it
fails the cointegration prerequisite. The screen's 3 apparent "passes" are
artifacts that don't survive scrutiny.

> **Why it was worth testing:** the live book is entirely directional/time-conditioned;
> a market-neutral spread-MR sleeve would be genuinely orthogonal. And the family
> wasn't truly in the graveyard — `equity_pairs` tested single STOCKS (decayed),
> `cross_asset_lead_lag` tested TIMING (HFT-arbed), `eth_btc_ratio` was crypto
> re-rating. Cointegrated liquid INDEX/METAL pairs (β-hedged log-spread reversion
> over days) was untested. Pre-stated prior: **low**.

## Method

β-hedged log-spread `logA − β·logB` (β = rolling 120d OLS, lagged); rolling 60d
z-score (lagged); enter −sign(z) at |z|≥2, exit at |z|≤0.5; daily P&L =
`pos_{t-1}·(retA − β_{t-1}·retB)` net of **both legs'** cost. Half-life from AR(1)
of the spread = cointegration/MR prerequisite check. Null = fade→momentum.
8 pairs, D1 2018–2026.

## Results

| pair | half-life (d) | trades | Sh full | null Sh | gap | HO Sh |
|---|---:|---:|---:|---:|---:|---:|
| GER40/EUSTX50 | 513 | 44 | −0.02 | +0.01 | −0.03 | +1.03 |
| SPX500/NDX100 | 1270 | 47 | −0.29 | +0.26 | −0.55 | −0.40 |
| GER40/FRA40 | 493 | 35 | −0.15 | +0.14 | −0.29 | +0.39 |
| EUSTX50/FRA40 | 754 | 45 | −0.01 | −0.03 | +0.02 | +0.15 |
| XAUUSD/XAGUSD | 596 | 56 | −0.29 | +0.28 | −0.56 | −0.48 |
| UK100/EUSTX50 | 464 | 42 | +0.34 | −0.37 | +0.71 | +0.88 |
| SPX500/GER40 | 495 | 43 | +0.75 | −0.77 | +1.51 | +0.63 |
| NDX100/GER40 | 561 | 49 | +0.48 | −0.49 | +0.97 | +0.29 |

## Why the 3 "passes" are artifacts (REJECT)

1. **Half-lives 464–1270 days → no pair is cointegrated at a tradeable horizon.**
   A real cointegrated spread reverts in days–weeks. ~495d means the spread is a
   near-random-walk; the apparent "reversion" is the **60d rolling z mechanically
   normalizing a drifting spread**, not genuine MR (a classic rolling-z-on-
   non-stationary trap). The cointegration prerequisite fails for ALL pairs.
2. **The genuinely-related pairs show nothing.** GER40/EUSTX50 (shared
   constituents), SPX/NDX, XAU/XAG — same-currency, same-region — are flat-to-neg
   with **negative null-gaps (momentum, not MR)**. Where cointegration *should*
   exist, there's no tradeable spread reversion.
3. **The "passers" are confounded + unstable.** SPX/GER, NDX/GER, UK/EUSTX are
   cross-region/cross-currency — the apparent edge is a low-freq US-vs-EU relative
   bet with embedded EURUSD the backtest under-models, **thin (~5 trades/yr, ~40
   total)**, and **regime-decaying**: SPX/GER +1.15/+1.01 (2018–22) → **+0.12**
   (2023–24); NDX/GER **inverts to −0.72** (2023–24). Worked-pre-2022-then-died.

## Verdict

**REJECT — no deployable cointegration spread-MR on Eightcap index/metal pairs.**
Confirms the low prior. With this, the non-structural Eightcap-native space is
also mapped: persistent premia (trend/carry/vol) blocked or decayed, intraday-MR
efficient, pairs/cointegration rejected. Remaining EV is a **broker change**
(IBKR/futures → trend + cross-sectional + real bonds) or **optimizing the existing
book**, not another Eightcap idea-hunt.

## Files
- `index_pairs_mr_demo.py` — β-hedged spread-MR screen + half-life check.
