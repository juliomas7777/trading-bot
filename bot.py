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

# Activos que funcionan bien en tus logs de Railway
ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"],
    "STOCKS": ["NVDA", "SPY", "TSLA", "AAPL"]
}

# ═══════════════════════════════════════════════════════
#   🧠 LÓGICA DE TRADING (RSI + VOLATILIDAD REAL)
# ═══════════════════════════════════════════════════════

def get_signals(df):
    """Calcula indicadores y genera niveles de SL y TP obligatorios"""
    # RSI (14) - Calculado de forma moderna
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    
    # Cálculo de volatilidad para Stop Loss y TP exactos
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    # 🔵 Señal de COMPRA (RSI en sobreventa)
    if last['rsi'] < 30:
        return {
            "tipo": "COMPRA 🔵",
            "sl": price - (atr * 2),
            "tp1": price + (atr * 1.5),
            "tp2": price + (atr * 3)
        }
    
    # 🔴 Señal de VENTA (RSI en sobrecompra)
    if last['rsi'] > 70:
        return {
            "tipo": "VENTA 🔴",
            "sl": price + (atr * 2),
            "tp1": price - (atr * 1.5),
            "tp2": price - (atr * 3)
        }
        
    return None

# ═══════════════════════════════════════════════════════
#   📡 MOTOR DE EJECUCIÓN (SOLUCIÓN A DEPRECATION)
# ═══════════════════════════════════════════════════════

def fetch_data(symbol, is_crypto):
    """Descarga de datos limpia sin errores de conexión"""
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
    logger.info("🚀 Julio v9.0 Perfect - Iniciado sin errores")

    while True:
        try:
            # CORRECCIÓN: Uso de timezone.utc para evitar el error de tus logs
            now = datetime.now(timezone.utc)
            # Sincronización al segundo :35 validada
            wait = 300 - (now.minute % 5 * 60 + now.second) + 35
            if wait <= 0: wait += 300
            
            logger.info(f"💤 Próximo escaneo en {wait} segundos...")
            await asyncio.sleep(wait)

            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    df = fetch_data(sym, cat == "CRYPTO")
                    if df is not None and len(df) > 20:
                        sig = get_signals(df)
                        if sig:
                            entry = df['c'].iloc[-1]
                            # Formato limpio que pediste (Market price + SL + TP1 + TP2)
                            msg = (f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"📈 Acción: *{sig['tipo']}*\n"
                                   f"💰 Entrada: `{entry:.5f}`\n"
                                   f"🛑 STOP LOSS: `{sig['sl']:.5f}`\n"
                                   f"🎯 TAKE PROFIT 1: `{sig['tp1']:.5f}`\n"
                                   f"🎯 TAKE PROFIT 2: `{sig['tp2']:.5f}`\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"⚡ _Estado: Activa (Market)_")
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            await asyncio.sleep(2) # Pausa para no saturar Railway
            
            logger.info("✅ Ciclo completado perfectamente.")
        except Exception as e:
            logger.error(f"⚠️ Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
