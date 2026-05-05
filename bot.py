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

# Esta es la llave para que no te sature:
# Guarda la última señal enviada para no repetirla.
memoria_senales = {} 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"]
}

# ═══════════════════════════════════════════════════════
#   🧠 ESTRATEGIA CON NIVELES REALES
# ═══════════════════════════════════════════════════════

def analizar(df):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    # Filtros estrictos para evitar señales falsas
    if last['rsi'] < 25:
        return {"tipo": "COMPRA 🔵", "sl": price-(atr*2), "tp1": price+(atr*1.5), "tp2": price+(atr*3)}
    if last['rsi'] > 75:
        return {"tipo": "VENTA 🔴", "sl": price+(atr*2), "tp1": price-(atr*1.5), "tp2": price-(atr*3)}
    return None

# ═══════════════════════════════════════════════════════
#   📡 EJECUCIÓN LIMPIA (SIN WARNINGS)
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("✅ Julio v10.0 iniciado. Limpiando advertencias...")

    while True:
        try:
            # SOLUCIÓN AL ICONO AMARILLO: Usamos timezone.utc siempre
            ahora = datetime.now(timezone.utc)
            espera = 300 - (ahora.minute % 5 * 60 + ahora.second) + 35
            if espera <= 0: espera += 300
            
            logger.info(f"💤 Esperando {espera}s para escaneo limpio.")
            await asyncio.sleep(espera)

            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    try:
                        if cat == "CRYPTO":
                            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=15m&limit=50", timeout=10).json()
                            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                        else:
                            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=2d", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                            q = r["chart"]["result"][0]["indicators"]["quote"][0]
                            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                        
                        df = df[["o","h","l","c"]].astype(float).dropna()
                        res = analizar(df)
                        
                        if res:
                            # SOLO envía si la señal es nueva para este activo
                            if memoria_senales.get(sym) != res['tipo']:
                                msg = (f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"📈 Acción: *{res['tipo']}*\n"
                                       f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                       f"🛑 SL: `{res['sl']:.5f}`\n"
                                       f"🎯 TP1: `{res['tp1']:.5f}`\n"
                                       f"🎯 TP2: `{res['tp2']:.5f}`\n"
                                       f"━━━━━━━━━━━━━━━━━━")
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                memoria_senales[sym] = res['tipo']
                                await asyncio.sleep(2)
                        else:
                            # Si ya no hay señal, reseteamos la memoria para ese activo
                            memoria_senales[sym] = None

                    except Exception as e:
                        continue
            
            logger.info("✅ Escaneo terminado. Todo en orden.")
        except Exception as e:
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
