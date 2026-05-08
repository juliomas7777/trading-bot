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

# MAPA COMPLETO CON LAS 10 CRYPTOS + RESTO DE ACTIVOS
ASSETS_MAP = {
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", # <--- AQUÍ ESTÁN LAS 10 CRYPTOS
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "^GDAXI": "DAX 40", "NVDA": "NVIDIA",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", 
    "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF", "AUDUSD=X": "AUD/USD", 
    "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

ultima_direccion_enviada = {}

# -------------------------------------------------------------------
# FORMATO VISUAL LIMPIO (Identificación rápida 🟢/🔴)
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, precio_entrada, sl, tp1, tp2, tp3):
    if direccion.upper() == "COMPRA":
        cabecera = "🟢🟢🟢🟢🟢🟢\n🟢 COMPRA 🟢\n🟢🟢🟢🟢🟢🟢"
    else:
        cabecera = "🔴🔴🔴🔴🔴🔴\n🔴 VENTA 🔴\n🔴🔴🔴🔴🔴🔴"

    mensaje = (
        f"{cabecera}\n\n"
        f"📈 *ACTIVO:* `{par}`\n"
        f"🚀 *ENTRADA:* `ICT Limit ({precio_entrada})`\n"
        f"🛡️ *STOP LOSS:* `{sl}`\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *TARGET 1:* `{tp1}`\n"
        f"🎯 *TARGET 2:* `{tp2}`\n"
        f"🎯 *TARGET 3:* `{tp3}`\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🕒 *CONFIRMACIÓN:* `H4 (Bias) + M15 (OTE)`"
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
        
        if tf == "4h": 
            df = df.iloc[::4, :].copy() 
            
        return df.tail(200).reset_index(drop=True)
    except: 
        return None

# -------------------------------------------------------------------
# ESTRATEGIA ICT ALEX RUIZ (Lógica y Fórmulas TP Exactas)
# -------------------------------------------------------------------
def est_estrategia_video(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50:
        return None, None, None, None, None, None

    # 1. Sesgo Semanal (Weekly Open)
    df_15m['week'] = df_15m['datetime'].dt.isocalendar().week
    current_week = df_15m['week'].iloc[-1]
    week_data = df_15m[df_15m['week'] == current_week]
    if len(week_data) == 0: return None, None, None, None, None, None
    
    weekly_open = week_data['open'].iloc[0]
    current_price = df_15m['close'].iloc[-1]
    
    # 2. Confirmación de Tendencia 4H
    h4_h1, h4_l1 = df_4h['high'].iloc[-1], df_4h['low'].iloc[-1]
    h4_h2, h4_l2 = df_4h['high'].iloc[-2], df_4h['low'].iloc[-2]
    h4_trend = "COMPRA" if (h4_h1 > h4_h2 and h4_l1 > h4_l2) else "VENTA" if (h4_h1 < h4_h2 and h4_l1 < h4_l2) else None
    
    # 3. Alineación: Precio vs Open + Tendencia H4
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else "VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None
    if not bias: return None, None, None, None, None, None

    # 4. Fibonacci OTE (0.62 - 0.79) en M15
    lookback = 30
    recent_high_idx = df_15m['high'].tail(lookback).idxmax()
    recent_low_idx = df_15m['low'].tail(lookback).idxmin()
    recent_high, recent_low = df_15m['high'].loc[recent_high_idx], df_15m['low'].loc[recent_low_idx]
    rango = recent_high - recent_low
    if rango <= 0: return None, None, None, None, None, None

    # FÓRMULAS TP EXACTAS DE ALEX RUIZ
    if bias == "COMPRA" and recent_low_idx < recent_high_idx:
        ote_inf, ote_sup = recent_high - (rango * 0.79), recent_high - (rango * 0.62)
        if ote_inf <= current_price <= ote_sup:
            return "COMPRA", round(current_price, 5), round(recent_low, 5), \
                   round(recent_high, 5), \
                   round(recent_high + (rango * 0.272), 5), \
                   round(recent_high + (rango * 0.618), 5)
                
    elif bias == "VENTA" and recent_high_idx < recent_low_idx:
        ote_inf, ote_sup = recent_low + (rango * 0.62), recent_low + (rango * 0.79)
        if ote_inf <= current_price <= ote_sup:
            return "VENTA", round(current_price, 5), round(recent_high, 5), \
                   round(recent_low, 5), \
                   round(recent_low - (rango * 0.272), 5), \
                   round(recent_low - (rango * 0.618), 5)

    return None, None, None, None, None, None

# -------------------------------------------------------------------
# MOTOR DE PROCESAMIENTO
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_15m = obtener_datos(ticker, "15m")
    df_4h = obtener_datos(ticker, "4h")
    if df_15m is None or df_4h is None: return

    res = est_estrategia_video(df_15m, df_4h)
    if not res[0]: return 

    dir, ent, sl, tp1, tp2, tp3 = res
    id_ref = f"{ticker}_{dir}_{ent}"
    if ultima_direccion_enviada.get(ticker) == id_ref: return

    enviar_telegram(generar_mensaje_telegram(nombre_claro, dir, ent, sl, tp1, tp2, tp3))
    ultima_direccion_enviada[ticker] = id_ref

# -------------------------------------------------------------------
# BUCLE PRINCIPAL
# -------------------------------------------------------------------
print("Bot Sincronizado: 10 Cryptos + Activos cargados. Estrategia Alex Ruiz activa.")
while True:
    ahora = datetime.now(TZ)
    if HORA_INICIO <= ahora.hour < HORA_FIN:
        if ahora.minute in [14, 29, 44, 59] and ahora.second == 30:
            for ticker, nombre in ASSETS_MAP.items():
                procesar_activo(ticker, nombre)
                time.sleep(0.3)
            time.sleep(40)
    time.sleep(1)
