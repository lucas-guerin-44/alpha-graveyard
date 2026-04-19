"""
Blended 3-strategy portfolio -- QuantConnect live algorithm.

Equal-weight (1/3 each) allocation across:
  1. XS-momentum long-only (live-deployed, params from qc_xs_momentum.py)
  2. Treasury-trend IEF-MH (research-validated Phase 2-7)
  3. BTC-trend MH-LO+pyramid (research-validated Phase 2-7)

Research-estimated blend Sharpe 1.29 (vs 0.91 / 0.91 / 0.64 standalone),
blend MDD -9% (vs -17% / -22% / -8% standalone). This algorithm runs the
QC-reality check: does the blend benefit survive execution costs on all
three legs simultaneously?

Sizing: each sub-strategy's position weights are scaled by ALLOC_FRAC =
1/3 before being passed to set_holdings. When XS-mom is fully long its
top-5 at 1/5 each, that becomes 1/15 (~6.67%) of TOTAL portfolio per
name. Max total exposure ~100% (no leverage).

Rebalance cadence:
  * XS-mom: every 63 bars (quarterly), anchored to SPY
  * Treasury-trend: every 21 bars (monthly), anchored to SPY
  * BTC-trend: every 21 bars (monthly), anchored to BTC's crypto calendar

See experiments/btc_trend/btc_phase7_correlation.py for research blend result.
"""

from AlgorithmImports import *
import numpy as np

# =============================================================================
# CONFIG
# =============================================================================

ALLOC_FRAC = 1.0 / 3.0
BARS_PER_YEAR = 252

# ---- XS-momentum (verbatim from qc_xs_momentum.py live params) ----
XS_LOOKBACK_BARS  = 189
XS_SKIP_BARS      = 42
XS_REBALANCE_BARS = 63
XS_TOP_K          = 5

XS_FX_PAIRS = ["AUDNZD","NZDCAD","GBPNZD","AUDCAD","CADJPY","NZDJPY",
               "EURGBP","EURNOK","USDZAR","EURUSD","GBPUSD"]
XS_EQUITY_ETFS    = ["EWZ","FXI","EWJ","SPY","QQQ","EWG"]
XS_COMMODITY_ETFS = ["GLD","USO"]
XS_SOFTS_FUTURES  = [
    ("COCOA",  Futures.Softs.COCOA),
    ("COFFEE", Futures.Softs.COFFEE),
    ("SUGAR",  Futures.Softs.SUGAR_11),
    ("COTTON", Futures.Softs.COTTON_2),
]

# ---- Treasury-trend (IEF-MH, 10% vol-target) ----
TT_LOOKBACKS        = (21, 63, 252)
TT_REBALANCE_BARS   = 21
TT_VOL_LOOKBACK     = 60
TT_VOL_TARGET_ANN   = 0.10
TT_GROSS_CAP        = 1.0

# ---- BTC-trend (MH-LO + pyramid, 15% vol-target) ----
BTC_LOOKBACKS         = (21, 63, 252)
BTC_REBALANCE_BARS    = 21
BTC_VOL_LOOKBACK      = 60
BTC_VOL_TARGET_ANN    = 0.15
BTC_GROSS_CAP         = 1.0
BTC_PYRAMID_STEPS     = 3
BTC_PYRAMID_ATR_MULT  = 1.0
BTC_ATR_LOOKBACK      = 14

WARMUP_BARS = max(
    XS_LOOKBACK_BARS + XS_SKIP_BARS,
    max(TT_LOOKBACKS) + TT_VOL_LOOKBACK,
    max(BTC_LOOKBACKS) + BTC_VOL_LOOKBACK,
) + 15


