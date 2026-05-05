import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN FINAL (VALIDADA)
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CRYPTO_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT", "XRPUSDT"]
FOREX_PAIRS   = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
OTHER_ASSETS  = ["SPY", "NVDA", "GC=F"]

# ═══════════════════════════════════════════════════════
#   🧠 MOTOR DE ESTRATEGIAS (4 SISTEMAS INDEPENDIENTES)
# ═══════════════════════════════════════════════════════

def get_indicators(df):
    # RSI
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    # Medias Móviles (Cruce SMA)
    df['sma_fast'] = df['c'].rolling(window=9).mean()
    df['sma_slow'] = df['c'].rolling(window=21).mean()
    
    # MACD
    ema12 = df['c'].ewm(span=12, adjust=False).mean()
    ema26 = df['c'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bandas de Bollinger
    df['ma20'] = df['c'].rolling(window=20).mean()
    df['std'] = df['c'].rolling(window=20).std()
    df['upper'] = df['ma20'] + (df['std'] * 2)
    df['lower'] = df['ma20'] - (df['std'] * 2)
    
    return df

def check_strategies(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['c']
    
    # 1. Estrategia RSI (Sobreventa/Sobrecompra)
    if last['rsi'] < 30: return "COMPRA (RSI)", "MARKET", price * 0.985, price * 1.02, price * 1.04
    if last['rsi'] > 70: return "VENTA (RSI)", "MARKET", price * 1.015, price * 0.98, price * 0.96
    
    # 2. Cruce de Medias SMA
    if prev['sma_fast'] < prev['sma_slow'] and last['sma_fast'] > last['sma_slow']:
        return "COMPRA (SMA Cross)", "LIMIT", price * 0.99, price * 1.03, price * 1.06
    
    # 3. MACD Golden Cross
    if prev['macd'] < prev['signal'] and last['macd'] > last['signal']:
        return "COMPRA (MACD)", "MARKET", price * 0.99, price * 1.02, price * 1.05
        
    # 4. Bollinger Rebound
    if last['c'] < last['lower']:
        return "COMPRA (Bollinger)", "LIMIT", price * 0.98, price * 1.02, price * 1.04

    return None, None, None, None, None

# ═══════════════════════════════════════════════════════
#   📡 CONEXIÓN Y SINCRONIZACIÓN (ESTILO INMORTAL)
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
    except: return None

async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Julio v7.0 Maestro Online - 4 Estrategias Activas")

    while True:
        try:
            now = datetime.now(timezone.utc)
            minutes_to_next = 5 - (now.minute % 5)
            target = now.replace(second=35, microsecond=0) + timedelta(minutes=minutes_to_next)
            if target <= now: target += timedelta(minutes=5)
            
            wait_time = (target - now).total_seconds()
            logger.info(f"💤 Sincronizado. Próximo escaneo en {int(wait_time)}s")
            await asyncio.sleep(wait_time + 2) # Buffer de cierre

            for tf in ["5m", "15m", "1h"]:
                for assets, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False), (OTHER_ASSETS, False)]:
                    for sym in assets:
                        df = fetch_data(sym, tf, is_crypto)
                        if df is not None and len(df) > 30:
                            df = get_indicators(df)
                            signal, o_type, sl, tp1, tp2 = check_strategies(df)
                            
                            if signal:
                                msg = (f"🤖 *JULIO v7.0:* {sym.replace('=X','')}\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"📊 Estrategia: *{signal}*\n"
                                       f"🕒 TF: *{tf}* | Tipo: *{o_type}*\n"
                                       f"💰 Precio: *{df['c'].iloc[-1]:.5f}*\n"
                                       f"🛑 Stop Loss: *{sl:.5f}*\n"
                                       f"🎯 TP1: *{tp1:.5f}* | TP2: *{tp2:.5f}*\n"
                                       f"━━━━━━━━━━━━━━━━━━")
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                await asyncio.sleep(1)
            logger.info("✅ Ciclo de 4 estrategias completado.")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(run_bot())
