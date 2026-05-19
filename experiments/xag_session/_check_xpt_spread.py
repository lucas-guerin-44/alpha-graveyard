"""Quick spread check on XPTUSD M1 last 30d — needed to determine if platinum
is cost-deployable on Eightcap retail."""
import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import pandas as pd

if not mt5.initialize():
    print('init fail'); exit(1)
si = mt5.symbol_info('XPTUSD')
print(f'XPTUSD: point={si.point} spread_pts={si.spread}')
end = datetime.now(timezone.utc)
rates = mt5.copy_rates_range('XPTUSD', mt5.TIMEFRAME_M1, end - timedelta(days=30), end)
mt5.shutdown()
df = pd.DataFrame(rates)
print(f'Got {len(df)} M1 bars')
if len(df):
    df['mid'] = (df['open'] + df['close']) / 2
    df['spread_bps'] = df['spread'] * si.point / df['mid'] * 1e4
    df['hour'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.hour
    print(f'FULL: median {df.spread_bps.median():.2f}bp p90 {df.spread_bps.quantile(0.9):.2f} max {df.spread_bps.max():.2f}')
    asia = df[df.hour.isin([22,23,0,1,2,3,4,5,6,7,8])]
    print(f'Asia 22-08: median {asia.spread_bps.median():.2f}bp p90 {asia.spread_bps.quantile(0.9):.2f}')
    ny = df[df.hour.isin([13,14,15,16,17,18,19,20])]
    print(f'NY 13-20:   median {ny.spread_bps.median():.2f}bp p90 {ny.spread_bps.quantile(0.9):.2f}')
