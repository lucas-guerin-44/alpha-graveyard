"""
BTC Trend Following (MH-LO + pyramid) -- QuantConnect live algorithm.

Research params from experiments/btc_trend/ (2018-2026 validation):
  LOOKBACKS = (21, 63, 252)   # 1M + 3M + 12M, sign-averaged
  REBALANCE_BARS = 21         # monthly
  VOL_TARGET_ANN = 0.15
  PYRAMID: K=3 units, ATR(14) * 1.0 favorable add, cap 1.00x vol-target

Research full-period Sharpe 0.83 (CAGR +10.0%, MDD -17% vs B&H -82%) at
10 bps/side honest CFD costs. Passes Phase 2-7 validation.

Instrument: BTCUSD on Coinbase (matches research 1:1, no ETF substitution
drag like BITO/GBTC). Long-only, vol-targeted, flat when signal turns.

See experiments/btc_trend/btc_trend.md for full thesis.
"""

from AlgorithmImports import *
import numpy as np

# =============================================================================
# CONFIG -- research-frozen params
# =============================================================================
LOOKBACKS        = (21, 63, 252)   # multi-horizon sign-average
REBALANCE_BARS   = 21              # monthly
VOL_LOOKBACK     = 60              # realized-vol window
VOL_TARGET_ANN   = 0.15            # 15% ann per full position
GROSS_CAP        = 1.0             # no leverage past vol-target
BARS_PER_YEAR    = 252             # annualisation factor

# Pyramid
PYRAMID_STEPS    = 3               # enter at 1/3, add 1/3 per favorable ATR
PYRAMID_ATR_MULT = 1.0
ATR_LOOKBACK     = 14

SYMBOL_TICKER = "BTCUSD"


