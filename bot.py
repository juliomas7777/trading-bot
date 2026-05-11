import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# ===================================================================
# CONFIGURACIÓN GLOBAL
# ===================================================================
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

ASSETS_MAP = {
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", "SPY": "S&P 500", "QQQ": "NASDAQ 100", 
    "^GDAXI": "DAX 40", "NVDA": "NVIDIA", "EURUSD=X": "EUR/USD", 
    "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", "USDCAD=X": "USD/CAD", 
    "USDCHF=X": "USD/CHF", "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

señales_enviadas = set()

# ===================================================================
# FUNCIONES DE SISTEMA
# ===================================================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def generar_mensaje_telegram(par, direccion, ent, sl, tp1, tp2=None, nombre_est="", marco="", timing=""):
    cabecera = "⚡ MARKET ORDER ⚡\n"
    cabecera += "🟢 COMPRA (LONG) 🟢" if (direccion == "COMPRA" or direccion == 1) else "🔴 VENTA (SHORT) 🔴"
    
    par_display = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️" if par == "GBP/USD" else f"📈 **ACTIVO: {par.upper()}**"
    
    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_est}`\n"
        f"⏳ **MARCO:** `{marco}`\n"
        f"{par_display}\n\n"
        f"🚀 **ENTRADA:** **{ent}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    if tp2: mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **{timing}:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
    return mensaje

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "15m": "15m", "4h": "1h"}
    ir = intervalos.get(tf, '15m')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={ir}&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}, 
                          index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ))
        return df.dropna()
    except:
        return None

# ===================================================================
# ESTRATEGIAS (LÓGICA ORIGINAL MANTENIDA)
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None
    df_15m['week'] = df_15m.index.isocalendar().week
    weekly_open = df_15m[df_15m['week'] == df_15m['week'].iloc[-1]]['open'].iloc[0]
    current_price = df_15m['close'].iloc[-1]
    h4_trend = "COMPRA" if df_4h['close'].iloc[-1] > df_4h['close'].iloc[-2] else "VENTA"
    
    bias = None
    if current_price < weekly_open and h4_trend == "COMPRA": bias = "COMPRA"
    elif current_price > weekly_open and h4_trend == "VENTA": bias = "VENTA"
    if not bias: return None

    rh, rl = df_15m['high'].tail(30).max(), df_15m['low'].tail(30).min()
    rng = rh - rl
    if rng <= 0: return None

    if bias == "COMPRA" and (rh - rng * 0.79) <= current_price <= (rh - rng * 0.62):
        return "COMPRA", round(current_price, 5), round(rl, 5), round(rh, 5), round(rh + (rng * 0.27), 5)
    if bias == "VENTA" and (rl + rng * 0.62) <= current_price <= (rl + rng * 0.79):
        return "VENTA", round(current_price, 5), round(rh, 5), round(rl, 5), round(rl - (rng * 0.27), 5)
    return None

def est_ict_1minuto(df_1m):
    if df_1m is None or len(df_1m) < 60: return None
    df = df_1m.copy()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    last_sh = df['high'].rolling(window=5, center=True).max().ffill().iloc[-1]
    last_sl = df['low'].rolling(window=5, center=True).min().ffill().iloc[-1]
    c, ema = df['close'].iloc[-1], df['EMA_50'].iloc[-1]
    
    if c > last_sh and c > ema:
        return "COMPRA", round(c, 5), round(last_sl, 5), round(last_sh + (last_sh - last_sl), 5)
    if c < last_sl and c < ema:
        return "VENTA", round(c, 5), round(last_sh, 5), round(last_sl - (last_sh - last_sl), 5)
    return None

# ===================================================================
# MOTOR DE EJECUCIÓN (SCANNER DINÁMICO)
# ===================================================================
print("🤖 BOT INICIADO | ICT 1M (Al Cierre) | ICT ALEX (30s Antes)")

while True:
    now = datetime.now(TZ)
    
    # --- BLOQUE 1: ICT 1 MINUTO (SEGUNDO 0 - CIERRE DE VELA) ---
    if now.second == 0:
        for ticker, name in ASSETS_MAP.items():
            if "-USD" in ticker or (HORA_INICIO <= now.hour < HORA_FIN):
                df_1 = obtener_datos(ticker, "1m")
                res_1min = est_ict_1minuto(df_1)
                if res_1min:
                    key_1 = f"{ticker}_1M_{now.strftime('%H%M')}"
                    if key_1 not in señales_enviadas:
                        msg = generar_mensaje_telegram(name, res_1min[0], res_1min[1], res_1min[2], res_1min[3], nombre_est="ICT 1 Minuto", marco="1M", timing="CIERRE VELA")
                        enviar_telegram(msg)
                        señales_enviadas.add(key_1)
        time.sleep(1.5)

    # --- BLOQUE 2: ICT ALEX RUIZ (SEGUNDO 30 - ANTICIPACIÓN) ---
    if now.second == 30:
        for ticker, name in ASSETS_MAP.items():
            if "-USD" in ticker or (HORA_INICIO <= now.hour < HORA_FIN):
                if now.minute % 15 == 14:
                    df_15 = obtener_datos(ticker, "15m")
                    df_4h = obtener_datos(ticker, "4h")
                    res_alex = est_ict_alex_m15(df_15, df_4h)
                    if res_alex:
                        key_alex = f"{ticker}_ALEX_{now.strftime('%H%M')}"
                        if key_alex not in señales_enviadas:
                            msg = generar_mensaje_telegram(name, res_alex[0], res_alex[1], res_alex[2], res_alex[3], tp2=res_alex[4], nombre_est="ICT Alex Ruiz", marco="15M", timing="ANTICIPACIÓN 30s")
                            enviar_telegram(msg)
                            señales_enviadas.add(key_alex)
        time.sleep(1.5)

    time.sleep(0.5)
    if now.hour == 0 and now.minute == 0: señales_enviadas.clear()
