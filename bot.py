#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN MAESTRA (JULIO)
# ═══════════════════════════════════════════════════════

TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

SCAN_INTERVAL_MINUTES = 5
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30
TOLERANCE      = 0.06 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── NUEVA LISTA DE ACTIVOS SOLICITADA ──

# Criptomonedas (Binance)
CRYPTO_ASSETS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", 
    "BCHUSDT", "XRPUSDT", "LTCUSDT", "LINKUSDT", "ZECUSDT", 
    "NEOUSDT", "MANAUSDT"
]

# Forex - Divisas (Yahoo Finance)
FOREX_PAIRS = [
    "AUDUSD=X", "NZDUSD=X", "GBPUSD=X", "EURUSD=X", 
    "USDJPY=X", "USDCHF=X", "USDCAD=X"
]

# Índices, ETFs, Futuros, Materias Primas y Acciones (Yahoo Finance)
# Nota: Para futuros de junio 2026 usamos códigos compatibles como ESM26.CME
OTHER_ASSETS = [
    "SPY", "ES=F", "GC=F", "NVDA"
]

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
#   📊  FUNCIONES TÉCNICAS
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, tf, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=100"
            df = pd.DataFrame(requests.get(url, timeout=10).json(), columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            # Rango ajustado para tener suficientes datos para EMA50
            p = "5d" if tf in ["5m","15m"] else "60d"
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={tf}&range={p}"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        
        df = df[["o","h","l","c"]].astype(float).dropna()
        return df
    except: return None

def get_market_analysis(series):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    ema50 = series.ewm(span=50, adjust=False).mean().iloc[-1]
    trend = "BULL" if series.iloc[-1] > ema50 else "BEAR"
    return round(rsi, 2), trend

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
    X, A, B, C, D = [x["p"] for x in pts]
    XA, AB, BC, CD, AD = abs(A-X), abs(B-A), abs(C-B), abs(D-C), abs(D-A)
    if 0 in (XA, AB, BC, CD): return False
    r1, r2, r3, r4 = AB/XA, BC/AB, CD/BC, AD/XA
    t = TOLERANCE
    return (pat["XAB"][0]*(1-t) <= r1 <= pat["XAB"][1]*(1+t) and
            pat["ABC"][0]*(1-t) <= r2 <= pat["ABC"][1]*(1+t) and
            pat["BCD"][0]*(1-t) <= r3 <= pat["BCD"][1]*(1+t) and
            pat["XAD"][0]*(1-t) <= r4 <= pat["XAD"][1]*(1+t))

# ═══════════════════════════════════════════════════════
#   🚀  EJECUCIÓN
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Armónico Multi-Activo iniciado...")
    
    while True:
        for tf in TIMEFRAMES:
            # Lista unificada de escaneo
            tasks = [
                (CRYPTO_ASSETS, True, "CRIPTO"),
                (FOREX_PAIRS, False, "FOREX"),
                (OTHER_ASSETS, False, "MERCADOS")
            ]
            
            for asset_list, is_crypto, cat_name in tasks:
                for sym in asset_list:
                    df = fetch_data(sym, tf, is_crypto)
                    if df is not None and len(df) > 60:
                        rsi, trend = get_market_analysis(df['c'])
                        
                        if rsi <= RSI_OVERSOLD or rsi >= RSI_OVERBOUGHT:
                            pivots = find_pivots(df)
                            if len(pivots) >= 5:
                                last_5 = pivots[-5:]
                                for name, data in HARMONIC_PATTERNS.items():
                                    if check_pattern(last_5, name):
                                        is_buy = last_5[-1]["t"] == "L"
                                        
                                        # Probabilidad por tendencia
                                        if (is_buy and trend == "BULL") or (not is_buy and trend == "BEAR"):
                                            prob, conf = "85% - 90%", "✅ Tendencia a favor"
                                        else:
                                            prob, conf = "60% - 65%", "⚠️ Contra tendencia"
                                        
                                        clean_name = sym.replace("=X","").replace("USDT","")
                                        status = "SOBREVENTA ❄️" if rsi <= 30 else "SOBRECOMPRA 🔥"
                                        
                                        msg = (f"{data['emoji']} *{name}* | {clean_name}\n"
                                               f"━━━━━━━━━━━━━━━━━━\n"
                                               f"🕒 TF: *{tf}* | {status}\n"
                                               f"📈 Acción: *{'COMPRA' if is_buy else 'VENTA'}*\n"
                                               f"📊 RSI: *{rsi}* | {conf}\n"
                                               f"🎯 Éxito: *{prob}*\n"
                                               f"💰 Precio: *{df['c'].iloc[-1]:.5f}*\n"
                                               f"━━━━━━━━━━━━━━━━━━")
                                        
                                        try:
                                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                        except: pass
                                        await asyncio.sleep(2)
                    await asyncio.sleep(0.5)
        
        logger.info("Ciclo completo. Esperando 5 minutos...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    asyncio.run(main())
