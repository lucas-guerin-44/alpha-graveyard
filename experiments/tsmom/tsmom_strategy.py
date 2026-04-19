"""Time-Series Momentum (TSMOM) — Moskowitz, Ooi, Pedersen (2012).

The canonical "slow trend-following" strategy. Signal is the sign of the
trailing N-month past return; position is held until the signal flips.
Sizing is volatility-targeted so each position contributes roughly the
same annualized portfolio volatility.

Why this is retail-defensible
-----------------------------
* Monthly rebalance (D1: ~21 bars) — HFT can't compete at this cadence.
* Works across asset classes (FX, commodities, equities, bonds) — the signal
  is a behavioral/structural phenomenon (investor under-reaction, demand
  for slow-moving assets), not a microstructure edge.
* Post-publication performance has held up reasonably well; the signal is
  robust across 200+ years of futures data (Hurst-Ooi-Pedersen 2017).
* Capacity-limited at the institutional scale that would arbitrage it away.

Implementation note: there are no conventional stops or take-profits. The
position holds until the next rebalance where the signal flips. We emulate
this inside the engine's entry/exit framework by (a) placing an effectively
unreachable initial stop, and (b) when the signal flips, ``manage_position``
collapses the stop so the broker's gap-through logic closes the trade at
the next bar's open.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

import numpy as np

from backtesting.strategy import Strategy
from backtesting.types import Bar, Trade


class TimeSeriesMomentumStrategy(Strategy):
    """Moskowitz-Ooi-Pedersen (2012) time-series momentum.

    Parameters
    ----------
    lookback_bars : int
        Past-return window for the signal. Default 252 (~12 months on D1).
    skip_bars : int
        Bars trimmed from the recent end of the lookback (classic 12-1
        momentum excludes the most recent month). Default 21.
    rebalance_bars : int
        Update the signal every N bars. Default 21 (monthly on D1).
    vol_lookback : int
        Window for realized-volatility estimation (position sizing).
        Default 60 (~3 months).
    vol_target_annual : float
        Target annualized volatility per position. Default 0.15 (15%).
    long_only : bool
        If True, short signals are treated as flat. Default False.
    min_abs_return : float
        Require the absolute past return to exceed this threshold before
        taking a position. Set >0 to filter out low-conviction signals.
        Default 0.0.
    bars_per_year : int
        Annualization factor for vol. Default 252.
    max_dd_halt : float
        Halt new entries when drawdown from peak equity exceeds this
        fraction. Default 0.30 (30%).
    size_cap_fraction : float
        Cap position notional at this fraction of equity. Default 1.0
        (no leverage). Set <1 to reduce gross exposure.
    """

    def __init__(
        self,
        lookback_bars: int = 252,
        skip_bars: int = 21,
        rebalance_bars: int = 21,
        vol_lookback: int = 60,
        vol_target_annual: float = 0.15,
        long_only: bool = False,
        min_abs_return: float = 0.0,
        bars_per_year: int = 252,
        max_dd_halt: float = 0.30,
        size_cap_fraction: float = 1.0,
    ):
        self.lookback_bars = int(lookback_bars)
        self.skip_bars = int(skip_bars)
        self.rebalance_bars = int(rebalance_bars)
        self.vol_lookback = int(vol_lookback)
        self.vol_target_annual = float(vol_target_annual)
        self.long_only = bool(long_only)
        self.min_abs_return = float(min_abs_return)
        self.bars_per_year = int(bars_per_year)
        self.max_dd_halt = float(max_dd_halt)
        self.size_cap_fraction = float(size_cap_fraction)

        # Keep lookback_bars+2 closes so we can look back `lookback_bars`
        # and trim `skip_bars` from the recent end.
        self._closes: deque = deque(maxlen=self.lookback_bars + 2)
        self._returns: deque = deque(maxlen=self.vol_lookback + 1)
        self._prev_close: Optional[float] = None
        self._last_rebalance: int = -(10**9)
        self._current_signal: int = 0
        self._has_position: bool = False
        self._position_side: int = 0
        self._peak_equity: float = 0.0

    # ------------------------------------------------------------------
    # Main hooks
    # ------------------------------------------------------------------

    def on_bar(self, i: int, bar: Bar, equity: float) -> Optional[Trade]:
        self._closes.append(bar.close)
        if self._prev_close is not None and self._prev_close > 0:
            self._returns.append((bar.close - self._prev_close) / self._prev_close)
        self._prev_close = bar.close

        self._peak_equity = max(self._peak_equity, equity)

        was_in_position = self._has_position
        self._has_position = False
        self._position_side = 0

        if (i - self._last_rebalance) >= self.rebalance_bars:
            new_signal = self._compute_signal()
            if new_signal is not None:
                self._current_signal = new_signal
                self._last_rebalance = i

        # While a position is open at start of bar, let manage_position handle
        # it (hold if signal matches, collapse stop if it flipped).
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
        # Effectively-disabled initial stops: a real market move would never
        # hit these. The signal-flip logic in manage_position handles exits.
        stop = entry * 0.01 if self._current_signal > 0 else entry * 100.0

        return Trade(
            entry_bar=bar,
            side=self._current_signal,
            size=size,
            entry_price=entry,
            stop_price=stop,
            take_profit=None,
        )

    def manage_position(self, bar: Bar, trade: Trade) -> None:
        self._has_position = True
        self._position_side = trade.side

        # Hold only while the signal still agrees with the position direction.
        # Close when signal has flipped OR gone to neutral (0) — both mean
        # "we no longer want to be in this direction". This matters especially
        # in long_only mode where signal cycles +1 -> 0 -> +1 and the neutral
        # step must close the long (previously returned early, leaving the
        # long open forever and distorting backtest results).
        if self._current_signal == trade.side:
            return

        # Signal no longer matches: collapse the stop so the broker closes at
        # next bar's open via its gap-through logic (bar.open <= stop for longs,
        # bar.open >= stop for shorts — both trivially true with these values).
        if trade.side > 0:
            trade.stop_price = bar.close * 10.0
        else:
            trade.stop_price = bar.close * 0.1

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_signal(self) -> Optional[int]:
        """Return +1 / -1 / 0 based on the trailing past return, or None if
        not enough history to evaluate."""
        if len(self._closes) < self.lookback_bars + 1:
            return None

        past = self._closes[-self.lookback_bars]
        # Skip the most recent `skip_bars` bars (standard 12-1 momentum)
        recent = self._closes[-1 - self.skip_bars] if self.skip_bars > 0 else self._closes[-1]
        if past <= 0:
            return 0

        past_return = (recent - past) / past

        if abs(past_return) < self.min_abs_return:
            return 0
        if past_return > 0:
            return 1
        return 0 if self.long_only else -1

    def _vol_targeted_size(self, equity: float, price: float) -> float:
        if len(self._returns) < self.vol_lookback or price <= 0 or equity <= 0:
            return 0.0

        arr = np.fromiter(self._returns, dtype=np.float64)[-self.vol_lookback:]
        daily_vol = float(arr.std(ddof=0))
        if daily_vol <= 0:
            return 0.0

        annual_vol = daily_vol * math.sqrt(self.bars_per_year)
        if annual_vol <= 0:
            return 0.0

        target_notional = equity * (self.vol_target_annual / annual_vol)
        target_notional = min(target_notional, equity * self.size_cap_fraction)
        size = target_notional / price
        return max(0.0, size)
