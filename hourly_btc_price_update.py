import requests
import pymysql
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime, timedelta

# Create a connection to the database
engine = create_engine('mysql+pymysql://username:password@bitcointracker_db_container/database')

# Fetch current price from Coingecko in 4 currencies
cg = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,eur,gbp,chf").json()
btc_data = cg['bitcoin']

now = datetime.utcnow()
now_ts = int(now.replace(minute=0, second=0, microsecond=0).timestamp())

df = pd.DataFrame([{
    'timestamp': now_ts,
    'price_usd': btc_data['usd'],
    'price_eur': btc_data['eur'],
    'price_gbp': btc_data['gbp'],
    'price_chf': btc_data['chf'],
}])

# Insert or update
with engine.connect() as conn:
    for _, row in df.iterrows():
        conn.execute(text("""
            INSERT INTO btc_prices (timestamp, price_usd, price_eur, price_gbp, price_chf)
            VALUES (:timestamp, :price_usd, :price_eur, :price_gbp, :price_chf)
            ON DUPLICATE KEY UPDATE
            price_usd=VALUES(price_usd),
            price_eur=VALUES(price_eur),
            price_gbp=VALUES(price_gbp),
            price_chf=VALUES(price_chf);
        """), {
            "timestamp": int(row['timestamp']),
            "price_usd": float(row['price_usd']),
            "price_eur": float(row['price_eur']),
            "price_gbp": float(row['price_gbp']),
            "price_chf": float(row['price_chf'])
        })
    conn.commit()

print("✅ Hourly update complete.")

# Delete hourly entries for entries older than 90 days to keep only the latest value for a day
# Calculate the 90- and 120-day cutoff ranges. We are not checking older than 120 days as they should already be fine.
cutoff_90 = datetime.utcnow() - timedelta(days=90)
cutoff_120 = datetime.utcnow() - timedelta(days=120)

with engine.connect() as conn:
    conn.execute(
        text("""
            DELETE FROM btc_prices
            WHERE FROM_UNIXTIME(timestamp) >= DATE(:cutoff_120)
              AND FROM_UNIXTIME(timestamp) < DATE(:cutoff_90)
              AND timestamp NOT IN (
                SELECT t FROM (
                  SELECT MAX(timestamp) AS t
                  FROM btc_prices
                  WHERE FROM_UNIXTIME(timestamp) >= DATE(:cutoff_120)
                    AND FROM_UNIXTIME(timestamp) < DATE(:cutoff_90)
                  GROUP BY DATE(FROM_UNIXTIME(timestamp))
                ) AS subquery
              );
        """),
        {
            "cutoff_120": cutoff_120.date(),
            "cutoff_90": cutoff_90.date()
        }
    )
    conn.commit()

