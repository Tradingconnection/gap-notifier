import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")

# Liste des symboles Finnhub
symbols = {
    "GOLD": "OANDA:XAU_USD",
    "OIL": "OANDA:WTICO_USD",
    "NASDAQ 100": "^NDX",
    "DOW JONES": "^DJI",
    "CAC 40": "^FCHI",
    "GERMAN DAX": "^GDAXI"
}

WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

def get_gap(symbol):
    base_url = "https://finnhub.io/api/v1/stock/candle"

    # Dates : hier (close) et aujourd’hui (open)
    today = datetime.now()
    yesterday = today - timedelta(days=3)  # on saute le week-end

    from_ts = int(yesterday.replace(hour=0, minute=0).timestamp())
    to_ts = int(today.replace(hour=23, minute=59).timestamp())

    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_ts,
        "to": to_ts,
        "token": API_KEY
    }

    response = requests.get(base_url, params=params)
    data = response.json()

    if data.get("s") != "ok" or len(data["c"]) < 2:
        print(f"⚠️ Données incomplètes pour {symbol}")
        return None

    # Close = avant-dernier jour, Open = dernier jour
    try:
        last_close = data["c"][-2]
        today_open = data["o"][-1]
        gap = (today_open - last_close) / last_close * 100
        direction = "🔼 GAP HAUSSIER" if gap > 0 else "🔽 GAP BAISSIER"
        return {
            "direction": direction,
            "gap": round(gap, 2),
            "open": round(today_open, 2),
            "close": round(last_close, 2)
        }
    except Exception as e:
        print(f"❌ Erreur sur {symbol} : {e}")
        return None

def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"📈 Gaps détectés – {now}\n\n"

    for name, symbol in symbols.items():
        result = get_gap(symbol)
        if result:
            message += (
                f"{name} → {result['direction']} de {abs(result['gap'])}%\n"
                f"(Open: {result['open']} | Close: {result['close']})\n\n"
            )
    return message

def send_to_discord(content):
    payload = {"content": content}
    try:
        r = requests.post(WEBHOOK_URL, json=payload)
        if r.status_code == 204:
            print("✅ Message envoyé")
        else:
            print(f"❌ Discord : {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Erreur Discord : {e}")

if __name__ == "__main__":
    msg = build_message()
    send_to_discord(msg)
