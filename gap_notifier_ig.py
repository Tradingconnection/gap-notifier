import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Configuration IG
IG_API_KEY = os.getenv("IG_API_KEY")
IG_IDENTIFIER = os.getenv("IG_IDENTIFIER")
IG_PASSWORD = os.getenv("IG_PASSWORD")

# Webhook Discord
WEBHOOK_URL = "https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx"

# Actifs à surveiller (epic codes ou market codes IG à ajuster manuellement)
symbols = {
    "GOLD": "CS.D.GC.MONTH1",
    "OIL": "CS.D.CL.MONTH1",
    "NASDAQ 100": "IX.D.NASDAQ.IFM.IP",
    "DOW JONES": "IX.D.DOW.IFM.IP",
    "CAC 40": "IX.D.CAC.IDC.IP",
    "GERMAN DAX": "IX.D.DAX.IDC.IP"
}

# Authentification IG
class IGSession:
    def __init__(self):
        self.api_key = IG_API_KEY
        self.identifier = IG_IDENTIFIER
        self.password = IG_PASSWORD
        self.base_url = "https://demo-api.ig.com/gateway/deal"
        self.headers = {
            "X-IG-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.session = requests.Session()
        self.security_token = None
        self.cst = None

    def login(self):
        url = f"{self.base_url}/session"
        payload = {
            "identifier": self.identifier,
            "password": self.password
        }
        r = self.session.post(url, json=payload, headers=self.headers)
        if r.status_code != 200:
            raise Exception(f"Erreur de connexion IG: {r.status_code} - {r.text}")
        self.cst = r.headers.get("CST")
        self.security_token = r.headers.get("X-SECURITY-TOKEN")
        self.headers.update({
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token
        })

    def get_prices(self, epic):
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"{self.base_url}/prices/{epic}?resolution=D&from={yesterday}T00:00:00&to={today}T23:59:59&pageSize=2"
        r = self.session.get(url, headers=self.headers)
        if r.status_code != 200:
            print(f"Erreur de données pour {epic} : {r.text}")
            return None
        data = r.json()
        prices = data.get("prices", [])
        if len(prices) < 2:
            return None
        close = prices[-2]["closePrice"]["bid"]
        open_ = prices[-1]["openPrice"]["bid"]
        return float(close), float(open_)

def build_message():
    ig = IGSession()
    try:
        ig.login()
    except Exception as e:
        return f"❌ Connexion IG échouée : {e}"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"📊 **Gaps détectés – {now}**\n\n"
    found_data = False

    for name, epic in symbols.items():
        result = ig.get_prices(epic)
        if result:
            found_data = True
            close, open_ = result
            gap = (open_ - close) / close * 100
            direction = "🔼 GAP HAUSSIER" if gap > 0 else "🔽 GAP BAISSIER"
            message += (
                f"**{name}** → {direction} de {abs(round(gap, 2))}%\n"
                f"(Open: {round(open_, 2)} | Close: {round(close, 2)})\n\n"
            )

    if not found_data:
        message += "⚠️ Aucune donnée exploitable pour les actifs sélectionnés.\n"

    message += "\n*Powered by [IG Markets](https://labs.ig.com)*"
    return message

def send_to_discord(content):
    payload = {"content": content}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        if response.status_code in [200, 204]:
            print("✅ Message Discord envoyé.")
        else:
            print(f"❌ Erreur Discord ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi Discord : {e}")

if __name__ == "__main__":
    try:
        msg = build_message()
        send_to_discord(msg)
    except Exception as e:
        print(f"❌ Erreur globale : {e}")
