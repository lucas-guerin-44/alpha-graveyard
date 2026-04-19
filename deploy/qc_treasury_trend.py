"""
Treasury Trend (IEF multi-horizon TSMOM) — QuantConnect live algorithm.

Research params from experiments/treasury_trend/ (2002-2026 validation):
  LOOKBACKS       = (21, 63, 252)   # 1M + 3M + 12M, sign-averaged per MOP 2012
  REBALANCE_BARS  = 21              # monthly
  VOL_LOOKBACK    = 60              # 60-day realised vol window
  VOL_TARGET_ANN  = 0.10            # 10% annualised when long
  GROSS_CAP       = 1.0             # no leverage past vol-target
  Signal scale    = avg(binary TSMOM signals) in {0, 1/3, 2/3, 1}
  Position: long IEF × scale × vol_target / realized_vol; BIL for the remainder

Research full-period Sharpe 0.67 (24y), holdout 2015-2026 Sharpe 0.42,
degradation 0.40 (under 0.5 kill threshold). Caught 2022 bond crash
cleanly: IEF-trend +1.41% vs TLT buy-and-hold -29.39%. Monthly correlation
with XS-mom ≈ 0 — first genuine diversifier in the project.

Variant preferred: **IEF-trend multi-horizon** over single-horizon 12M
because MH has 4× the trade count (77 vs 19) with near-identical Sharpe,
and better MDD (-8.1% vs -9.1%). Phases 2-7 all PASS on 24y sample.

Paste into a new Python algorithm in the QuantConnect IDE. PEP-8 snake_case
API (current QC convention as of 2026).

See experiments/treasury_trend/treasury_trend.md for the full thesis and
validation record.

---

Instruments on QC (all in free data tier, no paid add-ons needed):
  - IEF (iShares 7-10 Year Treasury Bond, ~$25B AUM, ~8y duration)
  - BIL (SPDR Bloomberg 1-3 Month T-Bill, effectively risk-free)

Both US-listed ETFs, trade 09:30-16:00 ET, 1-bps typical bid-ask spreads.
IB brokerage model applies ~$1/side commission for small retail orders.
Cost assumption in research was 3 bps/side = 6 bps round-trip; QC's
default fee model will be slightly different but in the same ballpark.
"""

from AlgorithmImports import *
import numpy as np


# =============================================================================
# CONFIG -- research-frozen params
# =============================================================================

LOOKBACKS        = (21, 63, 252)   # multi-horizon: 1M + 3M + 12M
REBALANCE_BARS   = 21              # monthly
VOL_LOOKBACK     = 60              # realised-vol window
VOL_TARGET_ANN   = 0.10            # 10% annualised when long
GROSS_CAP        = 1.0             # cap at 1.0x equity (no leverage past vol-target)
BARS_PER_YEAR    = 252             # annualisation factor

IEF_TICKER       = "IEF"           # iShares 7-10 Year Treasury
BIL_TICKER       = "BIL"           # SPDR 1-3 Month T-Bill (cash alt when flat)


