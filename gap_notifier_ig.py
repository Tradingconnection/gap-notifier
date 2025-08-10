import os
from datetime import datetime, timedelta, timezone, date
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# --- Config ---
load_dotenv()
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")
DISCORD_WEBHOOK_URL = os.getenv("https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx", "").strip()

# Futures/cash Yahoo
SYMBOLS = {
    "🪙 Gold (fut)":  "GC=F",
    "🛢 WTI (fut)":   "CL=F",
    "📈 Nasdaq (fut)": "NQ=F",
    "🏦 Dow (fut)":    "YM=F",
    "🇩🇪 GER40 (cash)": "^GDAXI",   # DAX cash (ouvre lundi)
}

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def week_refs(now_utc: datetime) -> tuple[date, date, str]:
    """
    Retourne (vendredi_cible, lundi_cible, note).
    Si on est AVANT la dispo de la bougie daily de lundi (selon actifs),
    on bascule automatiquement sur la semaine précédente.
    """
    # On considère que la bougie "lundi" est dispo dès lundi 00:30 UTC (safe).
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()  # lundi de cette semaine
    cutoff = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc) + timedelta(minutes=30)

    use_prev_week = now_utc < cutoff
    if use_prev_week:
        monday = monday_this - timedelta(days=7)
        note = " (semaine précédente)"
    else:
        monday = monday_this
        note = ""

    friday = monday - timedelta(days=3)   # lundi-3 = vendredi précédent
    return friday, monday, note

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    """
    Télécharge les daily entre start_d-3j et end_d+1j, pour être sûr d’avoir ven & lun.
    Index → dates naïves (UTC côté Yahoo).
    """
    start = start_d - timedelta(days=3)
    end   = end_d + timedelta(days=1)
    df = yf.download(tickers=ticker, interval="1d", start=start.isoformat(), end=end.isoformat(), progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    # Normalise l'index en date
    df.index = pd.to_datetime(df.index, utc=True).date
    return df

def friday_close_monday_open(df: pd.DataFrame, friday: date, monday: date) -> tuple[float | None, float | None]:
    """
    Extrait Close de vendredi et Open de lundi dans un DF daily Yahoo.
    """
    c_fri = float(df.loc[friday, "Close"]) if friday in df.index else None
    o_mon = float(df.loc[monday, "Open"])  if monday in df.index else None
    return c_fri, o_mon

if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f: _f.write("")

    now_utc = datetime.now(timezone.utc)
    friday_d, monday_d, note = week_refs(now_utc)

    header = f"📊 GAPS D’OUVERTURE – {(now_utc + timedelta(hours=2)).strftime('%d/%m/%Y')} (Yahoo, daily){note}\n"
    log(header)

    lines = []
    for label, sym in SYMBOLS.items():
        df = daily_ohlc(sym, friday_d, monday_d)
        close_fri, open_mon = friday_close_monday_open(df, friday_d, monday_d)

        if close_fri is not None and open_mon is not None:
            gap = open_mon - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%) — {sym}")
        else:
            miss = []
            if close_fri is None: miss.append("close ven.")
            if open_mon  is None: miss.append("open lun.")
            lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)}) — {sym}")

    body = "\n".join(lines)
    log(body)

    # Envoi Discord (seulement si DRY_RUN=0)
    if not DRY_RUN and DISCORD_WEBHOOK_URL:
        import requests
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": header + body}, timeout=30)
        log(f"Discord: {r.status_code}")
