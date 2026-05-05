import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone
from telegram import Bot

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN MAESTRA
# ═══════════════════════════════════════════════════════
TELEGRAM_TOKEN  = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID         = "541470482"

# Registro para evitar duplicados: guarda (Símbolo + Minuto de la señal)
registro_velas = {} 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"]
}

# ═══════════════════════════════════════════════════════
#   🧠 ESTRATEGIA TÉCNICA (RSI + ATR)
# ═══════════════════════════════════════════════════════

def analizar_mercado(df):
    # RSI con cálculo de precisión
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    # Umbrales de alta probabilidad
    if last['rsi'] < 25:
        return {"tipo": "COMPRA 🔵", "sl": price-(atr*2), "tp1": price+(atr*1.5), "tp2": price+(atr*3)}
    if last['rsi'] > 75:
        return {"tipo": "VENTA 🔴", "sl": price+(atr*2), "tp1": price-(atr*1.5), "tp2": price-(atr*3)}
    return None

# ═══════════════════════════════════════════════════════
#   📡 MOTOR DE TIEMPO REAL
# ═══════════════════════════════════════════════════════

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("⏳ Julio v11.0 Cronos - Esperando sincronización exacta...")

    while True:
        try:
            # Cálculo del tiempo hasta el próximo ciclo de 5 min (al segundo :35)
            ahora = datetime.now(timezone.utc)
            minutos_restantes = 4 - (ahora.minute % 5)
            segundos_restantes = 60 - ahora.second + 35
            total_espera = (minutos_restantes * 60) + segundos_restantes
            
            # Si el cálculo da más de 300s o menos de 0, ajustar
            if total_espera > 300: total_espera -= 300
            if total_espera <= 0: total_espera = 300

            logger.info(f"💤 Próximo rastreo en {total_espera}s (Sincronizado a vela de 5m)")
            await asyncio.sleep(total_espera)

            # --- INICIO DEL ESCANEO ---
            hora_senal = datetime.now(timezone.utc).strftime("%H:%M")
            
            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    try:
                        # Descarga de datos
                        if cat == "CRYPTO":
                            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=15m&limit=50", timeout=10).json()
                            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                        else:
                            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=2d", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                            q = r["chart"]["result"][0]["indicators"]["quote"][0]
                            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                        
                        df = df[["o","h","l","c"]].astype(float).dropna()
                        res = analizar_mercado(df)
                        
                        if res:
                            # 🛡️ FILTRO ANTI-SPAM: Símbolo + Minuto actual
                            # Solo envía si no ha mandado este símbolo en este minuto exacto
                            id_senal = f"{sym}_{hora_senal}"
                            
                            if id_senal not in registro_velas:
                                msg = (f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"📈 Acción: *{res['tipo']}*\n"
                                       f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                       f"🛑 SL: `{res['sl']:.5f}`\n"
                                       f"🎯 TP1: `{res['tp1']:.5f}`\n"
                                       f"🎯 TP2: `{res['tp2']:.5f}`\n"
                                       f"━━━━━━━━━━━━━━━━━━\n"
                                       f"⏰ Hora: `{hora_senal} UTC`")
                                
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                registro_velas[id_senal] = True
                                logger.info(f"✅ Señal enviada: {sym}")
                                await asyncio.sleep(2) # Respiro para el servidor
                                
                    except Exception: continue
            
            # Limpiar memoria de señales viejas para no saturar el bot
            if len(registro_velas) > 50: registro_velas.clear()
            
            logger.info("🔚 Ciclo de escaneo completado.")
            await asyncio.sleep(10) # Pausa mínima antes de recalcular siguiente ciclo

        except Exception as e:
            logger.error(f"⚠️ Error general: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
