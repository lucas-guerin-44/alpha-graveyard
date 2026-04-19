"""
Softs TSMOM Ensemble -- QuantConnect live algorithm.

Six-instrument ensemble validated through Phases 2-6 in
experiments/softs_ensemble/:
  COCOA + COFFEE + COTTON + CORN + SOYBEAN + LIVE_CATTLE

Each leg runs multi-horizon long-only TSMOM + Turtle-style pyramid
independently. Portfolio holds equal-weight (1/6 of equity target per
instrument). Research Sharpe 0.89 (CAGR +3.5%, MDD -13%) at 5 bps/side;
Phase 5 showed the strategy holds Sharpe 0.83+ even at 20 bps/side cost.
Phase 6 IS/OOS: 0.66 -> 1.44 (favourable 2023-2026 softs regime).

Expected QC realistic Sharpe: 0.55-0.70 (softs futures at IB are 2-4 bps
per side at our contract sizes -- cheaper than the research 5 bps).

See experiments/softs_ensemble/softs_ensemble.md for full thesis.
"""

from AlgorithmImports import *
import numpy as np

# =============================================================================
# CONFIG -- matches experiments/softs_ensemble/ baseline
# =============================================================================

LOOKBACKS            = (21, 63, 252)    # 1M + 3M + 12M sign-average
REBALANCE_BARS       = 21               # monthly on weekday calendar
VOL_LOOKBACK         = 60
VOL_TARGET_ANN       = 0.15
GROSS_CAP            = 1.0
BARS_PER_YEAR        = 252

# Pyramid
PYRAMID_STEPS        = 3
PYRAMID_ATR_MULT     = 1.0
ATR_LOOKBACK         = 14

# Ensemble sizing: each leg sized to 1/N of portfolio target weight.
# With 6 instruments max vol-target per leg is 1/6 = 16.67% notional.
# Max total portfolio notional ~100% when all 6 are fully long (3/3 pyramid).
INSTRUMENTS = [
    # (display_name, Futures root enum)
    ("COCOA",       Futures.Softs.COCOA),
    ("COFFEE",      Futures.Softs.COFFEE),
    ("COTTON",      Futures.Softs.COTTON_2),
    ("CORN",        Futures.Grains.CORN),
    ("SOYBEAN",     Futures.Grains.SOYBEANS),
    ("LIVE_CATTLE", Futures.Meats.LIVE_CATTLE),
]
N_LEGS               = len(INSTRUMENTS)
ALLOC_FRAC           = 1.0 / N_LEGS        # 1/6 per leg

WARMUP_BARS          = max(LOOKBACKS) + VOL_LOOKBACK + 15   # ~327


