#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN MAESTRA
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"
TOLERANCE       = 0.06 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── LISTA DE ACTIVOS ──
CRYPTO_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", "BCHUSDT", "XRPUSDT", "LTCUSDT", "LINKUSDT", "ZECUSDT", "NEOUSDT", "MANAUSDT"]
FOREX_PAIRS   = ["AUDUSD=X", "NZDUSD=X", "GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X"]
OTHER_ASSETS  = ["SPY", "ES=F", "GC=F", "NVDA"]

HARMONIC_PATTERNS = {
    "Butterfly": {"XAB": (0.786, 0.786), "ABC": (0.382, 0.886), "BCD": (1.618, 2.618), "XAD": (1.272, 1.618), "emoji": "🦋"},
    "Crab": {"XAB": (0.382, 0.618), "ABC": (0.382, 0.886), "BCD": (2.240, 3.618), "XAD": (1.618, 1.618), "emoji": "🦀"},
    "Shark": {"XAB": (0.382, 0.618), "ABC": (1.128, 1.618), "BCD": (1.618, 2.236), "XAD": (0.886, 1.128), "emoji": "🦈"},
    "Gartley": {"XAB": (0.618, 0.618), "ABC": (0.382, 0.886), "BCD": (1.272, 1.618), "XAD": (0.786, 0.786), "emoji": "🎯"},
    "Bat": {"XAB": (0.382, 0.500), "ABC": (0.382, 0.886), "BCD": (1.618, 2.618), "XAD": (0.886, 0.886), "emoji": "🦇"},
    "Cypher": {"XAB": (0.382, 0.618), "ABC": (1.272, 1.414), "BCD": (0.786, 0.786), "XAD": (0.786, 0.786), "emoji": "⚡"}
}

# ═══════════════════════════════════════════════════════
#   📊  LÓGICA TÉCNICA REFORZADA
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, tf, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=100"
            r = requests.get(url, timeout=12).json()
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={tf}&range=5d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        return df[["o","h","l","c"]].astype(float).dropna()
    except Exception as e:
        logger.warning(f"⚠️ Error en {symbol}: {e}")
        return None

def analyze(series):
    try:
        delta = series.diff()
        g = (delta.where(delta > 0, 0)).rolling(14).mean()
        l = (-delta.where(delta < 0, 0)).rolling(14).mean()
        # Manejo de división por cero
        l_replaced = l.replace(0, 0.00001)
        rsi = 100 - (100 / (1 + (g / l_replaced))).iloc[-1]
        ema = series.ewm(span=50).mean().iloc[-1]
        return round(rsi, 2), ("BULL" if series.iloc[-1] > ema else "BEAR")
    except: return 50.0, "NEUTRAL"

def get_pivots(df):
    p = []
    for i in range(5, len(df)-5):
        if df['h'].iloc[i] == df['h'].iloc[i-5:i+6].max(): p.append({"p":df['h'].iloc[i],"t":"H"})
        if df['l'].iloc[i] == df['l'].iloc[i-5:i+6].min(): p.append({"p":df['l'].iloc[i],"t":"L"})
    f = []
    for x in p:
        if not f or f[-1]["t"] != x["t"]: f.append(x)
        else:
            if (x["t"] == "H" and x["p"] > f[-1]["p"]) or (x["t"] == "L" and x["p"] < f[-1]["p"]): f[-1] = x
    return f

def check_pat(pts, name):
    pat = HARMONIC_PATTERNS[name]
    X,A,B,C,D = [x["p"] for x in pts]
    if 0 in [abs(A-X), abs(B-A), abs(C-B), abs(D-C)]: return False
    r = [abs(B-A)/abs(A-X), abs(C-B)/abs(B-A), abs(D-C)/abs(C-B), abs(D-A)/abs(A-X)]
    t = TOLERANCE
    return (pat["XAB"][0]*(1-t) <= r[0] <= pat["XAB"][1]*(1+t) and pat["ABC"][0]*(1-t) <= r[1] <= pat["ABC"][1]*(1+t) and
            pat["BCD"][0]*(1-t) <= r[2] <= pat["BCD"][1]*(1+t) and pat["XAD"][0]*(1-t) <= r[3] <= pat["XAD"][1]*(1+t))

# ═══════════════════════════════════════════════════════
#   🚀  NÚCLEO DE EJECUCIÓN (SIN AVISOS DE DEPRECACIÓN)
# ═══════════════════════════════════════════════════════

async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Julio v5.5 Elite Online")

    while True:
        try:
            # Sincronización perfecta al segundo :35
            now = datetime.now(timezone.utc)
            minutes_to_next = 5 - (now.minute % 5)
            target = now.replace(second=35, microsecond=0) + timedelta(minutes=minutes_to_next)
            
            if target <= now:
                target += timedelta(minutes=5)
            
            wait = (target - now).total_seconds()
            logger.info(f"💤 Sincronizado. Próximo escaneo en {int(wait)}s ({target.strftime('%H:%M:%S')} UTC)")
            await asyncio.sleep(wait)

            # Escaneo
            logger.info("🔎 Iniciando rastreo de señales...")
            for tf in ["5m", "15m", "1h"]:
                for assets, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False), (OTHER_ASSETS, False)]:
                    for sym in assets:
                        df = fetch_data(sym, tf, is_crypto)
                        if df is not None and len(df) > 60:
                            rsi, trend = analyze(df['c'])
                            if rsi <= 30 or rsi >= 70:
                                pivots = get_pivots(df)
                                if len(pivots) >= 5:
                                    for name, p_data in HARMONIC_PATTERNS.items():
                                        if check_pat(pivots[-5:], name):
                                            is_buy = pivots[-1]["t"] == "L"
                                            order = "**MARKET**" if (rsi < 25 or rsi > 75) else "**LIMIT**"
                                            msg = (f"{p_data['emoji']} *{name}* | {sym.replace('=X','')}\n"
                                                   f"━━━━━━━━━━━━━━━━━━\n"
                                                   f"📈 Acción: {'COMPRA 🟢' if is_buy else 'VENTA 🔴'} {order}\n"
                                                   f"🕒 TF: *{tf}* | RSI: *{rsi}*\n"
                                                   f"💰 Precio: *{df['c'].iloc[-1]:.5f}*\n"
                                                   f"━━━━━━━━━━━━━━━━━━")
                                            try:
                                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                                await asyncio.sleep(1)
                                            except: pass
                        await asyncio.sleep(0.05)
        except Exception as global_e:
            logger.error(f"❌ Error crítico en el ciclo: {global_e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())
