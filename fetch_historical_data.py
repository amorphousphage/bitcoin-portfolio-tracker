import yfinance as yf
import requests
import pymysql
from sqlalchemy import create_engine, text
import pandas as pd
import time
from datetime import datetime, timedelta

# MySQL connection
engine = create_engine('mysql+pymysql://username:password@bitcointracker_db_container/database')

# Create table if not exists
with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS btc_prices (
            timestamp INT PRIMARY KEY,
            price_usd DECIMAL(18,8) NOT NULL,
            price_eur DECIMAL(18,8) NOT NULL,
            price_gbp DECIMAL(18,8) NOT NULL,
            price_chf DECIMAL(18,8) NOT NULL
        );
    """))
    conn.commit()

# Download historical daily data until 90 days ago
btc = yf.Ticker("BTC-USD")
end_date = datetime.now() - timedelta(days=90)
history = btc.history(start="2010-07-18", end=end_date.strftime("%Y-%m-%d"), interval="1d")
history.reset_index(inplace=True)

rows = []
previous_rates = None

for idx, row in history.iterrows():
    date_str = row['Date'].strftime('%Y-%m-%d')
    price_usd = float(row['Close'])
    
    fx = requests.get(f"https://api.frankfurter.app/{date_str}?from=USD&to=EUR,GBP,CHF").json()
    if 'rates' in fx:
        rates = fx['rates']
        previous_rates = rates  # update previous rates
    elif previous_rates is not None:
        rates = previous_rates  # fallback to previous
    else:
        # first iteration has no previous -> skip
        continue

    rows.append({
        'timestamp': int(time.mktime(row['Date'].timetuple())),
        'price_usd': price_usd,
        'price_eur': price_usd * rates['EUR'],
        'price_gbp': price_usd * rates['GBP'],
        'price_chf': price_usd * rates['CHF'],
    })
    print("Done with ", date_str)
    time.sleep(0.2)

df = pd.DataFrame(rows)
print("Historical Data Frame generated, continuing with recent 90 days.")
# Download last 90 days from Coingecko hourly
coingecko = requests.get("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=90").json()
hourly_prices = coingecko['prices']
rows2 = []
previous_rates2 = None
for price_entry in hourly_prices:
    timestamp_ms, price_usd = price_entry
    timestamp = int(timestamp_ms / 1000)

    date_str = datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d')

    fx = requests.get(f"https://api.frankfurter.app/{date_str}?from=USD&to=EUR,GBP,CHF").json()
    if 'rates' in fx:
        rates = fx['rates']
        previous_rates = rates  # update previous rates
    elif previous_rates is not None:
        rates = previous_rates  # fallback to previous
    else:
        # first iteration has no previous -> skip
        continue

    rows2.append({
        'timestamp': timestamp,
        'price_usd': price_usd,
        'price_eur': price_usd * rates['EUR'],
        'price_gbp': price_usd * rates['GBP'],
        'price_chf': price_usd * rates['CHF'],
    })
    print("Done with ", date_str)
    time.sleep(0.2)

df2 = pd.DataFrame(rows2)
print("Combining Datasets")
# Combine datasets
full_df = pd.concat([df, df2]).drop_duplicates(subset='timestamp').sort_values(by='timestamp')
print("Writing to Database")
# Write to MySQL
full_df.to_sql("btc_prices", engine, if_exists="replace", index=False)

print("✅ Historical data import complete.")
