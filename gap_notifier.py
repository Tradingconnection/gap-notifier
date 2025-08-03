import yfinance as yf
import requests
from datetime import datetime

# Liste des actifs à surveiller
symbols = {
    "GOLD": "GC=F",
    "OIL": "CL=F",
    "NASDAQ 100": "^NDX",
    "DOW JONES": "^DJI",
    "CAC 40": "^FCHI",
    "GERMAN DAX": "^GDAXI"
}

WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

def get_gap(ticker):
    try:
        data = yf.download(ticker, period="7d", interval="1d", progress=False)

        # Vérifie la présence des colonnes essentielles
        if data is None or 'Close' not in data.columns or 'Open' not in data.columns:
            print(f"❌ Données manquantes pour {ticker}")
            return None

        data = data.dropna(subset=["Close", "Open"])

        if len(data) < 2:
            print(f"⚠️ Pas assez de données pour {ticker}")
            return None

        last_close = float(data['Close'].iloc[-2])
        today_open = float(data['Open'].iloc[-1])

        gap = (today_open - last_close) / last_close * 100
        direction = "🔼 GAP HAUSSIER" if gap > 0 else "🔽 GAP BAISSIER"

        return {
            "direction": direction,
            "gap": round(gap, 2),
            "open": round(today_open, 2),
            "close": round(last_close, 2)
        }

    except Exception as e:
        print(f"❌ Erreur avec {ticker} : {e}")
        return None

def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"📈 Gaps détectés – {now}\n\n"

    for name, ticker in symbols.items():
        result = get_gap(ticker)
        if result:
            message += (
                f"{name} → {result['direction']} de {abs(result['gap'])}%\n"
                f"(Open: {result['open']} | Close: {result['close']})\n\n"
            )
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
        print(f"❌ Erreur lors de l'envoi : {e}")

if __name__ == "__main__":
    msg = build_message()
    send_to_discord(msg)
