import logging
import asyncio
import pandas as pd
import requests
from datetime import datetime, timezone, time
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

registro_señales = {}
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
    "TRADICIONAL": ["NVDA", "GC=F", "^GSPC", "EURUSD=X", "GBPUSD=X"]
}

# ==========================================
# 🕒 LÓGICA DE HORARIOS PERSONALIZADA
# ==========================================
def es_horario_activo(categoria):
    ahora_dt = datetime.now(timezone.utc).astimezone(datetime.now().astimezone().tzinfo)
    ahora = ahora_dt.time()
    dia_semana = ahora_dt.weekday()  # 0=Lunes, 6=Domingo

    # --- HORARIO ENTRE SEMANA (Lunes a Viernes) ---
    if dia_semana < 5:
        if categoria == "CRYPTO":
            return time(7, 0) <= ahora <= time(22, 0)
        else:
            return time(7, 0) <= ahora <= time(20, 0)

    # --- HORARIO FIN DE SEMANA (Sábado y Domingo) ---
    else:
        if categoria == "CRYPTO":
            # Mañana: 10 a 14 | Tarde/Noche: 15 a 22
            bloque1 = time(10, 0) <= ahora <= time(14, 0)
            bloque2 = time(15, 0) <= ahora <= time(22, 0)
            return bloque1 or bloque2
        else:
            return False # Oro, Acciones e Índices cerrados el finde

# ==========================================
# 📊 MOTOR DE ESTRATEGIA (SMC + VOLUMEN)
# ==========================================
def obtener_datos(sym, tf, cat):
    try:
        if cat == "CRYPTO":
            url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit=60"
            r = requests.get(url, timeout=10).json()
            df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
        else:
            y_tf = "5m" if tf == "5m" else ("15m" if tf == "15m" else "60m")
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={y_tf}&range=5d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
            q = r["chart"]["result"][0]["indicators"]["quote"][0]
            df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"],"v":q["volume"]})
        
        df = df[["o","h","l","c","v"]].astype(float).dropna()
        return df
    except: return None

def detectar_señal(df):
    if len(df) < 5: return None
    is_bull = df['l'].iloc[-1] > df['h'].iloc[-3] # FVG Alcista
    is_bear = df['h'].iloc[-1] < df['l'].iloc[-3] # FVG Bajista
    vol_confirm = df['v'].iloc[-1] > df['v'].rolling(20).mean().iloc[-1]
    
    if is_bull and vol_confirm: return "BUY"
    if is_bear and vol_confirm: return "SELL"
    return None

# ==========================================
# 📡 MOTOR PRINCIPAL (T-5 SEGUNDOS)
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("⚡ Bot Quantfury Pro: Horarios Diferenciados Activados")

    while True:
        try:
            ahora_nav = datetime.now(timezone.utc)
            espera = 300 - ((ahora_nav.minute % 5) * 60 + ahora_nav.second) - 5
            if espera <= 0: espera += 300
            await asyncio.sleep(espera)

            for cat, symbols in ASSETS.items():
                # Verificamos si este grupo de activos debe trabajar ahora
                if not es_horario_activo(cat):
                    continue

                for sym in symbols:
                    res = {}
                    df_last = None
                    for tf in ["5m", "15m", "1h", "4h"]:
                        df = obtener_datos(sym, tf, cat)
                        if df is not None:
                            res[tf] = detectar_señal(df)
                            df_last = df
                    
                    # VALIDACIÓN DE CONFLUENCIAS
                    final_side, tipo = None, ""
                    if res.get("4h") == res.get("1h") == res.get("15m") and res.get("4h"):
                        final_side, tipo = res["4h"], "💎 CONFLUENCIA PRO (4h-1h-15m)"
                    elif res.get("1h") == res.get("15m") == res.get("5m") and res.get("1h"):
                        final_side, tipo = res["1h"], "⚡ CONFLUENCIA INTRA (1h-15m-5m)"

                    if final_side:
                        en = round(df_last['c'].iloc[-1], 4)
                        sl = round(df_last['l'].iloc[-3] if final_side == "BUY" else df_last['h'].iloc[-3], 4)
                        
                        msg = (
                            f"{tipo}\n"
                            f"📊 *ACTIVO:* {sym}\n"
                            f"🧭 *DIRECCIÓN:* {'🟢 COMPRA' if final_side == 'BUY' else '🔴 VENTA'}\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🚨 **ORDEN: MARKET (ENTRAR YA)** 🚨\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"📥 *ENTRADA:* `{en}`\n"
                            f"🛡️ *STOP LOSS:* `{sl}`\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🕒 _Filtro de Horario Dinámico Activo_"
                        )
                        await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                        await asyncio.sleep(2) # Evitar spam

            await asyncio.sleep(20)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
