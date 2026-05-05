import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN MAESTRA
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Activos actualizados y verificados
ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"],
    "STOCKS": ["NVDA", "SPY", "TSLA"]
}

# ═══════════════════════════════════════════════════════
#   🧠 LÓGICA DE TRADING DE ALTA PRECISIÓN
# ═══════════════════════════════════════════════════════

def get_signals(df):
    """Calcula indicadores y genera niveles de TP/SL reales"""
    # RSI
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    # Volatilidad para niveles (ATR simplificado)
    df['vol'] = (df['h'] - df['l']).rolling(10).mean()
    
    last = df.iloc[-1]
    price = last['c']
    vol = last['vol'] if last['vol'] > 0 else price * 0.005
    
    # Señal de COMPRA
    if last['rsi'] < 30:
        return {
            "tipo": "COMPRA 🔵",
            "sl": price - (vol * 2),
            "tp1": price + (vol * 1.5),
            "tp2": price + (vol * 3)
        }
    
    # Señal de VENTA
    if last['rsi'] > 70:
        return {
            "tipo": "VENTA 🔴",
            "sl": price + (vol * 2),
            "tp1": price - (vol * 1.5),
            "tp2": price - (vol * 3)
        }
        
    return None

# ═══════════════════════════════════════════════════════
#   📡 CONEXIÓN Y SINCRONIZACIÓN (ZERO ERRORS)
# ═══════════════════════════════════════════════════════

def fetch(symbol, is_crypto):
    try:
        if is_crypto:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=50"
            r = requests.get(url, timeout=10).json()
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=15m&range=2d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
        return df[["o","h","l","c"]].astype(float).dropna()
    except: return None

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🔥 Julio v8.0 Final Boss - Desplegado")

    while True:
        try:
            # Sincronización exacta al segundo :35 (Evita duplicados)
            now = datetime.now(timezone.utc)
            wait = 300 - (now.minute % 5 * 60 + now.second) + 35
            if wait <= 0: wait += 300
            
            logger.info(f"💤 Esperando {wait}s para el próximo escaneo técnico...")
            await asyncio.sleep(wait)

            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    df = fetch(sym, cat == "CRYPTO")
                    if df is not None and len(df) > 20:
                        sig = get_signals(df)
                        if sig:
                            entry = df['c'].iloc[-1]
                            msg = (f"🎯 *SEÑAL CONFIRMADA:* {sym.replace('=X','')}\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"📈 Acción: *{sig['tipo']}*\n"
                                   f"💰 Entrada: `{entry:.5f}`\n"
                                   f"🛑 STOP LOSS: `{sig['sl']:.5f}`\n"
                                   f"🎯 TAKE PROFIT 1: `{sig['tp1']:.5f}`\n"
                                   f"🎯 TAKE PROFIT 2: `{sig['tp2']:.5f}`\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"⚡ _Ejecución: Market Order_")
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            await asyncio.sleep(3) # Protección anti-spam Telegram
            
            logger.info("✅ Ciclo completado sin errores.")
        except Exception as e:
            logger.error(f"⚠️ Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
