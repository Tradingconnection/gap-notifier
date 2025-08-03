import requests
from datetime import datetime
import time
import os

# Liste des actifs à surveiller (identifiants de marché IG)
MARKETS = {
    "GOLD": "CS.D.GC.MONTH1.IP",
    "OIL": "CS.D.CL.MONTH1.IP",
    "NASDAQ 100": "IX.D.NASDAQ.IFD.IP",
    "DOW JONES": "IX.D.DOW.IFD.IP",
    "CAC 40": "IX.D.CAC.IDX.IP",
    "DAX": "IX.D.DAX.IFD.IP"
}

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

IG_API_KEY = os.getenv("IG_API_KEY")
IG_IDENTIFIER = os.getenv("IG_IDENTIFIER")
IG_PASSWORD = os.getenv("IG_PASSWORD")

BASE_URL = "https://api.ig.com/gateway/deal"
HEADERS = {
    "X-IG-API-KEY": IG_API_KEY,
    "Content-Type": "application/json",
    "Accept": "application/json"
}


def login():
    payload = {
        "identifier": IG_IDENTIFIER,
        "password": IG_PASSWORD
    }
    res = requests.post(BASE_URL + "/session", json=payload, headers=HEADERS)
    if res.status_code != 200:
        raise Exception("Erreur de connexion IG : " + res.text)

    HEADERS["X-SECURITY-TOKEN"] = res.headers.get("X-SECURITY-TOKEN")
    HEADERS["CST"] = res.headers.get("CST")


def get_last_two_candles(epic):
    params = {
        "resolution": "DAY",
        "max": 2
    }
    url = f"{BASE_URL}/prices/{epic}"
    res = requests.get(url, headers=HEADERS, params=params)
    if res.status_code != 200:
        print(f"❌ Échec récupération prix pour {epic} : {res.text}")
        return None

    data = res.json()
    candles = data.get("prices", [])
    if len(candles) < 2:
        return None

    return candles[-2], candles[-1]  # veille, aujourd'hui


def compute_gap(candle1, candle2):
    last_close = candle1['closePrice']['bid']
    today_open = candle2['openPrice']['bid']
    if last_close is None or today_open is None:
        return None
    gap = (today_open - last_close) / last_close * 100
    direction = "🔼 GAP HAUSSIER" if gap > 0 else "🔽 GAP BAISSIER"
    return round(gap, 2), round(last_close, 2), round(today_open, 2), direction


def build_message():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"📊 **Gaps détectés – {now}**\n\n"

    found = False
    for name, epic in MARKETS.items():
        try:
            candles = get_last_two_candles(epic)
            if not candles:
                continue

            gap_data = compute_gap(*candles)
            if not gap_data:
                continue

            gap, close, open_, direction = gap_data
            found = True
            message += (
                f"**{name}** → {direction} de `{abs(gap)}%`\n"
                f"*(Close: {close} → Open: {open_})*\n\n"
            )
        except Exception as e:
            print(f"Erreur pour {name} : {e}")
            continue

    if not found:
        message += "⚠️ Aucune donnée exploitable pour les actifs sélectionnés.\n"

    message += "\n*Powered by [IG Markets](https://labs.ig.com)*"
    return message


def send_to_discord(msg):
    try:
        res = requests.post(DISCORD_WEBHOOK, json={"content": msg})
        if res.status_code == 204:
            print("✅ Message Discord envoyé.")