class BlendedTrio(QCAlgorithm):
    """XS-mom + Treasury-trend + BTC-trend, equal-weight."""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self):
        self.set_start_date(2018, 1, 1)   # BTC data begins here
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        # No brokerage model set: QC falls back to DefaultBrokerageModel,
        # which is the only built-in that supports all the security types
        # we use here (stocks, FX, futures, crypto) in one algorithm.
        # IB/Coinbase brokerage models each only cover a subset and would
        # reject the others. Fee models are approximate per asset class.

        # ---- XS-mom universe ----
        self._xs_assets = {}
        for pair in XS_FX_PAIRS:
            sym = self.add_forex(pair, Resolution.DAILY, Market.OANDA).symbol
            self._xs_assets[pair] = sym
        for ticker in XS_EQUITY_ETFS:
            sym = self.add_equity(ticker, Resolution.DAILY).symbol
            self._xs_assets[ticker] = sym
        for ticker in XS_COMMODITY_ETFS:
            sym = self.add_equity(ticker, Resolution.DAILY).symbol
            self._xs_assets[ticker] = sym
        for name, root in XS_SOFTS_FUTURES:
            future = self.add_future(root, Resolution.DAILY)
            future.set_filter(0, 180)
            self._xs_assets[name] = future.symbol

        # ---- Treasury-trend ----
        self._ief = self.add_equity("IEF", Resolution.DAILY).symbol
        self._bil = self.add_equity("BIL", Resolution.DAILY).symbol

        # ---- BTC-trend ----
        self._btc = self.add_crypto(
            "BTCUSD", Resolution.DAILY, Market.COINBASE,
        ).symbol

        self.set_warm_up(WARMUP_BARS, Resolution.DAILY)

        # ---- Per-substrategy state ----
        # XS-mom
        self._xs_day = 0
        self._xs_last_rebal = -XS_REBALANCE_BARS

        # Treasury-trend
        self._tt_day = 0
        self._tt_last_rebal = -TT_REBALANCE_BARS

        # BTC-trend (pyramid state)
        self._btc_day = 0
        self._btc_last_rebal = -BTC_REBALANCE_BARS
        self._btc_cur_side = 0
        self._btc_cur_units = 0
        self._btc_full_target = 0.0
        self._btc_last_inc_price = None
        self._btc_last_inc_atr = None

        # ---- Schedules ----
        # XS-mom + treasury anchor to the equity calendar (SPY trading days).
        self.schedule.on(
            self.date_rules.every_day("SPY"),
            self.time_rules.before_market_close("SPY", 10),
            self._tick_equity_day,
        )
        # BTC anchors to its own 24/7 crypto calendar.
        self.schedule.on(
            self.date_rules.every_day(self._btc),
            self.time_rules.at(23, 55),
            self._tick_btc_day,
        )

    def on_data(self, data):
        pass

    # ------------------------------------------------------------------
    # Calendar ticks
    # ------------------------------------------------------------------

    def _tick_equity_day(self):
        if self.is_warming_up:
            return
        self._xs_day += 1
        self._tt_day += 1
        if self._xs_day - self._xs_last_rebal >= XS_REBALANCE_BARS:
            self._rebalance_xsmom()
        if self._tt_day - self._tt_last_rebal >= TT_REBALANCE_BARS:
            self._rebalance_treasury()

    def _tick_btc_day(self):
        if self.is_warming_up:
            return
        self._btc_day += 1
        if self._btc_day - self._btc_last_rebal >= BTC_REBALANCE_BARS:
            self._rebalance_btc()

    # ------------------------------------------------------------------
    # Shared data fetch
    # ------------------------------------------------------------------

    def _get_closes(self, symbol, n):
        hist = self.history(symbol, n, Resolution.DAILY)
        if hist is None or hist.empty:
            return None
        if "close" in hist.columns:
            closes = hist["close"].to_numpy()
        elif "askclose" in hist.columns and "bidclose" in hist.columns:
            closes = ((hist["bidclose"] + hist["askclose"]) / 2.0).to_numpy()
        else:
            return None
        closes = closes[~np.isnan(closes)]
        return closes if closes.size > 0 else None

    def _get_ohlc(self, symbol, n):
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

    # ------------------------------------------------------------------
    # XS-momentum
    # ------------------------------------------------------------------

    def _rebalance_xsmom(self):
        needed = XS_LOOKBACK_BARS + XS_SKIP_BARS + 2
        signals = {}
        for name, sym in self._xs_assets.items():
            closes = self._get_closes(sym, needed + 5)
            if closes is None or len(closes) < needed:
                continue
            past = closes[-XS_LOOKBACK_BARS]
            recent = closes[-(XS_SKIP_BARS + 1)]
            if past <= 0:
                continue
            signals[name] = (recent - past) / past

        self._xs_last_rebal = self._xs_day

        if len(signals) < XS_TOP_K:
            self.debug(f"XS: only {len(signals)} signals, skipping")
            return

        ranked = sorted(signals.items(), key=lambda x: x[1], reverse=True)
        top_names = {n for n, _ in ranked[:XS_TOP_K]}
        per_name_weight = ALLOC_FRAC / XS_TOP_K  # 1/15 = ~6.67%

        for name, sym in self._xs_assets.items():
            if name in top_names:
                self.set_holdings(sym, per_name_weight)
            elif self.portfolio[sym].invested:
                self.liquidate(sym)

        self.log(f"XS rebal: top-{XS_TOP_K}={sorted(top_names)} "
                 f"top_sig={ranked[0][1]:+.2%} bot_sig={ranked[-1][1]:+.2%}")

    # ------------------------------------------------------------------
    # Treasury-trend (IEF-MH)
    # ------------------------------------------------------------------

    def _rebalance_treasury(self):
        closes = self._get_closes(self._ief, max(TT_LOOKBACKS) + TT_VOL_LOOKBACK + 5)
        self._tt_last_rebal = self._tt_day
        if closes is None or len(closes) < max(TT_LOOKBACKS) + 2:
            return

        # Multi-horizon binary signal: mean of 1[past-return > 0] over each lookback.
        sigs = []
        for lb in TT_LOOKBACKS:
            if len(closes) <= lb:
                continue
            past = closes[-lb - 1]
            now = closes[-1]
            if past <= 0:
                continue
            sigs.append(1.0 if (now - past) / past > 0 else 0.0)
        sig = float(np.mean(sigs)) if sigs else 0.0  # in [0, 1]

        # Realized vol on t-1 window (shift-by-one, no look-ahead).
        if len(closes) < TT_VOL_LOOKBACK + 2:
            return
        win = closes[-TT_VOL_LOOKBACK - 1:-1]
        rets = np.diff(win) / win[:-1]
        rets = rets[np.isfinite(rets)]
        if len(rets) < TT_VOL_LOOKBACK // 2:
            return
        rv_daily = float(np.std(rets, ddof=1))
        if rv_daily <= 0:
            return
        rv_ann = rv_daily * np.sqrt(BARS_PER_YEAR)
        vol_scale = min(TT_VOL_TARGET_ANN / rv_ann, TT_GROSS_CAP)

        # Sub-portfolio weights (sum to 1): long IEF at sig * vol_scale,
        # remainder in BIL cash overlay. Then scale by ALLOC_FRAC.
        w_ief_sub = sig * vol_scale
        w_bil_sub = 1.0 - w_ief_sub

        self.set_holdings(self._ief, w_ief_sub * ALLOC_FRAC)
        self.set_holdings(self._bil, w_bil_sub * ALLOC_FRAC)

        self.log(f"TT rebal: sig={sig:.2f} vol_scale={vol_scale:.2f} "
                 f"IEF={w_ief_sub * ALLOC_FRAC:.3f} BIL={w_bil_sub * ALLOC_FRAC:.3f}")

    # ------------------------------------------------------------------
    # BTC-trend (MH-LO + pyramid)
    # ------------------------------------------------------------------

    def _rebalance_btc(self):
        ohlc = self._get_ohlc(self._btc, max(BTC_LOOKBACKS) + 5)
        self._btc_last_rebal = self._btc_day
        if ohlc is None:
            return
        closes, highs, lows = ohlc
        if len(closes) < max(BTC_LOOKBACKS) + 2:
            return

        # Multi-horizon signed signal
        sigs = []
        for lb in BTC_LOOKBACKS:
            if len(closes) <= lb:
                continue
            past = closes[-lb - 1]
            now = closes[-1]
            if past <= 0:
                continue
            r = (now - past) / past
            sigs.append(1.0 if r > 0 else (-1.0 if r < 0 else 0.0))
        sig_raw = float(np.mean(sigs)) if sigs else 0.0
        side_new = 1 if sig_raw > 0 else 0  # long-only, no shorts

        # Realized vol
        rv_ann = None
        if len(closes) >= BTC_VOL_LOOKBACK + 2:
            win = closes[-BTC_VOL_LOOKBACK - 1:-1]
            rets = np.diff(win) / win[:-1]
            rets = rets[np.isfinite(rets)]
            if len(rets) >= BTC_VOL_LOOKBACK // 2:
                s = float(np.std(rets, ddof=1))
                if s > 0:
                    rv_ann = s * np.sqrt(BARS_PER_YEAR)

        vol_scale = 0.0
        if rv_ann is not None and rv_ann > 1e-6:
            vol_scale = min(BTC_VOL_TARGET_ANN / rv_ann, BTC_GROSS_CAP)

        # ATR (simple mean of true range)
        atr_val = None
        if len(closes) >= BTC_ATR_LOOKBACK + 1:
            prev_close = closes[-BTC_ATR_LOOKBACK - 1:-1]
            h = highs[-BTC_ATR_LOOKBACK:]
            l = lows[-BTC_ATR_LOOKBACK:]
            tr = np.maximum.reduce([
                h - l,
                np.abs(h - prev_close),
                np.abs(l - prev_close),
            ])
            atr_val = float(np.mean(tr))
        price_t = float(closes[-1])

        # Pyramid state machine (mirrors simulate_tsmom_pyramid)
        if side_new == 0 or vol_scale <= 0.0:
            self._btc_cur_side = 0
            self._btc_cur_units = 0
            self._btc_full_target = 0.0
            self._btc_last_inc_price = None
            self._btc_last_inc_atr = None
            target_w_sub = 0.0
        elif side_new != self._btc_cur_side:
            self._btc_cur_side = side_new
            self._btc_full_target = vol_scale
            self._btc_cur_units = 1
            self._btc_last_inc_price = price_t
            self._btc_last_inc_atr = atr_val
            target_w_sub = side_new * vol_scale * (1.0 / BTC_PYRAMID_STEPS)
        else:
            self._btc_full_target = vol_scale
            can_add = (
                self._btc_cur_units < BTC_PYRAMID_STEPS
                and self._btc_last_inc_price is not None
                and self._btc_last_inc_atr is not None
                and self._btc_last_inc_atr > 0
            )
            if can_add:
                favorable = self._btc_cur_side * (price_t - self._btc_last_inc_price)
                if favorable >= BTC_PYRAMID_ATR_MULT * self._btc_last_inc_atr:
                    self._btc_cur_units += 1
                    self._btc_last_inc_price = price_t
                    self._btc_last_inc_atr = atr_val
            target_w_sub = (self._btc_cur_side * self._btc_full_target
                            * (self._btc_cur_units / BTC_PYRAMID_STEPS))

        self.set_holdings(self._btc, target_w_sub * ALLOC_FRAC)

        self.log(f"BTC rebal: sig={sig_raw:+.2f} side={self._btc_cur_side} "
                 f"units={self._btc_cur_units}/{BTC_PYRAMID_STEPS} "
                 f"sub_w={target_w_sub:.3f} port_w={target_w_sub * ALLOC_FRAC:.3f} "
                 f"px=${price_t:,.0f}")
