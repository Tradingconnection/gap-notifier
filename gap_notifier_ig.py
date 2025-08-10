import os
from datetime import datetime, timedelta, timezone
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# --- Config ---
load_dotenv()
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")
DISCORD_WEBHOOK_URL = os.getenv("https://discord.com/api/webhooks/1396818376852242495/m-F9GOn6oiqALUjqP6GZ9xycTk-pV9ie2fGA9KDk3J6aKxKQVKJZzipG2l0zAw5fNAMx", "").strip()

SYMBOLS = {
    "🪙 Gold (fut)": "GC=F",   # CME Gold futures
    "🛢 WTI (fut)":  "CL=F",   # NYMEX WTI futures
    "📈 Nasdaq (fut)": "NQ=F", # CME E-mini Nasdaq-100
    "🏦 Dow (fut)":     "YM=F",# CBOT Mini Dow
    "🇩🇪 GER40 (cash)": "^GDAXI" # DAX cash (approx pour GER40)
}

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def first_open(df: pd.DataFrame) -> float | None:
    if df is None or df.empty: return None
    # yfinance renvoie O/H/L/C ; on prend le premier Open
    return float(df["Open"].iloc[0])

def last_close(df: pd.DataFrame) -> float | None:
    if df is None or df.empty: return None
    return float(df["Close"].iloc[-1])

def m1_between(ticker: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame:
    # yfinance minute => period max 7d ; on télécharge 7d et on filtre
    df = yf.download(tickers=ticker, interval="1m", period="7d", progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    # index tz-naive en UTC côté yfinance -> convertissons proprement
    df.index = pd.to_datetime(df.index, utc=True)
    return df.loc[(df.index >= start_utc) & (df.index <= end_utc)]

if __name__ == "__main__":
    # reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f: _f.write("")

    now_utc = datetime.now(timezone.utc)
    header = f"📊 GAPS D’OUVERTURE – {(now_utc + timedelta(hours=2)).strftime('%d/%m/%Y')} (Yahoo, sans clé)\n"
    log(header)

    # Fenêtres (UTC)
    weekday = now_utc.weekday()  # 0=Mon..6=Sun
    last_friday = now_utc - timedelta(days=(weekday - 4) % 7)
    friday_from = last_friday.replace(hour=20, minute=0,  second=0, microsecond=0)
    friday_to   = last_friday.replace(hour=22, minute=30, second=0, microsecond=0)
    sunday      = last_friday + timedelta(days=2)
    sunday_from = sunday.replace(hour=22, minute=0, second=0, microsecond=0)
    sunday_to   = sunday.replace(hour=22, minute=20, second=0, microsecond=0)
    # DAX cash: prend lundi matin
    monday      = last_friday + timedelta(days=3)
    monday_from = monday.replace(hour=7, minute=0, second=0, microsecond=0)
    monday_to   = monday.replace(hour=7, minute=15, second=0, microsecond=0)

    lines = []
    for name, symbol in SYMBOLS.items():
        if symbol == "^GDAXI":
            fri = m1_between(symbol, friday_from, friday_to)
            mon = m1_between(symbol, monday_from, monday_to)
            close_fri = last_close(fri)
            open_mon  = first_open(mon)
            label = f"{name} (lun)"
        else:
            fri = m1_between(symbol, friday_from, friday_to)
            sun = m1_between(symbol, sunday_from, sunday_to)
            close_fri = last_close(fri)
            open_mon  = first_open(sun)  # ouverture dimanche 22:00 UTC
            label = name

        if close_fri is not None and open_mon is not None:
            gap = open_mon - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%) — {symbol}")
        else:
            miss = []
            if close_fri is None: miss.append("close ven.")
            if open_mon  is None: miss.append("open dim./lun.")
            lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)}) — {symbol}")

    log("\n".join(lines))

    # Envoi Discord facultatif (désactivé si DRY_RUN=1)
    if not DRY_RUN and os.getenv("DISCORD_WEBHOOK_URL"):
        import requests
        content = header + "\n".join(lines)
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        print("Discord:", r.status_code, r.text[:200] if r.text else "")
