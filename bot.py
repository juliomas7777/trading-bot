import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN Y MEMORIA
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

# Memoria de señales enviadas para evitar el bucle infinito
sent_signals = {} 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"]
}

# ═══════════════════════════════════════════════════════
#   🧠 LÓGICA DE FILTRADO TÉCNICO
# ═══════════════════════════════════════════════════════

def get_signals(df):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    # Solo genera señal si el RSI es extremo
    if last['rsi'] < 28:
        return {"tipo": "COMPRA 🔵", "sl": price-(atr*2), "tp1": price+(atr*1.5), "tp2": price+(atr*3)}
    if last['rsi'] > 72:
        return {"tipo": "VENTA 🔴", "sl": price+(atr*2), "tp1": price-(atr*1.5), "tp2": price-(atr*3)}
    return None

# ═══════════════════════════════════════════════════════
#   📡 MOTOR DE EJECUCIÓN CON FILTRO DE DUPLICADOS
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🛡️ Julio v9.5 Anti-Spam Activado")

    while True:
        try:
            now = datetime.now(timezone.utc)
            # Sincronización al segundo :35 para evitar solapamientos
            wait = 300 - (now.minute % 5 * 60 + now.second) + 35
            if wait <= 0: wait += 300
            
            logger.info(f"💤 Pausa de estabilidad: {wait}s")
            await asyncio.sleep(wait)

            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    # Descarga de datos (Binance o Yahoo)
                    df = None
                    try:
                        if cat == "CRYPTO":
                            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=15m&limit=50", timeout=10).json()
                            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                        else:
                            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=2d", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                            q = r["chart"]["result"][0]["indicators"]["quote"][0]
                            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                        
                        df = df[["o","h","l","c"]].astype(float).dropna()
                    except: continue

                    if df is not None and len(df) > 20:
                        sig = get_signals(df)
                        current_price = df['c'].iloc[-1]
                        
                        # CRÍTICO: Verificar si ya enviamos esta señal en este precio
                        if sig and sent_signals.get(sym) != sig['tipo']:
                            msg = (f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                   f"━━━━━━━━━━━━━━━━━━\n"
                                   f"📈 Acción: *{sig['tipo']}*\n"
                                   f"💰 Entrada: `{current_price:.5f}`\n"
                                   f"🛑 SL: `{sig['sl']:.5f}`\n"
                                   f"🎯 TP1: `{sig['tp1']:.5f}` | TP2: `{sig['tp2']:.5f}`\n"
                                   f"━━━━━━━━━━━━━━━━━━")
                            
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            sent_signals[sym] = sig['tipo'] # Guardar en memoria
                            await asyncio.sleep(5) # Evitar saturación de API
                        elif not sig:
                            sent_signals[sym] = None # Reset si ya no hay señal
            
            logger.info("✅ Escaneo limpio finalizado")
        except Exception as e:
            logger.error(f"⚠️ Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
