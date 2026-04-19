"""
Cross-Sectional Momentum (XS-mom) — QuantConnect live algorithm.

IS-optimal params from research repo validation (2015-2022 IS, 2023+ OOS):
  lookback=189, skip=42, rebalance=63, top_k=5

Research full-period Sharpe 0.92 (+260%). QC live-backtest Sharpe ~0.35
(+144%) due to ETF substitutions for CFDs, no BTC, and realistic costs.

Paste into a new Python algorithm in the QuantConnect IDE. PEP-8 snake_case
API (current QC convention as of 2026).

See experiments/xs_momentum/xs_momentum.md in the research repo for the full thesis and
validation record.
"""

from AlgorithmImports import *
import numpy as np

# =============================================================================
# CONFIG — IS-optimal params
# =============================================================================
LOOKBACK_BARS   = 189
SKIP_BARS       = 42
REBALANCE_DAYS  = 63
TOP_K           = 5

INCLUDE_FX              = True
INCLUDE_EQUITY_ETFS     = True
INCLUDE_COMMODITY_ETFS  = True
INCLUDE_SOFTS_FUTURES   = True
INCLUDE_CRYPTO          = False

FX_PAIRS = ["AUDNZD","NZDCAD","GBPNZD","AUDCAD","CADJPY","NZDJPY",
            "EURGBP","EURNOK","USDZAR","EURUSD","GBPUSD"]
EQUITY_ETFS = ["EWZ","FXI","EWJ","SPY","QQQ","EWG"]
COMMODITY_ETFS = ["GLD","USO"]
SOFTS_FUTURES = [
    ("COCOA",  Futures.Softs.COCOA),
    ("COFFEE", Futures.Softs.COFFEE),
    ("SUGAR",  Futures.Softs.SUGAR_11),
    ("COTTON", Futures.Softs.COTTON_2),
]


class CrossSectionalMomentumXSMOM(QCAlgorithm):
    """
    At each rebalance, rank all assets by past (lookback->skip) return,
    long the top K equal-weight, flatten everything else.
    """

    def initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        self.set_brokerage_model(
            BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
            AccountType.MARGIN,
        )

        self.assets = {}

        if INCLUDE_FX:
            for pair in FX_PAIRS:
                sym = self.add_forex(pair, Resolution.DAILY, Market.OANDA).symbol
                self.assets[pair] = sym

        if INCLUDE_EQUITY_ETFS:
            for ticker in EQUITY_ETFS:
                sym = self.add_equity(ticker, Resolution.DAILY).symbol
                self.assets[ticker] = sym

        if INCLUDE_COMMODITY_ETFS:
            for ticker in COMMODITY_ETFS:
                sym = self.add_equity(ticker, Resolution.DAILY).symbol
                self.assets[ticker] = sym

        if INCLUDE_SOFTS_FUTURES:
            for name, root in SOFTS_FUTURES:
                future = self.add_future(root, Resolution.DAILY)
                future.set_filter(0, 180)
                self.assets[name] = future.symbol

        if INCLUDE_CRYPTO:
            sym = self.add_crypto("BTCUSD", Resolution.DAILY, Market.COINBASE).symbol
            self.assets["BTCUSD"] = sym

        self.set_warm_up(LOOKBACK_BARS + SKIP_BARS + 5, Resolution.DAILY)

        self._trading_day_count = 0
        self._last_rebal_day = -REBALANCE_DAYS

        self.schedule.on(
            self.date_rules.every_day("SPY"),
            self.time_rules.before_market_close("SPY", 10),
            self.try_rebalance,
        )

    def _get_closes(self, symbol, n_bars):
        """Return numpy array of close prices. Handles FX quote-bars vs trade-bars."""
        hist = self.history(symbol, n_bars, Resolution.DAILY)
        if hist is None or hist.empty:
            return None

        if "close" in hist.columns:
            closes = hist["close"].values
        elif "askclose" in hist.columns and "bidclose" in hist.columns:
            closes = ((hist["bidclose"] + hist["askclose"]) / 2.0).values
        else:
            return None

        return closes[~np.isnan(closes)]

    def try_rebalance(self):
        if self.is_warming_up:
            return

        self._trading_day_count += 1
        if self._trading_day_count - self._last_rebal_day < REBALANCE_DAYS:
            return

        needed = LOOKBACK_BARS + SKIP_BARS + 2
        signals = {}
        for name, symbol in self.assets.items():
            closes = self._get_closes(symbol, needed + 5)
            if closes is None or len(closes) < needed:
                continue
            past   = closes[-LOOKBACK_BARS]
            recent = closes[-(SKIP_BARS + 1)]
            if past <= 0:
                continue
            signals[name] = (recent - past) / past

        if len(signals) < TOP_K:
            self.debug(f"Only {len(signals)} eligible signals — skipping rebalance")
            return

        ranked = sorted(signals.items(), key=lambda x: x[1], reverse=True)
        top_names = {n for n, _ in ranked[:TOP_K]}
        weight = 1.0 / TOP_K

        for name, symbol in self.assets.items():
            if name in top_names:
                self.set_holdings(symbol, weight)
            elif self.portfolio[symbol].invested:
                self.liquidate(symbol)

        self._last_rebal_day = self._trading_day_count
        self.log(f"Rebalance: long top-{TOP_K} = {sorted(top_names)} | "
                 f"top signal {ranked[0][1]:+.2%}, bottom {ranked[-1][1]:+.2%}")

    def on_data(self, data):
        pass
