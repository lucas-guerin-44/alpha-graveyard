#!/usr/bin/env python3
"""Eightcap trend-universe scope probe.

Scopes the DEPLOYABLE trend-following universe: for each candidate instrument,
pull from the live Eightcap MT5 terminal (a) tradeability (symbol exists +
trade_mode FULL), and (b) overnight financing (swap_long / swap_short), which is
the binding constraint for multi-week trend holds (lessons #59, #86).

Authoritative source = MT5 symbol_info (NOT datalake/disk — lake presence != broker
tradeable). Re-runnable on the live account.

Run: PYTHONIOENCODING=utf-8 venv/Scripts/python.exe experiments/trend_book/_scope_probe.py
"""
from __future__ import annotations
import MetaTrader5 as mt5

# tsmom universe (research names) + a few obvious trend candidates, grouped.
# We resolve each research name to the actual Eightcap symbol via fuzzy match.
CANDIDATES = {
    'FX majors':   ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'AUDUSD', 'NZDUSD'],
    'FX exotic':   ['AUDNZD', 'NZDCAD', 'GBPNZD', 'AUDCAD', 'CADJPY', 'NZDJPY',
                    'EURGBP', 'EURNOK', 'USDZAR'],
    'Index':       ['SPX500', 'NDX100', 'GER40', 'UK100', 'FRA40', 'JPN225', 'AUS200', 'HK50'],
    'Metals':      ['XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD', 'COPPER'],
    'Energy':      ['USOUSD', 'UKOUSD', 'NATGAS', 'WTI', 'XBRUSD', 'XTIUSD'],
    'Ag/softs':    ['COCOA', 'COFFEE', 'SUGAR', 'COTTON', 'CORN', 'WHEAT', 'SOYBEAN'],
    'Crypto':      ['BTCUSD', 'ETHUSD'],
    'Country ETF': ['EWZ', 'FXI', 'EWJ'],
}

SWAP_MODE = {0: 'DISABLED', 1: 'POINTS', 2: 'CCY_SYM', 3: 'CCY_MARGIN',
             4: 'CCY_DEP', 5: 'INT_CURR', 6: 'INT_OPEN', 7: 'REOPEN_C', 8: 'REOPEN_B'}
TRADE_MODE = {0: 'DISABLED', 1: 'LONGONLY', 2: 'SHORTONLY', 3: 'CLOSEONLY', 4: 'FULL'}


def annual_pct(si, price):
    """Best-effort annual financing % of notional for a LONG (and short)."""
    sl, ss = si.swap_long, si.swap_short
    if si.swap_mode == 1:  # POINTS: daily price-units = swap*point; frac = /price; ~365/yr
        if price and price > 0:
            return sl * si.point / price * 365 * 100, ss * si.point / price * 365 * 100
    elif si.swap_mode in (5, 6):  # INTEREST: swap_* already annual %
        return sl, ss
    return None, None


def main():
    if not mt5.initialize():
        print('MT5 init failed:', mt5.last_error())
        return 1
    all_syms = {s.name: s for s in (mt5.symbols_get() or [])}
    names = list(all_syms)

    def resolve(stub: str) -> str | None:
        # direct, then common Eightcap aliases / substring
        if stub in all_syms:
            return stub
        aliases = {
            'SPX500': ['US500', 'SP500', 'SPX500'], 'NDX100': ['US100', 'NAS100', 'USTEC'],
            'GER40': ['DE40', 'GER40', 'GER30', 'DE30'], 'UK100': ['UK100', 'FTSE100'],
            'FRA40': ['FRA40', 'FR40', 'CAC40'], 'JPN225': ['JP225', 'JPN225', 'JP225'],
            'AUS200': ['AUS200', 'AU200'], 'HK50': ['HK50', 'HSI50', 'HK33'],
            'USOUSD': ['XTIUSD', 'USOIL', 'WTI', 'USOUSD', 'OILUSD'],
            'UKOUSD': ['XBRUSD', 'UKOIL', 'BRENT', 'UKOUSD'],
            'WTI': ['XTIUSD', 'USOIL'], 'NATGAS': ['XNGUSD', 'NATGAS', 'NGAS'],
            'COPPER': ['XCUUSD', 'COPPER', 'COPPER-C'],
            'BTCUSD': ['BTCUSD'], 'ETHUSD': ['ETHUSD'],
            'EWZ': ['EWZ.US', 'EWZ'], 'FXI': ['FXI.US', 'FXI'], 'EWJ': ['EWJ.US', 'EWJ'],
            'COCOA': ['COCOA', 'COCOA-C'], 'COFFEE': ['COFFEE', 'COFFEE-C'],
            'SUGAR': ['SUGAR', 'SUGAR-C'], 'COTTON': ['COTTON', 'COTTON-C'],
            'CORN': ['CORN', 'CORN-C'], 'WHEAT': ['WHEAT', 'WHEAT-C'],
            'SOYBEAN': ['SOYBEAN', 'SOYBEAN-C', 'SOYBEANS'],
        }
        for a in aliases.get(stub, []):
            if a in all_syms:
                return a
        # substring fallback
        hits = [n for n in names if stub[:4] in n.upper()]
        return hits[0] if hits else None

    print(f'{"class":<11s} {"stub":<8s} {"broker":<10s} {"trade":<8s} {"swapmode":<8s} '
          f'{"swapL":>8s} {"swapS":>8s} {"annL%":>7s} {"annS%":>7s}  deployable')
    print('-' * 100)
    for cls, stubs in CANDIDATES.items():
        for stub in stubs:
            bn = resolve(stub)
            if bn is None:
                print(f'{cls:<11s} {stub:<8s} {"--":<10s} {"NOT OFFERED":<8s}')
                continue
            si = all_syms[bn]
            mt5.symbol_select(bn, True)
            tick = mt5.symbol_info_tick(bn)
            price = (tick.bid if tick else 0) or si.bid or 0
            al, ash = annual_pct(si, price)
            tm = TRADE_MODE.get(si.trade_mode, str(si.trade_mode))
            sm = SWAP_MODE.get(si.swap_mode, str(si.swap_mode))
            # deployable for long-only trend: FULL trade + long swap not catastrophic (> -12%/yr)
            dep = 'YES' if (si.trade_mode == 4 and (al is None or al > -12)) else \
                  ('swap?' if si.trade_mode == 4 else 'NO-trade')
            als = f'{al:>7.1f}' if al is not None else '   n/a '
            ass = f'{ash:>7.1f}' if ash is not None else '   n/a '
            print(f'{cls:<11s} {stub:<8s} {bn:<10s} {tm:<8s} {sm:<8s} '
                  f'{si.swap_long:>8.2f} {si.swap_short:>8.2f} {als} {ass}  {dep}')
    mt5.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
