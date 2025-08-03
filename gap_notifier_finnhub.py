import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FINNHUB_API_KEY")

# ✅ Actifs confirmés compatibles Finnhub en gratuit
symbols = {
    "GOLD": "OANDA:XAU_USD",
    "OIL": "OANDA:WTICO_USD",
    "NASDAQ 100 ETF (QQQ)": "US:QQQ",
    "DOW JONES ETF (DIA)": "US:DIA",
    "S&P 500 ETF (SPY)": "US:SPY",
    "DAX ETF (iShares)": "US:DAX"
}

WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

def get_gap(symbol):
    base_url = "https://finnhub.io/api/v1/stock/candle"

    today = datetime.utcnow()
    seven_days_ago = today - timedelta(days=7)

    from_ts = int(seven_days_ago.replace(hour=0, minute=0).timestamp())
    to_ts = int(today.replace(hour=23, minute=59).timestamp())

    params = {
        "symbol": symbol,
        "resolution": "D",
        "from": from_ts,
        "to": to_ts,
        "token": API_KEY
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        print(f"\n📡 {symbol}")
        print("URL ➜", response.url)
        print("Réponse JSON ➜", data)

        if data.get("s") != "ok" or len(data.get("c", [])) < 2:
            print(f"⚠️ Pas de données valides pour {symbol}")
            return None

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
        print(f"❌ Erreur avec {symbol} : {e}")
        return None

def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"📊 **Gaps détectés – {now}**\n\n"

    found = False
    for name, symbol in symbols.items():
        result = get_gap(symbol)
        if result:
            found = True
            message += (
                f"**{name}** → {result['direction']} de **{abs(result['gap'])}%**\n"
                f"`Open: {result['open']} | Close: {result['close']}`\n\n"
            )

    if not found:
        message += "⚠️ Aucune donnée exploitable pour les actifs sélectionnés."

    message += "\n*Powered by [Finnhub.io](https://finnhub.io)*"
    return message

def send_to_discord(content):
    payload = {"content": content}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("✅ Message envoyé avec succès.")
        else:
            print(f"❌ Erreur Discord ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Erreur Discord : {e}")

if __name__ == "__main__":
    msg = build_message()
    send_to_discord(msg)
