"""Pull XAUUSD M1 from datalake → ohlc_data/XAUUSD_M1.csv.

Shared with xau_fix_drift. Server limit is 10000 rows/request; M1 has
~5k-6k bars per trading week, so 7-day chunks fit cleanly with safety
margin. Pagination kicks in if a chunk maxes out (shouldn't, but safe).
"""
import os, requests, time
from datetime import date, timedelta, datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
URL = os.environ['DATALAKE_URL'].rstrip('/')
KEY = os.environ['DATALAKE_API_KEY']
OUT = 'ohlc_data/XAUUSD_M1.csv'

MIN_DATE = date(2018, 1, 1)
MAX_DATE = date(2026, 5, 1)
LIMIT = 10000


def chunks(d0, d1, days=7):
    cur = d0
    while cur < d1:
        nxt = min(cur + timedelta(days=days), d1)
        yield cur, nxt
        cur = nxt


def fetch_window(start, end):
    """Returns rows in [start, end). Paginates if response hits LIMIT."""
    out = []
    cursor = start
    while True:
        r = requests.get(
            f'{URL}/query',
            params={
                'instrument': 'XAUUSD',
                'timeframe': 'M1',
                'start': cursor.isoformat() if hasattr(cursor, 'isoformat') else str(cursor),
                'end': end.isoformat() if hasattr(end, 'isoformat') else str(end),
                'limit': LIMIT,
            },
            headers={'X-API-Key': KEY},
            timeout=120,
        )
        r.raise_for_status()
        rows = r.json().get('data', [])
        if not rows:
            return out
        out.extend(rows)
        if len(rows) < LIMIT:
            return out
        # Continue from the next minute after the last bar
        last_ts = pd.to_datetime(rows[-1]['timestamp'])
        cursor = last_ts + pd.Timedelta(minutes=1)
        if cursor.to_pydatetime().date() >= end:
            return out


def main():
    all_rows = []
    t_total = time.time()
    week_chunks = list(chunks(MIN_DATE, MAX_DATE, days=7))
    for i, (s, e) in enumerate(week_chunks):
        t0 = time.time()
        rows = fetch_window(s, e)
        all_rows.extend(rows)
        if i % 25 == 0 or i == len(week_chunks) - 1:
            print(f'  [{i+1}/{len(week_chunks)}] {s}: {len(rows)} rows in {time.time()-t0:.1f}s (total {len(all_rows):,})', flush=True)

    df = pd.DataFrame(all_rows)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp').drop_duplicates(subset='timestamp').reset_index(drop=True)
    print(f'\nfinal: {len(df):,} unique rows, {df["timestamp"].min()} → {df["timestamp"].max()}')
    print(f'total fetch time: {time.time()-t_total:.1f}s')
    df.to_csv(OUT, index=False)
    print(f'saved → {OUT} ({os.path.getsize(OUT)/1024/1024:.1f} MB)')


if __name__ == '__main__':
    main()
