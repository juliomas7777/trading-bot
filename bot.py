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
# FUNCIONES AUXILIARES
# ===================================================================
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def generar_mensaje(par, direccion, ent, sl, tp1, tp2=None, tp3=None, nombre_est="", marco=""):
    cabecera = "⚡ MARKET ORDER ⚡\n"
    if direccion == "COMPRA" or direccion == 1:
        cabecera += "🟢 COMPRA (LONG) 🟢"
    else:
        cabecera += "🔴 VENTA (SHORT) 🔴"

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
    
    hora_actual = datetime.now(TZ).strftime('%H:%M:%S')
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **ANTICIPACIÓN (30s):** `{hora_actual}`"
    return mensaje

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    intervalo_real = intervalos.get(tf, '15m')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo_real}&range=5d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}, 
                          index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ))
        return df.dropna()
    except:
        return None

# ===================================================================
# ESTRATEGIA 1: ICT ALEX RUIZ (M15 + H4) - COMPLETA
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None
    df = df_15m.copy()
    df_h4 = df_4h.copy()
    ts = df.index[-1]
    
    df['week'] = df.index.isocalendar().week
    current_week = df['week'].iloc[-1]
    df_weekly = df[df['week'] == current_week]
    if df_weekly.empty: return None
    
    weekly_open = df_weekly['open'].iloc[0]
    current_price = df['close'].iloc[-1]
    
    # Tendencia H4
    h4_high_now = df_h4['high'].iloc[-1]
    h4_high_prev = df_h4['high'].iloc[-2]
    h4_low_now = df_h4['low'].iloc[-1]
    h4_low_prev = df_h4['low'].iloc[-2]
    
    h4_trend = None
    if h4_high_now > h4_high_prev: h4_trend = "COMPRA"
    elif h4_low_now < h4_low_prev: h4_trend = "VENTA"
    
    bias = None
    if current_price < weekly_open and h4_trend == "COMPRA": bias = "COMPRA"
    elif current_price > weekly_open and h4_trend == "VENTA": bias = "VENTA"
    
    if not bias: return None

    r_high, r_low = df['high'].tail(30).max(), df['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None

    if bias == "COMPRA":
        entry_min = r_high - (rango * 0.79)
        entry_max = r_high - (rango * 0.62)
        if entry_min <= current_price <= entry_max:
            tp = r_high + (rango * 0.272)
            return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(tp, 5), ts
            
    elif bias == "VENTA":
        entry_min = r_low + (rango * 0.62)
        entry_max = r_low + (rango * 0.79)
        if entry_min <= current_price <= entry_max:
            tp = r_low - (rango * 0.272)
            return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(tp, 5), ts
            
    return None

# ===================================================================
# ESTRATEGIA 2: ICT 1 MINUTO - COMPLETA
# ===================================================================
def est_ict_1minuto(df_1m):
    if df_1m is None or len(df_1m) < 60: return None
    df = df_1m.copy()
    ts = df.index[-1]
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Identificación de Swings para estructura
    df['Swing_High'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())].ffill()
    df['Swing_Low'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())].ffill()
    
    c_close, ema_50 = df['close'].iloc[-1], df['EMA_50'].iloc[-1]
    l_high, l_low = df['Swing_High'].iloc[-1], df['Swing_Low'].iloc[-1]
    
    # Lógica de Break of Structure (BOS) y retroceso OTE simplificado para ejecución rápida
    # Compra: Cierre por encima de último Swing High + Precio sobre EMA50
    if c_close > l_high and c_close > ema_50:
        ent = round(c_close, 5)
        sl = round(l_low, 5)
        tp = round(l_high + (l_high - l_low) * 0.618, 5)
        return "COMPRA", ent, sl, tp, ts
        
    # Venta: Cierre por debajo de último Swing Low + Precio bajo EMA50
    if c_close < l_low and c_close < ema_50:
        ent = round(c_close, 5)
        sl = round(l_high, 5)
        tp = round(l_low - (l_high - l_low) * 0.618, 5)
        return "VENTA", ent, sl, tp, ts
        
    return None

# ===================================================================
# MOTOR PRINCIPAL (ICT ONLY - 30s ANTICIPACIÓN)
# ===================================================================
print("🚀 BOT INICIADO - ESTRATEGIAS ICT (Alex Ruiz + 1 Min) - 30s Anticipación")

while True:
    now = datetime.now(TZ)
    
    # Se activa cada minuto en el segundo 30
    if now.second == 30:
        for ticker, name in ASSETS_MAP.items():
            # Filtro Horario: Criptos 24/7, el resto de 7:00 a 22:00
            if "-USD" in ticker or (HORA_INICIO <= now.hour < HORA_FIN):
                
                # 1. Escaneo ICT 1 Minuto (Cada minuto)
                d1m = obtener_datos(ticker, "1m")
                r_ict1 = est_ict_1minuto(d1m)
                if r_ict1:
                    key1 = f"{ticker}_1M_{now.strftime('%H:%M')}"
                    if key1 not in señales_enviadas:
                        enviar_telegram(generar_mensaje(name, r_ict1[0], r_ict1[1], r_ict1[2], r_ict1[3], nombre_est="ICT 1 Min", marco="1M"))
                        señales_enviadas.add(key1)

                # 2. Escaneo ICT Alex Ruiz (Cada 15 min, 30s antes del cierre)
                if now.minute % 15 == 14:
                    d15m, d4h = obtener_datos(ticker, "15m"), obtener_datos(ticker, "4h")
                    r_alex = est_ict_alex_m15(d15m, d4h)
                    if r_alex:
                        keyA = f"{ticker}_ALEX_{now.strftime('%H:%M')}"
                        if keyA not in señales_enviadas:
                            enviar_telegram(generar_mensaje(name, r_alex[0], r_alex[1], r_alex[2], r_alex[3], r_alex[4], nombre_est="ICT Alex Ruiz", marco="15M"))
                            señales_enviadas.add(keyA)
        
        time.sleep(2) # Evitar re-entrada en el mismo segundo

    time.sleep(0.5)
    # Limpieza automática de memoria cada 500 señales
    if len(señales_enviadas) > 500:
        señales_enviadas.clear()
