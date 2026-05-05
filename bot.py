import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

registro_velas = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Diccionario de traducción de nombres
TRADUCCION_NOMBRES = {
    "GC=F": "ORO 🟡",
    "^GSPC": "SP500 🇺🇸",
    "BTCUSDT": "BITCOIN (BTC)",
    "ETHUSDT": "ETHEREUM (ETH)",
    "SOLUSDT": "SOLANA (SOL)",
    "BNBUSDT": "BINANCE COIN (BNB)",
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF"
}

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX_METALES_INDICES": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "GC=F", "^GSPC"]
}

TIMEFRAMES = ["15m", "1h", "4h"]

# ==========================================
# 🧠 ESTRATEGIAS
# ==========================================
def analizar_rsi_atr(df):
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, 0.0001)
    df['rsi'] = 100 - (100 / (1 + (gain / loss)))
    df['atr'] = (df['h'] - df['l']).rolling(14).mean()
    
    last = df.iloc[-1]
    price = last['c']
    atr = last['atr'] if last['atr'] > 0 else price * 0.005
    
    if last['rsi'] < 25:
        return {"tipo": "RSI SOBREVENTA 🔵", "sl": price-(atr*2), "tp": price+(atr*1.5)}
    if last['rsi'] > 75:
        return {"tipo": "RSI SOBRECOMPRA 🔴", "sl": price+(atr*2), "tp": price-(atr*1.5)}
    return None

def detectar_armonicos(df):
    if len(df) < 20: return None
    p = df['c'].values
    try:
        X, A, B, C, D = p[-5], p[-4], p[-3], p[-2], p[-1]
        XA, AB, BC, CD = A-X, B-A, C-B, D-C
        if XA == 0 or AB == 0: return None
        ret_AB, ret_AD = abs(AB/XA), abs((D-X)/XA)
        err = 0.06 
        patterns = [
            {"n": "GARTLEY", "B": 0.618, "D": 0.786},
            {"n": "BAT", "B": 0.382, "D": 0.886},
            {"n": "BUTTERFLY", "B": 0.786, "D": 1.27},
            {"n": "CRAB", "B": 0.382, "D": 1.618}
        ]
        for pat in patterns:
            if abs(ret_AB - pat['B']) < err and abs(ret_AD - pat['D']) < err:
                return {"nombre": pat['n'], "dir": "ALZA 🟢" if X < A else "BAJA 🔴"}
    except: return None
    return None

# ==========================================
# 📡 MOTOR DE TIEMPO REAL (-35 Segundos)
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Multiactivo - Sincronizado (T-35s)")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            espera = 900 - ((ahora.minute % 15) * 60 + ahora.second) - 35
            if espera <= 0: espera += 900
            await asyncio.sleep(espera)

            hora_ref = datetime.now(timezone.utc)
            m, h = hora_ref.minute, hora_ref.hour

            for tf in TIMEFRAMES:
                if tf == "1h" and m < 45: continue
                if tf == "4h" and (h % 4 != 3 or m < 45): continue

                for cat, symbols in ASSETS.items():
                    for sym in symbols:
                        try:
                            if cat == "CRYPTO":
                                url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit=50"
                                r = requests.get(url, timeout=10).json()
                                df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                            else:
                                y_tf = "60m" if tf != "15m" else "15m"
                                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={y_tf}&range=5d"
                                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                                q = r["chart"]["result"][0]["indicators"]["quote"][0]
                                df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                            
                            df = df[["o","h","l","c"]].astype(float).dropna()
                            tec = analizar_rsi_atr(df)
                            arm = detectar_armonicos(df)

                            if tec or arm:
                                id_s = f"{sym}_{tf}_{hora_ref.strftime('%H%M')}"
                                if id_s not in registro_velas:
                                    nombre_bonito = TRADUCCION_NOMBRES.get(sym, sym)
                                    msg = f"🎯 *SEÑAL:* {nombre_bonito}\n"
                                    msg += f"🕒 *TF:* {tf} (Pre-cierre)\n"
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    if arm:
                                        msg += f"📐 ESTRATEGIA: *PATRÓN {arm['nombre']}*\n"
                                        msg += f"🧭 DIRECCIÓN: *{arm['dir']}*\n"
                                    if tec:
                                        msg += f"📊 ESTRATEGIA: *{tec['tipo']}*\n"
                                        msg += f"💰 ENTRADA: `{df['c'].iloc[-1]:.5f}`\n"
                                        msg += f"🛑 SL: `{tec['sl']:.5f}`\n"
                                        msg += f"🎯 TP: `{tec['tp']:.5f}`\n"
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    msg += "⚠️ *Confirmar al cierre de vela*"
                                    
                                    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                    registro_velas[id_s] = True
                                    await asyncio.sleep(1)
                        except: continue

            if len(registro_velas) > 100: registro_velas.clear()
            await asyncio.sleep(40) 

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
