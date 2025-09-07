# gap_notifier_ig.py
import os
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# --- Config ---
load_dotenv()
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"              # 0 = envoie sur Discord
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# Libellés propres (sans tickers dans le message)
SYMBOLS = {
    "🪙 Gold":      "GC=F",
    "🛢 Oil":       "CL=F",
    "📈 Nasdaq":    "NQ=F",
    "🏦 Dow Jones": "YM=F",
    "🇩🇪 GER40":    "^GDAXI",  # DAX cash (ouvre lundi)
}

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def week_refs(now_utc: datetime) -> tuple[date, date]:
    """
    Retourne (vendredi, lundi) pour gap = Open(lun) - Close(ven).
    Si on est avant la bougie daily de lundi (00:30 UTC), on prend la semaine précédente.
    """
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()  # lundi courant
    cutoff = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=30)
    monday = monday_this - timedelta(days=7) if now_utc < cutoff else monday_this
    friday = monday - timedelta(days=3)
    return friday, monday

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    """Télécharge les daily autour de ven & lun pour être sûr d’avoir les deux points."""
    start = start_d - timedelta(days=3)
    end   = end_d + timedelta(days=1)
    try:
        df = yf.download(
            tickers=ticker,
            interval="1d",
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
        )
    except Exception:
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # Index → dates (sans tz) pour accès par df.loc[date]
    try:
        idx = pd.to_datetime(df.index, utc=True, errors="coerce")
        df.index = idx.date
    except Exception:
        return pd.DataFrame()

    return df

def friday_close_monday_open(df: pd.DataFrame, friday: date, monday: date) -> tuple[float | None, float | None]:
    c_fri = float(df.loc[friday, "Close"]) if friday in df.index else None
    o_mon = float(df.loc[monday, "Open"])  if monday in df.index else None
    return c_fri, o_mon

def post_to_discord(content: str):
    if not DISCORD_WEBHOOK_URL:
        log("Avertissement: DISCORD_WEBHOOK_URL non défini. Envoi désactivé.")
        return 0
    try:
        import requests
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        log(f"Discord HTTP {r.status_code}{(' ' + (r.text[:150] or '')) if r.text else ''}")
        return r.status_code
    except Exception as e:
        log(f"Erreur d'envoi Discord: {e}")
        return -1

if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f:
        _f.write("")

    now_utc = datetime.now(timezone.utc)
    friday_d, monday_d = week_refs(now_utc)

    today_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")
    header = f"📊 GAP D’OUVERTURE — Trading Connection | {today_paris}\n"
    log(header)

    lines = []
    for label, sym in SYMBOLS.items():
        df = daily_ohlc(sym, friday_d, monday_d)
        close_fri, open_mon = friday_close_monday_open(df, friday_d, monday_d)

        if close_fri is not None and open_mon is not None:
            gap = open_mon - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%)")
        else:
            miss = []
            if close_fri is None: miss.append("close ven.")
            if open_mon  is None: miss.append("open lun.")
            # Message cohérent le dimanche avant l'ouverture
            if "open lun." in miss:
                lines.append(f"{label} : ⚠️ Données indisponibles (open lun.)")
            else:
                lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)})")

    body = "\n".join(lines)
    log(body)

    # Envoi Discord (uniquement si DRY_RUN=0)
    if not DRY_RUN:
        post_to_discord(header + body)
    else:
        log("DRY_RUN=1 : aucun envoi Discord")
