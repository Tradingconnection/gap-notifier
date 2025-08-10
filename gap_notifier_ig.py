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
    """Retourne (vendredi, lundi) pour gap = Open(lun) - Close(ven).
       Si on est avant la bougie daily de lundi (00:30 UTC), on prend la semaine précédente."""
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()
    cutoff = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=30)
    if now_utc < cutoff:
        monday = monday_this - timedelta(days=7)
    else:
        monday = monday_this
    friday = monday - timedelta(days=3)
    return friday, monday

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    """Télécharge les daily autour de ven & lun pour être sûr d’avoir les deux points."""
    start = start_d - timedelta(days=3)
    end   = end_d + timedelta(days=1)
    df = yf.download(tickers=ticker, interval="1d", start=start.isoformat(), end=end.isoformat(), progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    idx = pd.to_datetime(df.index, utc=True)
    df.index = idx.date
    return df

def friday_close_monday_open(df: pd.DataFrame, friday: date, monday: date) -> tuple[float | None, float | None]:
    c_fri = float(df.loc[friday, "Close"]) if friday in df.index else None
    o_mon = float(df.loc[monday, "Open"])  if monday in df.index else None
    return c_fri, o_mon

if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f: _f.write("")

    # --- Garde-fou : ne poste que s'il est 17:10 à Paris ---
    paris_now = datetime.now(ZoneInfo("Europe/Paris"))
    if os.getenv("IGNORE_TIME_GUARD", "0") != "1":
        if not (paris_now.hour == 17 and paris_now.minute == 10):
            log(f"⏭️ Skip: il est {paris_now.strftime('%H:%M')} à Paris (pas 17:10).")
            raise SystemExit(0)

    now_utc = datetime.now(timezone.utc)
    friday_d, monday_d = week_refs(now_utc)

    today_paris = paris_now.strftime("%d/%m/%Y")
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
            lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)})")

    body = "\n".join(lines)
    log(body)

    # Envoi Discord (uniquement si DRY_RUN=0)
    if not DRY_RUN and DISCORD_WEBHOOK_URL:
        import requests
        try:
            r = requests.post(DISCORD_WEBHOOK_URL, json={"content": header + body}, timeout=30)
            log(f"Discord HTTP {r.status_code} {r.text[:150] if r.text else ''}")
        except Exception as e:
            log(f"Discord exception: {e}")
