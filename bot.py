import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone, time
import numpy as np
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN DE USUARIO
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD"],
    "FOREX": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "USDMXN"]
}

TIMEFRAMES = ["4h", "1h", "15m", "5m"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FUNCIONES TÉCNICAS ---
def calcular_rsi(df, periodo=14):
    delta = df['c'].diff()
    ganancia = (delta.where(delta > 0, 0)).rolling(window=periodo).mean()
    pérdida = (-delta.where(delta < 0, 0)).rolling(window=periodo).mean()
    rs = ganancia / pérdida
    return 100 - (100 / (1 + rs))

def obtener_datos(sym, tf):
    try:
        sym_api = sym
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
        # Ajustamos el rango según la temporalidad para no saturar
        rango = "15d" if tf in ["4h", "1h"] else "2d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range={rango}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 📉 LAS 3 ESTRATEGIAS REFINADAS
# ==========================================

def detectar_fvg_smc(df):
    if df is None or len(df) < 5: return None
    fvg_alcista = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bajista = df['h'].iloc[-1] < df['l'].iloc[-3]
    vol_ok = df['v'].iloc[-1] > df['v'].rolling(10).mean().iloc[-1]
    if fvg_alcista and vol_ok: return "BUY"
    if fvg_bajista and vol_ok: return "SELL"
    return None

def detectar_patron_w_m_pro(df):
    if df is None or len(df) < 35: return None, None
    df['rsi'] = calcular_rsi(df)
    precios, rsi_vals = df['c'].values, df['rsi'].values
    
    # Lógica W con Divergencia
    if precios[-1] > precios[-2]:
        l1_idx = np.argmin(precios[-30:-12]) + (len(precios)-30)
        l2_idx = np.argmin(precios[-10:]) + (len(precios)-10)
        if precios[l2_idx] <= precios[l1_idx] * 1.002 and rsi_vals[l2_idx] > rsi_vals[l1_idx]:
            return "W", {"entry": precios[-1], "sl": precios[l2_idx]*0.998, "base": precios[l1_idx]}
            
    # Lógica M con Divergencia
    if precios[-1] < precios[-2]:
        t1_idx = np.argmax(precios[-30:-12]) + (len(precios)-30)
        t2_idx = np.argmax(precios[-10:]) + (len(precios)-10)
        if precios[t2_idx] >= precios[t1_idx] * 0.998 and rsi_vals[t2_idx] < rsi_vals[t1_idx]:
            return "M", {"entry": precios[-1], "sl": precios[t2_idx]*1.002, "base": precios[t1_idx]}
    return None, None

def detectar_armonico_refinado(df):
    if df is None or len(df) < 40: return None, None
    p = df['c'].values
    # X=0, A=10, B=20, C=30, D=último (Simplificado para estabilidad)
    try:
        x, a, b, c, d = p[-40], p[-30], p[-20], p[-10], p[-1]
        ratio_ba = abs(a-b)/abs(x-a)
        ratio_cd = abs(c-d)/abs(b-c)
        # Filtro Gartley/Bat (0.618 / 1.27)
        if 0.5 < ratio_ba < 0.7 and 1.1 < ratio_cd < 1.6:
            if d < c and d < a: return "ARMÓNICO BULL", {"entry": d, "sl": d*0.996}
            if d > c and d > a: return "ARMÓNICO BEAR", {"entry": d, "sl": d*1.004}
    except: pass
    return None, None

# ==========================================
# 📡 MENSAJERÍA MULTI-TEMPORALIDAD
# ==========================================

async def enviar_señal_final(bot, sym, tf, titulo, info):
    entry = info['entry']
    sl = info['sl']
    base = info.get('base', entry)
    dist = abs(entry - base)
    
    # Nivel 50% para W/M
    limit_50 = base + (dist * 0.5) if titulo == "W" else base - (dist * 0.5)
    
    emoji = "🟢 COMPRA" if "W" in titulo or "BULL" in titulo or info.get('side')=="BUY" else "🔴 VENTA"
    
    msg = (
        f"🚨 **PATRÓN: {titulo}** 🚨\n"
        f"**ACTIVO:** `{sym}` | **TF:** `{tf.upper()}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**ACCIÓN:** {emoji}\n\n"
        f"⚡ **MARKET:** `{entry:.5f}`\n"
        f"🎯 **LIMIT (50%):** `{limit_50:.5f}`\n"
        f"🛑 **STOP LOSS:** `{sl:.5f}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ *Señal validada en {tf} con confluencia.*"
    )
    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")

# ==========================================
# 🚀 MOTOR DE ESCANEO TOTAL
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🔥 SCANNER TOTAL 4H-1H-15M-5M ACTIVADO")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            # Latido cada 15 min para no saturar logs
            if ahora.minute % 15 == 0 and ahora.second < 10:
                logger.info(f"💓 SCANNER OK - {ahora.strftime('%H:%M')} UTC")

            for tf in TIMEFRAMES:
                # El escáner de 5m corre siempre, el de 4h/1h cada 15 min
                if tf in ["4h", "1h"] and ahora.minute % 15 != 0: continue
                
                for cat, symbols in ASSETS.items():
                    for s in symbols:
                        df = obtener_datos(s, tf)
                        if df is None: continue
                        
                        # 1. W / M Pro (RSI + Fibo 50)
                        pat, info_w = detectar_patron_w_m_pro(df)
                        if pat: await enviar_señal_final(bot, s, tf, pat, info_w)
                        
                        # 2. Armónicos Refinados
                        arm, info_a = detectar_armonico_refinado(df)
                        if arm: await enviar_señal_final(bot, s, tf, "ARMÓNICO", info_a)
                        
                        # 3. SMC / FVG
                        smc = detectar_fvg_smc(df)
                        if smc:
                            m = f"⚡ **SMC ({tf.upper()})** ⚡\n**{s}:** {'🟢 COMPRA' if smc=='BUY' else '🔴 VENTA'}"
                            await bot.send_message(CHAT_ID, m, parse_mode="Markdown")
                        
                        await asyncio.sleep(0.5) # Evitar ban de API
            
            await asyncio.sleep(60) # Pausa entre escaneos completos
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main())
