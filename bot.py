import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN FINAL UNIFICADA
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY"]
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]

logging.basicConfig(level=logging.INFO)
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
        rango = "2d" if tf in ["5m", "15m"] else "30d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range={rango}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📉 ESTRATEGIAS (Canal, Armónico, SMC)
# ==========================================
def analizar_canal_wm(df, sym, tf):
    if len(df) < 60: return None
    precios = df['c'].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = slope * x + intercept
    desviacion = np.std(precios - linea_central)
    sup, inf = linea_central[-1] + (desviacion * 2), linea_central[-1] - (desviacion * 2)
    
    toques = np.sum(df['h'].values[-60:] >= (slope * x + intercept + desviacion * 1.8)) + \
             np.sum(df['l'].values[-60:] <= (slope * x + intercept - desviacion * 1.8))
    if toques < 3: return None

    # Dirección Estricta: Venta en Alcista / Compra en Bajista
    if slope > 0 and precios[-1] >= sup * 0.998:
        return {"nom": "CANAL", "p": precios[-1], "sl": precios[-1]*1.004, "tp": linea_central[-1], "side": "VENTA", "id": f"{sym}_{tf}_{round(slope,6)}", "pts": 10}
    if slope < 0 and precios[-1] <= inf * 1.002:
        return {"nom": "CANAL", "p": precios[-1], "sl": precios[-1]*0.996, "tp": linea_central[-1], "side": "COMPRA", "id": f"{sym}_{tf}_{round(slope,6)}", "pts": 10}
    return None

def analizar_armonicos(df):
    p = df['c'].values
    try:
        x, a, b, c, d = p[-40], p[-30], p[-20], p[-10], p[-1]
        if d < c and d < a: return {"nom": "ARMÓNICO", "p": d, "sl": d*0.995, "tp": c, "side": "COMPRA", "pts": 8}
        if d > c and d > a: return {"nom": "ARMÓNICO", "p": d, "sl": d*1.005, "tp": c, "side": "VENTA", "pts": 8}
    except: pass
    return None

def analizar_smc(df):
    fvg_bull = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bear = df['h'].iloc[-1] < df['l'].iloc[-3]
    if fvg_bull: return {"nom": "SMC", "p": df['c'].iloc[-1], "sl": df['l'].iloc[-3], "tp": df['c'].iloc[-1]*1.01, "side": "COMPRA", "pts": 6}
    if fvg_bear: return {"nom": "SMC", "p": df['c'].iloc[-1], "sl": df['h'].iloc[-3], "tp": df['c'].iloc[-1]*0.99, "side": "VENTA", "pts": 6}
    return None

# ==========================================
# 🧠 MOTOR DE MENSAJE ÚNICO CON DIRECCIÓN
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("📡 BOT UNIFICADO: Confluencia con Dirección (Compra/Venta)")

    while True:
        try:
            for tf in TIMEFRAMES:
                for cat, symbols in ASSETS.items():
                    for s in symbols:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        estrat_activas = [analizar_canal_wm(df, s, tf), analizar_armonicos(df), analizar_smc(df)]
                        analisis = [x for x in estrat_activas if x is not None]
                        
                        if len(analisis) >= 2:
                            lados = [x['side'] for x in analisis]
                            if all(x == lados[0] for x in lados):
                                # Elegimos la mejor operativa para los datos
                                analisis.sort(key=lambda x: x['pts'], reverse=True)
                                mejor = analisis[0]
                                num = len(analisis)
                                id_sig = mejor.get('id', f"{s}_{tf}_{mejor['nom']}")
                                
                                if estado_canales.get(f"{s}_{tf}") != id_sig:
                                    color = "🟢" if mejor['side'] == "COMPRA" else "🔴"
                                    icono = "💎" if num == 3 else color
                                    nombres = " + ".join([x['nom'] for x in analisis])
                                    
                                    # MENSAJE ÚNICO CON DIRECCIÓN CLARA
                                    msg = (
                                        f"{icono} **{mejor['side']} - {num}/3 SISTEMAS** {icono}\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"**ACTIVO:** `{s}` | **TF:** `{tf.upper()}`\n"
                                        f"**SISTEMAS:** `{nombres}`\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"🚀 **ENTRADA:** `{mejor['p']:.5f}`\n"
                                        f"🛑 **STOP LOSS:** `{mejor['sl']:.5f}`\n"
                                        f"🎯 **TAKE PROFIT:** `{mejor['tp']:.5f}`\n"
                                        f"━━━━━━━━━━━━━━━\n"
                                        f"{'💎 ALERTA DE ALTA PRECISIÓN (3/3)' if num == 3 else '✅ Confluencia detectada (2/3)'}"
                                    )
                                    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                    estado_canales[f"{s}_{tf}"] = id_sig
            await asyncio.sleep(60)
        except Exception: await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
