import os, json, base64, requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

# Chargement .env (utile en local)
load_dotenv()

# Vars env
API_KEY  = os.getenv("IG_API_KEY", "").strip()
USERNAME = os.getenv("IG_IDENTIFIER", "").strip()
PASSWORD = os.getenv("IG_PASSWORD", "").strip()
BASE_URL = os.getenv("IG_BASE_URL", "https://demo-api.ig.com/gateway/deal").strip()

# Dry-run / logging local
DRY_RUN  = os.getenv("DRY_RUN", "0") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")

# Nettoie le log au démarrage
try:
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write("")
except Exception:
    pass

def emit(msg: str):
    """Écrit dans le fichier log + print. En mode normal on pourrait pousser sur Discord."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    except Exception as e:
        print(f"[log error] {e}")
    print(msg)

# EPICs IG
ASSETS = {
    "🪙 Or (Gold)": "CS.D.GC.MONTH1.IP",
    "🛢 Pétrole (USOIL)": "CC.D.CL.USS.IP",
    "📈 Nasdaq 100": "IX.D.NASDAQ.CFD.IP",
    "🏦 Dow Jones": "IX.D.DOW.DAILY.IP",
    "🇩🇪 GER40 (DAX)": "IX.D.DAX.DAILY.IP",
}

# ---------- Login IG (chiffré puis fallback clair) ----------
def get_encryption_key():
    url = f"{BASE_URL}/session/encryptionKey"
    headers = {"X-IG-API-KEY": API_KEY, "Accept": "application/json", "Version": "1"}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        body = _safe_json(r)
        emit(f"⚠️ /session/encryptionKey échoué HTTP {r.status_code}\n{json.dumps(body, ensure_ascii=False, indent=2)}")
        return None, None
    data = r.json()
    return data.get("encryptionKey"), data.get("timeStamp")

def encrypt_password(pwd: str, ts: str, pub_b64: str) -> str:
    pub_der = base64.b64decode(pub_b64)
    rsa_key = RSA.import_key(pub_der)
    cipher = PKCS1_v1_5.new(rsa_key)
    return base64.b64encode(cipher.encrypt(f"{pwd}|{ts}".encode("utf-8"))).decode("utf-8")

def login_request(payload: dict):
    url = f"{BASE_URL}/session"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json",
        "Version": "2",
    }
    return requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)

def connect_ig():
    # 1) tentative chiffrée
    enc_key, ts = get_encryption_key()
    if enc_key and ts:
        try:
            enc_pwd = encrypt_password(PASSWORD, ts, enc_key)
            r = login_request({"identifier": USERNAME, "password": enc_pwd, "encryptedPassword": True})
            if r.status_code == 200:
                return r.headers.get("CST"), r.headers.get("X-SECURITY-TOKEN")
            body = _safe_json(r)
            # si autre chose qu'identifiants invalides, on arrête là
            if body.get("errorCode") not in ("error.security.invalid-details", "invalid.details", None):
                emit(f"⚠️ Login IG (chiffré) échoué HTTP {r.status_code}\n{json.dumps(body, ensure_ascii=False, indent=2)}")
                return None, None
        except Exception as e:
            emit(f"⚠️ Chiffrement/connexion chiffrée IG: {e}")

    # 2) tentative en clair
    r = login_request({"identifier": USERNAME, "password": PASSWORD, "encryptedPassword": False})
    if r.status_code == 200:
        return r.headers.get("CST"), r.headers.get("X-SECURITY-TOKEN")

    body = _safe_json(r)
    emit("⚠️ Login IG échoué"
         f"\n• HTTP: {r.status_code}"
         f"\n• Réponse: {json.dumps(body, ensure_ascii=False, indent=2)}"
         f"\n• URL: {BASE_URL}/session"
         f"\n• ENV: USERNAME={USERNAME}")
    return None, None

def _safe_json(resp):
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text}

# ---------- Prices ----------
def fetch_prices(epic: str, start_iso: str, end_iso: str, cst: str, xst: str):
    url = f"{BASE_URL}/prices/{epic}?resolution=MINUTE&from={start_iso}&to={end_iso}"
    headers = {
        "X-IG-API-KEY": API_KEY,
        "CST": cst,
        "X-SECURITY-TOKEN": xst,
        "Accept": "application/json",
        "Version": "3",
    }
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        emit(f"❌ /prices {epic} HTTP {r.status_code} {_safe_json(r)}")
        return None
    return r.json().get("prices", [])

def pick_friday_close(prices):  # dernière close vendredi
    if not prices: return None
    for p in reversed(prices):
        try: return float(p["closePrice"]["bid"])
        except: continue
    return None

def pick_sunday_open(prices):   # première open dimanche
    if not prices: return None
    for p in prices:
        try: return float(p["openPrice"]["bid"])
        except: continue
    return None

def iso(dt): return dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")

# ---------- Main ----------
if __name__ == "__main__":
    now_utc = datetime.now(timezone.utc)
    title = f"📊 GAPS D’OUVERTURE – {(now_utc + timedelta(hours=2)).strftime('%d/%m/%Y')}\n"
    emit(title)

    cst, xst = connect_ig()
    if not (cst and xst):
        emit("⛔ Connexion IG KO (voir détails ci-dessus).")
        raise SystemExit(1)

    # Fenêtres (UTC)
    weekday = now_utc.weekday()  # 0=Mon..6=Sun
    last_friday = now_utc - timedelta(days=(weekday - 4) % 7)
    friday_from, friday_to = iso(last_friday.replace(hour=20, minute=0)), iso(last_friday.replace(hour=22, minute=30))
    sunday = last_friday + timedelta(days=2)
    sunday_from, sunday_to = iso(sunday.replace(hour=21, minute=55)), iso(sunday.replace(hour=22, minute=15))

    lines = []
    for name, epic in ASSETS.items():
        fri = fetch_prices(epic, friday_from, friday_to, cst, xst)
        sun = fetch_prices(epic, sunday_from, sunday_to, cst, xst)
        close_fri = pick_friday_close(fri) if fri is not None else None
        open_sun  = pick_sunday_open(sun) if sun is not None else None
        if close_fri is not None and open_sun is not None:
            gap = open_sun - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{name} : {sign} {gap:.2f} ({pct:.2f}%)")
        else:
            miss = []
            if close_fri is None: miss.append("close vendredi")
            if open_sun  is None: miss.append("open dimanche")
            lines.append(f"{name} : ⚠️ Données indisponibles ({' & '.join(miss)})")
    emit("\n".join(lines))
