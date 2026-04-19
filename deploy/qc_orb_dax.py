"""
Opening Range Breakout on DAX (M5) -- QuantConnect live algorithm.

Research params from experiments/orb/ (2019-2026, GER40 CFD on MT5):
  OR_MINUTES           = 30       (opening range window, 09:00-09:30 Berlin)
  TOD_EXIT_MINUTES     = 180      (flat 3h after entry — edge half-life)
  STOP                 = opposite OR boundary (full-OR-width, no TP)
  SESSION              = 09:00-17:30 Europe/Berlin (Xetra cash hours)
  One round-trip per direction per day; flat overnight.

Research full-period Sharpe +0.58 (CAGR +3.0%, MDD -12.3%, PF 1.11) at
1pt/round-trip GER40 CFD cost. All 3 regime windows Sharpe >= +0.55 incl.
2023-2026 holdout +0.55. Fade-gap under symmetric 1:1 R:R = +0.97 confirms
real directional signal, not book-keeping artifact.

Year-by-year on holdout: 2023 +0.69, 2024 +0.96, 2025 -0.37, Q1'26 +2.19.
2025 was a losing year — ORB does not like slow-grind low-impulse regimes.

Expected live Sharpe after 50-70% haircut: +0.17 to +0.29. This is a
showcase / pipeline-validation deploy, not an institutional-grade alpha.

---

INSTRUMENT NOTE: the research was done on MT5 SPX500/NDX100/GER40 CFDs.
QC does NOT have a DAX CFD; the closest native instruments are:

  A) DAX futures on Eurex:    self.add_future("FDAX") or Futures.Indices.DAX
     (preferred — matches research semantics)
  B) MFDAX (micro) on Eurex:  smaller contract size, better retail fit
  C) EWG (MSCI Germany ETF):  US-listed, US-session only — BROKEN because
     DAX cash session is Berlin hours, not ET. Do NOT use EWG for this.

The primary live deployment path is MT5 on GER40 CFD (matches research 1:1).
This QC port exists to (a) validate the ORB logic on QC's independent bar
data + execution model, (b) measure futures-vs-CFD cost differential, (c)
provide a pipeline dress-rehearsal before MT5 live.

Paste into a new Python algorithm in the QuantConnect IDE. PEP-8 snake_case
API (current QC convention as of 2026).

See experiments/orb/orb.md for the full thesis and validation record.
"""

from AlgorithmImports import *
from datetime import time as dtime, timedelta


# =============================================================================
# CONFIG -- research-frozen params
# =============================================================================
OR_MINUTES           = 30          # first 30 min of session
TOD_EXIT_MINUTES     = 180         # hold 3h post-entry
ENTRY_CUTOFF_MIN     = 180         # no new entries 3h after session open
EXIT_MIN_BEFORE_SESSION_CLOSE = 5  # hard flat 5 min before session close

RTH_OPEN  = dtime(9,  0)           # 09:00 Europe/Berlin (Xetra open)
RTH_CLOSE = dtime(17, 30)          # 17:30 Europe/Berlin (Xetra close)

CONTRACTS = 1                      # front-month FDAX contracts per trade
# Note: 1 FDAX contract = EUR 25/point, notional ~EUR 500k.
# For retail, prefer MFDAX (EUR 5/point) if your broker/QC subscription supports it.

# Symbol choice. Prefer DAX (FDAX). If the constant does not resolve in your
# QC environment, fall back to ticker-string add_future.
FUTURE_ROOT = None  # filled in initialize() from Futures.Indices.DAX or "/FDAX"


