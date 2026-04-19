"""Fair Value Gap (imbalance) strategy for intraday trading.

Detects 3-candle price imbalances where aggressive momentum leaves a gap
between candle 1's wick and candle 3's wick, then enters when price
retraces into that gap zone with confirmation.

Designed for XAUUSD M5 but works on any instrument/timeframe.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from backtesting.indicators import ATR, EMA
from backtesting.strategy import Strategy
from backtesting.types import Bar, Trade

from strategies.base import TrendFilter, risk_adjusted_size


@dataclass
class FVGZone:
    """A Fair Value Gap zone waiting for price to retrace into it."""
    side: int           # +1 bullish FVG, -1 bearish FVG
    top: float          # Upper boundary of the gap
    bottom: float       # Lower boundary of the gap
    mid: float          # Midpoint
    bar_index: int      # Bar where FVG was detected
    state: str = "waiting"  # waiting → touched → (invalidated | filled)
    touch_bar: int = -1     # Bar index when first touched


class ImbalanceStrategy(Strategy):
    """Fair Value Gap (FVG) retracement strategy with two-bar confirmation.

    A Fair Value Gap is a 3-candle pattern where the middle candle's
    momentum leaves a gap between candle 1 and candle 3's wicks:

    - **Bullish FVG**: ``bar[i-2].high < bar[i].low`` — gap up
    - **Bearish FVG**: ``bar[i-2].low > bar[i].high`` — gap down

    The middle candle must show significant displacement (body >= ATR
    multiple) to filter noise.

    **Two-bar confirmation entry:**

    1. Bar A: price wicks into the zone (touch) — marks zone as ``touched``
    2. Bar B: close confirms rejection (close in FVG direction,
       close on the right side of zone midpoint) — generates signal
    3. Bar C: fill at open (next-bar-open execution)

    Zones are invalidated if price closes through the far boundary.

    Parameters
    ----------
    atr_period : int
        ATR period for volatility-based filters and stop placement.
    min_fvg_atr_mult : float
        Minimum FVG gap size as ATR multiple. Default 0.5.
    displacement_atr_mult : float
        Minimum middle-candle body as ATR multiple. Default 1.0.
    max_zones : int
        Maximum active zones tracked.
    zone_expiry_bars : int
        Bars before an unfilled zone expires. Default 72 (~6h on M5).
    atr_stop_buffer : float
        ATR multiple added beyond the FVG boundary for the stop.
    risk_reward : float
        TP distance as a multiple of risk.
    risk_per_trade : float
        Fraction of equity risked per trade.
    max_dd_halt : float
        Drawdown threshold to halt new entries.
    cooldown_bars : int
        Minimum bars between consecutive trades.
    session_filter : bool
        Only detect FVGs during London/NY sessions (07-21 UTC).
    trend_filter_period : int
        EMA period for trend direction filter (0 = disabled).
    momentum_period : int
        EMA period for momentum slope filter. When > 0, only allows
        entries when the EMA slope agrees with the FVG direction:
        rising EMA for longs, falling for shorts. The slope is measured
        as the EMA change over ``momentum_lookback`` bars. Set to 0
        to disable. Default 50 (~12h on M15).
    momentum_lookback : int
        Number of bars over which to measure EMA slope. Default 10.
    trail_trigger_r : float
        Move the stop once profit reaches this many R. Set to 0 to
        disable trailing. Default 0 (disabled — fixed TP works best
        with high R:R targets).
    trail_to_r : float
        Where to move the stop, in R from entry. 0.0 = breakeven,
        0.5 = lock in half the initial risk as profit. Only used
        when ``trail_trigger_r > 0``.
    use_limit_entry : bool
        If True, use a limit order at the zone midpoint instead of
        a market order at bar close. The backtester fills the order
        only when price reaches the limit. Gives better fills but
        may miss zones that bounce off the edge. Default False.
    swing_lookback : int
        Lookback period for detecting swing highs/lows used as HTF
        structure levels. FVGs near a swing level are higher quality.
        Set to 0 to disable. Default 0.
    swing_proximity_atr : float
        Maximum distance (in ATR multiples) between a FVG zone and
        the nearest swing level for the confluence filter. Only used
        when ``swing_lookback > 0``. Default 3.0.
    """

    def __init__(
        self,
        atr_period: int = 14,
        min_fvg_atr_mult: float = 1.0,
        displacement_atr_mult: float = 2.0,
        max_zones: int = 10,
        zone_expiry_bars: int = 72,
        atr_stop_buffer: float = 0.3,
        risk_reward: float = 3.0,
        risk_per_trade: float = 0.02,
        max_dd_halt: float = 0.50,
        cooldown_bars: int = 6,
        session_filter: bool = True,
        trend_filter_period: int = 500,
        momentum_period: int = 100,
        momentum_lookback: int = 5,
        trail_trigger_r: float = 0.0,
        trail_to_r: float = 0.0,
        use_limit_entry: bool = False,
        swing_lookback: int = 0,
        swing_proximity_atr: float = 3.0,
    ):
        self.min_fvg_atr_mult = min_fvg_atr_mult
        self.displacement_atr_mult = displacement_atr_mult
        self.max_zones = max_zones
        self.zone_expiry_bars = zone_expiry_bars
        self.atr_stop_buffer = atr_stop_buffer
        self.risk_reward = risk_reward
        self.risk_per_trade = risk_per_trade
        self.max_dd_halt = max_dd_halt
        self.cooldown_bars = cooldown_bars
        self.session_filter = session_filter
        self.momentum_lookback = momentum_lookback
        self.trail_trigger_r = trail_trigger_r
        self.trail_to_r = trail_to_r
        self.use_limit_entry = use_limit_entry
        self.swing_lookback = swing_lookback
        self.swing_proximity_atr = swing_proximity_atr

        self._atr = ATR(atr_period)
        self._trend_filter = TrendFilter(trend_filter_period)
        self._momentum_ema = EMA(momentum_period) if momentum_period > 0 else None
        self._momentum_buf: list[float] = []
        self._zones: deque[FVGZone] = deque(maxlen=max_zones)

        # Rolling window of the last 3 bars
        self._bar_buf: list[Bar] = []

        # Swing high/low tracking for HTF confluence
        self._high_buf: list[float] = []
        self._low_buf: list[float] = []
        self._swing_highs: list[float] = []
        self._swing_lows: list[float] = []

        self._peak_equity = 0.0
        self._bars_since_trade = 999
        self._has_position = False
        self._current_atr: float = 0.0

    @staticmethod
    def _in_session(bar: Bar) -> bool:
        """Return True if bar falls within London/NY sessions (07-21 UTC)."""
        return 7 <= bar.ts.hour < 21

    def _update_swings(self, bar: Bar) -> None:
        """Track swing highs/lows for HTF structure confluence."""
        if self.swing_lookback <= 0:
            return

        self._high_buf.append(bar.high)
        self._low_buf.append(bar.low)
        lb = self.swing_lookback

        # Need 2*lb+1 bars to detect a swing at the midpoint
        if len(self._high_buf) < 2 * lb + 1:
            return

        # Check if the bar at position -lb-1 is a swing point
        mid = len(self._high_buf) - lb - 1
        mid_high = self._high_buf[mid]
        mid_low = self._low_buf[mid]

        # Swing high: higher than all lb bars before and after
        is_swing_high = all(
            mid_high >= self._high_buf[mid - j] and mid_high >= self._high_buf[mid + j]
            for j in range(1, lb + 1)
        )
        if is_swing_high:
            self._swing_highs.append(mid_high)
            if len(self._swing_highs) > 50:
                self._swing_highs = self._swing_highs[-30:]

        # Swing low: lower than all lb bars before and after
        is_swing_low = all(
            mid_low <= self._low_buf[mid - j] and mid_low <= self._low_buf[mid + j]
            for j in range(1, lb + 1)
        )
        if is_swing_low:
            self._swing_lows.append(mid_low)
            if len(self._swing_lows) > 50:
                self._swing_lows = self._swing_lows[-30:]

        # Keep buffers bounded
        if len(self._high_buf) > 2 * lb + 100:
            trim = len(self._high_buf) - 2 * lb - 50
            self._high_buf = self._high_buf[trim:]
            self._low_buf = self._low_buf[trim:]

    def _near_swing_level(self, zone: 'FVGZone', atr_val: float) -> bool:
        """Check if a FVG zone is near a recent swing high/low."""
        if self.swing_lookback <= 0:
            return True  # filter disabled

        max_dist = atr_val * self.swing_proximity_atr
        zone_mid = zone.mid

        # For bullish FVGs, check proximity to swing lows (support)
        # For bearish FVGs, check proximity to swing highs (resistance)
        levels = self._swing_lows if zone.side == 1 else self._swing_highs

        for level in reversed(levels):
            if abs(zone_mid - level) <= max_dist:
                return True
        return False

    def _momentum_allows(self, side: int) -> bool:
        """Return True if momentum slope agrees with trade direction."""
        if self._momentum_ema is None:
            return True
        buf = self._momentum_buf
        if len(buf) < self.momentum_lookback + 1:
            return True
        slope = buf[-1] - buf[-(self.momentum_lookback + 1)]
        if side > 0:
            return slope > 0
        return slope < 0

    def on_bar(self, i: int, bar: Bar, equity: float) -> Optional[Trade]:
        atr_val = self._atr.update(bar.high, bar.low, bar.close)
        self._trend_filter.update(bar.close)
        self._update_swings(bar)
        if self._momentum_ema is not None:
            mval = self._momentum_ema.update(bar.close)
            if mval is not None:
                self._momentum_buf.append(mval)
                # Keep buffer bounded
                if len(self._momentum_buf) > self.momentum_lookback + 50:
                    self._momentum_buf = self._momentum_buf[-(self.momentum_lookback + 10):]
        self._peak_equity = max(self._peak_equity, equity)
        self._bars_since_trade += 1
        if atr_val is not None:
            self._current_atr = atr_val

        was_in_position = self._has_position
        self._has_position = False

        # Maintain 3-bar window
        self._bar_buf.append(bar)
        if len(self._bar_buf) > 3:
            self._bar_buf.pop(0)

        if atr_val is None or atr_val <= 0:
            return None

        # --- Phase 1: Invalidate zones where price closed through ---
        for zone in self._zones:
            if zone.state in ("invalidated", "filled"):
                continue
            if zone.side == 1 and bar.close < zone.bottom:
                zone.state = "invalidated"
            elif zone.side == -1 and bar.close > zone.top:
                zone.state = "invalidated"

        # --- Phase 2: Detect new FVG zones ---
        if len(self._bar_buf) == 3:
            b0, b1, b2 = self._bar_buf
            min_gap = atr_val * self.min_fvg_atr_mult
            min_body = atr_val * self.displacement_atr_mult
            in_session = not self.session_filter or self._in_session(b1)
            middle_body = abs(b1.close - b1.open)
            has_displacement = middle_body >= min_body

            if (in_session and has_displacement
                    and b1.close > b1.open
                    and b0.high < b2.low
                    and (b2.low - b0.high) >= min_gap):
                self._zones.append(FVGZone(
                    side=1, top=b2.low, bottom=b0.high,
                    mid=(b2.low + b0.high) / 2, bar_index=i,
                ))

            if (in_session and has_displacement
                    and b1.close < b1.open
                    and b0.low > b2.high
                    and (b0.low - b2.high) >= min_gap):
                self._zones.append(FVGZone(
                    side=-1, top=b0.low, bottom=b2.high,
                    mid=(b0.low + b2.high) / 2, bar_index=i,
                ))

        # --- Phase 3: Expire old zones ---
        while (self._zones
               and (i - self._zones[0].bar_index) > self.zone_expiry_bars):
            self._zones.popleft()

        # --- Phase 4: Touch detection (always runs, regardless of position) ---
        if not self.use_limit_entry:
            for zone in self._zones:
                if zone.state != "waiting":
                    continue
                if (i - zone.bar_index) < 2:
                    continue
                if zone.side == 1 and bar.low <= zone.top:
                    zone.state = "touched"
                    zone.touch_bar = i
                elif zone.side == -1 and bar.high >= zone.bottom:
                    zone.state = "touched"
                    zone.touch_bar = i

        # --- Phase 5: Entry (gated by position and cooldown) ---
        if was_in_position:
            return None
        if self._bars_since_trade < self.cooldown_bars:
            return None

        if self.use_limit_entry:
            # LIMIT PATH: place limit at zone.mid as soon as zone is detected.
            # The backtester holds the order pending until price reaches mid.
            for zone in reversed(self._zones):
                if zone.state != "waiting":
                    continue
                if (i - zone.bar_index) < 2:
                    continue
                trade = self._build_trade(bar, zone, atr_val, equity)
                if trade is not None:
                    zone.state = "filled"
                    return trade
        else:
            # MARKET PATH: two-bar confirmation (touch → confirm → market fill)
            for zone in reversed(self._zones):
                if zone.state != "touched":
                    continue
                if zone.touch_bar == i:
                    continue

                confirmed = False
                if zone.side == 1:
                    confirmed = (bar.close >= zone.mid
                                 and bar.close >= zone.bottom)
                else:
                    confirmed = (bar.close <= zone.mid
                                 and bar.close <= zone.top)

                if confirmed:
                    trade = self._build_trade(bar, zone, atr_val, equity)
                    if trade is not None:
                        zone.state = "filled"
                        return trade

        return None

    def _build_trade(self, bar: Bar, zone: FVGZone, atr_val: float,
                     equity: float) -> Optional[Trade]:
        """Build a trade with stop beyond zone boundary + buffer."""
        if not self._trend_filter.allows(zone.side, bar.close):
            return None
        if not self._momentum_allows(zone.side):
            return None
        if not self._near_swing_level(zone, atr_val):
            return None

        # Entry price: zone midpoint for limit orders, bar close for market
        if self.use_limit_entry:
            entry = zone.mid
        else:
            entry = bar.close

        buffer = atr_val * self.atr_stop_buffer

        if zone.side == 1:
            stop = zone.bottom - buffer
        else:
            stop = zone.top + buffer

        risk = abs(entry - stop)
        if risk <= 0:
            return None
        tp = entry + zone.side * risk * self.risk_reward

        size = risk_adjusted_size(equity, entry, stop, self.risk_per_trade,
                                  self._peak_equity, self.max_dd_halt)
        if size > 0:
            self._bars_since_trade = 0
            self._has_position = True
            limit = zone.mid if self.use_limit_entry else None
            return Trade(entry_bar=bar, side=zone.side, size=size,
                         entry_price=entry, stop_price=stop,
                         take_profit=tp, limit_price=limit)
        return None

    def manage_position(self, bar: Bar, trade: Trade) -> None:
        """Optionally trail the stop once profit reaches a threshold."""
        self._has_position = True

        if self.trail_trigger_r <= 0:
            return

        initial_risk = abs(trade.entry_price - trade.stop_price)
        if initial_risk <= 0:
            return

        profit = (bar.close - trade.entry_price) * trade.side

        if profit >= initial_risk * self.trail_trigger_r:
            new_stop = trade.entry_price + trade.side * initial_risk * self.trail_to_r
            if trade.side > 0:
                trade.stop_price = max(trade.stop_price, new_stop)
            else:
                trade.stop_price = min(trade.stop_price, new_stop)
