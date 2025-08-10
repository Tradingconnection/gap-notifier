import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Charger les variables du fichier .env
load_dotenv()

# Identifiants IG
API_KEY = os.getenv("IG_API_KEY")
USERNAME = os.getenv("IG_IDENTIFIER")
PASSWORD = os.getenv("IG_PASSWORD")
BASE_URL = os.getenv("IG_BASE_URL")

# Webhook Discord
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Liste des actifs et EPIC IG
ASSETS = {
    "🪙 Gold": "CS.D.GC.MONTH1.IP",
    "🛢 Oil": "CC.D.CL.USS.IP",
    "📈 Nasdaq": "IX.D.NASDAQ.CFD.IP",
    "🏦 Dow Jones": "IX.D.DOW.DAILY.IP",
    "🇩🇪 GER40": "IX.D.DAX.DAILY.IP"
}

def connect_ig():
    """Connexion à IG et récupération des tokens CST et X-SECURITY-TOKEN"""
    url = f"{BASE_URL}/session"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Version": "2"
    }
    payload = {
        "identifier": USERNAME,
        "password": PASSWORD
    }

    r = requests.post(url, headers=headers, data=json.dumps(payload))
    if r.status_code == 200:
        print("✅ Connexion IG réussie")
        return r.headers.get("CST"), r.headers.get("X-SECURITY-TOKEN")
    else:
        raise Exception(f"Erreur de connexion IG: {r.status_code} - {r.text}")

def get_price(epic, date_from, date_to, cst, xst):
    """Récupère les prix entre deux dates"""
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
    """Envoie un message sur Discord via webhook"""
    payload = {"content": message}
    r = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if r.status_code == 204:
        print("✅ Message envoyé sur Discord")
    else:
        print(f"❌ Erreur Discord: {r.status_code} - {r.text}")

if __name__ == "__main__":
    try:
        # Connexion IG
        cst, xst = connect_ig()

        # Dates
        today = datetime.utcnow()
        last_friday = today - timedelta(days=(today.weekday() - 4) % 7)
        sunday_open = last_friday + timedelta(days=2)

        friday_str = last_friday.strftime("%Y-%m-%dT21:00:00")
        sunday_str = sunday_open.strftime("%Y-%m-%dT21:05:00")

        message = f"📊 **GAPS D’OUVERTURE – {today.strftime('%d/%m/%Y')}**\n"

        for name, epic in ASSETS.items():
            close_fri, open_sun = get_price(epic, friday_str, sunday_str, cst, xst)
            if close_fri and open_sun:
                gap = open_sun - close_fri
                gap_pct = (gap / close_fri) * 100
                sign = "🟢" if gap > 0 else "🔴"
                message += f"{name} : {sign} {gap:.2f} ({gap_pct:.2f}%)\n"
            else:
                message += f"{name} : ⚠️ Données indisponibles\n"

        # Envoi Discord
        send_to_discord(message)

    except Exception as e:
        print(f"❌ Erreur: {e}")
