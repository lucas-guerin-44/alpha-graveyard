"""One-shot XAUUSD H1 puller from datalake. Discarded after profiling lands."""
import os, requests, time, sys
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
url = os.environ['DATALAKE_URL'].rstrip('/')
key = os.environ['DATALAKE_API_KEY']

all_rows = []
for yr in range(2012, 2027):
    t0 = time.time()
    r = requests.get(
        f'{url}/api/query',
        params={
            'instrument': 'XAUUSD',
            'timeframe': 'H1',
            'start': f'{yr}-01-01',
            'end': f'{yr}-12-31',
            'limit': 10000,
        },
        headers={'X-API-Key': key},
        timeout=60,
    )
    rows = r.json().get('data', [])
    elapsed = time.time() - t0
    all_rows.extend(rows)
    print(f'  {yr}: {len(rows)} rows in {elapsed:.1f}s (total {len(all_rows)})', flush=True)

df = pd.DataFrame(all_rows)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').drop_duplicates(subset='timestamp')
print(f'\nfinal: {len(df)} unique rows, {df["timestamp"].min()} -> {df["timestamp"].max()}')
df.to_csv('ohlc_data/XAUUSD_H1.csv', index=False)
print('saved')
