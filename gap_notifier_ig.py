import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Charger .env
load_dotenv()

API_KEY = os.getenv("IG_API_KEY")
USERNAME = os.getenv("IG_IDENTIFIER")
PASSWORD = os.getenv("IG_PASSWORD")
BASE_URL = os.getenv("IG_BASE_URL")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

ASSETS = {
    "🪙 Gold": "CS.D.GC.MONTH1.IP",
    "🛢 Oil": "CC.D.CL.USS.IP",
    "📈 Nasdaq": "IX.D.NASDAQ.CFD.IP",
    "🏦 Dow Jones": "IX.D.DOW.DAILY.IP",
    "🇩🇪 GER40": "IX.D.DAX.DAILY.IP"
}

def connect_ig():
    """Connexion à IG"""
    url = f"{BASE_URL}/session"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "2"
    }
    payload = {"identifier": USERNAME, "password": PASSWORD}
    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code == 200:
        return r.headers.get("CST"), r.headers.get("X-SECURITY-TOKEN")
    return None, None

def get_price(epic, date_from, date_to, cst, xst):
    """Récupère prix IG"""
    url = f"{BASE_URL}/prices/{epic}?resolution=MINUTE&from={date_from}&to={date_to}"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "CST": cst,
        "X-SECURITY-TOKEN": xst,
        "Accept": "application/json"
    }
    r = requests.get(url, headers=headers)
    data = r.json()
    if "prices" in data and data["prices"]:
        first = data["prices"][0]["openPrice"]["bid"]
        last = data["prices"][-1]["closePrice"]["bid"]
        return first, last
    return None, None

def send_to_discord(message):
    """Envoi Discord"""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Webhook Discord manquant")
        return
    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    if r.status_code == 204:
        print("✅ Message envoyé sur Discord")
    else:
        print(f"❌ Erreur Discord: {r.status_code} - {r.text}")

if __name__ == "__main__":
    cst, xst = connect_ig()
    today = datetime.utcnow()

    message = f"📊 **GAPS D’OUVERTURE – {today.strftime('%d/%m/%Y')}**\n"
    if not cst or not xst:
        message += "⚠️ Erreur connexion IG\n"
        send_to_discord(message)
        exit()

    last_friday = today - timedelta(days=(today.weekday() - 4) % 7)
    sunday_open = last_friday + timedelta(days=2)

    friday_str = last_friday.strftime("%Y-%m-%dT21:00:00")
    sunday_str = sunday_open.strftime("%Y-%m-%dT21:05:00")

    for name, epic in ASSETS.items():
        close_fri, open_sun = get_price(epic, friday_str, sunday_str, cst, xst)
        if close_fri and open_sun:
            gap = open_sun - close_fri
            gap_pct = (gap / close_fri) * 100
            sign = "🟢" if gap > 0 else "🔴"
            message += f"{name} : {sign} {gap:.2f} ({gap_pct:.2f}%)\n"
        else:
            message += f"{name} : ⚠️ Données indisponibles\n"

    send_to_discord(message)
