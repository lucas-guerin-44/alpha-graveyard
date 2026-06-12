# xau_break_retest_h1 — Deploy procedure

**Target:** deploy to MT5 VPS as paper this morning, before NY 12:00 UTC.
**Status:** Phase 2-3 PASS (all 6 controls, see `xau_break_retest_h1.md`).

This deploy is **additive** — it does NOT touch the deployed `xau_break_retest_m15`. The new H1 EA defers to the M15 (asymmetric coordination via `XAUCoordinator.mqh`).

## Pre-flight (5 min — do these BEFORE compiling)

### 1. Confirm Eightcap MT5 account is in HEDGING mode
- In MT5 terminal: **Tools → Options → Account** OR look at the account summary panel.
- Look for `Account Type: Hedging` (NOT `Netting`).
- If Netting: STOP. Hedging is required because H1 and M15 strategies may simultaneously hold positions in opposite directions on XAU.
- (Eightcap CFD accounts default to hedging — but confirm.)

### 2. Confirm margin headroom
- Current deployed XAU strategy uses 0.50% per trade risk-sized lots.
- New H1 EA also uses 0.50% — worst case (M15 long + M15 short + H1 leg, capped at 3 positions) = ~1.5% account at risk.
- Eightcap XAUUSD margin requirement is typically 1% (100:1 leverage) — three concurrent positions of ~0.02-0.05 lot would use ~0.6-1.5% margin. Confirm account has >5% free margin as buffer.

### 3. Confirm spread on the live VPS terminal
- Open the XAUUSD M1 chart, watch the spread for 30 seconds during a quiet moment.
- Should be **~0.16 pt 99.9% of the time** per your earlier confirmation.
- If consistently > 0.30 pt: pause deploy and revisit C3.

## Compile + deploy (your steps)

### 4. Compile `xau_break_retest_h1.mq5`
- MetaEditor → open `deploy/mq5/xau_break_retest_h1.mq5` → F7 (Compile)
- The include path is `deploy/mq5/include/XAUCoordinator.mqh` (relative) — MetaEditor needs that subdirectory present alongside the .mq5 file.
- 0 errors expected. Compile warnings about unused `barOpen` / `barMinUtc` are fine (those are in the M15 sibling too).

### 5. Transfer to VPS
- Copy the compiled `xau_break_retest_h1.ex5` to the VPS MT5 instance's `MQL5/Experts/` directory.
- Also copy `xau_break_retest_h1.mq5` (source) so the VPS can recompile if MT5 build version changes.
- Also copy `deploy/mq5/include/XAUCoordinator.mqh` to the VPS's `MQL5/Include/` directory (this is where MetaEditor looks for relative includes by default — or to `MQL5/Experts/include/` matching the source layout).

### 6. Refresh MT5 Navigator
- In the VPS MT5 terminal: View → Navigator → right-click "Expert Advisors" → Refresh.
- `xau_break_retest_h1` should appear in the EA list.

### 7. Attach to chart
- Open a **XAUUSD H1** chart (NOT M15 — the EA refuses to attach otherwise).
- Drag `xau_break_retest_h1` from Navigator onto the chart.
- Settings dialog:
  - **Common tab**: tick "Allow Algo Trading", tick "Allow modification of Signal settings"
  - **Inputs tab**: defaults are correct for deploy. Confirm:
    - `InpMagicNumber = 42009`
    - `InpCommentTag = "XAUBRH1"`
    - `InpSessionStartHourUTC = 12` / `InpSessionEndHourUTC = 18` / `InpEntryCutoffHourUTC = 18`
    - `InpSwingLookbackBars = 4` / `InpRetestWindowBars = 1` / `InpTimeExitBars = 2`
    - `InpUseRiskSizing = true` / `InpRiskPercent = 0.50`
- Click OK. Confirm the smiley face appears in the chart's top-right (= EA active).

## Post-attach verification (do this NOW)

### 8. Verify init log
- Open the Experts log tab (bottom of MT5).
- You should see, within 2 seconds of attachment:
  ```
  [XAUBRH1] Initialised. Symbol=XAUUSD Session=12:00-18:00 UTC EntryCutoff=18:00 UTC
  [XAUBRH1] Params: swing=4bars retest=1bars tol=0.30*ATR stop=1.20*ATR ATR(14) time_exit=2bars sizing=RISK 0.50% equity (cap 0.50 lots)
  [XAUBRH1] Direction = FADE (short the up-retest, long the down-retest)
  [XAUBRH1] XAU coordinator cap = 3 simultaneous registered XAU positions
  [XAUBRH1] XAU_open total registered positions: N / cap 3
  [XAUBRH1] Symbol specs: tick_size=... vol_min=0.01 ...
  [XAUBRH1] Time check: server=... UTC=... server_offset_from_UTC=+2.0h (or +3.0h in summer)
  [XAUBRH1] Session 12-18 UTC = ~14-20 server time (or 15-21 in summer)
  ```
