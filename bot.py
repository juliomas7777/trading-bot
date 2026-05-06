import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone, time
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN DE USUARIO
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

# 21 ACTIVOS TOTALES (Nomenclatura Quantfury)
ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD"],
    "FOREX_USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "USDTWD", "USDMXN", "USDCNH"]
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# 🕒 LÓGICA DE HORARIOS (Cierre 22:00 y Finde)
# ==========================================
def es_horario_activo(categoria):
    ahora_dt = datetime.now(timezone.utc).astimezone(datetime.now().astimezone().tzinfo)
    ahora = ahora_dt.time()
    dia = ahora_dt.weekday() # 0=Lunes, 6=Domingo

    if dia < 5: # Lunes a Viernes
        if categoria == "CRYPTO":
            return time(7, 0) <= ahora <= time(22, 0)
        else:
            return time(7, 0) <= ahora <= time(20, 0)
    else: # Fin de Semana (Solo Crypto)
        if categoria == "CRYPTO":
            return (time(10, 0) <= ahora <= time(14, 0)) or (time(15, 0) <= ahora <= time(22, 0))
        return False

# ==========================================
# 📡 FUNCIONES DE SEÑAL Y PRE-AVISO
# ==========================================
async def enviar_pre_alerta(bot, sym, side, tipo):
    dir_v = "COMPRA 🟢" if side == "BUY" else "VENTA 🔴"
    est = "4h-1h-15m" if "PRO" in tipo else "1h-15m-5m"
    msg = (
        f"⚠️⚠️⚠️⚠️⚠️\n"
        f"**PRE-AVISO 2 MINUTOS**\n\n"
        f"**ACTIVO:** `{sym}`\n"
        f"**DIRECCIÓN:** `{dir_v}`\n"
        f"**ESTRATEGIA:** `{est}`"
    )
    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")

def detectar_fvg_smc(df):
    if len(df) < 5: return None
    # Lógica SMC: FVG + Confirmación de Volumen
    fvg_alcista = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bajista = df['h'].iloc[-1] < df['l'].iloc[-3]
    vol_ok = df['v'].iloc[-1] > df['v'].rolling(20).mean().iloc[-1]
    
    if fvg_alcista and vol_ok: return "BUY"
    if fvg_bajista and vol_ok: return "SELL"
    return None

def obtener_datos(sym, tf):
    # Adaptador para traer datos de Yahoo/Binance simulando Quantfury
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={tf}&range=5d"
        if "USD" in sym and len(sym) > 5: # Ajuste para Crypto/Forex en API
            sym_api = sym.replace("USD", "-USD") if "BTC" in sym or "ETH" in sym else sym + "=X"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

# ==========================================
# 🚀 MOTOR PRINCIPAL
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("✅ Bot Quantfury 21 Activos - Iniciado")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            sec = (ahora.minute % 5) * 60 + ahora.second
            
            # --- 1. DETECCIÓN PRE-AVISO (Faltan 2 min para cierre de vela 5m) ---
            if 178 <= sec <= 185:
                for cat, symbols in ASSETS.items():
                    if not es_horario_activo(cat): continue
                    for s in symbols:
                        df = obtener_datos(s, "5m")
                        side = detectar_fvg_smc(df)
                        if side: await enviar_pre_alerta(bot, s, side, "INTRA")
                await asyncio.sleep(10)

            # --- 2. SEÑAL MARKET FINAL (T-5 Segundos) ---
            espera = 300 - sec - 5
            if espera > 0: await asyncio.sleep(espera)
            
            for cat, symbols in ASSETS.items():
                if not es_horario_activo(cat): continue
                for s in symbols:
                    res = {tf: detectar_fvg_smc(obtener_datos(s, tf)) for tf in ["5m", "15m", "1h", "4h"]}
                    
                    final_side = None
                    if res["4h"] == res["1h"] == res["15m"] and res["4h"]: final_side, t = res["4h"], "💎 PRO"
                    elif res["1h"] == res["15m"] == res["5m"] and res["1h"]: final_side, t = res["1h"], "⚡ INTRA"

                    if final_side:
                        m = (f"🚨 **ORDEN: MARKET** 🚨\n\n**ACTIVO:** {s}\n**ACCIÓN:** {'🟢 COMPRA' if final_side=='BUY' else '🔴 VENTA'}\n"
                             f"**SL:** Debajo de Mecha anterior")
                        await bot.send_message(CHAT_ID, m, parse_mode="Markdown")
            
            await asyncio.sleep(30)
        except Exception as e:
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
