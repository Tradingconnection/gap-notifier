import os
import json
import base64
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Crypto (RSA PKCS1 v1.5 pour le login chiffré IG)
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

# -- Chargement du .env (utile en local ; sur Actions on exporte déjà les vars) --
load_dotenv()

# ---- Variables d'environnement ----
API_KEY = os.getenv("IG_API_KEY", "").strip()
USERNAME = os.getenv("IG_IDENTIFIER", "").strip()   # ex: LUCAS2212
PASSWORD = os.getenv("IG_PASSWORD", "").strip()
BASE_URL = os.getenv("IG_BASE_URL", "https://demo-api.ig.com/gateway/deal").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# ---- EPICs IG ----
ASSETS = {
    "🪙 Or (Gold)": "CS.D.GC.MONTH1.IP",
    "🛢 Pétrole (USOIL)": "CC.D.CL.USS.IP",
    "📈 Nasdaq 100": "IX.D.NASDAQ.CFD.IP",
    "🏦 Dow Jones": "IX.D.DOW.DAILY.IP",
    "🇩🇪 GER40 (DAX)": "IX.D.DAX.DAILY.IP",
}

# ------------ Discord ------------
def send_to_discord(content: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        print("❌ Webhook Discord manquant (DISCORD_WEBHOOK_URL).")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        if r.status_code in (200, 204):
            print("✅ Message envoyé sur Discord")
        else:
            print(f"❌ Erreur Discord: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Exception envoi Discord: {e}")

# ------------ IG API (login chiffré) ------------
def get_encryption_key():
    """Récupère la clé publique RSA et le timestamp d'IG pour chiffrer le mot de passe."""
    url = f"{BASE_URL}/session/encryptionKey"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "Accept": "application/json",
        "Version": "1",
        "User-Agent": "gap-weekly-bot/1.0",
    }
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        send_to_discord(
            "⚠️ **Récupération encryptionKey échouée**\n"
            f"• HTTP: `{r.status_code}`\n"
            f"• Réponse: ```json\n{json.dumps(body, ensure_ascii=False, indent=2)}\n```"
        )
        return None, None
    data = r.json()
    return data.get("encryptionKey"), data.get("timeStamp")

def encrypt_password(password: str, time_stamp: str, modulus_b64: str) -> str:
    """Chiffre `password|timeStamp` en RSA, encodé Base64 (PKCS1 v1.5)."""
    # Le champ encryptionKey d'IG est une clé publique RSA encodée base64 DER
    pub_der = base64.b64decode(modulus_b64)
    rsa_key = RSA.import_key(pub_der)
    cipher = PKCS1_v1_5.new(rsa_key)
    plaintext = f"{password}|{time_stamp}".encode("utf-8")
    encrypted = cipher.encrypt(plaintext)
    return base64.b64encode(encrypted).decode("utf-8")

def connect_ig():
    """
    Connexion à IG avec mot de passe chiffré.
    En cas d'échec, envoie un message détaillé sur Discord (HTTP + body).
    Retourne (CST, X-SECURITY-TOKEN) si OK, sinon (None, None).
    """
    enc_key, ts = get_encryption_key()
    if not enc_key or not ts:
        return None, None

    enc_pwd = encrypt_password(PASSWORD, ts, enc_key)

    url = f"{BASE_URL}/session"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
        "Version": "2",
        "User-Agent": "gap-weekly-bot/1.0",
    }
    payload = {
        "identifier": USERNAME,
        "password": enc_pwd,
        "encryptedPassword": True
    }

    try:
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    except Exception as e:
        send_to_discord(f"⚠️ **Login IG échoué (exception réseau)**\n```{e}```")
        return None, None

    if r.status_code == 200:
        cst = r.headers.get("CST")
        xst = r.headers.get("X-SECURITY-TOKEN")
        if not cst or not xst:
            send_to_discord("⚠️ **Login IG réussi mais tokens manquants (CST/X-SECURITY-TOKEN)**.")
            return None, None
        print("✅ Connexion IG réussie (mot de passe chiffré)")
        return cst, xst

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    tips = (
        "\n**Pistes de résolution :**\n"
        "• Vérifie que `IG_IDENTIFIER` est bien ton pseudo IG (ex: `LUCAS2212`).\n"
        "• Assure-toi d’utiliser le bon environnement (DEMO ⇄ BASE_URL demo / LIVE ⇄ BASE_URL live).\n"
        "• Si 2FA/OTP activé, valide la connexion API depuis l’Espace Client IG (rubrique API).\n"
        "• Si l’erreur persiste en DEMO, essaye de te connecter au site IG DEMO avec ces identifiants pour confirmer.\n"
    )

    send_to_discord(
        "⚠️ **Login IG échoué**\n"
        f"• HTTP: `{r.status_code}`\n"
        f"• Réponse: ```json\n{json.dumps(body, ensure_ascii=False, indent=2)}\n```\n"
        f"• URL: `{url}`\n"
        f"• ENV: `BASE_URL={BASE_URL}` `USERNAME={USERNAME}`\n"
        + tips
    )
    return None, None

