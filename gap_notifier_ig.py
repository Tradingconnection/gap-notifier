#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# ===================== Config =====================
load_dotenv()

# 0 = envoie sur Discord, 1 = n'envoie pas (mode test)
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")

# Laisse ton .env tel quel : DISCORD_WEBHOOK_URL=...
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

# Libellés → tickers (on garde TES tickers)
SYMBOLS = {
    "🪙 Gold":      "GC=F",    # COMEX Gold futures (Globex);
    "🛢 Oil":       "CL=F",    # WTI futures (Globex)
    "📈 Nasdaq":    "NQ=F",    # E-mini Nasdaq futures (Globex)
    "🏦 Dow Jones": "YM=F",    # E-mini Dow futures (Globex)
    "🇩🇪 GER40":    "^GDAXI",  # DAX cash (ouvre lundi matin Europe)
}

# ===================== Utils =====================

def log(msg: str):
    """Écrit dans le fichier log + stdout."""
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def week_refs(now_utc: datetime) -> tuple[date, date]:
    """
    Retourne (vendredi, lundi) pour calculer GAP = Open(lun) - Close(ven).

    On considère que la "nouvelle semaine" démarre à l'ouverture Globex,
    soit le DIMANCHE à ~22:00 UTC. À partir de 22:00 UTC dimanche,
    on bascule sur le lundi "courant". Avant ça, on reste sur la semaine précédente.
    """
    # Lundi courant en date (indépendant de l'heure)
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()

    # Cutoff Globex pour ce lundi : dimanche 22:00 UTC (soit lundi 00:00 UTC - 2h)
    monday_midnight_utc = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc)
    globex_cutoff = monday_midnight_utc - timedelta(hours=2)  # dimanche 22:00 UTC

    if now_utc >= globex_cutoff:
        monday = monday_this
    else:
        monday = monday_this - timedelta(days=7)

    friday = monday - timedelta(days=3)
    return friday, monday

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    """
    Télécharge des bougies daily autour de ven & lun pour être sûr d’avoir les deux points.
    """
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

# ===================== Main =====================

if __name__ == "__main__":
    # Reset log à chaque run
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
            # Cas manquants — typiquement avant l'ouverture cash, ou si Yahoo n'a pas encore publié la daily
            miss_open = (open_mon is None)
            if miss_open:
                # message uniforme comme tes exemples
                lines.append(f"{label} : ⚠️ Données indisponibles (open lun.)")
            else:
                # rare : close ven. manquante
                lines.append(f"{label} : ⚠️ Données indisponibles (close ven.)")

    body = "\n".join(lines)
    log(body)

    # Envoi Discord (uniquement si DRY_RUN=0)
    if not DRY_RUN:
        post_to_discord(header + body)
    else:
        log("DRY_RUN=1 : aucun envoi Discord")
