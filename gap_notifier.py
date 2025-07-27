import yfinance as yf
import requests
from datetime import datetime

# Actifs à surveiller
symbols = {
    "GOLD": "GC=F",
    "OIL": "CL=F",
    "NASDAQ 100": "^NDX",
    "DOW JONES": "^DJI",
    "CAC 40": "^FCHI",
    "GERMAN DAX": "^GDAXI"
}

# Ton webhook Discord
WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

def get_gap(ticker):
    data = yf.download(ticker, period="5d", interval="1d", progress=False)
    if len(data) < 2:
        return None

    last_close = data['Close'].iloc[-2]
    today_open = data['Open'].iloc[-1]

    gap = (today_open - last_close) / last_close * 100
    direction = "🔼 GAP HAUSSIER" if gap > 0 else "🔽 GAP BAISSIER" if gap < 0 else "⏸️ Stable"

    return today_open, last_close, gap, direction

def build_messages():
    messages = []
    for name, symbol in symbols.items():
        result = get_gap(symbol)
        if result:
            open_price, close_price, gap, direction = result
            message = (
                f"**{name}** → {direction} de {gap:.2f}%\n"
                f"(Open: {open_price:.2f} | Close: {close_price:.2f})"
            )
        else:
            message = f"**{name}** → ❌ Données indisponibles"
        messages.append(message)
    return messages

def send_to_discord(messages):
    content = f"📈 **Gaps détectés** – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" + "\n\n".join(messages)
    print(content)
    response = requests.post(WEBHOOK_URL, json={"content": content})

    if response.status_code == 204:
        print("✅ Message envoyé à Discord.")
    else:
        print(f"❌ Échec Discord – Code {response.status_code} – {response.text}")

if __name__ == "__main__":
    send_to_discord(build_messages())
