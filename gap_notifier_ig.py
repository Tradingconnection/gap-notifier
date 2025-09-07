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

DRY_RUN   = os.getenv("DRY_RUN", "1") == "1"          # 0 => envoi Discord
FORCE_SEND = os.getenv("FORCE_SEND", "0") == "1"      # 1 => envoi même avant 22:00 UTC
LOG_PATH  = os.getenv("OUTPUT_LOG", "gap_output.txt")

DISCORD_WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    or os.getenv("DISCORD_WEBHOOK", "").strip()
)

SYMBOLS = {
    "🪙 Gold":      "GC=F",
    "🛢 Oil":       "CL=F",
    "📈 Nasdaq":    "NQ=F",
    "🏦 Dow Jones": "YM=F",
    "🇩🇪 GER40":    "^GDAXI",
}

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def is_before_globex_open(now_utc: datetime) -> bool:
    # Dimanche (6) avant 22:00 UTC => pas d'open Monday sur les futures
    return now_utc.weekday() == 6 and now_utc.hour < 22

def week_refs(now_utc: datetime) -> tuple[date, date]:
    monday_this = (now_utc - timedelta(days=now_utc.weekday())).date()
    monday_midnight_utc = datetime.combine(monday_this, datetime.min.time(), tzinfo=timezone.utc)
    globex_cutoff = monday_midnight_utc - timedelta(hours=2)  # dimanche 22:00 UTC
    monday = monday_this if now_utc >= globex_cutoff else (monday_this - timedelta(days=7))
    friday = monday - timedelta(days=3)
    return friday, monday

def daily_ohlc(ticker: str, start_d: date, end_d: date) -> pd.DataFrame:
    start = start_d - timedelta(days=3)
    end   = end_d + timedelta(days=1)
    try:
        df = yf.download(
            tickers=ticker, interval="1d",
            start=start.isoformat(), end=end.isoformat(),
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
        log("Webhook Discord absent (DISCORD_WEBHOOK_URL / DISCORD_WEBHOOK).")
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
    # Reset log
    with open(LOG_PATH, "w", encoding="utf-8") as _f:
        _f.write("")

    # Infos debug utiles
    log(f"DEBUG DRY_RUN={int(DRY_RUN)} FORCE_SEND={int(FORCE_SEND)} "
        f"WEBHOOK_SET={'yes' if bool(DISCORD_WEBHOOK_URL) else 'no'}")

    now_utc = datetime.now(timezone.utc)

    # Garde anti-préouverture (contournable par FORCE_SEND=1)
    if is_before_globex_open(now_utc) and not FORCE_SEND:
        paris_now = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y %H:%M")
        log(f"[SKIP] Avant ouverture Globex (UTC {now_utc:%Y-%m-%d %H:%M}) — aucune publication Discord. (Paris {paris_now})")
        sys.exit(0)

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

    if not DRY_RUN:
        post_to_discord(header + body)
    else:
        log("DRY_RUN=1 : aucun envoi Discord")
