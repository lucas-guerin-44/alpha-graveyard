//+------------------------------------------------------------------+
//|                                                     orb_dax.mq5  |
//| Opening Range Breakout on GER40 (DAX) M5 — LONG-only             |
//|                                                                  |
//| Research config from experiments/orb/ (2019-2026):               |
//|   OR_MINUTES           = 30       (09:00-09:30 Berlin)           |
//|   TOD_EXIT_MINUTES     = 180      (hold 3h post-entry)           |
//|   STOP                 = opposite OR boundary                    |
//|   InpLongOnly          = true     (shorts are a drag 3/3 regimes)|
//|   InpUseRiskSizing     = true     (0.25% equity risk per trade)  |
//|   InpMaxLots           = 0.5      (emergency cap, €10/pt = €500) |
//|   No take-profit. One round-trip per day (long side).            |
//|                                                                  |
//| Research results (2019-01 to 2026-04, GER40 M5, cost 1pt RT):    |
//|                                                                  |
//|   Metric              Symmetric T+180   LONG-only (this config)  |
//|   Full-sample Sharpe  +0.58             +0.76                    |
//|   2019-2020 Sharpe    +0.56             +0.94                    |
//|   2021-2022 Sharpe    +0.69             +0.44                    |
//|   2023-2026 holdout   +0.55             +0.93                    |
//|   Max DD              -10.83%           -7.77%                   |
//|   Trades/week         7.5               3.8                      |
//|   Fade-gap (1:1 RR)   +0.97             n/a                      |
//|                                                                  |
//| Drift benchmark (unconditional long 10:00-13:00 Berlin, no       |
//| trigger) 2023-2026 holdout Sharpe: +0.25. Whole-session           |
//| unconditional long 2023-2026: -0.10. ORB LONG-only holdout +0.93 |
//| minus drift +0.25 = +0.68 alpha delta — edge is NOT drift-capture|
//|                                                                  |
//| Expected live Sharpe after 50-70% haircut: +0.23 to +0.46.       |
//|                                                                  |
//| Only the 2021-2022 vol regime had symmetric long/short edge.     |
//| Shorts are logged for shadow analysis (flag off) so we can        |
//| detect a regime flip and re-enable if shadow-PnL turns positive. |
//|                                                                  |
//| IMPORTANT: Session times are in BROKER SERVER TIME, not Berlin.  |
//| Check MT5 clock (top right) vs real Berlin time, adjust the      |
//| SessionStartHour/Min inputs when attaching the EA.               |
//|                                                                  |
//| Example: if broker server = GMT and it's winter, Berlin 09:00    |
//| = server 08:00, so SessionStartHour = 8.                         |
//+------------------------------------------------------------------+

#property copyright "ORB DAX research repo"
#property version   "1.20"
#property strict

#include <Trade/Trade.mqh>

// ================================ Inputs ================================

input group "=== Session (BROKER SERVER TIME, not Berlin local!) ==="
input int      InpSessionStartHour = 8;    // Xetra 09:00 Berlin; adjust for broker server TZ
input int      InpSessionStartMin  = 0;
input int      InpSessionEndHour   = 16;   // Xetra 17:30 Berlin
input int      InpSessionEndMin    = 30;

input group "=== ORB parameters (research-frozen) ==="
input int      InpOrMinutes         = 30;  // opening range window length
input int      InpTodExitMinutes    = 180; // flat this many minutes after entry
input int      InpEntryCutoffMin    = 180; // no new entries after this many min into session
input int      InpExitBeforeCloseMin= 5;   // hard flatten this many min before session close

input group "=== Trade ==="
input bool     InpLongOnly          = true; // LONG-only per research — shorts are a drag in 3/3 regimes except 2021-2022 vol; log for shadow analysis
input int      InpMagicNumber       = 42001;
input int      InpSlippagePoints    = 50;
input string   InpCommentTag        = "ORB-DAX";

input group "=== Position sizing ==="
// Conservative defaults for a ~5k EUR account on GER40 (Germany 40 Cash).
// Broker: contract size = 10, vol_min=vol_step=0.01, vol_max=25.
// Point value = €10/pt/lot. At 0.25% risk (€12.50) and typical 50pt stop,
// raw lots = 12.50 / 500 = 0.025 -> rounds to 0.02 at 0.01 step.
// MaxLots=0.5 caps single-trade worst case at ~€500 = ~10% account with a
// 100pt stop; that's an emergency ceiling, not a normal trade size.
input bool     InpUseRiskSizing     = true;  // true = size by % of equity risked to stop; false = use InpFixedLots
input double   InpRiskPercent       = 0.25;  // % of account equity risked per trade (loss at stop)
input double   InpMaxLots           = 0.5;   // hard safety cap regardless of risk calc
input double   InpFixedLots         = 0.02;  // fallback lot size when InpUseRiskSizing=false or calc fails

