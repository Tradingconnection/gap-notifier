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

# 0 = envoi Discord, 1 = pas d'envoi (test)
DRY_RUN  = os.getenv("DRY_RUN", "1") == "1"
LOG_PATH = os.getenv("OUTPUT_LOG", "gap_output.txt")

# Webhook: accepte DISCORD_WEBHOOK_URL ou DISCORD_WEBHOOK
DISCORD_WEBHOOK_URL = (
    os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    or os.getenv("DISCORD_WEBHOOK", "").strip()
)

# Libellés → tickers (tes choix)
SYMBOLS = {
    "🪙 Gold":      "GC=F",    # COMEX Gold futures
    "🛢 Oil":       "CL=F",    # WTI futures
    "📈 Nasdaq":    "NQ=F",    # E-mini Nasdaq (futures)
    "🏦 Dow Jones": "YM=F",    # E-mini Dow (futures)
    "🇩🇪 GER40":    "^GDAXI",  # DAX cash
}

# ===================== Utils =====================

def log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + ("\n" if not msg.endswith("\n") else ""))
    print(msg)

def week_refs(now_utc: datetime) -> tuple[date, date]:
    """
    GAP = Open(lun) - Close(ven).
    On bascule sur la semaine 'courante' à partir de DIMANCHE 22:00 UTC.
    """
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

def last_price_fallback(ticker: str) -> float | None:
    """
    Récupère un dernier prix 'indicatif' si l'open Monday n'existe pas encore.
    On tente d'abord fast_info.last_price, puis un intraday court.
    """
    try:
        tk = yf.Ticker(ticker)
        # 1) fast_info.last_price
        try:
            lp = float(getattr(tk.fast_info, "last_price"))
            if lp and lp == lp:  # not NaN
                return lp
        except Exception:
            pass
        # 2) intraday 5m sur 1 jour (si session ouverte)
        try:
            intr = tk.history(period="1d", interval="5m")
            if intr is not None and not intr.empty:
                return float(intr["Close"].iloc[-1])
        except Exception:
            pass
    except Exception:
        pass
    return None

def post_to_discord(content: str):
    if not DISCORD_WEBHOOK_URL:
        log("Webhook Discord absent (DISCORD_WEBHOOK_URL ou DISCORD_WEBHOOK).")
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
    friday_d, monday_d = week_refs(now_utc)

    today_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y")
    header = f"📊 GAP D’OUVERTURE — Trading Connection | {today_paris}\n"
    log(header)

    lines = []
    for label, sym in SYMBOLS.items():
        df = daily_ohlc(sym, friday_d, monday_d)
        close_fri, open_mon = friday_close_monday_open(df, friday_d, monday_d)

        if close_fri is not None and open_mon is not None:
            # Cas idéal : Monday open dispo
            gap = open_mon - close_fri
            pct = (gap / close_fri) * 100 if close_fri else 0.0
            sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
            lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%)")
        else:
            # Fallback : utiliser un dernier prix indicatif si possible
            last_px = last_price_fallback(sym)
            if close_fri is not None and last_px is not None:
                gap = last_px - close_fri
                pct = (gap / close_fri) * 100 if close_fri else 0.0
                sign = "🟢" if gap > 0 else "🔴" if gap < 0 else "⚪"
                # (i) on ne marque pas "indicatif" pour rester fidèle à ton format demandé
                lines.append(f"{label} : {sign} {gap:.2f} ({pct:.2f}%)")
            else:
                # Dernier recours
                miss = []
                if close_fri is None: miss.append("close ven.")
                if open_mon  is None: miss.append("open lun.")
                lines.append(f"{label} : ⚠️ Données indisponibles ({' & '.join(miss)})")

    body = "\n".join(lines)
    log(body)

    # Envoi Discord (uniquement si DRY_RUN=0)
    if not DRY_RUN:
        post_to_discord(header + body)
    else:
        log("DRY_RUN=1 : aucun envoi Discord")