# ------------ Récup prix ------------
def fetch_prices(epic: str, start_iso: str, end_iso: str, cst: str, xst: str):
    url = f"{BASE_URL}/prices/{epic}?resolution=MINUTE&from={start_iso}&to={end_iso}"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "CST": cst,
        "X-SECURITY-TOKEN": xst,
        "Accept": "application/json",
        "Version": "3",
        "User-Agent": "gap-weekly-bot/1.0",
    }
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except Exception as e:
        print(f"❌ Exception fetch_prices {epic}: {e}")
        return None

    if r.status_code != 200:
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        print(f"❌ Erreur /prices {epic}: {r.status_code} - {body}")
        return None

    try:
        data = r.json()
    except Exception as e:
        print(f"❌ JSON invalide /prices {epic}: {e}")
        return None

    return data.get("prices", [])

def pick_friday_close(prices: list) -> float | None:
    if not prices:
        return None
    for p in reversed(prices):
        try:
            return float(p["closePrice"]["bid"])
        except Exception:
            continue
    return None

def pick_sunday_open(prices: list) -> float | None:
    if not prices:
        return None
    for p in prices:
        try:
            return float(p["openPrice"]["bid"])
        except Exception:
            continue
    return None

def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")

# ------------ Main ------------
if __name__ == "__main__":
    now_utc = datetime.now(timezone.utc)
    # Affichage date (Paris)
    today_paris = (now_utc + timedelta(hours=2)).strftime("%d/%m/%Y")  # simple offset été

    header = f"📊 **GAPS D’OUVERTURE – {today_paris}**\n"
    report = []

    # Connexion IG (chiffrée)
    cst, xst = connect_ig()
    if not cst or not xst:
        # Détail d’erreur déjà envoyé
        send_to_discord(header + "⚠️ Erreur connexion IG (voir détails ci-dessus).")
        raise SystemExit(1)

    # Fenêtres horaires (UTC) robustes
    weekday = now_utc.weekday()  # 0=Mon ... 6=Sun
    last_friday = now_utc - timedelta(days=(weekday - 4) % 7)
    friday_start = last_friday.replace(hour=20, minute=0, second=0, microsecond=0)
    friday_end   = last_friday.replace(hour=22, minute=30, second=0, microsecond=0)

    sunday = last_friday + timedelta(days=2)
    sunday_start = sunday.replace(hour=21, minute=55, second=0, microsecond=0)
    sunday_end   = sunday.replace(hour=22, minute=15, second=0, microsecond=0)

    friday_from = iso(friday_start)
    friday_to   = iso(friday_end)
    sunday_from = iso(sunday_start)
    sunday_to   = iso(sunday_end)

    for name, epic in ASSETS.items():
        fri_prices = fetch_prices(epic, friday_from, friday_to, cst, xst)
        sun_prices = fetch_prices(epic, sunday_from, sunday_to, cst, xst)

        close_fri = pick_friday_close(fri_prices) if fri_prices is not None else None
        open_sun  = pick_sunday_open(sun_prices) if sun_prices is not None else None

        if close_fri is not None and open_sun is not None:
            gap = open_sun - close_fri
            gap_pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            report.append(f"{name} : {sign} {gap:.2f} ({gap_pct:.2f}%)")
        else:
            reason = []
            if close_fri is None:
                reason.append("close vendredi indisponible")
            if open_sun is None:
                reason.append("ouverture dimanche indisponible")
            detail = " / ".join(reason) if reason else "donnée manquante"
            report.append(f"{name} : ⚠️ Données indisponibles ({detail})")

    send_to_discord(header + "\n".join(report))
