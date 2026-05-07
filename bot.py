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

ASSETS = {
    "TOP": ["NVDA", "TSLA", "XAUUSD", "SPY", "QQQ", "DAX"],
    "CRYPTO": ["BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD", "XRPUSD"],
    "FOREX_USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "USDTWD", "USDMXN", "USDCNH"]
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def es_horario_activo(categoria):
    ahora_dt = datetime.now(timezone.utc).astimezone(datetime.now().astimezone().tzinfo)
    ahora = ahora_dt.time()
    dia = ahora_dt.weekday()
    if dia < 5:
        if categoria == "CRYPTO": return time(7, 0) <= ahora <= time(22, 0)
        else: return time(7, 0) <= ahora <= time(20, 0)
    else:
        if categoria == "CRYPTO": return (time(10, 0) <= ahora <= time(14, 0)) or (time(15, 0) <= ahora <= time(22, 0))
        return False

async def enviar_pre_alerta(bot, sym, side, tipo):
    dir_v = "COMPRA 🟢" if side == "BUY" else "VENTA 🔴"
    msg = f"⚠️⚠️⚠️⚠️⚠️\n**PRE-AVISO 2 MINUTOS**\n\n**ACTIVO:** `{sym}`\n**DIRECCIÓN:** `{dir_v}`"
    try: await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
    except: pass

def detectar_fvg_smc(df):
    if df is None or len(df) < 5: return None
    fvg_alcista = df['l'].iloc[-1] > df['h'].iloc[-3]
    fvg_bajista = df['h'].iloc[-1] < df['l'].iloc[-3]
    vol_ok = df['v'].iloc[-1] > df['v'].rolling(10).mean().iloc[-1]
    if fvg_alcista and vol_ok: return "BUY"
    if fvg_bajista and vol_ok: return "SELL"
    return None

def obtener_datos(sym, tf):
    try:
        # Intenta obtener datos con un timeout para que no se congele
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={tf}&range=2d"
        if "USD" in sym and len(sym) > 5:
            sym_api = sym.replace("USD", "-USD") if any(x in sym for x in ["BTC", "ETH", "SOL"]) else sym + "=X"
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym_api}?interval={tf}&range=2d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        q = r["chart"]["result"][0]["indicators"]["quote"][0]
        return pd.DataFrame({"v":q["volume"],"h":q["high"],"l":q["low"],"c":q["close"]}).dropna()
    except: return None

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 BOT ACTIVADO - Patrullando 21 activos de Quantfury")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            # El "Latido": Cada 5 minutos imprime que está vivo
            if ahora.minute % 5 == 0 and ahora.second < 10:
                logger.info("💓 BOT VIVO: Escaneando mercados ahora mismo...")

            sec = (ahora.minute % 5) * 60 + ahora.second
            
            # --- PRE-AVISO (Minuto 3 de la vela) ---
            if 178 <= sec <= 185:
                for cat, symbols in ASSETS.items():
                    if not es_horario_activo(cat): continue
                    for s in symbols:
                        side = detectar_fvg_smc(obtener_datos(s, "5m"))
                        if side: await enviar_pre_alerta(bot, s, side, "INTRA")
                await asyncio.sleep(10)

            # --- MARKET (Fin de vela) ---
            if 290 <= sec <= 298:
                for cat, symbols in ASSETS.items():
                    if not es_horario_activo(cat): continue
                    for s in symbols:
                        res_15 = detectar_fvg_smc(obtener_datos(s, "15m"))
                        res_5 = detectar_fvg_smc(obtener_datos(s, "5m"))
                        if res_15 and res_15 == res_5:
                            m = f"🚨 **ORDEN: MARKET** 🚨\n\n**ACTIVO:** {s}\n**ACCIÓN:** {'🟢 COMPRA' if res_15=='BUY' else '🔴 VENTA'}"
                            await bot.send_message(CHAT_ID, m, parse_mode="Markdown")
                await asyncio.sleep(10)
            
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error en bucle: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