- **Critical to confirm**:
  - `server_offset_from_UTC = +2.0h or +3.0h` (Eightcap is EET/EEST). If it shows +0.0h or +1.0h, broker server timezone is unexpected — pause deploy.
  - `XAU_open total registered positions: N / cap 3` — N should be 0 (or whatever the M15/xau_session currently hold).

### 9. Confirm no stale state
- Tools → Options → Expert Advisors → ensure "Disable algo trading when the account has been changed" is unchecked (or the EA may pause silently after a reconnect).
- Confirm "Allow Algo Trading" is enabled globally (top toolbar button — should be GREEN, not red).

## Day 1 monitoring (today)

### 10. First-trade watch (NY session 12:00-18:00 UTC)
- Today's NY 12:00 UTC is **14:00 Berlin** (winter EET) or **15:00 Berlin** (summer EEST).
- Watch the Experts log for either of these patterns within the session:
  - `[XAUBRH1] UP break armed @ ... close=... > swing_high=...` → break detected
  - `[XAUBRH1] DOWN break armed @ ... close=... < swing_low=...` → break detected
  - `[XAUBRH1] SHORT (up-retest fade) ... lots @ ...` OR `[XAUBRH1] LONG (down-retest fade) ...` → entry
- If the session passes (18:00 UTC) with **no break detected**, that's normal — the strategy averages ~2-3 trades/week.
- Force-flat at 18:00 UTC: should see `[XAUBRH1] Exit ... reason=session_end` if a position was open.

### 11. Cross-check the M15 EA still works
- The M15 EA is untouched but they share the XAU instrument. Open the Experts log filtered for `[XAUBR]` (NOT XAUBRH1) — its 13-15 UTC NY-AM trades should still appear as before.
- If M15 stops trading after attaching the H1 EA: something coordinator-related is wrong. Detach H1 and investigate.

### 12. Daily report includes new tag automatically
- The `deploy/vps/report_mt5.sh` cron job (21:00 Berlin Mon-Fri) parses logs for `[TAG]` patterns and auto-discovers strategies — `XAUBRH1` will appear in tomorrow's report with no changes needed.

## Weekly review (next Friday)

### 13. Confirm cadence and PnL direction
- Expected: ~2-3 H1 trades this week (Mon-Fri).
- Expected per-trade gross magnitude: ~3.5 bp = ~$1/lot on a 0.05-lot trade ≈ small but consistent.
- Mode of failure to watch for: coordinator blocks > 50% of H1 entries (would indicate cap is too tight; relax to 4 in `XAUCoordinator.mqh`).

### 14. If clean after week 1, deploy phase 2
- Retrofit `xau_break_retest_m15.mq5` to include the coordinator (symmetric coverage). Single 2-line patch:
  - Add `#include "include/XAUCoordinator.mqh"` near the top
  - Add `if(!XAU_ExposureCapOK(InpMagicNumber)) { ... ; return; }` immediately before each `trade.Sell` / `trade.Buy` call
- This is a low-risk patch — the cap is loose enough that the M15 won't notice in normal operation, only on rare 3+-concurrent-position days.

## Rollback plan (if anything breaks)

- **EA fails to attach**: check the log error. `INIT_PARAMETERS_INCORRECT` = wrong chart timeframe or symbol. Re-attach to a fresh XAUUSD H1 chart.
- **EA blocks every entry**: the coordinator cap may be wrongly counting zombie positions. Restart MT5 terminal — `XAU_CountOpenXauPositions()` rebuilds from broker state.
- **Unexpected trade direction or size**: detach immediately. Open positions remain (no close-on-detach behavior) — close manually if needed. Investigate before re-attaching.

## Files involved (deployment artifacts)

- `deploy/mq5/xau_break_retest_h1.mq5` — new EA source
- `deploy/mq5/include/XAUCoordinator.mqh` — shared coordinator (new)
- `deploy/mq5/xau_break_retest_m15.mq5` — **untouched** in this deploy (phase 2 patch later)

## Magic-number registry (single source of truth: `XAUCoordinator.mqh`)

| EA | Magic |
|---|---|
| xau_session | 42003 |
| xau_break_retest_m15 | 42008 |
| **xau_break_retest_h1** (new) | **42009** |
| Future XAU strategies | 42010+ |

## Phase 4 follow-up (not blocking today's deploy)

- Real-tick spread audit on Eightcap M1 over 12-18 UTC window (C3 PASSES at confirmed 0.16pt, but a 30-day on-VPS audit would formally close out C3)
- Block-bootstrap on H1 trades using the actual broker fill prices once 4+ weeks of paper data exist (vs the simulated fills in research)
- Add to `portfolio_risk_parity` overlay as 9th component (quarterly rebal — next scheduled rebal date TBD)