class BtcTrendFollowing(QCAlgorithm):
    """Multi-horizon long-only TSMOM on BTCUSD with Turtle-style pyramid."""

    def initialize(self):
        self.set_start_date(2018, 1, 1)
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        # Coinbase for crypto. Switch to a live venue (Binance, Kraken, etc.)
        # before deploying with real capital.
        self.set_brokerage_model(BrokerageName.COINBASE, AccountType.CASH)

        self._symbol = self.add_crypto(
            SYMBOL_TICKER, Resolution.DAILY, Market.COINBASE,
        ).symbol

        # Need LOOKBACKS max + VOL_LOOKBACK buffer + a few bars.
        self._warmup_bars = max(LOOKBACKS) + VOL_LOOKBACK + 10
        self.set_warm_up(self._warmup_bars, Resolution.DAILY)

        # Pyramid state
        self._cur_side = 0             # 0 or +1 (long-only)
        self._cur_units = 0            # 0 .. PYRAMID_STEPS
        self._full_target = 0.0        # magnitude of full-vol-target weight
        self._last_inc_price = None
        self._last_inc_atr = None

        # Rebalance cadence
        self._trading_day_count = 0
        self._last_rebal_day = -REBALANCE_BARS  # ensure first bar triggers

        # Schedule: check every day at market-close; actual rebal gated by
        # REBALANCE_BARS counter (so we rebal exactly every 21 bars).
        # Use a daily schedule anchored to BTC's own trading calendar.
        self.schedule.on(
            self.date_rules.every_day(self._symbol),
            self.time_rules.at(23, 55),   # just before daily bar close
            self.try_rebalance,
        )

    # -------------------------------------------------------------------
    # Indicators (computed fresh from history each rebalance, matching
    # research simulator exactly)
    # -------------------------------------------------------------------

    def _get_history(self, n_bars):
        """Return (closes, highs, lows) numpy arrays, oldest->newest. None if short."""
        hist = self.history(self._symbol, n_bars, Resolution.DAILY)
        if hist is None or hist.empty:
            return None
        # Crypto bars always have close/high/low columns.
        closes = hist["close"].to_numpy()
        highs = hist["high"].to_numpy()
        lows = hist["low"].to_numpy()
        mask = ~(np.isnan(closes) | np.isnan(highs) | np.isnan(lows))
        if not mask.any():
            return None
        return closes[mask], highs[mask], lows[mask]

    @staticmethod
    def _multi_horizon_signal(closes):
        """Average of sign(past-return over each lookback). In [-1, 1]."""
        sigs = []
        for lb in LOOKBACKS:
            if len(closes) <= lb:
                continue
            past = closes[-lb - 1]
            now = closes[-1]
            if past <= 0:
                continue
            r = (now - past) / past
            sigs.append(1.0 if r > 0 else (-1.0 if r < 0 else 0.0))
        if not sigs:
            return 0.0
        return float(np.mean(sigs))

    @staticmethod
    def _realized_vol_ann(closes):
        """Annualised daily-return std from trailing VOL_LOOKBACK bars.
        Shifted by 1 (use t-1 data to decide t position, no look-ahead)."""
        if len(closes) < VOL_LOOKBACK + 2:
            return None
        # Compute vol on returns up to t-1 (exclude most recent bar).
        window = closes[-VOL_LOOKBACK - 1:-1]
        rets = np.diff(window) / window[:-1]
        rets = rets[np.isfinite(rets)]
        if len(rets) < VOL_LOOKBACK // 2:
            return None
        s = float(np.std(rets, ddof=1))
        if s <= 0:
            return None
        return s * np.sqrt(BARS_PER_YEAR)

    @staticmethod
    def _atr(highs, lows, closes, n=ATR_LOOKBACK):
        """Simple mean of true range over n bars. Matches research atr_series()."""
        if len(closes) < n + 1:
            return None
        prev_close = closes[-n - 1:-1]
        h = highs[-n:]
        l = lows[-n:]
        tr = np.maximum.reduce([
            h - l,
            np.abs(h - prev_close),
            np.abs(l - prev_close),
        ])
        return float(np.mean(tr))

    # -------------------------------------------------------------------
    # Main rebalance logic
    # -------------------------------------------------------------------

    def try_rebalance(self):
        if self.is_warming_up:
            return

        self._trading_day_count += 1
        if self._trading_day_count - self._last_rebal_day < REBALANCE_BARS:
            return

        # Fetch enough history for all three lookbacks + vol + ATR.
        needed = max(LOOKBACKS) + 5
        data = self._get_history(needed)
        if data is None:
            self.debug("No history returned; skipping rebalance")
            return
        closes, highs, lows = data
        if len(closes) < max(LOOKBACKS) + 2:
            self.debug(f"Insufficient bars ({len(closes)}); skipping")
            return

        # Compute signal + vol + ATR using t-1 data (latest complete bar).
        # np.sign(multi-horizon average) gives direction; LO clips negatives.
        sig_raw = self._multi_horizon_signal(closes)
        side_new = 1 if sig_raw > 0 else 0     # long-only: no shorts

        rv_ann = self._realized_vol_ann(closes)
        vol_scale = 0.0
        if rv_ann is not None and rv_ann > 1e-6:
            vol_scale = min(VOL_TARGET_ANN / rv_ann, GROSS_CAP)

        atr_val = self._atr(highs, lows, closes)
        price_t = float(closes[-1])

        # --- Pyramid state machine (matches simulate_tsmom_pyramid) ---
        target_w = 0.0
        if side_new == 0 or vol_scale <= 0.0:
            # Flat or no vol signal -> close everything.
            self._cur_side = 0
            self._cur_units = 0
            self._full_target = 0.0
            self._last_inc_price = None
            self._last_inc_atr = None
            target_w = 0.0
        elif side_new != self._cur_side:
            # New direction (first entry this cycle).
            self._cur_side = side_new
            self._full_target = vol_scale
            self._cur_units = 1
            self._last_inc_price = price_t
            self._last_inc_atr = atr_val
            target_w = self._cur_side * self._full_target * (self._cur_units / PYRAMID_STEPS)
        else:
            # Same direction: refresh full_target, try to pyramid up.
            self._full_target = vol_scale
            can_add = (
                self._cur_units < PYRAMID_STEPS
                and self._last_inc_price is not None
                and self._last_inc_atr is not None
                and self._last_inc_atr > 0
            )
            if can_add:
                favorable = self._cur_side * (price_t - self._last_inc_price)
                if favorable >= PYRAMID_ATR_MULT * self._last_inc_atr:
                    self._cur_units += 1
                    self._last_inc_price = price_t
                    self._last_inc_atr = atr_val
            target_w = self._cur_side * self._full_target * (self._cur_units / PYRAMID_STEPS)

        # --- Execute ---
        self.set_holdings(self._symbol, target_w)

        self._last_rebal_day = self._trading_day_count
        self.log(
            f"Rebal@{self.time.date()}: sig={sig_raw:+.2f} side={self._cur_side} "
            f"units={self._cur_units}/{PYRAMID_STEPS} vol_ann={rv_ann:.3f} "
            f"vol_scale={vol_scale:.2f} target_w={target_w:+.3f} price=${price_t:,.0f}"
        )

    def on_data(self, data):
        pass