// ================================ State ================================

CTrade trade;

// Per-day state (reset on new session day).
datetime g_currentSessionDate = 0;
double   g_orHigh     = 0.0;
double   g_orLow      = 0.0;
bool     g_orComplete = false;
int      g_positionSide = 0;   // -1 short, 0 flat, +1 long
double   g_entryPrice = 0.0;
datetime g_entryTime  = 0;
double   g_stopPrice  = 0.0;
bool     g_longTaken  = false;
bool     g_shortTaken = false;

datetime g_lastBarTime = 0;

// ================================ Helpers ================================

// Returns minute-of-session for the given bar time, or -1 if before session,
// or SESSION_DURATION if at/after session close.
int MinuteOfSession(datetime barTime)
{
   MqlDateTime dt;
   TimeToStruct(barTime, dt);
   int bar_mod = dt.hour * 60 + dt.min;
   int session_start = InpSessionStartHour * 60 + InpSessionStartMin;
   return bar_mod - session_start;
}

int SessionDurationMin()
{
   return (InpSessionEndHour * 60 + InpSessionEndMin)
        - (InpSessionStartHour * 60 + InpSessionStartMin);
}

datetime SessionDateKey(datetime barTime)
{
   MqlDateTime dt;
   TimeToStruct(barTime, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
}

void ResetDayState()
{
   g_orHigh = 0.0;
   g_orLow  = 0.0;
   g_orComplete = false;
   g_positionSide = 0;
   g_entryPrice = 0.0;
   g_entryTime  = 0;
   g_stopPrice  = 0.0;
   g_longTaken  = false;
   g_shortTaken = false;
}

// Risk-based lot sizing. Uses OrderCalcProfit to get broker-exact loss per
// lot for the entry->stop leg in account currency, then lots = risk / loss.
// Clamps to symbol volume min/max/step and InpMaxLots. Falls back to
// InpFixedLots if InpUseRiskSizing is false or the calc fails.
double CalculateLotSize(ENUM_ORDER_TYPE orderType, double entryPrice, double stopPrice)
{
   if(!InpUseRiskSizing) return InpFixedLots;

   double stopDistance = MathAbs(entryPrice - stopPrice);
   if(stopDistance <= 0.0)
   {
      Print("[ORB-DAX] Sizing fallback: stop distance = 0");
      return InpFixedLots;
   }

   // Probe loss for 1 lot via MT5's own calculator — handles tick-value
   // quirks for CFDs/futures without us hard-coding contract size.
   double lossFor1Lot = 0.0;
   if(!OrderCalcProfit(orderType, _Symbol, 1.0, entryPrice, stopPrice, lossFor1Lot))
   {
      PrintFormat("[ORB-DAX] Sizing fallback: OrderCalcProfit failed, err=%d", GetLastError());
      return InpFixedLots;
   }
   lossFor1Lot = MathAbs(lossFor1Lot);
   if(lossFor1Lot <= 0.0)
   {
      Print("[ORB-DAX] Sizing fallback: loss-per-lot = 0");
      return InpFixedLots;
   }

   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * InpRiskPercent / 100.0;
   double rawLots    = riskAmount / lossFor1Lot;

   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   double lots = rawLots;
   if(volStep > 0.0) lots = MathFloor(lots / volStep) * volStep;
   if(lots < volMin) lots = volMin;
   if(lots > volMax) lots = volMax;
   if(lots > InpMaxLots) lots = InpMaxLots;

   PrintFormat("[ORB-DAX] Sizing: equity=%.2f risk=%.2f%% (%.2f) stop_dist=%.2f loss/lot=%.2f raw_lots=%.3f -> lots=%.2f",
               equity, InpRiskPercent, riskAmount, stopDistance, lossFor1Lot, rawLots, lots);
   return lots;
}

// Rebuild OR high/low from historical bars of today's session up to the
// current bar. Called if EA is attached mid-session or mid-OR-window.
void RebuildORFromHistory(datetime currentBarTime)
{
   MqlRates rates[];
   if(CopyRates(_Symbol, PERIOD_M5, 0, 200, rates) < 1) return;

   datetime today = SessionDateKey(currentBarTime);
   double hi = 0.0, lo = 0.0;
   bool   any = false;
   for(int i = 0; i < ArraySize(rates); i++)
   {
      if(SessionDateKey(rates[i].time) != today) continue;
      int mod = MinuteOfSession(rates[i].time);
      if(mod < 0 || mod >= InpOrMinutes) continue;
      if(!any || rates[i].high > hi) hi = rates[i].high;
      if(!any || rates[i].low  < lo) lo = rates[i].low;
      any = true;
   }
   if(any && hi > lo)
   {
      g_orHigh = hi;
      g_orLow  = lo;
   }
}

// ================================ Lifecycle ================================

int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFilling(ORDER_FILLING_FOK);
   string sizingMode = InpUseRiskSizing
                       ? StringFormat("RISK %.2f%% equity (cap %.2f lots)", InpRiskPercent, InpMaxLots)
                       : StringFormat("FIXED %.2f lots", InpFixedLots);
   PrintFormat("[ORB-DAX] Initialised. Session=%02d:%02d-%02d:%02d (broker time), OR=%dmin, TODexit=%dmin, dir=%s, sizing=%s",
               InpSessionStartHour, InpSessionStartMin,
               InpSessionEndHour, InpSessionEndMin,
               InpOrMinutes, InpTodExitMinutes,
               InpLongOnly ? "LONG-ONLY (shorts shadow-logged)" : "BOTH (symmetric)",
               sizingMode);

   // Log symbol specs so you can sanity-check sizing math on attach.
   PrintFormat("[ORB-DAX] Symbol: tick_size=%.5f tick_value=%.5f vol_min=%.2f vol_max=%.2f vol_step=%.2f",
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));

   // Timezone diagnostic: broker server time vs UTC. Compare against your
   // wall-clock Berlin time to figure out the offset → pick InpSessionStartHour.
   // Rule: InpSessionStartHour = 9 + (broker_offset_from_Berlin_hours)
   datetime serverNow = TimeTradeServer();
   datetime utcNow    = TimeGMT();
   long     offset_s  = (long)(serverNow - utcNow);
   PrintFormat("[ORB-DAX] Time check: server=%s  GMT=%s  offset_from_UTC=%+.1fh  -> Berlin_summer_offset=%+.1fh  (set InpSessionStartHour = 9 + Berlin_summer_offset if in summer, else 9 + Berlin_winter_offset)",
               TimeToString(serverNow, TIME_DATE|TIME_SECONDS),
               TimeToString(utcNow,    TIME_DATE|TIME_SECONDS),
               offset_s / 3600.0,
               (offset_s / 3600.0) - 2.0);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   PrintFormat("[ORB-DAX] Deinit reason=%d", reason);
}

