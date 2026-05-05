import logging
import asyncio
import pandas as pd
import requests
import numpy as np
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
#   📐 ESTRATEGIA DE PATRONES ARMÓNICOS
# ═══════════════════════════════════════════════════════
def detectar_patrones_armonicos(df):
    \"\"\"
    Detecta patrones armónicos básicos (Gartley, Bat, Butterfly, Crab)
    basado en los últimos 5 puntos de giro (simulados por máximos/mínimos).
    \"\"\"
    # Necesitamos al menos 50 velas para buscar pivots
    if len(df) < 50:
        return None
        
    prices = df['c'].values
    
    # Simulación de detección de pivots (X, A, B, C, D)
    # En una implementación real se usaría un algoritmo de ZigZag.
    # Aquí buscamos retrocesos recientes.
    
    # Tomamos los últimos puntos significativos
    # X=df-4, A=df-3, B=df-2, C=df-1, D=df (actual)
    try:
        X, A, B, C, D = prices[-5], prices[-4], prices[-3], prices[-2], prices[-1]
        
        XA = A - X
        AB = B - A
        BC = C - B
        CD = D - C
        
        if XA == 0: return None
        
        # Ratios
        ret_AB = abs(AB / XA)
        ret_BC = abs(BC / AB)
        ret_CD = abs(CD / BC)
        ret_AD = abs((D - X) / XA) # D relative to XA
        
        err = 0.05 # 5% de tolerancia
        
        patterns = [
            {"name": "Gartley", "B": 0.618, "D": 0.786},
            {"name": "Bat", "B": 0.382, "D": 0.886},
            {"name": "Butterfly", "B": 0.786, "D": 1.27},
            {"name": "Crab", "B": 0.382, "D": 1.618}
        ]
        
        for p in patterns:
            if abs(ret_AB - p['B']) < err and abs(ret_AD - p['D']) < err:
                # Determinar si es Bullish o Bearish
                # Bullish: X < A y D < C (M en Gartley/Bat)
                # Bearish: X > A y D > C (W en Gartley/Bat)
                if X < A: # Estructura alcista (Bullish Pattern -> Compra)
                    return {"nombre": p['name'], "tipo": "ALZA 🟢", "emoji": "📈"}
                else: # Estructura bajista (Bearish Pattern -> Venta)
                    return {"nombre": p['name'], "tipo": "BAJA 🔴", "emoji": "📉"}
                    
    except Exception:
        return None
        
    return None
# ═══════════════════════════════════════════════════════
#   📡 MOTOR DE TIEMPO REAL
# ═══════════════════════════════════════════════════════
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("⏳ Julio v12.0 - Iniciando Escáner de 15 Minutos + Armónicos...")
    while True:
        try:
            # Sincronización a velas de 15 minutos (ya no de 5)
            ahora = datetime.now(timezone.utc)
            minutos_restantes = 14 - (ahora.minute % 15)
            segundos_restantes = 60 - ahora.second + 5 # 5 segundos de margen para que la vela cierre
            total_espera = (minutos_restantes * 60) + segundos_restantes
            
            if total_espera <= 0: total_espera = 900 # Si algo falla, esperar 15 min
            logger.info(f"💤 Próximo rastreo en {total_espera}s (Sincronizado a vela de 15m)")
            await asyncio.sleep(total_espera)
            # --- INICIO DEL ESCANEO ---
            hora_senal = datetime.now(timezone.utc).strftime("%H:%M")
            
            for cat, symbols in ASSETS.items():
                for sym in symbols:
                    try:
                        # Descarga de datos
                        if cat == "CRYPTO":
                            r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=15m&limit=100", timeout=10).json()
                            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                        else:
                            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=5d", headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                            q = r["chart"]["result"][0]["indicators"]["quote"][0]
                            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                        
                        df = df[["o","h","l","c"]].astype(float).dropna()
                        
                        # Análisis 1: RSI + ATR
                        res_tec = analizar_mercado(df)
                        # Análisis 2: Patrones Armónicos
                        res_arm = detectar_patrones_armonicos(df)
                        
                        id_senal = f"{sym}_{hora_senal}"
                        
                        if (res_tec or res_arm) and id_senal not in registro_velas:
                            msg = f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                            msg += "━━━━━━━━━━━━━━━━━━\n"
                            
                            if res_arm:
                                msg += f"📐 Patrón: *{res_arm['nombre']}*\n"
                                msg += f"🧭 Tendencia: *{res_arm['tipo']}*\n"
                            
                            if res_tec:
                                msg += f"📊 Estrategia RSI: *{res_tec['tipo']}*\n"
                                msg += f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                msg += f"🛑 SL: `{res_tec['sl']:.5f}`\n"
                                msg += f"🎯 TP1: `{res_tec['tp1']:.5f}`\n"
                                msg += f"🎯 TP2: `{res_tec['tp2']:.5f}`\n"
                            else:
                                # Si solo hay armónico, dar precio de entrada actual
                                msg += f"💰 Precio Actual: `{df['c'].iloc[-1]:.5f}`\n"
                                
                            msg += "━━━━━━━━━━━━━━━━━━\n"
                            msg += f"⏰ Hora: `{hora_senal} UTC`"
                            
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            registro_velas[id_senal] = True
                            logger.info(f"✅ Señal enviada: {sym}")
                            await asyncio.sleep(2)
                                
                    except Exception as e:
                        logger.error(f"Error procesando {sym}: {e}")
                        continue
            
            # Limpiar memoria
            if len(registro_velas) > 100: registro_velas.clear()
            
            logger.info("🔚 Ciclo de escaneo completado.")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"⚠️ Error general: {e}")
            await asyncio.sleep(60)
if __name__ == "__main__":
    asyncio.run(main())
