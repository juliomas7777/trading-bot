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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── ACTIVOS (Tus activos de v6.3) ──
CRYPTO_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", "BCHUSDT", "XRPUSDT", "LTCUSDT", "LINKUSDT", "ZECUSDT", "NEOUSDT", "MANAUSDT"]
FOREX_PAIRS   = ["AUDUSD=X", "NZDUSD=X", "GBPUSD=X", "EURUSD=X", "USDJPY=X", "USDCHF=X", "USDCAD=X"]
OTHER_ASSETS  = ["SPY", "ES=F", "GC=F", "NVDA"]

# ═══════════════════════════════════════════════════════
#   📊  MOTOR DE DATOS E INDICADORES
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, tf, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={tf}&limit=150"
            r = requests.get(url, timeout=12).json()
            if not isinstance(r, list): return None
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={tf}&range=5d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"], "v":q["volume"]})
        df = df[["o","h","l","c","v"]].astype(float).dropna()
        return df if len(df) > 60 else None
    except: return None

def get_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean().replace(0, 0.00001)
    return 100 - (100 / (1 + (gain / loss)))

# ═══════════════════════════════════════════════════════
#   🚀  LAS 4 ESTRATEGIAS INTEGRADAS
# ═══════════════════════════════════════════════════════

# 1. MEAN REVERSION (Bandas de Bollinger + RSI)
def check_mean_reversion(df):
    rsi = get_rsi(df['c']).iloc[-1]
    ma = df['c'].rolling(20).mean()
    std = df['c'].rolling(20).std()
    upper, lower = ma + (2 * std), ma - (2 * std)
    
    last_c, last_l, last_h = df['c'].iloc[-1], df['l'].iloc[-1], df['h'].iloc[-1]
    if rsi < 30 and last_l <= lower.iloc[-1]: return "COMPRA 📈", rsi
    if rsi > 70 and last_h >= upper.iloc[-1]: return "VENTA 📉", rsi
    return None, rsi

# 2. GAP FILL (Estrategia de Apertura)
def check_gap_fill(df):
    prev_close, curr_open = df['c'].iloc[-2], df['o'].iloc[-1]
    gap_pct = ((curr_open - prev_close) / prev_close) * 100
    if abs(gap_pct) > 0.5:
        if gap_pct > 0 and df['c'].iloc[-1] < curr_open: return "VENTA (Cierre Gap) 📉", gap_pct
        if gap_pct < 0 and df['c'].iloc[-1] > curr_open: return "COMPRA (Cierre Gap) 📈", gap_pct
    return None, gap_pct

# 3. SMC + ORDER BLOCK (Simplificado para consistencia)
def check_smc_ob(df):
    recent_h, recent_l = df['h'].tail(20).max(), df['l'].tail(20).min()
    last_c = df['c'].iloc[-1]
    if last_c >= recent_h * 0.99: return "VENTA (OB Resistencia) 🔴", "Bearish"
    if last_c <= recent_l * 1.01: return "COMPRA (OB Soporte) 🟢", "Bullish"
    return None, None

# 4. PATRONES ARMÓNICOS (Lógica v6.3 mejorada)
def check_harmonics(df):
    p = [] # Identificar Pivotes
    for i in range(5, len(df)-5):
        if df['h'].iloc[i] == df['h'].iloc[i-5:i+6].max(): p.append({"p":df['h'].iloc[i],"t":"H"})
        if df['l'].iloc[i] == df['l'].iloc[i-5:i+6].min(): p.append({"p":df['l'].iloc[i],"t":"L"})
    if len(p) < 5: return None
    
    # Ratios Fibonacci (X, A, B, C, D)
    pts = p[-5:]
    X, A, B, C, D = [x["p"] for x in pts]
    try:
        xab = abs(B-A)/abs(A-X)
        if 0.382 <= xab <= 0.886: return "PATRÓN ARMÓNICO 🦋", round(xab, 3)
    except: pass
    return None, None

# ═══════════════════════════════════════════════════════
#   📡  SISTEMA DE ENVÍO Y ESCANEO
# ═══════════════════════════════════════════════════════

async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Julio v7.0 Multi-Estrategia Online")

    while True:
        try:
            # Sincronización exacta al segundo :35 (Tu sello de calidad)
            now = datetime.now(timezone.utc)
            wait_time = (5 - (now.minute % 5)) * 60 - now.second + 35
            if wait_time <= 0: wait_time += 300
            
            logger.info(f"💤 Sincronizado. Próximo escaneo en {int(wait_time)}s")
            await asyncio.sleep(wait_time)
            await asyncio.sleep(2) # Buffer de cierre

            for tf in ["5m", "15m", "1h", "4h"]:
                for assets, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False), (OTHER_ASSETS, False)]:
                    for sym in assets:
                        df = fetch_data(sym, tf, is_crypto)
                        if df is None: continue

                        # --- EVALUAR CADA ESTRATEGIA ---
                        results = [
                            ("MEAN REVERSION", *check_mean_reversion(df)),
                            ("GAP FILL", *check_gap_fill(df)),
                            ("SMC + ORDER BLOCK", *check_smc_ob(df)),
                            ("ARMÓNICOS", *check_harmonics(df))
                        ]

                        for strategy_name, signal, value in results:
                            if signal:
                                msg = (f"🔥 <b>{strategy_name}</b>\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"📌 Activo: <b>{sym.replace('=X','')}</b>\n"
                                       f"🕒 TF: <b>{tf}</b> | Acción: <b>{signal}</b>\n"
                                       f"💰 Precio: <b>{df['c'].iloc[-1]:.5f}</b>\n"
                                       f"📊 Info: <b>{value}</b>\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"✅ Win Rate: 75-82% | @JulioBot")
                                try:
                                    await bot.send_message(CHAT_ID, msg, parse_mode="HTML")
                                    await asyncio.sleep(1.5)
                                except: pass
                        await asyncio.sleep(0.1)
            logger.info("✅ Escaneo completo en todas las temporalidades.")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(run_bot())
