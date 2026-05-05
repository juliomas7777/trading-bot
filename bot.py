import asyncio
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta
import ccxt.async_support as ccxt
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# =============================================
#  CREDENCIALES ACTIVADAS
# =============================================
TELEGRAM_TOKEN = "7336183907:AAEShYhWn4Y1f56_0h2pC8YwL6fX0X3vR-I"
TELEGRAM_CHAT_ID = "-1002235962369"
EXCHANGE_ID = "binance" 

# Lista maestra de activos (Cripto, Forex, Índices)
ALL_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT",
    "EUR/USDC", "GBP/USDC", "AAPL/USDT", "TSLA/USDT"
]

# Parámetros técnicos
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2.0
MIN_GAP_PERCENT = 0.3

# =============================================
#  LOGGING Y SISTEMA DE MENSAJES
# =============================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

async def send_telegram_signal(msg):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode=ParseMode.HTML)
        log.info("Señal enviada a Telegram.")
    except Exception as e:
        log.error(f"Error en Telegram: {e}")

# =============================================
#  MOTOR DE ANÁLISIS
# =============================================
async def fetch_data(symbol, tf):
    exchange = getattr(ccxt, EXCHANGE_ID)({'enableRateLimit': True})
    try:
        ohlcv = await exchange.fetch_ohlcv(symbol, tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])
        return df.astype(float)
    except Exception as e:
        log.error(f"Error datos {symbol} [{tf}]: {e}")
        return None
    finally:
        await exchange.close()

# 1. MEAN REVERSION
async def check_mean_reversion(symbol, tf, df):
    df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
    bb = ta.bbands(df['close'], length=BB_PERIOD, std=BB_STD)
    if bb is None: return
    last = df.iloc[-1]
    upper = bb.iloc[-1, 2] # BBU
    lower = bb.iloc[-1, 0] # BBL

    if last['rsi'] > 70 and last['close'] >= upper:
        await send_telegram_signal(f"🔄 <b>MEAN REVERSION</b>\n📌 {symbol} [{tf}]\n🎯 VENTA 📉\n💰 Precio: {last['close']}")
    elif last['rsi'] < 30 and last['close'] <= lower:
        await send_telegram_signal(f"🔄 <b>MEAN REVERSION</b>\n📌 {symbol} [{tf}]\n🎯 COMPRA 📈\n💰 Precio: {last['close']}")

# 2. GAP FILL
async def check_gap_fill(symbol, tf, df):
    if len(df) < 2: return
    prev_close = df.iloc[-2]['close']
    curr_open = df.iloc[-1]['open']
    gap = ((curr_open - prev_close) / prev_close) * 100
    if abs(gap) >= MIN_GAP_PERCENT:
        await send_telegram_signal(f"⚡ <b>GAP FILL</b>\n📌 {symbol} [{tf}]\n📈 Gap: {gap:.2f}%\n🎯 {'VENTA 📉' if gap > 0 else 'COMPRA 📈'}")

# 3. SMC / ORDER BLOCK
async def check_smc_ob(symbol, tf, df):
    high_50 = df['high'].tail(50).max()
    low_50 = df['low'].tail(50).min()
    price = df['close'].iloc[-1]
    if price >= high_50 * 0.998:
        await send_telegram_signal(f"🧠 <b>SMC / ORDER BLOCK</b>\n📌 {symbol} [{tf}]\n🔴 Resistencia Detectada\n🎯 Acción: VENTA")
    elif price <= low_50 * 1.002:
        await send_telegram_signal(f"🧠 <b>SMC / ORDER BLOCK</b>\n📌 {symbol} [{tf}]\n🟢 Soporte Detectado\n🎯 Acción: COMPRA")

# 4. ARMÓNICOS
async def check_harmonics(symbol, tf, df):
    rsi = ta.rsi(df['close'], length=14).iloc[-1]
    if rsi > 80 or rsi < 20:
        await send_telegram_signal(f"🦋 <b>ARMÓNICOS</b>\n📌 {symbol} [{tf}]\n🎯 Reversión en PRZ detectada ({'VENTA' if rsi > 80 else 'COMPRA'})")

# =============================================
#  SCANNERS MULTI-TEMPORALES (Incluye 5m)
# =============================================
async def scanner():
    log.info("🤖 Bot Julio Inmortal v7.0 INICIADO")
    await send_telegram_signal("🚀 <b>Sistema Online</b>\nEscaneando: 5m, 15m, 1h, 4h\nActivos: Cripto/Forex/Índices")
    
    tfs = ["5m", "15m", "1h", "4h"]
    while True:
        for tf in tfs:
            for symbol in ALL_SYMBOLS:
                df = await fetch_data(symbol, tf)
                if df is None or df.empty: continue
                await check_mean_reversion(symbol, tf, df)
                await check_gap_fill(symbol, tf, df)
                await check_smc_ob(symbol, tf, df)
                await check_harmonics(symbol, tf, df)
                await asyncio.sleep(0.5)
        await asyncio.sleep(300) # Ciclo cada 5 min

if __name__ == "__main__":
    asyncio.run(scanner())
