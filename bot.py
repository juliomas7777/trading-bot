import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timezone
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN DE USUARIO
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY"]
}

# 5m para observar, las demás para asegurar tendencia
TIMEFRAMES = ["5m", "15m", "1h", "4h"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Memoria para no repetir señales en el mismo canal
estado_canales = {}

# ==========================================
# 📈 FUNCIONES TÉCNICAS Y DESCARGA
# ==========================================
def obtener_datos(sym, tf):
    try:
        sym_api = sym
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
        rango = "7d" if tf in ["5m", "15m"] else "30d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range={rango}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📊 ESTRATEGIA 1: CANALES + W/M + EXTENSIÓN FIBO
# ==========================================
def analizar_canal_y_wm(df, sym, tf):
    precios = df['c'].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = slope * x + intercept
    desviacion = np.std(precios - linea_central)
    sup, inf = linea_central[-1] + (desviacion * 2), linea_central[-1] - (desviacion * 2)
    
    precio_actual = precios[-1]
    id_canal = f"{sym}_{tf}_{round(slope, 7)}"

    # Reset por ruptura
    if precio_actual > sup * 1.002 or precio_actual < inf * 0.998:
        return None, None, 0

    # Lógica de Gatillo W/M (2ª Pata)
    recientes = precios[-20:]
    if slope > 0 and precio_actual <= inf * 1.0005: # Canal Alcista -> Buscar W
        mins = [i for i in range(1, len(recientes)-1) if recientes[i] < recientes[i-1] and recientes[i] < recientes[i+1]]
        if len(mins) >= 2:
            p1, p3 = recientes[mins[-2]], precio_actual
            p2 = np.max(recientes[mins[-2]:])
            tp1 = p3 + abs(p1-p2)
            return "CANAL_WM", {"p": precio_actual, "sl": p3 - abs(p1-p2)*0.4, "tp1": tp1, "id": id_canal}, 9
            
    elif slope < 0 and precio_actual >= sup * 0.9995: # Canal Bajista -> Buscar M
        maxs = [i for i in range(1, len(recientes)-1) if recientes[i] > recientes[i-1] and recientes[i] > recientes[i+1]]
        if len(maxs) >= 2:
            p1, p3 = recientes[maxs[-2]], precio_actual
            p2 = np.min(recientes[maxs[-2]:])
            tp1 = p3 - abs(p1-p2)
            return "CANAL_WM", {"p": precio_actual, "sl": p3 + abs(p1-p2)*0.4, "tp1": tp1, "id": id_canal}, 9
            
    return None, None, 0

# ==========================================
# 📐 ESTRATEGIA 2 Y 3: ARMONICOS Y SMC (RESUMIDO)
# ==========================================
def detectar_otros(df):
    # Aquí iría la lógica de SMC y Armónicos que ya tenemos
    # Devuelve el nombre de la estrategia y su puntuación (Score 4-6)
    return None, None, 0

# ==========================================
# 🧠 SELECTOR DE ALTA PROBABILIDAD (TU IMAGEN)
# ==========================================
def calcular_score_final(tf, puntos_base):
    bonos_tf = {"4h": 3, "1h": 2, "15m": 1, "5m": 0}
    return puntos_base + bonos_tf.get(tf, 0)

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 BOT MAESTRO INICIADO: CANALES + W/M + ARMONICOS + SMC")

    while True:
        try:
            for tf in TIMEFRAMES:
                for cat, symbols in ASSETS.items():
                    for s in symbols:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        # Ejecutar estrategias
                        est, info, pts = analizar_canal_y_wm(df, s, tf)
                        
                        if est:
                            score = calcular_score_final(tf, pts)
                            # Evitar repetición en el mismo canal
                            if estado_canales.get(f"{s}_{tf}") != info['id']:
                                emoji = "💎" if score >= 8 else "🚨"
                                msg = (
                                    f"{emoji} **ESTRATEGIA GANADORA ({score}/10)**\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"**ACTIVO:** `{s}` | **TF:** `{tf.upper()}`\n"
                                    f"**SISTEMA:** `{est}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🚀 **MARKET:** `{info['p']:.5f}`\n"
                                    f"🛑 **STOP LOSS:** `{info['sl']:.5f}`\n"
                                    f"🎯 **TP 1 (Nivel 1):** `{info['tp1']:.5f}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"💡 *Confirmación en 2ª pata del canal.*"
                                )
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                estado_canales[f"{s}_{tf}"] = info['id']
                
            await asyncio.sleep(60) # Escaneo cada minuto
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
