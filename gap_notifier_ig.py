# gap_notifier_fxcm.py
import os
from datetime import datetime, timedelta, timezone
import pandas as pd

from dotenv import load_dotenv
import fxcmpy
import requests

# --------- Config / ENV ----------
load_dotenv()
FXCM_TOKEN = os.getenv("FXCM_TOKEN", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")

ASSET_ALIASES = {
    "gold": ["XAU/USD", "XAUUSD"],
    "oil": ["USOil", "USOIL", "USOIL."],
    "nasdaq": ["NAS100", "NAS 100"],
    "dowjones": ["US30", "US 30", "WALLSTREET30"],
    "ger40": ["GER30", "DE40", "DAX"]
}

# --------- IO helpers ----------
def write(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    except Exception:
        pass
    print(msg)

def send_to_discord(content: str):
    if DRY_RUN or not DISCORD_WEBHOOK_URL:
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        # Discord renvoie 204 No Content si OK
        if r.status_code not in (200, 204):
            write(f"❌ Discord: {r.status_code} - {r.text}")
    except Exception as e:
        write(f"❌ Discord exception: {e}")

# --------- FXCM ----------
def connect_fxcm():
    if not FXCM_TOKEN:
        write("⛔ FXCM_TOKEN manquant dans .env")
        return None
    try:
        con = fxcmpy.fxcmpy(access_token=FXCM_TOKEN, log_level="error", server="demo")
        # ping simple
        _ = con.get_instruments()
        write("✅ Connexion FXCM OK")
        return con
    except Exception as e:
        write(f"⛔ Connexion FXCM KO: {e}")
        return None

def best_symbol(con, wanted_list):
    """Trouve le symbole exact chez FXCM à partir d’une liste d’alias."""
    instruments = [s.strip() for s in con.get_instruments()]
    # 1) match exact
    for w in wanted_list:
        if w in instruments:
            return w
    # 2) match insensible casse / slash
    canon = lambda s: s.replace("/", "").replace(" ", "").lower()
    inst_map = {canon(s): s for s in instruments}
    for w in wanted_list:
        cw = canon(w)
        if cw in inst_map:
            return inst_map[cw]
    return None

def m1_between(con, symbol, start_dt, end_dt):
    """Bougies minute entre deux timestamps UTC. Renvoie DataFrame (index datetime)."""
    # fxcmpy accepte start / end en datetime (UTC) et colonnes ciblées
    df = con.get_candles(symbol, period="m1", start=start_dt, end=end_dt,
                         columns=["bidopen", "bidclose"])
    # S’assure que l’index est en tz-aware UTC
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
    else:
        df.index = df.index.tz_convert(timezone.utc)
    return df.sort_index()

def pick_friday_close(df: pd.DataFrame):
    # dernière bidclose dispo dans la fenêtre
    if df is None or df.empty: return None
    return float(df["bidclose"].iloc[-1])

def pick_sunday_open(df: pd.DataFrame):
    # première bidopen dispo dans la fenêtre
    if df is None or df.empty: return None
    return float(df["bidopen"].iloc[0])

def compute_gap(con, label, aliases, fri_from, fri_to, sun_from, sun_to):
    sym = best_symbol(con, aliases)
    if not sym:
        return f"{label} : ⚠️ Symbole introuvable chez FXCM ({'/'.join(aliases)})"

    fri = m1_between(con, sym, fri_from, fri_to)
    sun = m1_between(con, sym, sun_from, sun_to)

    close_fri = pick_friday_close(fri)
    open_sun = pick_sunday_open(sun)

    if close_fri is not None and open_sun is not None:
        gap = open_sun - close_fri
        pct = (gap / close_fri) * 100 if close_fri else 0.0
        sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
        return f"{label} : {sign} {gap:.2f} ({pct:.2f}%)  —  {sym}"
    else:
        miss = []
        if close_fri is None: miss.append("close ven.")
        if open_sun  is None: miss.append("open dim.")
        return f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)}) — {sym}"

# --------- Main ----------
if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f: _f.write("")

    now_utc = datetime.now(timezone.utc)
    header = f"📊 GAPS D’OUVERTURE – {(now_utc + timedelta(hours=2)).strftime('%d/%m/%Y')} (FXCM)\n"
    write(header)

    con = connect_fxcm()
    if not con:
        raise SystemExit(1)

    # Fenêtres (UTC) robustes: ven 20:00→22:30 et dim 21:55→22:15
    weekday = now_utc.weekday()              # 0=Mon..6=Sun
    last_friday = now_utc - timedelta(days=(weekday - 4) % 7)
    fri_from = last_friday.replace(hour=20, minute=0,  second=0, microsecond=0)
    fri_to   = last_friday.replace(hour=22, minute=30, second=0, microsecond=0)
    sunday   = last_friday + timedelta(days=2)
    sun_from = sunday.replace(hour=21, minute=55, second=0, microsecond=0)
    sun_to   = sunday.replace(hour=22, minute=15, second=0, microsecond=0)

    lines = []
    lines.append(compute_gap(con, "🪙 Gold",      ASSET_ALIASES["gold"],      fri_from, fri_to, sun_from, sun_to))
    lines.append(compute_gap(con, "🛢 Oil",       ASSET_ALIASES["oil"],       fri_from, fri_to, sun_from, sun_to))
    lines.append(compute_gap(con, "📈 Nasdaq",    ASSET_ALIASES["nasdaq"],    fri_from, fri_to, sun_from, sun_to))
    lines.append(compute_gap(con, "🏦 Dow Jones", ASSET_ALIASES["dowjones"],  fri_from, fri_to, sun_from, sun_to))
    lines.append(compute_gap(con, "🇩🇪 GER40",    ASSET_ALIASES["ger40"],     fri_from, fri_to, sun_from, sun_to))

    msg = header + "\n".join(lines)
    write("\n".join(lines))
    send_to_discord(msg)

    try:
        con.close()
    except Exception:
        pass
