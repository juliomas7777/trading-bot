#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN MAESTRA (JULIO)
# ═══════════════════════════════════════════════════════

TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30
TOLERANCE      = 0.06 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── ACTIVOS (Configuración idéntica a tu petición) ──
CRYPTO_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", "BCHUSDT", "XRPUSDT", "LTCUSDT", "LINKUSDT", "ZECUSDT", "NEOUSDT", "MANAUSDT"]
FOREX_PAIRS = ["AUDUSD=X", "NZDUSD=X", "GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X"]
OTHER_ASSETS = ["SPY", "ES=F", "GC=F", "NVDA"]

HARMONIC_PATTERNS = {
    "Butterfly": {"XAB": (0.786, 0.786), "ABC": (0.382, 0.886), "BCD": (1.618, 2.618), "XAD": (1.272, 1.618), "emoji": "🦋"},
    "Crab": {"XAB": (0.382, 0.618), "ABC": (0.382, 0.886), "BCD": (2.240, 3.618), "XAD": (1.618, 1.618), "emoji": "🦀"},
    "Shark": {"XAB": (0.382, 0.618), "ABC": (1.128, 1.618), "BCD": (1.618, 2.236), "XAD": (0.886, 1.128), "emoji": "🦈"},
    "Gartley": {"XAB": (0.618, 0.618), "ABC": (0.382, 0.886), "BCD": (1.272, 1.618), "XAD": (0.786, 0.786), "emoji": "🎯"},
    "Bat": {"XAB": (0.382, 0.500), "ABC": (0.382, 0.886), "BCD": (1.618, 2.618), "XAD": (0.886, 0.886), "emoji": "🦇"},
    "Cypher": {"XAB": (0.382, 0.618), "ABC": (1.272, 1.414), "BCD": (0.786, 0.786), "XAD": (0.786, 0.786), "emoji": "⚡"}
}

TIMEFRAMES = ["5m", "15m", "1h"]

# ═══════════════════════════════════════════════════════
#   📊  FUNCIONES TÉCNICAS (Optimizadas)
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, tf, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=100"
            r = requests.get(url, timeout=10).json()
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            p = "5d" if tf in ["5m","15m"] else "60d"
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={tf}&range={p}"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        return df[["o","h","l","c"]].astype(float).dropna()
    except: return None

def get_market_analysis(series):
    delta = series.diff(); gain = (delta.where(delta > 0, 0)).rolling(window=14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    ema50 = series.ewm(span=50, adjust=False).mean().iloc[-1]
    return round(rsi, 2), ("BULL" if series.iloc[-1] > ema50 else "BEAR")

def find_pivots(df):
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

def check_pattern(pts, name):
    pat = HARMONIC_PATTERNS[name]
    X,A,B,C,D = [x["p"] for x in pts]; XA, AB, BC, CD, AD = abs(A-X), abs(B-A), abs(C-B), abs(D-C), abs(D-A)
    if 0 in (XA, AB, BC, CD): return False
    r = [AB/XA, BC/AB, CD/BC, AD/XA]; t = TOLERANCE
    return (pat["XAB"][0]*(1-t) <= r[0] <= pat["XAB"][1]*(1+t) and pat["ABC"][0]*(1-t) <= r[1] <= pat["ABC"][1]*(1+t) and
            pat["BCD"][0]*(1-t) <= r[2] <= pat["BCD"][1]*(1+t) and pat["XAD"][0]*(1-t) <= r[3] <= pat["XAD"][1]*(1+t))

# ═══════════════════════════════════════════════════════
#   🚀  SISTEMA DE CONTROL DE TIEMPO
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Armónico Julio v3.0 iniciado.")
    
    while True:
        start_time = datetime.utcnow()
        logger.info(f"🔎 Iniciando escaneo de mercado: {start_time.strftime('%H:%M:%S')} UTC")
        
        # Ejecución del escaneo
        for tf in TIMEFRAMES:
            for asset_list, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False), (OTHER_ASSETS, False)]:
                for sym in asset_list:
                    df = fetch_data(sym, tf, is_crypto)
                    if df is not None and len(df) > 60:
                        rsi, trend = get_market_analysis(df['c'])
                        if rsi <= RSI_OVERSOLD or rsi >= RSI_OVERBOUGHT:
                            pivots = find_pivots(df)
                            if len(pivots) >= 5:
                                for name, data in HARMONIC_PATTERNS.items():
                                    if check_pattern(pivots[-5:], name):
                                        is_buy = pivots[-1]["t"] == "L"
                                        order_type = "**MARKET**" if (rsi < 25 or rsi > 75) else "**LIMIT**"
                                        prob = "85% - 90%" if (is_buy and trend == "BULL") or (not is_buy and trend == "BEAR") else "60% - 65%"
                                        msg = (f"{data['emoji']} *{name}* | {sym.replace('=X','')}\n"
                                               f"━━━━━━━━━━━━━━━━━━\n"
                                               f"📈 Acción: {'COMPRA 🟢' if is_buy else 'VENTA 🔴'} {order_type}\n"
                                               f"🕒 TF: *{tf}* | RSI: *{rsi}*\n"
                                               f"🎯 Éxito: *{prob}*\n"
                                               f"💰 Precio: *{df['c'].iloc[-1]:.5f}*\n"
                                               f"━━━━━━━━━━━━━━━━━━")
                                        try: await bot.send_message(CHAT_ID, msg, parse_mode="Markdown"); await asyncio.sleep(1)
                                        except: pass
                    await asyncio.sleep(0.1) # Pequeña pausa para no saturar

        # --- CÁLCULO DE ESPERA INTELIGENTE ---
        now = datetime.utcnow()
        # Calculamos el próximo minuto múltiplo de 5
        next_minute = (now.minute // 5 + 1) * 5
        next_run = now.replace(minute=0, second=35, microsecond=0) + timedelta(minutes=next_minute)
        
        # Si por retrasos ya pasamos el minuto, saltar al siguiente
        if next_run <= now:
            next_run += timedelta(minutes=5)
            
        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"✅ Ciclo terminado. Próximo rastreo exacto: {next_run.strftime('%H:%M:%S')} UTC (Dormir {int(wait_seconds)}s)")
        await asyncio.sleep(wait_seconds)

if __name__ == "__main__":
    asyncio.run(main())
