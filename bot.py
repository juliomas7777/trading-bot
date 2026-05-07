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

# Eliminado 5m para mayor seguridad y menos ruido
TIMEFRAMES = ["15m", "1h", "4h"]

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
        rango = "7d" if tf == "15m" else "30d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range={rango}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📉 ESTRATEGIA 1: CANAL DE REGRESIÓN + ₩/M
# ==========================================
def analizar_canal_wm(df, sym, tf):
    if len(df) < 60: return None, None, 0
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
        if f"{sym}_{tf}" in estado_canales: del estado_canales[f"{sym}_{tf}"]
        return None, None, 0

    recientes = precios[-20:]
    if slope > 0 and precio_actual <= inf * 1.0005: # COMPRA
        mins = [i for i in range(1, len(recientes)-1) if recientes[i] < recientes[i-1] and recientes[i] < recientes[i+1]]
        if len(mins) >= 2:
            p1, p3 = recientes[mins[-2]], precio_actual
            p2 = np.max(recientes[mins[-2]:])
            tp1 = p3 + abs(p1 - p2)
            return "CANAL ₩ (COMPRA)", {"p": precio_actual, "sl": p3 - abs(p1-p2)*0.4, "tp1": tp1, "id": id_canal, "side": "BUY"}, 8

    elif slope < 0 and precio_actual >= sup * 0.9995: # VENTA
        maxs = [i for i in range(1, len(recientes)-1) if recientes[i] > recientes[i-1] and recientes[i] > recientes[i+1]]
        if len(maxs) >= 2:
            p1, p3 = recientes[maxs[-2]], precio_actual
            p2 = np.min(recientes[maxs[-2]:])
            tp1 = p3 - abs(p1 - p2)
            return "CANAL M (VENTA)", {"p": precio_actual, "sl": p3 + abs(p1-p2)*0.4, "tp1": tp1, "id": id_canal, "side": "SELL"}, 8
            
    return None, None, 0

# ==========================================
# 📐 ESTRATEGIA 2: ARMÓNICOS
# ==========================================
def analizar_armonicos(df):
    if len(df) < 40: return None, None, 0
    p = df['c'].values
    try:
        x, a, b, c, d = p[-40], p[-30], p[-20], p[-10], p[-1]
        ratio_ba = abs(a-b)/abs(x-a)
        if 0.5 < ratio_ba < 0.7:
            if d < c and d < a: return "ARMÓNICO (COMPRA)", {"p": d, "sl": d*0.995, "tp1": c, "side": "BUY"}, 6
            if d > c and d > a: return "ARMÓNICO (VENTA)", {"p": d, "sl": d*1.005, "tp1": c, "side": "SELL"}, 6
    except: pass
    return None, None, 0

# ==========================================
# ⚡ ESTRATEGIA 3: SMC (FVG)
# ==========================================
def analizar_smc(df):
    if len(df) < 5: return None, None, 0
    fvg_bull = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bear = df['h'].iloc[-1] < df['l'].iloc[-3]
    if fvg_bull: return "SMC FVG (COMPRA)", {"p": df['c'].iloc[-1], "sl": df['l'].iloc[-3], "tp1": df['c'].iloc[-1]*1.01, "side": "BUY"}, 4
    if fvg_bear: return "SMC FVG (VENTA)", {"p": df['c'].iloc[-1], "sl": df['h'].iloc[-3], "tp1": df['c'].iloc[-1]*0.99, "side": "SELL"}, 4
    return None, None, 0

# ==========================================
# 🧠 LÓGICA DE ENVÍO Y PRIORIDAD
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("📡 BOT ACTUALIZADO: Sin 5m. Operando 15m, 1h, 4h.")

    while True:
        try:
            for tf in TIMEFRAMES:
                for cat, symbols in ASSETS.items():
                    for s in symbols:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        res = []
                        # Escaneo de estrategias
                        e1_n, e1_i, e1_p = analizar_canal_wm(df, s, tf)
                        if e1_n: res.append({'nom': e1_n, 'info': e1_i, 'pts': e1_p + (2 if tf=="4h" else (1 if tf=="1h" else 0))})
                        
                        e2_n, e2_i, e2_p = analizar_armonicos(df)
                        if e2_n: res.append({'nom': e2_n, 'info': e2_i, 'pts': e2_p + (2 if tf=="4h" else (1 if tf=="1h" else 0))})
                        
                        e3_n, e3_i, e3_p = analizar_smc(df)
                        if e3_n: res.append({'nom': e3_n, 'info': e3_i, 'pts': e3_p + (2 if tf=="4h" else (1 if tf=="1h" else 0))})

                        if not res: continue
                        res.sort(key=lambda x: x['pts'], reverse=True)
                        mejor = res[0]

                        id_sig = mejor['info'].get('id', f"{s}_{tf}_{mejor['nom']}")
                        if estado_canales.get(f"{s}_{tf}") != id_sig:
                            color = "🟢" if mejor['info']['side'] == "BUY" else "🔴"
                            msg = (
                                f"{color} **{mejor['nom']}** {color}\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"**SCORE:** `{mejor['pts']}/10` | **TF:** `{tf.upper()}`\n"
                                f"**ACTIVO:** `{s}`\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"🚀 **MARKET:** `{mejor['info']['p']:.5f}`\n"
                                f"🛑 **STOP LOSS:** `{mejor['info']['sl']:.5f}`\n"
                                f"🎯 **TP 1:** `{mejor['info']['tp1']:.5f}`\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"📊 *Temporalidad confirmada: {tf.upper()}*"
                            )
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            estado_canales[f"{s}_{tf}"] = id_sig
            await asyncio.sleep(60) # Revisión cada minuto
        except Exception: await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
