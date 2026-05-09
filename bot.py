import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

ASSETS_MAP = {
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", 
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "^GDAXI": "DAX 40", "NVDA": "NVIDIA",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", 
    "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF", "AUDUSD=X": "AUD/USD", 
    "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

ultima_señal_ict = {}
ultima_señal_smc = {}

# -------------------------------------------------------------------
# FORMATO VISUAL TELEGRAM
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, precio_entrada, sl, tp1, tp2, tp3, nombre_estrategia):
    if direccion.upper() == "COMPRA":
        cabecera = "🟢🟢🟢🟢🟢🟢\n🟢 COMPRA 🟢\n🟢🟢🟢🟢🟢🟢"
    else:
        cabecera = "🔴🔴🔴🔴🔴🔴\n🔴 VENTA 🔴\n🔴🔴🔴🔴🔴🔴"

    if par == "GBP/USD":
        alerta_par = f"⚠️⚠️⚠️ *¡¡{par}!!* ⚠️⚠️⚠️"
    else:
        alerta_par = f"📈 *ACTIVO:* `{par}`"

    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 *ESTRATEGIA:* `{nombre_estrategia}`\n"
        f"{alerta_par}\n"
        f"🚀 *ENTRADA:* `Limit ({precio_entrada})`\n"
        f"🛡️ *STOP LOSS:* `{sl}`\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *TARGET 1:* `{tp1}`\n"
        f"🎯 *TARGET 2:* `{tp2}`\n"
        f"🎯 *TARGET 3:* `{tp3}`\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🕒 *CONFIRMACIÓN:* `H4 + M15`"
    )
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# -------------------------------------------------------------------
# OBTENCIÓN DE DATOS
# -------------------------------------------------------------------
def obtener_datos(simbolo, tf="15m"):
    rango = "60d"
    intervalo = "15m" if tf == "15m" else "1h"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range={rango}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        timestamps = data["timestamp"]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "datetime": pd.to_datetime(timestamps, unit='s', utc=True).tz_convert(TZ),
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }).dropna()
        if tf == "4h": df = df.iloc[::4, :].copy() 
        return df.tail(200).reset_index(drop=True)
    except: return None

# -------------------------------------------------------------------
# ESTRATEGIA 1: ICT ALEX RUIZ 
# -------------------------------------------------------------------
def est_estrategia_ict_alex(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None, None, None, None, None, None
    df_15m['week'] = df_15m['datetime'].dt.isocalendar().week
    current_week = df_15m['week'].iloc[-1]
    week_data = df_15m[df_15m['week'] == current_week]
    if len(week_data) == 0: return None, None, None, None, None, None
    weekly_open = week_data['open'].iloc[0]
    current_price = df_15m['close'].iloc[-1]
    
    h4_h1, h4_l1 = df_4h['high'].iloc[-1], df_4h['low'].iloc[-1]
    h4_h2, h4_l2 = df_4h['high'].iloc[-2], df_4h['low'].iloc[-2]
    h4_trend = "COMPRA" if (h4_h1 > h4_h2 and h4_l1 > h4_l2) else "VENTA" if (h4_h1 < h4_h2 and h4_l1 < h4_l2) else None
    
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else "VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None
    if not bias: return None, None, None, None, None, None

    lookback = 30
    recent_high_idx, recent_low_idx = df_15m['high'].tail(lookback).idxmax(), df_15m['low'].tail(lookback).idxmin()
    recent_high, recent_low = df_15m['high'].loc[recent_high_idx], df_15m['low'].loc[recent_low_idx]
    rango = recent_high - recent_low
    if rango <= 0: return None, None, None, None, None, None

    if bias == "COMPRA" and recent_low_idx < recent_high_idx:
        if (recent_high - (rango * 0.79)) <= current_price <= (recent_high - (rango * 0.62)):
            return "COMPRA", round(current_price, 5), round(recent_low, 5), round(recent_high, 5), round(recent_high + (rango * 0.272), 5), round(recent_high + (rango * 0.618), 5)
    elif bias == "VENTA" and recent_high_idx < recent_low_idx:
        if (recent_low + (rango * 0.62)) <= current_price <= (recent_low + (rango * 0.79)):
            return "VENTA", round(current_price, 5), round(recent_high, 5), round(recent_low, 5), round(recent_low - (rango * 0.272), 5), round(recent_low - (rango * 0.618), 5)
    return None, None, None, None, None, None

# -------------------------------------------------------------------
# ESTRATEGIA 2: SMC 
# -------------------------------------------------------------------
def est_estrategia_smc(df):
    # 👇 AQUÍ VA TU ESTRATEGIA SMC ANTERIOR 👇
    
    return None, None, None, None, None, None

# -------------------------------------------------------------------
# MOTOR DE PROCESAMIENTO
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_15m = obtener_datos(ticker, "15m")
    df_4h = obtener_datos(ticker, "4h")
    if df_15m is None or df_4h is None: return

    res_ict = est_estrategia_ict_alex(df_15m, df_4h)
    if res_ict[0]:
        dir, ent, sl, tp1, tp2, tp3 = res_ict
        id_ref = f"{ticker}_{dir}_{ent}"
        if ultima_señal_ict.get(ticker) != id_ref:
            enviar_telegram(generar_mensaje_telegram(nombre_claro, dir, ent, sl, tp1, tp2, tp3, "ICT Alex Ruiz"))
            ultima_señal_ict[ticker] = id_ref

    res_smc = est_estrategia_smc(df_15m)  
    if res_smc[0]:
        dir, ent, sl, tp1, tp2, tp3 = res_smc
        id_ref = f"{ticker}_{dir}_{ent}"
        if ultima_señal_smc.get(ticker) != id_ref:
            enviar_telegram(generar_mensaje_telegram(nombre_claro, dir, ent, sl, tp1, tp2, tp3, "SMC (Smart Money)"))
            ultima_señal_smc[ticker] = id_ref

# -------------------------------------------------------------------
# BUCLE PRINCIPAL (CON HORARIO HÍBRIDO)
# -------------------------------------------------------------------
print("Bot Activo: Forex/Índices (07h-22h) | Cryptos (24/7)")
while True:
    ahora = datetime.now(TZ)
    # Entra en los minutos de cierre de vela M15
    if ahora.minute in [14, 29, 44, 59] and ahora.second == 30:
        for ticker, nombre in ASSETS_MAP.items():
            
            # Comprobación mágica: ¿Es una Crypto? (Todos los tickers crypto terminan en "-USD")
            es_crypto = "-USD" in ticker
            
            # Opera si es crypto (siempre) O si es horario de Forex/Indices
            if es_crypto or (HORA_INICIO <= ahora.hour < HORA_FIN):
                procesar_activo(ticker, nombre)
                time.sleep(0.3)
                
        time.sleep(40) # Espera para no repetir el bucle en el mismo minuto
    time.sleep(1)
