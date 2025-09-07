#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# ===================== Config =====================
load_dotenv()

# 0 = envoi Discord, 1 = pas d'envoi (test)
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")

# Accepte DEUX noms possibles pour le webhook
DISCORD_WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    or os.getenv("DISCORD_WEBHOOK", "").strip()
)

# Libellés → tickers (on garde tes choix)
SYMBOLS = {
    "🪙 Gold":      "GC=F",    # COMEX Gold futures (Globex)
    "🛢 Oil":       "CL=F",    # WTI futures (Globex)
    "📈 Nasdaq":    "NQ=F",    # E-mini Nasdaq (Globex)
    "🏦 Dow Jones": "YM=F",    # E-mini Dow (Globex)
    "🇩🇪 GER40":    "^GDAXI",  # DAX cash (ouvre lundi matin Europe)
}

# ===================== Helpers =====================

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def is_before_globex_open(now_utc: datetime) -> bool:
    """
    True si DIMANCHE avant 22:00 UTC (Globex ré-ouvre vers 22:00 UTC).
    """
    return now_utc.weekday() == 6 and now_utc.hour < 22

def week_refs(now_utc: datetime) -> tuple[date, date]:
    """
    Retourne (vendredi, lundi) pour GAP = Open(lun) - Close(ven).
    On bascule sur la semaine 'courante' à partir de DIMANCHE 22:00 UTC.
    """
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()
    monday_midnight_utc = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc)
    globex_cutoff = monday_midnight_utc - timedelta(hours=2)  # dimanche 22:00 UTC
    monday = monday_this if now_utc >= globex_cutoff else (monday_this - timedelta(days=7))
    friday = monday - timedelta(days=3)
    return friday, monday

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    """
    Télécharge des daily autour de ven & lun pour couvrir les deux points.
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
        log("Avertissement: webhook non défini (DISCORD_WEBHOOK_URL ou DISCORD_WEBHOOK). Envoi désactivé.")
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
    # Reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f:
        _f.write("")

    now_utc = datetime.now(timezone.utc)
    paris_now_str = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y %H:%M")

    # 1) Si on est dimanche avant 22:00 UTC, on POSTE quand même un message clair
    if is_before_globex_open(now_utc):
        note = (f"⚠️ Marchés Globex pas encore ouverts.\n"
                f"⏰ Réouverture ~22:00 UTC (≈ { (datetime.now(ZoneInfo('Europe/Paris')) + timedelta(hours=(22 - now_utc.hour))).strftime('%H:%M') } Paris si le lancement est immédiat).\n"
                f"Relance planifiée automatique à 22:05 UTC.\n"
                f"(Heure locale actuelle : {paris_now_str})")
        log(note)
        if not DRY_RUN:
            post_to_discord("📊 GAP D’OUVERTURE — Trading Connection\n" + note)
        else:
            log("DRY_RUN=1 : aucun envoi Discord (note pré-ouverture).")
        sys.exit(0)

    # 2) Calcul normal du GAP
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
            if open_mon is None:
                lines.append(f"{label} : ⚠️ Données indisponibles (open lun.)")
            else:
                lines.append(f"{label} : ⚠️ Données indisponibles (close ven.)")

    body = "\n".join(lines)
    log(body)

    # 3) Envoi Discord (uniquement si DRY_RUN=0)
    if not DRY_RUN:
        post_to_discord(header + body)
    else:
        log("DRY_RUN=1 : aucun envoi Discord")
