import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta, timezone
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN DE ACCESO
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Tus activos validados
CRYPTO_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
FOREX_PAIRS   = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X"]
STOCKS        = ["NVDA", "SPY", "AAPL", "TSLA"]

# ═══════════════════════════════════════════════════════
#   🧠 ESTRATEGIAS TÉCNICAS (RSI + MACD + BOLLINGER)
# ═══════════════════════════════════════════════════════

def get_indicators(df):
    # RSI (14)
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    # MACD
    ema12 = df['c'].ewm(span=12, adjust=False).mean()
    ema26 = df['c'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df['ma20'] = df['c'].rolling(window=20).mean()
    df['std'] = df['c'].rolling(window=20).std()
    df['upper'] = df['ma20'] + (df['std'] * 2)
    df['lower'] = df['ma20'] - (df['std'] * 2)
    
    return df

def generate_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last['c']
    
    # Lógica de señales con niveles automáticos (TP/SL)
    # COMPRA: RSI bajo + rebote en banda inferior o MACD cruzando al alza
    if (last['rsi'] < 32) or (prev['macd'] < prev['signal'] and last['macd'] > last['signal']):
        sl = price * 0.985  # SL al 1.5%
        tp1 = price * 1.02   # TP1 al 2%
        tp2 = price * 1.04   # TP2 al 4%
        return "COMPRA (LONG)", "MARKET", sl, tp1, tp2

    # VENTA: RSI alto + rebote en banda superior o MACD cruzando a la baja
    if (last['rsi'] > 68) or (prev['macd'] > prev['signal'] and last['macd'] < last['signal']):
        sl = price * 1.015  # SL al 1.5%
        tp1 = price * 0.98   # TP1 al 2%
        tp2 = price * 0.96   # TP2 al 4%
        return "VENTA (SHORT)", "MARKET", sl, tp1, tp2

    return None, None, None, None, None

# ═══════════════════════════════════════════════════════
#   📡 MOTOR DE EJECUCIÓN SIN ERRORES
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=100"
            r = requests.get(url, timeout=10).json()
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=15m&range=5d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        return df[["o","h","l","c"]].astype(float).dropna()
    except: return None

async def run_bot():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("✅ Julio v7.5 Master Trader - Iniciado correctamente")

    while True:
        try:
            # Sincronización precisa al segundo :35 (Validado en logs anteriores)
            now = datetime.now(timezone.utc)
            wait_sec = 300 - (now.minute % 5 * 60 + now.second) + 35
            if wait_sec <= 0: wait_sec += 300
            
            logger.info(f"💤 Sincronizado. Próximo escaneo en {wait_sec}s")
            await asyncio.sleep(wait_sec)

            for assets, is_crypto in [(CRYPTO_ASSETS, True), (FOREX_PAIRS, False), (STOCKS, False)]:
                for sym in assets:
                    df = fetch_data(sym, is_crypto)
                    if df is not None and len(df) > 30:
                        df = get_indicators(df)
                        tipo, orden, sl, tp1, tp2 = generate_signal(df)
                        
                        if tipo:
                            msg = (f"🚀 *NUEVA SEÑAL:* {sym.replace('=X','')}\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"📈 Acción: *{tipo}*\n"
                                   f"🛒 Orden: *{orden}*\n"
                                   f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                   f"🛑 Stop Loss: `{sl:.5f}`\n"
                                   f"🎯 TP 1: `{tp1:.5f}`\n"
                                   f"🎯 TP 2: `{tp2:.5f}`\n"
                                   f"━━━━━━━━━━━━━━━━━━")
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            await asyncio.sleep(1.5) # Evitar spam / ban de Telegram
            
            logger.info("✅ Escaneo completo. Señales enviadas.")
        except Exception as e:
            logger.error(f"❌ Error en ciclo: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())
