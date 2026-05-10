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

# Listado de activos
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

# Memoria para evitar spam (Clave: Activo + Timestamp de la vela)
señales_enviadas = set()

# -------------------------------------------------------------------
# FORMATO VISUAL TELEGRAM
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, precio_entrada, sl, tp1, tp2, tp3, nombre_estrategia):
    cabecera = "🟢🟢🟢🟢🟢🟢\n🟢 COMPRA 🟢\n🟢🟢🟢🟢🟢🟢" if direccion.upper() == "COMPRA" else "🔴🔴🔴🔴🔴🔴\n🔴 VENTA 🔴\n🔴🔴🔴🔴🔴🔴"

    if par == "GBP/USD":
        alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️"
    else:
        alerta_par = f"📈 **ACTIVO: {par.upper()}**"

    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_estrategia}`\n"
        f"{alerta_par}\n\n"
        f"🚀 **ENTRADA:** **{precio_entrada}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    
    if tp2 is not None:
        mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    if tp3 is not None:
        mensaje += f"🎯 **TARGET 3:** **{tp3}**\n"
        
    mensaje += (
        f"━━━━━━━━━━━━━━━\n\n"
        f"🕒 **VELA CERRADA A LAS:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
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
    intervalo = "15m" if tf == "15m" else "1h"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range=60d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "datetime": pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ),
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }).dropna()
        
        if tf == "4h": 
            df = df.iloc[::4, :].copy() 
            
        return df.tail(100).reset_index(drop=True)
    except: 
        return None

# -------------------------------------------------------------------
# ESTRATEGIA: ICT ALEX RUIZ (M15 + H4)
# -------------------------------------------------------------------
def est_estrategia_ict_alex(df_15m, df_4h):
    # Usamos .iloc[:-1] para analizar solo la vela que ACABA DE CERRAR
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None, None, None, None, None, None, None
    
    df_15m_cerrado = df_15m.iloc[:-1].copy()
    df_4h_cerrado = df_4h.iloc[:-1].copy()
    
    last_candle_time = df_15m_cerrado['datetime'].iloc[-1]
    
    df_15m_cerrado['week'] = df_15m_cerrado['datetime'].dt.isocalendar().week
    weekly_open = df_15m_cerrado[df_15m_cerrado['week'] == df_15m_cerrado['week'].iloc[-1]]['open'].iloc[0]
    current_price = df_15m_cerrado['close'].iloc[-1]
    
    h4_trend = "COMPRA" if (df_4h_cerrado['high'].iloc[-1] > df_4h_cerrado['high'].iloc[-2]) else "VENTA" if (df_4h_cerrado['low'].iloc[-1] < df_4h_cerrado['low'].iloc[-2]) else None
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else "VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None
    
    if not bias: return None, None, None, None, None, None, last_candle_time

    r_high, r_low = df_15m_cerrado['high'].tail(30).max(), df_15m_cerrado['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None, None, None, None, None, None, last_candle_time

    if bias == "COMPRA":
        if (r_high - (rango * 0.79)) <= current_price <= (r_high - (rango * 0.62)):
            return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.272), 5), round(r_high + (rango * 0.618), 5), last_candle_time
    elif bias == "VENTA":
        if (r_low + (rango * 0.62)) <= current_price <= (r_low + (rango * 0.79)):
            return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.272), 5), round(r_low - (rango * 0.618), 5), last_candle_time
    
    return None, None, None, None, None, None, last_candle_time

# -------------------------------------------------------------------
# BUCLE PRINCIPAL (SOLO ICT)
# -------------------------------------------------------------------
print("Bot ICT Activo: Analizando cierres de vela M15...")

while True:
    ahora = datetime.now(TZ)
    
    for ticker, nombre in ASSETS_MAP.items():
        es_crypto = "-USD" in ticker
        if es_crypto or (HORA_INICIO <= ahora.hour < HORA_FIN):
            
            df_15m = obtener_datos(ticker, "15m")
            df_4h = obtener_datos(ticker, "4h")
            
            res = est_estrategia_ict_alex(df_15m, df_4h)
            
            # res[-1] es el timestamp de la vela analizada
            if res and res[0]:
                dir, ent, sl, tp1, tp2, tp3, candle_ts = res
                
                # Creamos una clave única: Activo + HoraVela + MinutoVela
                id_unico = f"{ticker}_{candle_ts.strftime('%Y-%m-%d_%H:%M')}"
                
                if id_unico not in señales_enviadas:
                    enviar_telegram(generar_mensaje_telegram(nombre, dir, ent, sl, tp1, tp2, tp3, "ICT Alex Ruiz"))
                    señales_enviadas.add(id_unico)
                    print(f"[{ahora.strftime('%H:%M:%S')}] Señal ICT enviada para {nombre}")
                    
                    # Limpieza básica para que la memoria no crezca infinitamente
                    if len(señales_enviadas) > 200:
                        señales_enviadas.clear()
            
            time.sleep(0.5)
            
    time.sleep(30) # Escanea cada 30 segundos pero solo actúa si la vela cerrada cambia
