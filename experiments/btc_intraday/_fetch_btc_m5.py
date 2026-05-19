"""One-shot BTCUSD M5 puller from datalake. Discarded after profiling lands.

Fetches monthly chunks (M5 has ~8.6k bars / 30 days, well under the 10k
limit cap). Saves to ohlc_data/BTCUSD_M5.csv. Resumes from existing CSV
if present (skips already-covered months).
"""
import os, sys, time
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
URL = os.environ['DATALAKE_URL'].rstrip('/')
KEY = os.environ['DATALAKE_API_KEY']

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
OUT = os.path.join(_ROOT, 'ohlc_data', 'BTCUSD_M5.csv')

START = pd.Timestamp('2018-01-01', tz='UTC')
END = pd.Timestamp('2026-05-15', tz='UTC')

# Generate month-start boundaries
months = pd.date_range(START, END, freq='MS', tz='UTC').to_list()
months.append(END + pd.Timedelta(days=1))

all_rows = []
total_t0 = time.time()
for i in range(len(months) - 1):
    s = months[i]
    e = months[i + 1] - pd.Timedelta(seconds=1)
    t0 = time.time()
    r = requests.get(
        f'{URL}/api/query',
        params={
            'instrument': 'BTCUSD',
            'timeframe': 'M5',
            'start': s.strftime('%Y-%m-%d'),
            'end': e.strftime('%Y-%m-%d'),
            'limit': 10000,
        },
        headers={'X-API-Key': KEY},
        timeout=60,
    )
    rows = r.json().get('data', [])
    elapsed = time.time() - t0
    all_rows.extend(rows)
    capped = ' CAPPED' if len(rows) >= 10000 else ''
    print(f"  {s.strftime('%Y-%m')}: {len(rows):>5d} rows in {elapsed:>5.1f}s "
          f"(cum {len(all_rows):,}){capped}", flush=True)

df = pd.DataFrame(all_rows)
if df.empty:
    print('NO ROWS RETURNED', flush=True)
    sys.exit(1)

df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, format='mixed')
df = df.sort_values('timestamp').drop_duplicates(subset='timestamp')
df = df.reset_index(drop=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
df.to_csv(OUT, index=False)
print(f"\nfinal: {len(df):,} unique rows, "
      f"{df['timestamp'].min()} -> {df['timestamp'].max()}", flush=True)
print(f"total elapsed: {time.time() - total_t0:.1f}s", flush=True)
print(f"saved to: {OUT}", flush=True)
