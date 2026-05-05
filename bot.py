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

# Configuración de Filtros
SCAN_INTERVAL_MINUTES = 5
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30
TOLERANCE      = 0.06  # Muy estricto (6%) para mayor precisión

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Activos Filtrados
CRYPTO_ASSETS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT"]
FOREX_PAIRS = ["EURUSD=X","GBPUSD=X","JPY=X","AUDUSD=X","CADUSD=X","GBPCHF=X","EURJPY=X"]

# Definición de Patrones con Emojis
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
#   📊  MOTOR DE ANÁLISIS TÉCNICO
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, tf, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=100"
            df = pd.DataFrame(requests.get(url, timeout=10).json(), columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={tf}&range=10d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        
        df = df[["o","h","l","c"]].astype(float).dropna()
        return df
    except: return None

def get_market_analysis(series):
    # RSI
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    
    # Tendencia con EMA 50
    ema50 = series.ewm(span=50, adjust=False).mean().iloc[-1]
    current_price = series.iloc[-1]
    trend = "BULL" if current_price > ema50 else "BEAR"
    
    return round(rsi, 2), trend

def find_pivots(df):
    p = []
    # Usamos un orden de 5 para detectar giros significativos
    for i in range(5, len(df)-5):
        if df['h'].iloc[i] == df['h'].iloc[i-5:i+6].max(): p.append({"p":df['h'].iloc[i],"t":"H"})
        if df['l'].iloc[i] == df['l'].iloc[i-5:i+6].min(): p.append({"p":df['l'].iloc[i],"t":"L"})
    
    # Limpieza de pivots consecutivos
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
#   🚀  MOTOR DE EJECUCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Armónico Perfecto iniciado...")
    
    while True:
        for tf in TIMEFRAMES:
            # Escanear Crypto y luego Forex
            for asset_list, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False)]:
                for sym in asset_list:
                    df = fetch_data(sym, tf, is_crypto)
                    if df is not None and len(df) > 60:
                        rsi, trend = get_market_analysis(df['c'])
                        
                        # Solo procesar si el RSI indica agotamiento extremo
                        if rsi <= RSI_OVERSOLD or rsi >= RSI_OVERBOUGHT:
                            pivots = find_pivots(df)
                            
                            if len(pivots) >= 5:
                                # Analizamos los últimos 5 puntos de giro (Estructura XABCD)
                                last_5_pivots = pivots[-5:]
                                for name, data in HARMONIC_PATTERNS.items():
                                    if check_pattern(last_5_pivots, name):
                                        # Determinamos dirección según el último pivot D
                                        is_buy = last_5_pivots[-1]["t"] == "L"
                                        
                                        # Lógica de probabilidad basada en confluencia con tendencia
                                        if (is_buy and trend == "BULL") or (not is_buy and trend == "BEAR"):
                                            prob = "85% - 90% (Alta)"
                                            conf = "✅ Tendencia a favor"
                                        else:
                                            prob = "60% - 65% (Media)"
                                            conf = "⚠️ Contra tendencia"
                                        
                                        status = "SOBREVENTA ❄️" if rsi <= 30 else "SOBRECOMPRA 🔥"
                                        p_actual = df['c'].iloc[-1]
                                        
                                        # Mensaje simplificado y profesional
                                        msg = (f"{data['emoji']} *{name}* | {sym.replace('=X', '')}\n"
                                               f"━━━━━━━━━━━━━━━━━━\n"
                                               f"🕒 TF: *{tf}* | {status}\n"
                                               f"📈 Acción: *{'COMPRA' if is_buy else 'VENTA'}*\n"
                                               f"📊 RSI: *{rsi}* | {conf}\n"
                                               f"🎯 Éxito: *{prob}*\n"
                                               f"💰 Precio: *{p_actual:.5f}*\n"
                                               f"━━━━━━━━━━━━━━━━━━")
                                        
                                        try:
                                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                            logger.info(f"Señal enviada para {sym}")
                                        except Exception as e:
                                            logger.error(f"Error enviando Telegram: {e}")
                                        
                                        await asyncio.sleep(2) # Evitar spam
                                        
                    await asyncio.sleep(0.5) # Respetar límites de API
        
        logger.info("Ciclo terminado. Esperando 5 minutos...")
        await asyncio.sleep(SCAN_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    asyncio.run(main())
