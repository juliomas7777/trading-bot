import logging
import asyncio
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timezone
from telegram import Bot

# ==========================================
# ⚙️ CONFIGURACIÓN (REVISAR TOKENS)
# ==========================================
TELEGRAM_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

# Registro anti-duplicados
registro_velas = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ASSETS = {
    "CRYPTO": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"],
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X"]
}

TIMEFRAMES = ["15m", "1h", "4h"]

# ==========================================
# 🧠 ESTRATEGIA 1: RSI + ATR
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
        return {"tipo": "COMPRA 🔵", "sl": price-(atr*2), "tp1": price+(atr*1.5), "tp2": price+(atr*3)}
    if last['rsi'] > 75:
        return {"tipo": "VENTA 🔴", "sl": price+(atr*2), "tp1": price-(atr*1.5), "tp2": price-(atr*3)}
    return None

# ==========================================
# 📐 ESTRATEGIA 2: PATRONES ARMÓNICOS
# ==========================================
def detectar_armonicos(df):
    if len(df) < 20: return None
    p = df['c'].values
    try:
        # Puntos X, A, B, C, D (basado en las últimas velas)
        X, A, B, C, D = p[-5], p[-4], p[-3], p[-2], p[-1]
        XA, AB, BC, CD = A-X, B-A, C-B, D-C
        if XA == 0 or AB == 0 or BC == 0: return None
        
        # Ratios de Fibonacci
        ret_AB = abs(AB/XA)
        ret_BC = abs(BC/AB)
        ret_CD = abs(CD/BC)
        ret_AD = abs((D-X)/XA)
        
        err = 0.06 # Tolerancia
        patterns = [
            {"n": "Gartley", "B": 0.618, "D": 0.786},
            {"n": "Bat", "B": 0.382, "D": 0.886},
            {"n": "Butterfly", "B": 0.786, "D": 1.27},
            {"n": "Crab", "B": 0.382, "D": 1.618}
        ]
        
        for pat in patterns:
            if abs(ret_AB - pat['B']) < err and abs(ret_AD - pat['D']) < err:
                direccion = "ALZA 🟢" if X < A else "BAJA 🔴"
                return {"nombre": pat['n'], "dir": direccion}
    except: return None
    return None

# ==========================================
# 📡 MOTOR DE TIEMPO REAL (-35 Segundos)
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Activo - Sincronizando 15m, 1h, 4h (T-35s)")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            # Sincronización al próximo bloque de 15 minutos
            segundos_actuales = (ahora.minute % 15) * 60 + ahora.second
            espera = 900 - segundos_actuales - 35
            
            if espera <= 0: espera += 900
            
            logger.info(f"💤 Espera: {espera}s para el próximo escaneo.")
            await asyncio.sleep(espera)

            # Escaneo
            hora_ref = datetime.now(timezone.utc)
            m, h = hora_ref.minute, hora_ref.hour

            for tf in TIMEFRAMES:
                # Lógica de filtrado de temporalidad
                if tf == "1h" and m < 45: continue
                if tf == "4h" and (h % 4 != 3 or m < 45): continue

                for cat, symbols in ASSETS.items():
                    for sym in symbols:
                        try:
                            # Descarga segura de datos
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
                                    msg = f"🎯 *SEÑAL:* {sym.replace('=X','')}\n"
                                    msg += f"🕒 *TF:* {tf} (Pre-cierre)\n"
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    if arm:
                                        msg += f"📐 Patrón: *{arm['nombre']}*\n"
                                        msg += f"🧭 Dirección: *{arm['dir']}*\n"
                                    if tec:
                                        msg += f"📈 Acción RSI: *{tec['tipo']}*\n"
                                        msg += f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                        msg += f"🛑 SL: `{tec['sl']:.5f}`\n"
                                        msg += f"🎯 TP1: `{tec['tp1']:.5f}`\n"
                                    msg += "━━━━━━━━━━━━━━━━━━\n"
                                    msg += "⚠️ *Confirmar al cierre de vela*"
                                    
                                    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                    registro_velas[id_s] = True
                                    await asyncio.sleep(1)
                        except: continue

            if len(registro_velas) > 100: registro_velas.clear()
            await asyncio.sleep(40) # Evitar re-escaneo en el mismo bloque

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
