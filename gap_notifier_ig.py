import requests
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration IG API
IG_API_KEY = os.getenv("IG_API_KEY")
IG_IDENTIFIER = os.getenv("IG_IDENTIFIER")
IG_PASSWORD = os.getenv("IG_PASSWORD")
IG_ACCOUNT_TYPE = os.getenv("IG_ACCOUNT_TYPE", "DEMO")
IG_BASE_URL = os.getenv("IG_BASE_URL", "https://demo-api.ig.com/gateway/deal")

# Configuration Discord
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Headers initiaux
HEADERS = {
    "X-IG-API-KEY": IG_API_KEY,
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json; charset=UTF-8",
    "Version": "2"
}

def log_to_discord(message):
    print("Envoi Discord :")
    print(message)
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    except Exception as e:
        print("Erreur Discord :", str(e))


def authenticate_ig():
    auth_data = {
        "identifier": IG_IDENTIFIER,
        "password": IG_PASSWORD
    }
    try:
        response = requests.post(f"{IG_BASE_URL}/session", json=auth_data, headers=HEADERS)
        if response.status_code == 200:
            cst = response.headers.get("CST")
            x_security_token = response.headers.get("X-SECURITY-TOKEN")
            HEADERS.update({"CST": cst, "X-SECURITY-TOKEN": x_security_token})
            print("✅ Connexion IG réussie.")
            return True
        else:
            log_to_discord(f"❌ Connexion IG échouée : {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_to_discord(f"❌ Erreur de connexion IG : {str(e)}")
        return False


def get_epic_from_market(market_name):
    url = f"{IG_BASE_URL}/markets?searchTerm={market_name}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            if data["markets"]:
                return data["markets"][0]["epic"]
        print(f"⚠️ EPIC introuvable pour {market_name}")
        return None
    except Exception as e:
        print(f"Erreur EPIC : {str(e)}")
        return None


def get_prices(epic, date_from, date_to):
    url = f"{IG_BASE_URL}/prices/{epic}"
    params = {
        "resolution": "HOUR",
        "from": date_from,
        "to": date_to,
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        print(f"⏳ Requête IG: {url} ? {params}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Données récupérées IG ({epic}) : {len(data.get('prices', []))} éléments")
            return data.get("prices", [])
        else:
            print(f"❌ Erreur récupération prix IG : {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"❌ Exception récupération prix : {str(e)}")
        return []


def detect_gap(prices):
    if len(prices) < 2:
        return None
    open_price = prices[0]["openPrice"]["bid"]
    sunday_open = prices[-1]["openPrice"]["bid"]
    gap = sunday_open - open_price
    gap_percent = (gap / open_price) * 100
    return {
        "friday_close": open_price,
        "sunday_open": sunday_open,
        "gap": gap,
        "gap_percent": gap_percent
    }


def format_gap_message(market, gap_info):
    direction = "📈 HAUSSIER" if gap_info["gap"] > 0 else "📉 BAISSIER"
    return (
        f"**{market}**\n"
        f"Vendredi clôture : `{gap_info['friday_close']:.2f}`\n"
        f"Dimanche ouverture : `{gap_info['sunday_open']:.2f}`\n"
        f"Gap détecté : `{gap_info['gap']:.2f}` pts ({gap_info['gap_percent']:.2f}%) {direction}\n"
        f"-----------------------------"
    )


def main():
    if not authenticate_ig():
        return

    today = datetime.datetime.utcnow()
    last_friday = today - datetime.timedelta(days=(today.weekday() + 3) % 7 + 2)
    friday = last_friday.replace(hour=20, minute=0, second=0, microsecond=0)
    sunday = friday + datetime.timedelta(days=2, hours=4)

    date_from = friday.strftime("%Y-%m-%dT%H:%M:%S")
    date_to = sunday.strftime("%Y-%m-%dT%H:%M:%S")

    print(f"🔍 Période analysée IG : {date_from} → {date_to}")

    markets = {
        "FR40": "France 40",
        "DE30": "Allemagne 40",
        "US500": "US 500"
    }

    messages = ["📊 **Résumé des gaps détectés (IG Markets)**"]
    for symbol, name in markets.items():
        epic = get_epic_from_market(name)
        if not epic:
            messages.append(f"❌ {name} : EPIC introuvable")
            continue

        prices = get_prices(epic, date_from, date_to)
        gap_info = detect_gap(prices)
        if gap_info:
            messages.append(format_gap_message(name, gap_info))
        else:
            messages.append(f"⚠️ {name} : Pas assez de données IG (reçues: {len(prices)})")

    final_message = "\n".join(messages)
    log_to_discord(final_message)
    print("✅ Résumé envoyé sur Discord.")


if __name__ == "__main__":
    main()
