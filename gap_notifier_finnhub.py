import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")

symbols = {
    "GOLD": "OANDA:XAU_USD",
    "OIL": "OANDA:WTICO_USD",
    "NASDAQ 100 ETF (QQQ)": "US:QQQ",
    "DOW JONES ETF (DIA)": "US:DIA",
    "SP500 ETF (SPY)": "US:SPY"
}

today = datetime.utcnow()
seven_days_ago = today - timedelta(days=7)

from_ts = int(seven_days_ago.replace(hour=0, minute=0).timestamp())
to_ts = int(today.replace(hour=23, minute=59).timestamp())

for name, symbol in symbols.items():
    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_ts,
        "to": to_ts,
        "token": API_KEY
    }
    url = "https://finnhub.io/api/v1/stock/candle"
    r = requests.get(url, params=params)
    data = r.json()

    print(f"\n🔎 {name} ({symbol})")
    print(f"Réponse Finnhub ➜ {data}")
