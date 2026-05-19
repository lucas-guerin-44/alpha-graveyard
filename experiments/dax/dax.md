# DAX-focused strategy research

Rationale: across three distinct intraday theses (ORB, z-score MR, EOD-unwind), DAX is the one index where mechanisms consistently show directional content — traced to its single-venue auction structure (Xetra open 09:00, close 17:30), absence of a 0DTE-options ecosystem, moderate retail leverage, and the 15:30-17:30 Berlin overlap with NY RTH. This folder explores four untested angles that exploit that structure directly.

All four follow the same methodology — numpy inner loop, pre-committed kill criteria, regime breakdown (2019-2020 / 2021-2022 / 2023-2026 holdout), cost sensitivity (0.5/1.0/2.0/3.0 pt RT), null-check.

| Strategy | Mechanism | Baseline Sh | Holdout Sh | Verdict | File |
|---|---|---|---|---|---|
| Pre-auction drift | Institutional pre-close rebalance flow concentrates in 17:10-17:30 Xetra auction window | −0.66 | −1.18 | **REJECT (inverted)** | [pre_auction.md](pre_auction.md) |
| Overnight drift capture | Passive always-long 17:25 → 09:00 to quantify the DAX overnight premium | +0.80 research / **−0.34 QC futures** | — | **REJECT — CFD-data artifact, exposed by QC validation** | [overnight.md](overnight.md) |
| US → DAX lead-lag | SPX first-15-min-of-RTH signal traded on DAX 15:45-17:15 Berlin overlap | −0.48 | −0.45 | **REJECT (inverted)** | [us_lead.md](us_lead.md) |
| Gap fade | Xetra open auction overshoots on macro-news gaps, first-hour fills the gap | −1.04 | −1.25 | **REJECT (inverted)** | [gap_fade.md](gap_fade.md) |

## Phase 2 summary (2026-04-20)

Three of four tombstone as REJECT with null-check inversion — each null direction weakly wins, none tradeable:
- **Pre-auction**: DAX mean-reverts the prior 60-min move rather than continuing it.
- **US lead-lag**: DAX fades the US open impulse (already arb'd by 15:45 Berlin via futures), not continuing it.
- **Gap fade**: DAX gaps continue, consistent with institutional-news-driven gaps rather than retail-panic auction overshoots.

**All four REJECT after QC validation.** Overnight-combined appeared to PASS in research (+0.80 Sharpe) but QC port to FDAX continuous futures returned Sharpe −0.34 — the CFD research edge did not survive translation to an executable futures instrument. See [overnight.md §QC futures validation](overnight.md) for the full diagnostic. Root cause: MT5 CFD provider synthesizes the overnight close-to-open return via dealer-desk quote mechanics that don't exist on futures.

**Deployment implication**: deploy ORB T+180 LONG-only standalone per [qc_orb_dax.py](../../deploy/qc_orb_dax.py) / [experiments/orb/orb.md](../orb/orb.md). No other DAX strategy from this folder clears the bar.

**Methodological lesson**: MT5-CFD research on any overnight/session-gap thesis must be cross-validated on continuously-traded futures before any deploy step. CFD synthetic quote handling over session breaks is a source of phantom alpha that Phase 2 cost sensitivity and regime breakdown do not catch.

Shared helpers live in [_common.py](_common.py) — session config, load, Sharpe, regime breakdown, kill-criteria reporting.
