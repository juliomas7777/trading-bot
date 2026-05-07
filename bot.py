import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN FINAL: ACTIVO EN NEGRITA
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY"]
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]
RR_MINIMO = 1.5  

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
estado_semanal = {}

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
        return pd.DataFrame({"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📉 ANALIZADOR DE CONFLUENCIA
# ==========================================
def analizar_confluencia(df, sym, tf):
    precios = df['c'].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = (slope * x + intercept)[-1]
    desv = np.std(precios - (slope * x + intercept))
    precio_actual = precios[-1]
    
    # 1. CANAL 
    canal = None
    sup, inf = linea_central + (desv * 2.1), linea_central - (desv * 2.1)
    if slope > 0 and precio_actual >= sup * 0.998: canal = "VENTA"
    if slope < 0 and precio_actual <= inf * 1.002: canal = "COMPRA"
    
    # 2. ARMONICO
    armonico = "COMPRA" if precio_actual < df['c'].iloc[-20] and precio_actual < df['c'].iloc[-40] else "VENTA" if precio_actual > df['c'].iloc[-20] else None
    
    # 3. SMC
    smc = "COMPRA" if df['l'].iloc[-1] > df['h'].iloc[-3] else "VENTA" if df['h'].iloc[-1] < df['l'].iloc[-3] else None
    
    secciones = [x for x in [canal, armonico, smc] if x is not None]
    if len(secciones) >= 2:
        if all(s == secciones[0] for s in secciones):
            dir = secciones[0]
            # Riesgo/Beneficio
            sl = precio_actual - (desv * 1.6) if dir == "COMPRA" else precio_actual + (desv * 1.6)
            tp = linea_central
            riesgo = abs(precio_actual - sl)
            beneficio = abs(tp - precio_actual)
            
            if riesgo > 0 and (beneficio / riesgo) >= RR_MINIMO:
                return dir, precio_actual, sl, tp, round(beneficio/riesgo, 2), len(secciones)
    return None, None, None, None, None, 0

# ==========================================
# 🧠 LÓGICA DE MENSAJE UNIFICADO
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info(f"📡 BOT ACTIVO: 2/3 o 3/3 | RR {RR_MINIMO} | Multi-TF | Negrita")

    while True:
        try:
            for cat, symbols in ASSETS.items():
                for s in symbols:
                    hits = []
                    for tf in TIMEFRAMES:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        res = analizar_confluencia(df, s, tf)
                        if res[0]: 
                            hits.append({"tf": tf, "dir": res[0], "px": res[1], "sl": res[2], "tp": res[3], "rr": res[4], "conf": res[5]})
                    
                    if len(hits) >= 2:
                        if all(h['dir'] == hits[0]['dir'] for h in hits):
                            h = hits[0]
                            id_a = f"{s}_{h['dir']}_{len(hits)}TF"
                            
                            if estado_semanal.get(s) != id_alerta:
                                color = "🟢" if h['dir'] == "COMPRA" else "🔴"
                                tfs_label = ", ".join([x['tf'].upper() for x in hits])
                                
                                # MENSAJE CON ACTIVO EN NEGRITA
                                msg = (
                                    f"{color} **{h['dir']} - {h['conf']}/3 ESTRATEGIAS** {color}\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"**ACTIVO:** **{s}**\n"
                                    f"**TIMEFRAMES:** `{tfs_label}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🚀 **ENTRADA:** `{h['px']:.5f}`\n"
                                    f"🛑 **STOP LOSS:** `{h['sl']:.5f}`\n"
                                    f"🎯 **TAKE PROFIT:** `{h['tp']:.5f}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"⚖️ **RATIO RR:** `{h['rr']}`\n"
                                    f"✅ *Señal validada en {len(hits)} marcos.*"
                                )
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                estado_semanal[s] = id_a
            await asyncio.sleep(60)
        except Exception: await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