class DaxOpeningRangeBreakout(QCAlgorithm):
    """
    Opening-range breakout on DAX futures, 5-minute bars, Berlin session.

    Per trading day:
      1. Track OR high/low during 09:00-09:30 Berlin.
      2. From 09:30 onward, on M5 close > OR_high: long next bar open,
         stop at OR_low. On M5 close < OR_low: short, stop at OR_high.
      3. Exit at T+180min after entry OR stop-hit OR 17:25 Berlin,
         whichever first.
      4. Max one round-trip per direction per day. Flat overnight.
    """

    def initialize(self):
        self.set_start_date(2019, 1, 1)
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        # IB has Eurex DAX futures (ticker DAX / FDAX).
        self.set_brokerage_model(
            BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
            AccountType.MARGIN,
        )

        # Time zone the session times below are interpreted in.
        self.set_time_zone("Europe/Berlin")

        # Subscribe to DAX futures, minute resolution. We consolidate to 5-min
        # internally because QC's minute bars are native and 5-min is a
        # derived consolidation for index futures.
        future = self.add_future(Futures.Indices.DAX, Resolution.MINUTE)
        # Continuous front-month contract; 0-180 day filter keeps us on the
        # nearest contract with room before expiry.
        future.set_filter(0, 180)
        self._future = future
        self._symbol = future.symbol

        # Consolidate minute bars to 5-min bars for the signal.
        consolidator = TradeBarConsolidator(timedelta(minutes=5))
        consolidator.data_consolidated += self._on_m5_bar
        self.subscription_manager.add_consolidator(self._symbol, consolidator)
        self._consolidator = consolidator

        # State machine (per-day). All reset in _reset_day_state at open.
        self._or_high = None
        self._or_low = None
        self._or_complete = False
        self._position_side = 0        # -1 short, 0 flat, +1 long
        self._entry_price = None
        self._entry_time = None        # datetime (Berlin) of fill
        self._stop_price = None
        self._long_taken = False
        self._short_taken = False
        self._session_day = None       # date(Berlin) of current session

        # Schedule session-open reset and session-close flatten.
        # Use calendar-day schedule with time-of-day at session boundaries.
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(RTH_OPEN.hour, RTH_OPEN.minute),
            self._on_session_open,
        )
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(RTH_CLOSE.hour, RTH_CLOSE.minute - EXIT_MIN_BEFORE_SESSION_CLOSE),
            self._on_session_close_imminent,
        )

    # ---------------------------------------------------------------------
    # Session lifecycle
    # ---------------------------------------------------------------------

    def _on_session_open(self):
        """Called at 09:00 Berlin — reset per-day state."""
        self._or_high = None
        self._or_low = None
        self._or_complete = False
        self._position_side = 0
        self._entry_price = None
        self._entry_time = None
        self._stop_price = None
        self._long_taken = False
        self._short_taken = False
        self._session_day = self.time.date()

    def _on_session_close_imminent(self):
        """Called at 17:25 Berlin — force-flatten any open position."""
        if self._position_side != 0:
            self.liquidate(self._symbol, tag="eod-flatten")
            self.log(f"EOD flatten {self._position_side:+d}")
            self._position_side = 0

    # ---------------------------------------------------------------------
    # Main signal handler on 5-min bars
    # ---------------------------------------------------------------------

    def _on_m5_bar(self, sender, bar):
        if self.is_warming_up:
            return

        ts = bar.end_time  # Berlin local time, end of 5-min bar
        # Skip bars outside the RTH window.
        t = ts.time()
        if t < RTH_OPEN or t >= RTH_CLOSE:
            return
        if ts.date() != self._session_day:
            # Safety: re-init if schedule hasn't fired (warmup, missed event).
            self._on_session_open()
            self._session_day = ts.date()

        minute_of_day = (t.hour * 60 + t.minute) - (RTH_OPEN.hour * 60 + RTH_OPEN.minute)

        # ------ 1) During OR window: accumulate high/low ------
        if minute_of_day < OR_MINUTES:
            self._or_high = bar.high if self._or_high is None else max(self._or_high, bar.high)
            self._or_low = bar.low if self._or_low is None else min(self._or_low, bar.low)
            return

        if not self._or_complete:
            # OR window just ended; finalise.
            if self._or_high is None or self._or_low is None or self._or_high <= self._or_low:
                # Malformed OR — skip this day.
                self._or_complete = True
                return
            self._or_complete = True
            self.log(f"OR set: high={self._or_high:.2f} low={self._or_low:.2f} width={self._or_high - self._or_low:.2f}")

        # ------ 2) Exit checks if currently in a position ------
        if self._position_side != 0:
            # Stop: bar.low (long) / bar.high (short) vs stop_price.
            hit_stop = False
            if self._position_side == 1 and bar.low <= self._stop_price:
                hit_stop = True
            elif self._position_side == -1 and bar.high >= self._stop_price:
                hit_stop = True

            # Time-of-day exit: T+TOD_EXIT_MINUTES after entry.
            tod_exit = False
            if self._entry_time is not None:
                held_minutes = (ts - self._entry_time).total_seconds() / 60.0
                if held_minutes >= TOD_EXIT_MINUTES:
                    tod_exit = True

            if hit_stop or tod_exit:
                reason = "stop" if hit_stop else "tod"
                self.liquidate(self._symbol, tag=reason)
                self.log(f"Exit {self._position_side:+d} @ {bar.close:.2f} reason={reason}")
                self._position_side = 0
                self._entry_price = None
                self._entry_time = None
                self._stop_price = None
                return

        # ------ 3) Entry check (only if flat and within entry cutoff) ------
        if self._position_side != 0:
            return
        if minute_of_day >= ENTRY_CUTOFF_MIN:
            return

        # Breakout direction based on M5 close vs OR boundaries.
        if not self._long_taken and bar.close > self._or_high:
            self._enter(+1, bar, stop_price=self._or_low)
            self._long_taken = True
        elif not self._short_taken and bar.close < self._or_low:
            self._enter(-1, bar, stop_price=self._or_high)
            self._short_taken = True

    # ---------------------------------------------------------------------
    # Entry helper
    # ---------------------------------------------------------------------

    def _enter(self, side, bar, stop_price):
        """Submit a market order; fill will be on next bar open.
        Store entry_price/entry_time after fill via on_order_event.
        """
        if side == +1:
            ticket = self.market_order(self._symbol, CONTRACTS, tag="orb-long")
        else:
            ticket = self.market_order(self._symbol, -CONTRACTS, tag="orb-short")
        self._position_side = side
        self._stop_price = stop_price
        # Fill price + time set in on_order_event; use bar.close as interim.
        self._entry_price = bar.close
        self._entry_time = bar.end_time
        self.log(f"Enter {side:+d} @ ~{bar.close:.2f} stop={stop_price:.2f} "
                 f"or_high={self._or_high:.2f} or_low={self._or_low:.2f}")

    def on_order_event(self, order_event):
        """Update entry_price/entry_time to actual fill on entry orders."""
        if order_event.status != OrderStatus.FILLED:
            return
        if order_event.direction == OrderDirection.BUY and self._position_side == 1:
            # long entry fill
            self._entry_price = order_event.fill_price
            self._entry_time = order_event.utc_time.astimezone(self.time_zone) if hasattr(order_event, 'utc_time') else self.time
        elif order_event.direction == OrderDirection.SELL and self._position_side == -1:
            # short entry fill
            self._entry_price = order_event.fill_price
            self._entry_time = order_event.utc_time.astimezone(self.time_zone) if hasattr(order_event, 'utc_time') else self.time
        # Exit fills don't need to update entry state — they're handled by
        # liquidate() + state reset in _on_m5_bar.

    def on_data(self, data):
        # Signal handler is on consolidated M5 bars via _on_m5_bar.
        pass
