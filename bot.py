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

TIMEFRAMES = ["1h", "4h"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

estado_canales = {}

# ==========================================
# 📈 MOTOR DE DATOS
# ==========================================
def obtener_datos(sym, tf):
    try:
        sym_api = sym
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range=30d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📉 LAS 3 ESTRATEGIAS
# ==========================================
def analizar_canal_wm(df, sym, tf):
    if len(df) < 60: return None
    precios = df['c'].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = slope * x + intercept
    desviacion = np.std(precios - linea_central)
    sup, inf = linea_central[-1] + (desviacion * 2), linea_central[-1] - (desviacion * 2)
    precio_actual = precios[-1]
    id_canal = f"{sym}_{tf}_{round(slope, 7)}"
    
    if precio_actual > sup * 1.002 or precio_actual < inf * 0.998:
        if f"{sym}_{tf}" in estado_canales: del estado_canales[f"{sym}_{tf}"]
        return None

    recientes = precios[-20:]
    if slope > 0 and precio_actual <= inf * 1.0005: # COMPRA
        mins = [i for i in range(1, len(recientes)-1) if recientes[i] < recientes[i-1] and recientes[i] < recientes[i+1]]
        if len(mins) >= 2:
            p1, p3 = recientes[mins[-2]], precio_actual
            p2 = np.max(recientes[mins[-2]:])
            return {"nom": "CANAL ₩", "p": precio_actual, "sl": p3 - abs(p1-p2)*0.4, "tp1": p3 + abs(p1-p2), "id": id_canal, "side": "COMPRA"}
    
    elif slope < 0 and precio_actual >= sup * 0.9995: # VENTA
        maxs = [i for i in range(1, len(recientes)-1) if recientes[i] > recientes[i-1] and recientes[i] > recientes[i+1]]
        if len(maxs) >= 2:
            p1, p3 = recientes[maxs[-2]], precio_actual
            p2 = np.min(recientes[maxs[-2]:])
            return {"nom": "CANAL M", "p": precio_actual, "sl": p3 + abs(p1-p2)*0.4, "tp1": p3 - abs(p1-p2), "id": id_canal, "side": "VENTA"}
    return None

def analizar_armonicos(df):
    p = df['c'].values
    try:
        x, a, b, c, d = p[-40], p[-30], p[-20], p[-10], p[-1]
        ratio_ba = abs(a-b)/abs(x-a)
        if 0.5 < ratio_ba < 0.7:
            if d < c and d < a: return {"nom": "ARMÓNICO", "p": d, "sl": d*0.995, "tp1": c, "side": "COMPRA"}
            if d > c and d > a: return {"nom": "ARMÓNICO", "p": d, "sl": d*1.005, "tp1": c, "side": "VENTA"}
    except: pass
    return None

def analizar_smc(df):
    fvg_bull = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bear = df['h'].iloc[-1] < df['l'].iloc[-3]
    if fvg_bull: return {"nom": "SMC FVG", "p": df['c'].iloc[-1], "sl": df['l'].iloc[-3], "tp1": df['c'].iloc[-1]*1.01, "side": "COMPRA"}
    if fvg_bear: return {"nom": "SMC FVG", "p": df['c'].iloc[-1], "sl": df['h'].iloc[-3], "tp1": df['c'].iloc[-1]*0.99, "side": "VENTA"}
    return None

# ==========================================
# 🧠 MOTOR DE CONFLUENCIA OBLIGATORIA
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("📡 BOT DE CONFLUENCIA ACTIVO (Min. 2 Estrategias Coincidentes)")

    while True:
        try:
            for tf in TIMEFRAMES:
                for cat, symbols in ASSETS.items():
                    for s in symbols:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        # Ejecutar los 3 análisis
                        c1 = analizar_canal_wm(df, s, tf)
                        c2 = analizar_armonicos(df)
                        c3 = analizar_smc(df)

                        analisis = [x for x in [c1, c2, c3] if x is not None]
                        
                        # FILTRO 1: ¿Hay al menos 2 estrategias activas?
                        if len(analisis) >= 2:
                            lados = [x['side'] for x in analisis]
                            
                            # FILTRO 2: ¿Todas las señales activas van hacia el mismo lado?
                            if all(x == lados[0] for x in lados):
                                mejor = analisis[0] # Usamos los datos de la primera (Canal suele mandar)
                                
                                id_sig = mejor.get('id', f"{s}_{tf}_{mejor['nom']}")
                                if estado_canales.get(f"{s}_{tf}") != id_sig:
                                    emoji = "🟢" if mejor['side'] == "COMPRA" else "🔴"
                                    nombres = " + ".join([x['nom'] for x in analisis])
                                    
                                    msg = (
                                        f"{emoji} **CONFLUENCIA: {lados[0]}** {emoji}\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"**ESTRATEGIAS:** `{nombres}`\n"
                                        f"**ACTIVO:** `{s}` | **TF:** `{tf.upper()}`\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🚀 **ENTRADA MARKET:** `{mejor['p']:.5f}`\n"
                                        f"🛑 **STOP LOSS:** `{mejor['sl']:.5f}`\n"
                                        f"🎯 **TP 1:** `{mejor['tp1']:.5f}`\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🔥 *¡ALERTA MÁXIMA! {len(analisis)} sistemas coinciden.*"
                                    )
                                    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                    estado_canales[f"{s}_{tf}"] = id_sig
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
