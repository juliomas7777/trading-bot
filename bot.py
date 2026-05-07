import logging
import asyncio
import pandas as pd
import requests
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN ULTRA-FILTRADA
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

estado_semanal = {}

# ==========================================
# 📈 MOTOR DE DATOS Y ESTRATEGIAS
# ==========================================
def obtener_datos(sym, tf):
    try:
        sym_api = sym
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range=30d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

def analizar_todo(df, sym, tf):
    # 1. CANAL
    precios = df['c'].values[-60:]; x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    desv = np.std(precios - (slope * x + intercept))
    sup, inf = (slope * x + intercept)[-1] + (desv * 2), (slope * x + intercept)[-1] - (desv * 2)
    
    canal = None
    if slope > 0 and precios[-1] >= sup * 0.998: canal = "VENTA"
    if slope < 0 and precios[-1] <= inf * 1.002: canal = "COMPRA"
    
    # 2. ARMONICO
    armonico = None
    p = df['c'].values; x_a, a, b, c, d = p[-40], p[-30], p[-20], p[-10], p[-1]
    if d < c and d < a: armonico = "COMPRA"
    if d > c and d > a: armonico = "VENTA"
    
    # 3. SMC
    smc = None
    if df['l'].iloc[-1] > df['h'].iloc[-3]: smc = "COMPRA"
    if df['h'].iloc[-1] < df['l'].iloc[-3]: smc = "VENTA"
    
    # ¿COINCIDEN LAS 3?
    if canal and armonico and smc and (canal == armonico == smc):
        return canal, precios[-1]
    return None, None

# ==========================================
# 🧠 LÓGICA MULTI-TIMEFRAME (2 TF MÍNIMO)
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("📡 MODO ULTRA-FILTRADO: 3/3 Estrategias en 2+ Timeframes")

    while True:
        try:
            for cat, symbols in ASSETS.items():
                for s in symbols:
                    coincidencias_tf = [] # Guardará (tf, direccion, precio)
                    
                    for tf in TIMEFRAMES:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        dir, px = analizar_todo(df, s, tf)
                        if dir:
                            coincidencias_tf.append({"tf": tf, "dir": dir, "px": px})
                    
                    # SI HAY 2 O MÁS TIMEFRAMES CON LAS 3 ESTRATEGIAS COINCIDIENDO
                    if len(coincidencias_tf) >= 2:
                        direcciones = [x['dir'] for x in coincidencias_tf]
                        # Validar que todos los TFs apunten al mismo lado
                        if all(d == direcciones[0] for d in direcciones):
                            dir_final = direcciones[0]
                            tfs_texto = ", ".join([x['tf'].upper() for x in coincidencias_tf])
                            
                            id_alerta = f"{s}_{dir_final}_{tfs_texto}"
                            if estado_semanal.get(s) != id_alerta:
                                color = "🟢" if dir_final == "COMPRA" else "🔴"
                                msg = (
                                    f"{color} **{dir_final} CONFIRMADA** {color}\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"**ACTIVO:** `{s}`\n"
                                    f"**TIMEFRAMES:** `{tfs_texto}`\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🔥 **CONFLUENCIA TOTAL (3/3)**\n"
                                    f"✅ **DETECTADA EN {len(coincidencias_tf)} MARCOS DE TIEMPO**\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"📊 *Señal de altísima probabilidad.*"
                                )
                                await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                estado_semanal[s] = id_alerta
            await asyncio.sleep(60)
        except Exception: await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
