import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# ===================================================================
# CONFIGURACIÓN GLOBAL Y DICCIONARIOS
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

CRYPTO_MACD = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]
señales_enviadas = set()

# ===================================================================
# FUNCIONES DE TELEGRAM Y OBTENCIÓN DE DATOS
# ===================================================================
def generar_mensaje_telegram(par, direccion, ent, sl, tp1, tp2=None, tp3=None, nombre_est="", marco="", tipo_orden="MARKET"):
    cabecera = "⚡ MARKET ORDER ⚡\n" if "LIMIT" not in tipo_orden else "🔵🔵 LIMIT ORDER 🔵🔵\n"
    cabecera += "🟢 COMPRA (LONG) 🟢" if (direccion == 1 or "COMPRA" in str(direccion).upper()) else "🔴 VENTA (SHORT) 🔴"
    
    alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️" if par == "GBP/USD" else f"📈 **ACTIVO: {par.upper()}**"
    
    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_est}`\n"
        f"⏳ **MARCO:** `{marco}`\n"
        f"{alerta_par}\n\n"
        f"🚀 **ENTRADA:** **{ent}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    if tp2: mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    if tp3: mensaje += f"🎯 **TARGET 3:** **{tp3}**\n"
    
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **HORA SEÑAL:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    intervalo_real = intervalos.get(tf, '15m')
    # LÍNEA CORREGIDA (Evita el SyntaxError de la llave abierta)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo_real}&range=5d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}, 
                          index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ))
        return df.dropna()
    except: return None

# ===================================================================
# ESTRATEGIAS ICT (MODIFICADAS PARA DISPARAR 30s ANTES)
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None
    df, df_h4 = df_15m.copy(), df_4h.copy()
    ts = df.index[-1]
    
    current_week = df.index.isocalendar().week[-1]
    df_weekly = df[df.index.isocalendar().week == current_week]
    if df_weekly.empty: return None
    
    weekly_open = df_weekly['open'].iloc[0]
    current_price = df['close'].iloc[-1]
    
    h4_trend = "COMPRA" if df_h4['high'].iloc[-1] > df_h4['high'].iloc[-2] else "VENTA" if df_h4['low'].iloc[-1] < df_h4['low'].iloc[-2] else None
    bias = "COMPRA" if current_price < weekly_open and h4_trend == "COMPRA" else "VENTA" if current_price > weekly_open and h4_trend == "VENTA" else None
    
    if not bias: return None
    r_high, r_low = df['high'].tail(30).max(), df['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None

    if bias == "COMPRA" and (r_high - (rango * 0.79) <= current_price <= r_high - (rango * 0.62)):
        return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.272), 5), ts
    if bias == "VENTA" and (r_low + (rango * 0.62) <= current_price <= r_low + (rango * 0.79)):
        return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.272), 5), ts
    return None

def est_ict_1minuto(df_1m):
    if df_1m is None or len(df_1m) < 60: return None
    df = df_1m.copy()
    ts = df.index[-1]
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['SH'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())].ffill()
    df['SL'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())].ffill()
    
    c_close, ema_50, l_high, l_low = df['close'].iloc[-1], df['EMA_50'].iloc[-1], df['SH'].iloc[-1], df['SL'].iloc[-1]
    
    if c_close > l_high and c_close > ema_50:
        return "COMPRA", round(c_close, 5), round(l_low, 5), round(l_high + (l_high-l_low)*0.5, 5), ts
    if c_close < l_low and c_close < ema_50:
        return "VENTA", round(c_close, 5), round(l_high, 5), round(l_low - (l_high-l_low)*0.5, 5), ts
    return None

# ===================================================================
# ESTRATEGIA MACD (SE MANTIENE 3s ANTES)
# ===================================================================
def est_estrategia_precision(df_menor, df_mayor):
    df_htf, df_ltf = df_mayor.copy(), df_menor.copy()
    df_htf['EMA_100'] = df_htf['close'].ewm(span=100, adjust=False).mean()
    df_combined = pd.merge_asof(df_ltf.sort_index(), df_htf[['EMA_100']].sort_index(), left_index=True, right_index=True, direction='backward')
    
    ema_f, ema_s = df_combined['close'].ewm(span=12).mean(), df_combined['close'].ewm(span=26).mean()
    macd, signal = ema_f - ema_s, (ema_f - ema_s).ewm(span=9).mean()
    
    df_combined['Signal'] = 0
    df_combined.loc[(macd > signal) & (df_combined['close'] > df_combined['EMA_100']), 'Signal'] = 1
    df_combined.loc[(macd < signal) & (df_combined['close'] < df_combined['EMA_100']), 'Signal'] = -1
    return df_combined

# ===================================================================
# MOTOR PRINCIPAL
# ===================================================================
print("🤖 BOT INICIADO - ICT 30s / MACD 3s")

while True:
    ahora = datetime.now(TZ)
    
    # ACCIÓN EN EL SEGUNDO 30 (SÓLO ICT)
    if ahora.second == 30:
        for ticker, nombre in ASSETS_MAP.items():
            if "-USD" in ticker or (HORA_INICIO <= ahora.hour < HORA_FIN):
                # 1. ICT 1 Min
                d1m = obtener_datos(ticker, "1m")
                r2 = est_ict_1minuto(d1m)
                if r2:
                    id2 = f"{ticker}_1M_{r2[4].strftime('%H%M')}"
                    if id2 not in señales_enviadas:
                        enviar_telegram(generar_mensaje_telegram(nombre, r2[0], r2[1], r2[2], r2[3], nombre_est="ICT 1 Min", marco="1M"))
                        señales_enviadas.add(id2)
                
                # 2. ICT Alex Ruiz (Cada 15 min)
                if ahora.minute % 15 == 14:
                    d15, d4h = obtener_datos(ticker, "15m"), obtener_datos(ticker, "4h")
                    r1 = est_ict_alex_m15(d15, d4h)
                    if r1:
                        id1 = f"{ticker}_ALEX_{r1[5].strftime('%H%M')}"
                        if id1 not in señales_enviadas:
                            enviar_telegram(generar_mensaje_telegram(nombre, r1[0], r1[1], r1[2], r1[3], r1[4], nombre_est="ICT Alex Ruiz", marco="15M"))
                            señales_enviadas.add(id1)
        time.sleep(1)

    # ACCIÓN EN EL SEGUNDO 57 (SÓLO MACD)
    if ahora.second == 57:
        for ticker, nombre in ASSETS_MAP.items():
            if ticker in CRYPTO_MACD or ("USD" in ticker and "=X" in ticker):
                if ahora.minute % 5 == 4:
                    d5, d15 = obtener_datos(ticker, "5m"), obtener_datos(ticker, "15m")
                    df_m = est_estrategia_precision(d5, d15)
                    if not df_m.empty and df_m.iloc[-1]['Signal'] != 0:
                        v = df_m.iloc[-1]
                        id3 = f"{ticker}_MACD_{df_m.index[-1].strftime('%H%M')}"
                        if id3 not in señales_enviadas:
                            enviar_telegram(generar_mensaje_telegram(nombre, v['Signal'], round(v['close'],5), round(v['EMA_100'],5), round(v['close']*1.01,5), nombre_est="MACD 2.0", marco="5M"))
                            señales_enviadas.add(id3)
        time.sleep(1)

    if ahora.hour == 0 and ahora.minute == 0: señales_enviadas.clear()
    time.sleep(0.5)