// ================================ Main loop ================================

void OnTick()
{
   // Only act on a NEW completed M5 bar (index 1 is the last-closed).
   datetime lastClosedBarTime = iTime(_Symbol, PERIOD_M5, 1);
   if(lastClosedBarTime == 0 || lastClosedBarTime == g_lastBarTime) return;
   g_lastBarTime = lastClosedBarTime;

   double barOpen  = iOpen (_Symbol, PERIOD_M5, 1);
   double barHigh  = iHigh (_Symbol, PERIOD_M5, 1);
   double barLow   = iLow  (_Symbol, PERIOD_M5, 1);
   double barClose = iClose(_Symbol, PERIOD_M5, 1);

   // ---- Session-day rollover ----
   datetime dayKey = SessionDateKey(lastClosedBarTime);
   if(dayKey != g_currentSessionDate)
   {
      g_currentSessionDate = dayKey;
      ResetDayState();
   }

   // ---- Session boundary checks ----
   int mod = MinuteOfSession(lastClosedBarTime);
   int session_duration = SessionDurationMin();
   int exit_cutoff = session_duration - InpExitBeforeCloseMin;

   if(mod < 0 || mod >= session_duration) return;     // outside RTH

   // ---- 1) OR window: accumulate high/low ----
   if(mod < InpOrMinutes)
   {
      if(g_orHigh == 0.0 || barHigh > g_orHigh) g_orHigh = barHigh;
      if(g_orLow  == 0.0 || barLow  < g_orLow ) g_orLow  = barLow;
      return;
   }

   // ---- 2) Finalise OR (if first post-OR bar and we haven't already) ----
   if(!g_orComplete)
   {
      if(g_orHigh == 0.0 || g_orLow == 0.0 || g_orHigh <= g_orLow)
         RebuildORFromHistory(lastClosedBarTime);  // attached mid-session -> rebuild

      if(g_orHigh > g_orLow)
      {
         g_orComplete = true;
         PrintFormat("[ORB-DAX] OR set: high=%.2f low=%.2f width=%.2f",
                     g_orHigh, g_orLow, g_orHigh - g_orLow);
      }
      else
      {
         g_orComplete = true;   // malformed — skip trading today
         Print("[ORB-DAX] Malformed OR (high<=low); no trades today");
         return;
      }
   }

   // ---- 3) Exit checks (if a position is open) ----
   if(g_positionSide != 0 && PositionSelect(_Symbol))
   {
      bool hitStop = false;
      if(g_positionSide == 1  && barLow  <= g_stopPrice) hitStop = true;
      if(g_positionSide == -1 && barHigh >= g_stopPrice) hitStop = true;

      bool todExit = false;
      if(g_entryTime > 0)
      {
         int heldMin = (int)((lastClosedBarTime - g_entryTime) / 60);
         if(heldMin >= InpTodExitMinutes) todExit = true;
      }

      bool forcedClose = (mod >= exit_cutoff);

      if(hitStop || todExit || forcedClose)
      {
         string reason = hitStop ? "stop" : (todExit ? "tod" : "eod");
         if(trade.PositionClose(_Symbol))
         {
            PrintFormat("[ORB-DAX] Exit side=%+d @ %.2f reason=%s (PnL on close)",
                        g_positionSide, barClose, reason);
         }
         else
         {
            PrintFormat("[ORB-DAX] PositionClose FAILED: %s", trade.ResultRetcodeDescription());
         }
         g_positionSide = 0;
         g_entryPrice = 0.0;
         g_entryTime  = 0;
         g_stopPrice  = 0.0;
         return;
      }
   }

   // ---- 4) Entry checks (only if flat and within entry window) ----
   if(g_positionSide != 0) return;
   if(PositionSelect(_Symbol)) return;   // external position open; stay out
   if(mod >= InpEntryCutoffMin) return;

   // Long on close > OR high
   if(!g_longTaken && barClose > g_orHigh)
   {
      double sl       = g_orLow;
      double estEntry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double lots     = CalculateLotSize(ORDER_TYPE_BUY, estEntry, sl);
      if(lots <= 0.0)
      {
         Print("[ORB-DAX] Skipping LONG: lot calc returned 0");
         return;
      }
      if(trade.Buy(lots, _Symbol, 0.0, sl, 0.0, InpCommentTag + "-L"))
      {
         g_positionSide = 1;
         g_entryPrice   = trade.ResultPrice();
         g_entryTime    = lastClosedBarTime;
         g_stopPrice    = sl;
         g_longTaken    = true;
         PrintFormat("[ORB-DAX] LONG %.2f lots @ %.2f stop=%.2f or_high=%.2f or_low=%.2f",
                     lots, g_entryPrice, g_stopPrice, g_orHigh, g_orLow);
      }
      else
      {
         PrintFormat("[ORB-DAX] Buy FAILED: %s", trade.ResultRetcodeDescription());
      }
   }
   // Short on close < OR low
   else if(!g_shortTaken && barClose < g_orLow)
   {
      double sl = g_orHigh;
      if(InpLongOnly)
      {
         // Shadow-log only — research says short leg is a net drag except in
         // sustained bear regimes (2021-2022 vol window). If live SHORT shadow
         // PnL turns persistently positive over 3-6 months, consider enabling.
         g_shortTaken = true;
         PrintFormat("[ORB-DAX] SHORT signal (shadow, not traded) @ %.2f or_high=%.2f or_low=%.2f",
                     barClose, g_orHigh, g_orLow);
      }
      else
      {
         double estEntry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double lots     = CalculateLotSize(ORDER_TYPE_SELL, estEntry, sl);
         if(lots <= 0.0)
         {
            Print("[ORB-DAX] Skipping SHORT: lot calc returned 0");
            return;
         }
         if(trade.Sell(lots, _Symbol, 0.0, sl, 0.0, InpCommentTag + "-S"))
         {
            g_positionSide = -1;
            g_entryPrice   = trade.ResultPrice();
            g_entryTime    = lastClosedBarTime;
            g_stopPrice    = sl;
            g_shortTaken   = true;
            PrintFormat("[ORB-DAX] SHORT %.2f lots @ %.2f stop=%.2f or_high=%.2f or_low=%.2f",
                        lots, g_entryPrice, g_stopPrice, g_orHigh, g_orLow);
         }
         else
         {
            PrintFormat("[ORB-DAX] Sell FAILED: %s", trade.ResultRetcodeDescription());
         }
      }
   }
}
//+------------------------------------------------------------------+
