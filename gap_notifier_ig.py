import os
import requests
import json

# Charger les identifiants depuis les variables d'environnement (secrets GitHub)
API_KEY = os.environ.get("IG_API_KEY")
USERNAME = os.environ.get("IG_USERNAME")
PASSWORD = os.environ.get("IG_PASSWORD")
BASE_URL = "https://demo-api.ig.com/gateway/deal"  # Utiliser https://api.ig.com/gateway/deal pour le compte réel

def connect_ig():
    """Connexion à l'API IG et récupération des tokens"""
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

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if response.status_code == 200:
        cst = response.headers.get("CST")
        x_security_token = response.headers.get("X-SECURITY-TOKEN")
        print("✅ Connexion IG réussie")
        return cst, x_security_token
    else:
        print(f"❌ Erreur de connexion IG: {response.status_code} - {response.text}")
        return None, None

if __name__ == "__main__":
    connect_ig()
