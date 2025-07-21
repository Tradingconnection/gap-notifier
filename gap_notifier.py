import requests
from datetime import datetime

# Même liste d’actifs
symbols = {
    "GOLD": "GC=F",
    "OIL": "CL=F",
    "NASDAQ 100": "^NDX",
    "DOW JONES": "^DJI",
    "CAC 40": "^FCHI",
    "GERMAN DAX": "^GDAXI"
}

WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"  # 🔁 Remplace par ton vrai webhook

def simulate_fake_gaps():
    messages = []
    for name in symbols.keys():
        today_open = 103
        yesterday_close = 100
        gap = (today_open - yesterday_close) / yesterday_close * 100

        direction = "🔼 GAP HAUSSIER simulé"
        message = f"**{name}** → {direction} de {gap:.2f}%\n(Open: {today_open:.2f} | Close: {yesterday_close:.2f})"
        messages.append(message)

    return messages

def send_to_discord(messages):
    content = f"🧪 **TEST – Gaps simulés** – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n" + "\n\n".join(messages)
    print("➡️ Test Discord :\n", content)
    response = requests.post(WEBHOOK_URL, json={"content": content})

    if response.status_code == 204:
        print("[✔] Test envoyé avec succès à Discord.")
    else:
        print(f"[✖] Échec de l'envoi – Code {response.status_code} – {response.text}")

if __name__ == "__main__":
    messages = simulate_fake_gaps()
    send_to_discord(messages)
