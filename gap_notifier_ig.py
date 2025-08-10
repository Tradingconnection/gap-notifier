import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")
DISCORD_WEBHOOK_URL = os.getenv("https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx", "").strip()

SYMBOLS = {
    "🪙 Gold (fut)": "GC=F",
    "🛢 WTI (fut)":  "CL=F",
    "📈 Nasdaq (fut)": "NQ=F",
    "🏦 Dow (fut)":     "YM=F",
    "🇩🇪 GER40 (cash)": "^GDAXI"  # DAX cash: on prendra l'ouverture LUN matin
}

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def first_open(df: pd.DataFrame) -> float | None:
    if df is None or df.empty: return None
    return float(df["Open"].iloc[0])

def last_close(df: pd.DataFrame) -> float | None:
    if df is None or df.empty: return None
    return float(df["Close"].iloc[-1])

def m1_between(ticker: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    df = yf.download(tickers=ticker, interval="1m", period="7d", progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index, utc=True)
    return df.loc[(df.index >= start_utc) & (df.index <= end_utc)]

def compute_windows(now_utc: datetime):
    """
    Si on est AVANT l'ouverture de ce dimanche (~22:00 UTC),
    on bascule automatiquement sur la SEMAINE PRÉCÉDENTE pour garantir un résultat.
    """
    weekday = now_utc.weekday()  # 0=Mon..6=Sun
    last_friday = now_utc - timedelta(days=(weekday - 4) % 7)
    sunday      = last_friday + timedelta(days=2)

    # Fenêtres (UTC)
    friday_from = last_friday.replace(hour=20, minute=0,  second=0, microsecond=0)
    friday_to   = last_friday.replace(hour=22, minute=30, second=0, microsecond=0)
    sunday_from = sunday.replace(hour=22, minute=0, second=0, microsecond=0)
    sunday_to   = sunday.replace(hour=22, minute=20, second=0, microsecond=0)

    # DAX cash (lundi matin)
    monday      = last_friday + timedelta(days=3)
    monday_from = monday.replace(hour=7, minute=0, second=0, microsecond=0)
    monday_to   = monday.replace(hour=7, minute=15, second=0, microsecond=0)

    note = ""
    # Si on lance AVANT dimanche 22:20 UTC, on prend la semaine précédente
    if now_utc < sunday_to:
        friday_from  -= timedelta(days=7)
        friday_to    -= timedelta(days=7)
        sunday_from  -= timedelta(days=7)
        sunday_to    -= timedelta(days=7)
        monday_from  -= timedelta(days=7)
        monday_to    -= timedelta(days=7)
        note = " (semaine précédente – marché pas encore rouvert)"

    return (friday_from, friday_to, sunday_from, sunday_to, monday_from, monday_to, note)

if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f: _f.write("")

    now_utc = datetime.now(timezone.utc)
    (fri_from, fri_to, sun_from, sun_to, mon_from, mon_to, note) = compute_windows(now_utc)

    header = f"📊 GAPS D’OUVERTURE – {(now_utc + timedelta(hours=2)).strftime('%d/%m/%Y')} (Yahoo){note}\n"
    log(header)

    lines = []
    for name, symbol in SYMBOLS.items():
        if symbol == "^GDAXI":
            fri = m1_between(symbol, fri_from, fri_to)  # souvent vide (hors heures cash)
            mon = m1_between(symbol, mon_from, mon_to)
            close_fri = last_close(fri)  # peut être None pour le cash
            open_x    = first_open(mon)
            label = f"{name} (lun)"
        else:
            fri = m1_between(symbol, fri_from, fri_to)
            sun = m1_between(symbol, sun_from, sun_to)
            close_fri = last_close(fri)
            open_x    = first_open(sun)
            label = name

        if close_fri is not None and open_x is not None:
            gap = open_x - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%) — {symbol}")
        else:
            miss = []
            if close_fri is None: miss.append("close ven.")
            if open_x   is None: miss.append("open dim./lun.")
            lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)}) — {symbol}")

    body = "\n".join(lines)
    log(body)

    if not DRY_RUN and DISCORD_WEBHOOK_URL:
        import requests
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": header + body}, timeout=30)
        print("Discord:", r.status_code, r.text[:200] if r.text else "")
