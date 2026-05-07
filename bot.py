import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN: CIERRE DE VELA + RR 1.2
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDJPY"]
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]
RR_MINIMO = 1.2 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
estado_semanal = {}

# ==========================================
# 📈 MOTOR DE DATOS (Detecta Cierre)
# ==========================================
def obtener_datos(sym, tf):
    try:
        sym_api = sym
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range=30d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
        
        # Filtro de Cierre: En 1h y 4h, ignoramos la última vela si aún no ha cerrado según el tiempo de la API
        if tf in ["1h", "4h"]:
            return df.iloc[:-1] # Trabajamos con la vela cerrada anterior
        return df
    except: return None

# ==========================================
# 📉 ANALIZADOR DE CONFLUENCIA
# ==========================================
def analizar_confluencia(df, sym, tf):
    # Usamos el último precio de la vela cerrada (o actual en 5m/15m)
    precios = df['c'].values[-60:]
    precio_referencia = precios[-1] 
    
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea_central = (slope * x + intercept)[-1]
    desv = np.std(precios - (slope * x + intercept))
    
    # ESTRATEGIA CANAL
    canal = None
    sup, inf = linea_central + (desv * 2.1), linea_central - (desv * 2.1)
    if slope > 0 and precio_referencia >= sup * 0.998: canal = "VENTA"
    if slope < 0 and precio_referencia <= inf * 1.002: canal = "COMPRA"
    
    # ESTRATEGIA ARMONICO
    armonico = "COMPRA" if precio_referencia < df['c'].iloc[-20] else "VENTA" if precio_referencia > df['c'].iloc[-20] else None
    
    # ESTRATEGIA SMC
    smc = "COMPRA" if df['l'].iloc[-1] > df['h'].iloc[-3] else "VENTA" if df['h'].iloc[-1] < df['l'].iloc[-3] else None
    
    secciones = [x for x in [canal, armonico, smc] if x is not None]
    
    if len(secciones) >= 2 and all(s == secciones[0] for s in secciones):
        dir = secciones[0]
        sl = precio_referencia - (desv * 1.5) if dir == "COMPRA" else precio_referencia + (desv * 1.5)
        tp = linea_central
        
        riesgo = abs(precio_referencia - sl)
        beneficio = abs(tp - precio_referencia)
        
        if riesgo > 0 and (beneficio / riesgo) >= RR_MINIMO:
            return dir, precio_referencia, sl, tp, round(beneficio/riesgo, 2), len(secciones)
    return None, None, None, None, None, 0

# ==========================================
# 🧠 LÓGICA DE ENVÍO
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info(f"📡 BOT CIERRE DE VELA: 1H/4H Filtrado | Activo en **Negrita**")

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
                    
                    if len(hits) >= 2 and all(h['dir'] == hits[0]['dir'] for h in hits):
                        h = hits[0]
                        # ID único para no repetir señal de la misma vela
                        id_a = f"{s}_{h['dir']}_{h['px']}" 
                        
                        if estado_semanal.get(s) != id_a:
                            color = "🟢" if h['dir'] == "COMPRA" else "🔴"
                            tfs_label = ", ".join([x['tf'].upper() for x in hits])
                            tipo_orden = "MERCADO (Cierre Confirmado)" if "1H" in tfs_label or "4H" in tfs_label else "MERCADO (Inmediata)"
                            
                            msg = (
                                f"{color} **{h['dir']} - {h['conf']}/3 SISTEMAS** {color}\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"**ACTIVO:** **{s}**\n"
                                f"**TFs:** `{tfs_label}`\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"🚀 **ENTRADA:** `{h['px']:.5f}`\n"
                                f"🛑 **STOP LOSS:** `{h['sl']:.5f}`\n"
                                f"🎯 **TAKE PROFIT:** `{h['tp']:.5f}`\n"
                                f"━━━━━━━━━━━━━━━\n"
                                f"📝 **TIPO:** `{tipo_orden}`\n"
                                f"⚖️ **RATIO RR:** `{h['rr']}`"
                            )
                            await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                            estado_semanal[s] = id_a
            await asyncio.sleep(60)
        except Exception: await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
