"""Trend-filtered Time-Series Momentum strategy.

Extends :class:`TimeSeriesMomentumStrategy` with a long-term EMA regime
filter. The canonical TSMOM signal is the sign of the trailing 12-1
month return. That signal flips too eagerly at V-shaped reversals (e.g.
SPX500 going short at the March 2020 bottom) because the past-return
sign inverts before the trend structure actually breaks.

This variant gates the raw momentum signal by an EMA regime check:
  * Long  allowed only when ``close > ema(trend_filter_period)``
  * Short allowed only when ``close < ema(trend_filter_period)``
  * Otherwise the rebalance sets ``_current_signal = 0`` (stay flat).

When ``trend_filter_period == 0`` (the default), the filter is disabled
and behavior is identical to the parent class.
"""

from __future__ import annotations

from typing import Optional

from backtesting.indicators import EMA
from backtesting.types import Bar, Trade
from tsmom_strategy import TimeSeriesMomentumStrategy


class TrendFilteredTSMOMStrategy(TimeSeriesMomentumStrategy):
    """TSMOM with an EMA regime filter.

    Parameters
    ----------
    trend_filter_period : int
        EMA period used as the regime filter. 0 disables the filter
        (strategy reverts to vanilla TSMOM). Default 0.
    **kwargs
        All other kwargs are forwarded to
        :class:`TimeSeriesMomentumStrategy`.
    """

    def __init__(self, trend_filter_period: int = 0, **kwargs):
        super().__init__(**kwargs)
        self.trend_filter_period = int(trend_filter_period)
        self._ema: Optional[EMA] = (
            EMA(period=self.trend_filter_period)
            if self.trend_filter_period > 0
            else None
        )
        self._ema_value: Optional[float] = None

    def on_bar(self, i: int, bar: Bar, equity: float) -> Optional[Trade]:
        # Update the regime filter first so the gate sees the current bar's
        # EMA when the rebalance fires.
        if self._ema is not None:
            self._ema_value = self._ema.update(bar.close)

        # If the filter is disabled, fall straight through to the parent.
        if self._ema is None:
            return super().on_bar(i, bar, equity)

        # We need to intercept the signal at rebalance time. Replicate the
        # parent's bookkeeping, then run the gated signal update, and finally
        # delegate the rest of the entry/risk logic to super() by temporarily
        # suppressing the rebalance inside super().on_bar (we already did it).
        #
        # Approach: call super().on_bar, but first pre-apply the gate by
        # overriding _compute_signal via a wrapper. Simpler: just run the
        # same logic as parent but with a gated signal.

        self._closes.append(bar.close)
        if self._prev_close is not None and self._prev_close > 0:
            self._returns.append(
                (bar.close - self._prev_close) / self._prev_close
            )
        self._prev_close = bar.close

        self._peak_equity = max(self._peak_equity, equity)

        was_in_position = self._has_position
        self._has_position = False
        self._position_side = 0

        if (i - self._last_rebalance) >= self.rebalance_bars:
            new_signal = self._compute_signal()
            if new_signal is not None:
                gated = self._apply_trend_filter(new_signal, bar.close)
                self._current_signal = gated
                self._last_rebalance = i

        if was_in_position:
            return None

        if self._current_signal == 0:
            return None

        if self._peak_equity > 0:
            dd = (self._peak_equity - equity) / self._peak_equity
            if dd >= self.max_dd_halt:
                return None

        size = self._vol_targeted_size(equity, bar.close)
        if size <= 0:
            return None

        entry = bar.close
        stop = entry * 0.01 if self._current_signal > 0 else entry * 100.0

        return Trade(
            entry_bar=bar,
            side=self._current_signal,
            size=size,
            entry_price=entry,
            stop_price=stop,
            take_profit=None,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_trend_filter(self, raw_signal: int, close: float) -> int:
        """Gate the raw momentum signal by the EMA regime filter.

        Returns 0 if the EMA is not warmed up yet, or if the signal
        disagrees with the regime. Otherwise returns ``raw_signal``.
        """
        if self._ema_value is None:
            # EMA not yet warmed up: stay flat rather than trust an
            # unfiltered signal.
            return 0
        if raw_signal > 0 and close > self._ema_value:
            return 1
        if raw_signal < 0 and close < self._ema_value:
            return -1
        return 0