class TreasuryTrendMHLO(QCAlgorithm):
    """
    Multi-horizon long-only TSMOM on IEF with BIL as cash alternative.

    Signal at each monthly rebalance:
        for lb in (21, 63, 252):
            s[lb] = 1 if IEF[t] / IEF[t-lb] - 1 > 0 else 0
        scale = mean(s) ∈ {0, 1/3, 2/3, 1}

    Position size:
        vol = realised 60-day std of IEF daily returns × sqrt(252)
        vol_scale = min(VOL_TARGET_ANN / vol, GROSS_CAP)
        ief_weight = scale × vol_scale
        bil_weight = 1 - ief_weight

    Rebalance every 21 trading days. Otherwise carry previous weights.
    Long-only; BIL absorbs whatever fraction of the book isn't in IEF.
    """

    def initialize(self):
        self.set_start_date(2015, 1, 1)
        self.set_end_date(2026, 4, 18)
        self.set_cash(100_000)

        self.set_brokerage_model(
            BrokerageName.INTERACTIVE_BROKERS_BROKERAGE,
            AccountType.MARGIN,
        )

        self._ief_symbol = self.add_equity(IEF_TICKER, Resolution.DAILY).symbol
        self._bil_symbol = self.add_equity(BIL_TICKER, Resolution.DAILY).symbol

        # Warm-up: need max lookback (252) + vol window (60) + buffer.
        self._warmup_bars = max(LOOKBACKS) + VOL_LOOKBACK + 10
        self.set_warm_up(self._warmup_bars, Resolution.DAILY)

        # Rebalance cadence.
        self._trading_day_count = 0
        self._last_rebal_day = -REBALANCE_BARS  # ensure the first eligible day triggers

        # Anchor schedule to IEF's own calendar. Check daily at close; actual
        # rebalance is gated by the REBALANCE_BARS counter.
        self.schedule.on(
            self.date_rules.every_day(self._ief_symbol),
            self.time_rules.before_market_close(self._ief_symbol, 10),
            self.try_rebalance,
        )

    # -------------------------------------------------------------------
    # Data helpers
    # -------------------------------------------------------------------

    def _get_closes(self, symbol, n_bars):
        """Pull n_bars of daily close prices for a tradable equity."""
        hist = self.history(symbol, n_bars, Resolution.DAILY)
        if hist is None or hist.empty or "close" not in hist.columns:
            return None
        closes = hist["close"].values
        return closes[~np.isnan(closes)]

    def _multi_horizon_signal(self, closes):
        """Average of binary TSMOM signals across the configured lookbacks.

        Returns a float in [0, 1]. Each lookback contributes 1/N if the
        trailing return over that lookback is positive.
        """
        n = len(closes)
        sub_signals = []
        for lb in LOOKBACKS:
            if n <= lb:
                return None                         # insufficient history
            past = closes[-(lb + 1)]                # price lb bars ago (skip today)
            recent = closes[-1]
            if past <= 0:
                return None
            r = recent / past - 1.0
            sub_signals.append(1.0 if r > 0 else 0.0)
        return float(np.mean(sub_signals))

    def _realized_vol(self, closes):
        """Annualised realised vol over the last VOL_LOOKBACK daily returns."""
        if len(closes) < VOL_LOOKBACK + 1:
            return None
        rets = np.diff(closes[-(VOL_LOOKBACK + 1):]) / closes[-(VOL_LOOKBACK + 1):-1]
        rets = rets[np.isfinite(rets)]
        if rets.size < VOL_LOOKBACK // 2:
            return None
        std = float(np.std(rets, ddof=1))
        if std <= 0 or not np.isfinite(std):
            return None
        return std * np.sqrt(BARS_PER_YEAR)

    # -------------------------------------------------------------------
    # Core rebalance
    # -------------------------------------------------------------------

    def try_rebalance(self):
        if self.is_warming_up:
            return

        self._trading_day_count += 1
        if self._trading_day_count - self._last_rebal_day < REBALANCE_BARS:
            return

        needed = max(LOOKBACKS) + VOL_LOOKBACK + 2
        ief_closes = self._get_closes(self._ief_symbol, needed + 5)
        if ief_closes is None or len(ief_closes) < needed:
            self.debug(f"IEF history insufficient ({None if ief_closes is None else len(ief_closes)} bars) — skipping rebalance")
            return

        scale = self._multi_horizon_signal(ief_closes)   # in [0, 1]
        vol = self._realized_vol(ief_closes)

        if scale is None or vol is None:
            self.debug(f"signal={scale} vol={vol} — skipping rebalance")
            return

        vol_scale = min(VOL_TARGET_ANN / vol, GROSS_CAP)
        ief_weight = float(scale) * float(vol_scale)
        bil_weight = max(0.0, 1.0 - ief_weight)

        # Clamp to [0, GROSS_CAP] defensively.
        ief_weight = max(0.0, min(ief_weight, GROSS_CAP))

        self.set_holdings(self._ief_symbol, ief_weight)
        self.set_holdings(self._bil_symbol, bil_weight)

        self._last_rebal_day = self._trading_day_count

        # Decompose signal for log clarity.
        lb_signs = []
        for lb in LOOKBACKS:
            past = ief_closes[-(lb + 1)]
            r = ief_closes[-1] / past - 1.0
            lb_signs.append(f"{lb}d={'+' if r > 0 else '-'}{abs(r):.1%}")

        self.log(
            f"Rebal: scale={scale:.2f} vol={vol:.2%} "
            f"vol_scale={vol_scale:.2f} | IEF={ief_weight:.2%} BIL={bil_weight:.2%} "
            f"| signals: {' '.join(lb_signs)}"
        )

    def on_data(self, data):
        pass
