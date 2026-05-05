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

# Registro para evitar duplicados: (Símbolo + Temporalidad + Hora)
registro_velas = {} 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"]
}

# Temporalidades activas
TIMEFRAMES = ["15m", "1h", "4h"]

# ═══════════════════════════════════════════════════════
#   🧠 ESTRATEGIA TÉCNICA (RSI + ATR)
# ═══════════════════════════════════════════════════════
def analizar_mercado(df):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    if last['rsi'] < 25:
        return {"tipo": "COMPRA 🔵", "sl": price-(atr*2), "tp1": price+(atr*1.5), "tp2": price+(atr*3)}
    if last['rsi'] > 75:
        return {"tipo": "VENTA 🔴", "sl": price+(atr*2), "tp1": price-(atr*1.5), "tp2": price-(atr*3)}
    return None

# ═══════════════════════════════════════════════════════
#   📐 ESTRATEGIA DE PATRONES ARMÓNICOS
# ═══════════════════════════════════════════════════════
def detectar_patrones_armonicos(df):
    if len(df) < 50: return None
    prices = df['c'].values
    try:
        X, A, B, C, D = prices[-5], prices[-4], prices[-3], prices[-2], prices[-1]
        XA, AB, BC, CD = A-X, B-A, C-B, D-C
        if XA == 0: return None
        ret_AB, ret_AD = abs(AB/XA), abs((D-X)/XA)
        err = 0.05
        patterns = [
            {"name": "Gartley", "B": 0.618, "D": 0.786},
            {"name": "Bat", "B": 0.382, "D": 0.886},
            {"name": "Butterfly", "B": 0.786, "D": 1.27},
            {"name": "Crab", "B": 0.382, "D": 1.618}
        ]
        for p in patterns:
            if abs(ret_AB - p['B']) < err and abs(ret_AD - p['D']) < err:
                return {"nombre": p['name'], "tipo": "ALZA 🟢" if X < A else "BAJA 🔴"}
    except: return None
    return None

# ═══════════════════════════════════════════════════════
#   📡 MOTOR MULTI-TEMPORALIDAD (Sincronizado -35s)
# ═══════════════════════════════════════════════════════
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Julio v12.0 - Escaneando 15m, 1h y 4h (35s antes del cierre)")

    while True:
        try:
            # --- LÓGICA DE TIEMPO (35 segundos antes del cierre de vela de 15m) ---
            ahora = datetime.now(timezone.utc)
            # Calculamos cuántos segundos faltan para el próximo múltiplo de 15 minutos
            minutos_actuales = ahora.minute
            segundos_actuales = ahora.second
            
            proximo_bloque_15 = (15 - (minutos_actuales % 15))
            # Tiempo total en segundos hasta el cierre de la vela
            segundos_hasta_cierre = (proximo_bloque_15 * 60) - segundos_actuales
            # Restamos 35 segundos para enviar la señal antes del cierre
            espera_real = segundos_hasta_cierre - 35

            if espera_real <= 0: # Si ya estamos en el margen de 35s, esperamos al siguiente ciclo
                espera_real += 900
            
            logger.info(f"💤 Esperando {espera_real} segundos para enviar señales antes del cierre...")
            await asyncio.sleep(espera_real)

            # --- INICIO DEL ESCANEO ---
            ahora_ejecucion = datetime.now(timezone.utc)
            minuto_ref = ahora_ejecucion.minute
            hora_ref = ahora_ejecucion.hour
            
            for tf in TIMEFRAMES:
                # Solo escaneamos 1h y 4h si el minuto actual está cerca de su cierre
                if tf == "1h" and minuto_ref < 45: continue
                if tf == "4h" and (hora_ref % 4 != 3 or minuto_ref < 45): continue

                for cat, symbols in ASSETS.items():
                    for sym in symbols:
                        try:
                            # 1. Obtener Datos
                            if cat == "CRYPTO":
                                url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit=50"
                                r = requests.get(url, timeout=10).json()
                                df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                            else:
                                # Yahoo requiere intervalos específicos
                                y_tf = "60m" if tf == "1h" else "15m"
                                if tf == "4h": y_tf = "60m" # Yahoo no da 4h limpia, usamos 1h y remuestreamos si fuera necesario
                                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={y_tf}&range=5d"
                                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                                q = r["chart"]["result"][0]["indicators"]["quote"][0]
                                df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                            
                            df = df[["o","h","l","c"]].astype(float).dropna()
                            
                            # 2. Analizar
                            res_tec = analizar_mercado(df)
                            res_arm = detectar_patrones_armonicos(df)
                            
                            if res_tec or res_arm:
                                id_senal = f"{sym}_{tf}_{ahora_ejecucion.strftime('%H:%M')}"
                                if id_senal not in registro_velas:
                                    msg = f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                    msg += f"🕒 *TF:* {tf} (Pre-cierre)\n"
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    
                                    if res_arm:
                                        msg += f"📐 Patrón: *{res_arm['nombre']}*\n"
                                        msg += f"🧭 Acción: *{res_arm['tipo']}*\n"
                                    
                                    if res_tec:
                                        msg += f"📊 RSI: *{res_tec['tipo']}*\n"
                                        msg += f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                        msg += f"🛑 SL: `{res_tec['sl']:.5f}`\n"
                                        msg += f"🎯 TP1: `{res_tec['tp1']:.5f}`\n"
                                        msg += f"🎯 TP2: `{res_tec['tp2']:.5f}`\n"
                                    
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    msg += "⚠️ *Entrar antes del cierre de vela*"
                                    
                                    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                    registro_velas[id_senal] = True
                                    await asyncio.sleep(1) 
                                    
                        except Exception as e:
                            continue

            # Limpiar registros antiguos cada hora
            if len(registro_velas) > 100: registro_velas.clear()
            
            # Pausa de seguridad para no repetir el mismo bloque
            await asyncio.sleep(40) 

        except Exception as e:
            logger.error(f"⚠️ Error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