class SoftsTrendEnsemble(QCAlgorithm):
    """Multi-horizon long-only TSMOM + pyramid on six ag/livestock futures."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self):
        self.set_start_date(2015, 1, 2)
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        # IB supports all futures we use here. No crypto, no FX, no equity
        # ETFs -- single-brokerage algorithm.
        self.set_brokerage_model(
            BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
            AccountType.MARGIN,
        )

        # Universe: subscribe each future as a CONTINUOUS contract (auto-
        # rolled front month, back-ratio adjusted). The canonical symbol
        # returned by add_future then behaves like a single tradable series
        # -- set_holdings and history() on it both work. The older
        # add_future + set_filter pattern only builds a chain, which
        # requires manual chain-selection to trade -- that's why the first
        # backtest sat at $100k forever.
        self._assets: dict[str, Symbol] = {}
        for name, root in INSTRUMENTS:
            future = self.add_future(
                root,
                Resolution.DAILY,
                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                contract_depth_offset=0,
            )
            self._assets[name] = future.symbol
            self.debug(f"Subscribed {name} continuous future: {future.symbol}")

        self.set_warm_up(WARMUP_BARS, Resolution.DAILY)

        # SPY as a passive calendar anchor (weekday schedule). Using it only
        # for the scheduler; no holdings.
        self._spy = self.add_equity("SPY", Resolution.DAILY).symbol

        # Per-leg pyramid state -- one dict per instrument.
        self._state: dict[str, dict] = {
            name: {
                "cur_side": 0,
                "cur_units": 0,
                "full_target": 0.0,
                "last_inc_price": None,
                "last_inc_atr": None,
            }
            for name, _ in INSTRUMENTS
        }

        # Single shared day counter -- all 6 legs rebalance on the same cadence.
        self._day = 0
        self._last_rebal_day = -REBALANCE_BARS  # ensure first valid day triggers

        # Schedule: every weekday right before the US close. This approximates
        # the research's daily-bar cadence on business days.
        self.schedule.on(
            self.date_rules.every_day(self._spy),
            self.time_rules.before_market_close(self._spy, 10),
            self._tick_day,
        )

    def on_data(self, data):
        pass

    # ------------------------------------------------------------------
    # Calendar tick
    # ------------------------------------------------------------------

    def _tick_day(self):
        if self.is_warming_up:
            return
        self._day += 1
        if self._day - self._last_rebal_day < REBALANCE_BARS:
            return
        self._rebalance_all()
        self._last_rebal_day = self._day

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_ohlc(self, symbol, n):
        """Return (closes, highs, lows) numpy arrays, oldest->newest. None if short."""
        hist = self.history(symbol, n, Resolution.DAILY)
        if hist is None or hist.empty:
            return None
        closes = hist["close"].to_numpy()
        highs = hist["high"].to_numpy()
        lows = hist["low"].to_numpy()
        mask = ~(np.isnan(closes) | np.isnan(highs) | np.isnan(lows))
        if not mask.any():
            return None
        return closes[mask], highs[mask], lows[mask]

    @staticmethod
    def _multi_horizon_signal(closes):
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
        if len(closes) < VOL_LOOKBACK + 2:
            return None
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

    # ------------------------------------------------------------------
    # Per-leg rebalance (pyramid state machine per instrument)
    # ------------------------------------------------------------------

    def _process_leg(self, name: str, symbol, closes, highs, lows, alloc_frac: float):
        """Update pyramid state for one leg and issue set_holdings at the
        adaptive alloc_frac (= 1 / active_count, not the hard-coded 1/N)."""
        st = self._state[name]

        sig_raw = self._multi_horizon_signal(closes)
        side_new = 1 if sig_raw > 0 else 0   # long-only

        rv_ann = self._realized_vol_ann(closes)
        vol_scale = 0.0
        if rv_ann is not None and rv_ann > 1e-6:
            vol_scale = min(VOL_TARGET_ANN / rv_ann, GROSS_CAP)

        atr_val = self._atr(highs, lows, closes)
        price_t = float(closes[-1])

        if side_new == 0 or vol_scale <= 0.0:
            st["cur_side"] = 0
            st["cur_units"] = 0
            st["full_target"] = 0.0
            st["last_inc_price"] = None
            st["last_inc_atr"] = None
            target_w_sub = 0.0
        elif side_new != st["cur_side"]:
            st["cur_side"] = side_new
            st["full_target"] = vol_scale
            st["cur_units"] = 1
            st["last_inc_price"] = price_t
            st["last_inc_atr"] = atr_val
            target_w_sub = side_new * vol_scale * (1.0 / PYRAMID_STEPS)
        else:
            st["full_target"] = vol_scale
            can_add = (
                st["cur_units"] < PYRAMID_STEPS
                and st["last_inc_price"] is not None
                and st["last_inc_atr"] is not None
                and st["last_inc_atr"] > 0
            )
            if can_add:
                favorable = st["cur_side"] * (price_t - st["last_inc_price"])
                if favorable >= PYRAMID_ATR_MULT * st["last_inc_atr"]:
                    st["cur_units"] += 1
                    st["last_inc_price"] = price_t
                    st["last_inc_atr"] = atr_val
            target_w_sub = st["cur_side"] * st["full_target"] * (st["cur_units"] / PYRAMID_STEPS)

        target_w = target_w_sub * alloc_frac
        self.set_holdings(symbol, target_w)

        return {
            "sig": sig_raw,
            "side": st["cur_side"],
            "units": st["cur_units"],
            "target_w": target_w,
        }

    def _rebalance_all(self):
        # Pass 1: fetch history for each leg, collect active ones.
        active = []        # list of (name, symbol, closes, highs, lows)
        inactive = []      # list of name (for logging)
        for name, symbol in self._assets.items():
            data = self._get_ohlc(symbol, max(LOOKBACKS) + 5)
            if data is None:
                inactive.append((name, "no history"))
                continue
            closes, highs, lows = data
            if len(closes) < max(LOOKBACKS) + 2:
                inactive.append((name, f"only {len(closes)} bars"))
                continue
            active.append((name, symbol, closes, highs, lows))

        if inactive:
            self.log(f"Rebal@{self.time.date()} INACTIVE: "
                     + ", ".join(f"{n}({r})" for n, r in inactive))
        if not active:
            self.log(f"Rebal@{self.time.date()} no active legs, skip")
            return

        # Adaptive allocation: split portfolio across the legs that actually
        # have data. If 6/6 are live we're 1/6 each (matches research); if
        # only 3/6 are live we go 1/3 each so aggregate exposure is preserved.
        alloc_frac = 1.0 / len(active)

        # Pass 2: run the pyramid state machine + set_holdings.
        summaries = []
        for name, symbol, closes, highs, lows in active:
            res = self._process_leg(name, symbol, closes, highs, lows, alloc_frac)
            summaries.append((name, res))

        parts = []
        for name, r in summaries:
            marker = f"+{r['units']}" if r["side"] > 0 else "."
            parts.append(f"{name}:{marker}")
        total_w = sum(r["target_w"] for _, r in summaries)
        self.log(f"Rebal@{self.time.date()} active={len(active)}/{len(self._assets)} "
                 f"alloc={alloc_frac:.3f} total_w={total_w:.2f} | " + " ".join(parts))
