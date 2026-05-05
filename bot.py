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

# Traducción de activos para el mensaje
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
    "FOREX_INDICES_METALES": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "GC=F", "^GSPC"]
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]

# ==========================================
# 📐 ESTRATEGIA: PATRONES ARMÓNICOS
# ==========================================
def detectar_armonico(df):
    if len(df) < 10: return None
    p = df['c'].values
    try:
        # Puntos X, A, B, C, D
        X, A, B, C, D = p[-5], p[-4], p[-3], p[-2], p[-1]
        XA, AB, BC, CD = A-X, B-A, C-B, D-C
        if XA == 0 or AB == 0: return None
        
        ret_AB = abs(AB/XA)
        ret_AD = abs((D-X)/XA)
        
        err = 0.06 
        patterns = [
            {"n": "GARTLEY", "B": 0.618, "D": 0.786},
            {"n": "BAT", "B": 0.382, "D": 0.886},
            {"n": "BUTTERFLY", "B": 0.786, "D": 1.27},
            {"n": "CRAB", "B": 0.382, "D": 1.618}
        ]
        
        for pat in patterns:
            if abs(ret_AB - pat['B']) < err and abs(ret_AD - pat['D']) < err:
                return {"nombre": pat['n'], "dir": "ALZA 🟢" if D < X else "BAJA 🔴"}
    except: return None
    return None

# ==========================================
# 🕯️ CONFIRMACIÓN: VELAS DE RECHAZO
# ==========================================
def confirmar_vela(df, direccion):
    c1 = df.iloc[-1] # Actual
    c2 = df.iloc[-2] # Anterior
    c3 = df.iloc[-3] # Tras-anterior

    body1 = abs(c1['c'] - c1['o'])
    w_up1 = c1['h'] - max(c1['c'], c1['o'])
    w_do1 = min(c1['c'], c1['o']) - c1['l']
    
    body2 = abs(c2['c'] - c2['o'])
    tot2 = c2['h'] - c2['l']

    if "ALZA" in direccion:
        # 🟢 Engulfing (Envolvente)
        if c1['c'] > c1['o'] and c2['c'] < c2['o'] and c1['c'] > c2['o']:
            return "ENGULFING ALCISTA"
        # 🟢 Pin Bar / Doji Rechazo
        if w_do1 > (2 * body1) and w_up1 < (0.5 * w_do1):
            return "PIN BAR / RECHAZO"
        # 🟢 Morning Star
        if c3['c'] < c3['o'] and body2 < (tot2 * 0.3) and c1['c'] > c1['o']:
            return "MORNING STAR"
            
    if "BAJA" in direccion:
        # 🔴 Engulfing (Envolvente)
        if c1['c'] < c1['o'] and c2['c'] > c2['o'] and c1['c'] < c2['o']:
            return "ENGULFING BAJISTA"
        # 🔴 Pin Bar / Doji Rechazo
        if w_up1 > (2 * body1) and w_do1 < (0.5 * w_up1):
            return "PIN BAR / RECHAZO"
        # 🔴 Evening Star
        if c3['c'] > c3['o'] and body2 < (tot2 * 0.3) and c1['c'] < c1['o']:
            return "EVENING STAR"

    return None

# ==========================================
# 📡 MOTOR DE TIEMPO REAL
# ==========================================
async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    logger.info("🚀 Bot Armónico Iniciado (T-35s)")

    while True:
        try:
            ahora = datetime.now(timezone.utc)
            espera = 300 - ((ahora.minute % 5) * 60 + ahora.second) - 35
            if espera <= 0: espera += 300
            await asyncio.sleep(espera)

            hora_ref = datetime.now(timezone.utc)
            m, h = hora_ref.minute, hora_ref.hour

            for tf in TIMEFRAMES:
                if tf == "15m" and (m % 15) < 14: continue
                if tf == "1h" and m < 59: continue
                if tf == "4h" and (h % 4 != 3 or m < 59): continue

                for cat, symbols in ASSETS.items():
                    for sym in symbols:
                        try:
                            # Descarga segura
                            if cat == "CRYPTO":
                                url = f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit=30"
                                r = requests.get(url, timeout=10).json()
                                df = pd.DataFrame(r, columns=["ts","o","h","l","c","v","ct","qv","t","tbb","tbq","i"])
                            else:
                                y_tf = "5m" if tf == "5m" else ("15m" if tf == "15m" else "60m")
                                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval={y_tf}&range=5d"
                                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
                                q = r["chart"]["result"][0]["indicators"]["quote"][0]
                                df = pd.DataFrame({"o":q["open"],"h":q["high"],"l":q["low"],"c":q["close"]})
                            
                            df = df[["o","h","l","c"]].astype(float).dropna()
                            
                            armonico = detectar_armonico(df)
                            if armonico:
                                confirmacion = confirmar_vela(df, armonico["dir"])
                                if confirmacion:
                                    id_s = f"{sym}_{tf}_{hora_ref.strftime('%H%M')}"
                                    if id_s not in registro_velas:
                                        nombre_bot = TRADUCCION_NOMBRES.get(sym, sym)
                                        msg = f"🎯 *SEÑAL:* {nombre_bot}\n"
                                        msg += f"🕒 TF: *{tf}*\n"
                                        msg += "━━━━━━━━━━━━━━━━━━\n"
                                        msg += f"📐 Armónico: *{armonico['nombre']}*\n"
                                        msg += f"🕯️ Vela: *{confirmacion}*\n"
                                        msg += f"🧭 Dirección: *{armonico['dir']}*\n"
                                        msg += "━━━━━━━━━━━━━━━━━━\n"
                                        msg += f"💰 Entrada: `{df['c'].iloc[-1]:.5f}`\n"
                                        msg += "⚠️ *Confirmar al cierre*"
                                        
                                        await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
                                        registro_velas[id_s] = True
                        except: continue
            await asyncio.sleep(40)
        except Exception as e:
            logger.error(f"Error: {e}")
            await asyncio.sleep(20)

if __name__ == "__main__":
    asyncio.run(main())
