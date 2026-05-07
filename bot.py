import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN PRO: RR MÍNIMO 1.5
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY"]
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]
RR_MINIMO = 1.5  # Arriesgas 1 para ganar 1.5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
estado_semanal = {}

# ==========================================
# 📉 MOTOR DE ANÁLISIS CON CÁLCULO DE NIVELES
# ==========================================
def analizar_todo(df, sym, tf):
    precios = df['c'].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = (slope * x + intercept)[-1]
    desv = np.std(precios - (slope * x + intercept))
    
    precio_actual = precios[-1]
    sup, inf = linea_central + (desv * 2.1), linea_central - (desv * 2.1)
    
    # 1. CANAL
    canal = None
    if slope > 0 and precio_actual >= sup * 0.998: canal = "VENTA"
    if slope < 0 and precio_actual <= inf * 1.002: canal = "COMPRA"
    
    # 2. ARMONICO & 3. SMC (Simplificado para validación de dirección)
    p = df['c'].values
    armonico = "COMPRA" if p[-1] < p[-10] and p[-1] < p[-30] else "VENTA"
    smc = "COMPRA" if df['l'].iloc[-1] > df['h'].iloc[-3] else "VENTA" if df['h'].iloc[-1] < df['l'].iloc[-3] else None
    
    if canal and armonico and smc and (canal == armonico == smc):
        # --- CÁLCULO DE RATIO RR ---
        if canal == "COMPRA":
            sl = precio_actual - (desv * 1.5) # SL por debajo del mínimo del canal
            tp = linea_central                # TP en la media del canal
        else:
            sl = precio_actual + (desv * 1.5) # SL por encima del máximo del canal
            tp = linea_central                # TP en la media del canal
            
        riesgo = abs(precio_actual - sl)
        beneficio = abs(tp - precio_actual)
        
        if riesgo > 0 and (beneficio / riesgo) >= RR_MINIMO:
            return canal, precio_actual, sl, tp, round(beneficio/riesgo, 2)
            
    return None, None, None, None, None

# ==========================================
# 🧠 LÓGICA DE ENVÍO CON FILTRO RR
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info(f"📡 MODO RENTABLE: RR Mínimo {RR_MINIMO} | 2+ TFs")

    while True:
        try:
            for cat, symbols in ASSETS.items():
                for s in symbols:
                    coincidencias = []
                    for tf in TIMEFRAMES:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        dir, px, sl, tp, rr = analizar_todo(df, s, tf)
                        if dir: coincidencias.append({"tf": tf, "dir": dir, "px": px, "sl": sl, "tp": tp, "rr": rr})
                    
                    if len(coincidencias) >= 2:
                        # Validar misma dirección en los TFs encontrados
                        if all(x['dir'] == coincidencias[0]['dir'] for x in coincidencias):
                            c = coincidencias[0] # Usamos los datos del primer TF que activó
                            id_alerta = f"{s}_{c['dir']}_{len(coincidencias)}TF"
                            
                            if estado_semanal.get(s) != id_alerta:
                                color = "🟢" if c['dir'] == "COMPRA" else "🔴"
                                msg = (
                                    f"{color} **{c['dir']} (RR {c['rr']})** {color}\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"**ACTIVO:** `{s}` | **TFs:** `{', '.join([x['tf'].upper() for x in coincidencias])}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🚀 **ENTRADA:** `{c['px']:.5f}`\n"
                                    f"🛑 **STOP LOSS:** `{c['sl']:.5f}`\n"
                                    f"🎯 **TAKE PROFIT:** `{c['tp']:.5f}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"💰 *Ganas {c['rr']} veces lo que arriesgas.*"
                                )
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                estado_semanal[s] = id_alerta
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error: {e}"); await asyncio.sleep(20)

# (La función obtener_datos se mantiene igual que antes)
