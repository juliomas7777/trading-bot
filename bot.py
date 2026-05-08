import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACION
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")

HORA_INICIO = 7
HORA_FIN = 22

ASSETS_MAP = {
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "^GDAXI": "DAX 40", "NVDA": "NVIDIA",
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY", "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

ultima_direccion_enviada = {}

# -------------------------------------------------------------------
# FUNCIONES DE FORMATO Y TELEGRAM
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, precio_entrada, sl, tp1, tp2, tp3, temporalidad, alerta=False):
    if direccion.upper() == "COMPRA":
        icono_direccion = "🟢 COMPRA 🟢"
        emoji_puntos = "🟩"
    else:
        icono_direccion = "🔴 VENTA 🔴"
        emoji_puntos = "🟥"

    cabecera_confluencia = "⚠️⚠️⚠️⚠️\n" if alerta else ""

    mensaje = (
        f"{cabecera_confluencia}"
        f"{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}\n"
        f"        {icono_direccion}\n"
        f"{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}{emoji_puntos}\n\n"
        f"📈 *ACTIVO:* `{par}`\n"
        f"🚀 *ENTRADA:* `ICT Limit ({precio_entrada})`\n"
        f"🛡️ *STOP LOSS:* `{sl}`\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *TARGET 1:* `{tp1}`\n"
        f"🎯 *TARGET 2:* `{tp2}`\n"
        f"🎯 *TARGET 3:* `{tp3}`\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🕒 *CONFIRMACIÓN:* `{temporalidad}`\n"
    )
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# -------------------------------------------------------------------
# LÓGICA TÉCNICA
# -------------------------------------------------------------------
def obtener_datos(simbolo, tf="1h"):
    intervalo = "1h"
    rango = "30d" if tf == "1h" else "60d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range={rango}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}).dropna()
        if tf == "4h": df = df.iloc[::4, :].copy() 
        return df.tail(200).reset_index(drop=True)
    except: return None

# -------------------------------------------------------------------
# NUEVAS ESTRATEGIAS (SUSTITUIDAS SIN TOCAR NADA MÁS)
# -------------------------------------------------------------------
def est_ict_fvg(df):
    if len(df) < 3: return None, None
    h1, l1 = df["high"].iloc[-3], df["low"].iloc[-3]
    h3, l3 = df["high"].iloc[-1], df["low"].iloc[-1]
    
    cuerpo2 = abs(df["close"].iloc[-2] - df["open"].iloc[-2])
    rango_promedio = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    
    if l3 > h1 and cuerpo2 > (rango_promedio * 0.7): 
        return "COMPRA", round(h1 + (l3 - h1) / 2, 5)
    
    if h3 < l1 and cuerpo2 > (rango_promedio * 0.7):
        return "VENTA", round(l1 - (l1 - h3) / 2, 5)
    
    return None, None

def est_alex_ruiz(df):
    if len(df) < 200: return None, None
    ema50 = df["close"].ewm(span=50).mean()
    sma200 = df["close"].rolling(200).mean()
    
    sma_trending_up = sma200.iloc[-1] > sma200.iloc[-5]
    sma_trending_down = sma200.iloc[-1] < sma200.iloc[-5]
    
    c, o, l, h = df["close"].iloc[-1], df["open"].iloc[-1], df["low"].iloc[-1], df["high"].iloc[-1]
    
    if c > sma200.iloc[-1] and sma_trending_up and l <= ema50.iloc[-1] and c > o: 
        return "COMPRA", c
    
    if c < sma200.iloc[-1] and sma_trending_down and h >= ema50.iloc[-1] and c < o: 
        return "VENTA", c
        
    return None, None

def est_bollinger(df):
    if len(df) < 20: return None, None
    m, s = df["close"].rolling(20).mean(), df["close"].rolling(20).std()
    lower, upper = m - s*2, m + s*2
    c, o = df["close"].iloc[-1], df["open"].iloc[-1]
    
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=7).mean()
    rsi = 100 - (100 / (1 + (gain / loss)))
    
    if c < lower.iloc[-1] and rsi.iloc[-1] < 30 and c > o: 
        return "COMPRA", c
    
    if c > upper.iloc[-1] and rsi.iloc[-1] > 70 and c < o: 
        return "VENTA", c
        
    return None, None

# -------------------------------------------------------------------
# MOTOR DE PROCESAMIENTO
# -------------------------------------------------------------------
def obtener_temporalidad_confirmada(df_h4, df_h1):
    res_h4, px_h4 = est_ict_fvg(df_h4)
    if res_h4:
        return "H4 (Prioridad Alta)", res_h4, px_h4
    
    res_h1, px_h1 = est_ict_fvg(df_h1)
    if res_h1:
        return "H1 (Confirmación Media)", res_h1, px_h1
    
    return None, None, None

def procesar_activo(ticker, nombre_claro):
    df_h1 = obtener_datos(ticker, "1h")
    df_h4 = obtener_datos(ticker, "4h")
    if df_h1 is None or df_h4 is None: return

    temporalidad, direccion, precio_entrada = obtener_temporalidad_confirmada(df_h4, df_h1)
    if not temporalidad: return 

    estrategias_activas = 1
    # Check confluencia en H1
    if est_alex_ruiz(df_h1)[0] == direccion: estrategias_activas += 1
    if est_bollinger(df_h1)[0] == direccion: estrategias_activas += 1

    id_ref = f"{ticker}_{direccion}_{estrategias_activas}"
    if ultima_direccion_enviada.get(ticker) == id_ref: return

    # Cálculo niveles (ATR)
    tr = pd.concat([df_h1["high"]-df_h1["low"], (df_h1["high"]-df_h1["close"].shift(1)).abs(), (df_h1["low"]-df_h1["close"].shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    dist = atr * 2
    
    sl = round(precio_entrada - dist if direccion == "COMPRA" else precio_entrada + dist, 5)
    tp1 = round(precio_entrada + (dist * 1.5) if direccion == "COMPRA" else precio_entrada - (dist * 1.5), 5)
    tp2 = round(precio_entrada + (dist * 3) if direccion == "COMPRA" else precio_entrada - (dist * 3), 5)
    tp3 = round(precio_entrada + (dist * 5) if direccion == "COMPRA" else precio_entrada - (dist * 5), 5)

    mensaje = generar_mensaje_telegram(
        par=nombre_claro,
        direccion=direccion,
        precio_entrada=precio_entrada,
        sl=sl, tp1=tp1, tp2=tp2, tp3=tp3,
        temporalidad=temporalidad,
        alerta=(estrategias_activas >= 2)
    )
    
    enviar_telegram(mensaje)
    ultima_direccion_enviada[ticker] = id_ref

# -------------------------------------------------------------------
# BUCLE
# -------------------------------------------------------------------
print("Bot Sincronizado: Estrategias mejoradas sustituidas con éxito.")

while True:
    ahora = datetime.now(TZ)
    if HORA_INICIO <= ahora.hour < HORA_FIN:
        if ahora.minute in [14, 29, 44, 59] and ahora.second == 30:
            for ticker, nombre_claro in ASSETS_MAP.items():
                procesar_activo(ticker, nombre_claro)
                time.sleep(0.3)
            time.sleep(40) 
    time.sleep(1)
