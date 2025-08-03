import requests
import os
from dotenv import load_dotenv

load_dotenv()

class IGSession:
    def __init__(self):
        self.api_key = os.getenv("IG_API_KEY")
        self.identifier = os.getenv("IG_IDENTIFIER")
        self.password = os.getenv("IG_PASSWORD")
        self.access_token = None
        self.cst = None

    def login(self):
        url = "https://api.ig.com/gateway/deal/session"
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=UTF-8",
            "X-IG-API-KEY": self.api_key,
            "Version": "2"
        }
        data = {
            "identifier": self.identifier,
            "password": self.password
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            self.cst = response.headers["CST"]
            self.access_token = response.headers["X-SECURITY-TOKEN"]
            print("✅ Connexion IG réussie.")
        else:
            raise Exception(f"❌ Erreur de connexion IG : {response.status_code} - {response.text}")

    def get_headers(self):
        if not self.access_token or not self.cst:
            raise Exception("Non authentifié.")
        return {
            "X-IG-API-KEY": self.api_key,
            "X-SECURITY-TOKEN": self.access_token,
            "CST": self.cst,
            "Accept": "application/json; charset=UTF-8",
            "Version": "3"
        }
