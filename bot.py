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
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def formato_senal_limpia(par, direccion, precio_entrada, sl, tp1, tp2, tp3, temporalidad, alerta=False):
    # Si hay confluencia (alerta=True), añadimos los triángulos arriba
    prefijo = "⚠️⚠️⚠️⚠️\n" if alerta else ""
    
    mensaje = (
        f"{prefijo}🔔 *NUEVA SEÑAL DETECTADA*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 *ACTIVO:* `{par}`\n"
        f"↕️ *DIRECCIÓN:* `{direccion}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🚀 *EJECUCIÓN:* `ICT Limit ({precio_entrada})`\n"
        f"🛡️ *STOP LOSS:* `{sl}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 *TAKE PROFIT 1:* `{tp1}`\n"
        f"🎯 *TAKE PROFIT 2:* `{tp2}`\n"
        f"🎯 *TAKE PROFIT 3:* `{tp3}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕒 *CONFIRMACIÓN:* `{temporalidad}`\n"
        f"💡 _Estrategia validada con éxito._"
    )
    return mensaje

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

def calc_atr(df, p=14):
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

# -------------------------------------------------------------------
# ESTRATEGIAS
# -------------------------------------------------------------------
def est_ict_fvg(df):
    h1, l1 = df["high"].iloc[-3], df["low"].iloc[-3]
    h3, l3 = df["high"].iloc[-1], df["low"].iloc[-1]
    if l3 > h1: return "COMPRA", h1 + (l3 - h1) / 2
    if h3 < l1: return "VENTA", l1 - (l1 - h3) / 2
    return None, None

def est_alex_ruiz(df):
    ema50, sma200 = df["close"].ewm(span=50).mean(), df["close"].rolling(200).mean()
    c, o, l, h = df["close"].iloc[-1], df["open"].iloc[-1], df["low"].iloc[-1], df["high"].iloc[-1]
    if c > sma200.iloc[-1] and l <= ema50.iloc[-1] and c > o: return "COMPRA", c
    if c < sma200.iloc[-1] and h >= ema50.iloc[-1] and c < o: return "VENTA", c
    return None, None

def est_bollinger(df):
    m, s = df["close"].rolling(20).mean(), df["close"].rolling(20).std()
    lower, upper = m - s*2, m + s*2
    c = df["close"].iloc[-1]
    if c < lower.iloc[-1]: return "COMPRA", c
    if c > upper.iloc[-1]: return "VENTA", c
    return None, None

# -------------------------------------------------------------------
# MOTOR DE PROCESAMIENTO
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_h1 = obtener_datos(ticker, "1h")
    df_h4 = obtener_datos(ticker, "4h")
    if df_h1 is None or df_h4 is None: return

    señales = []
    
    # 1. Verificar confirmación de temporalidad
    confirmacion = None
    # Prioridad H4
    res_ict_h4, px_ict_h4 = est_ict_fvg(df_h4)
    if res_ict_h4:
        confirmacion = "H4 (Confirmado)"
    else:
        res_ict_h1, px_ict_h1 = est_ict_fvg(df_h1)
        if res_ict_h1:
            confirmacion = "H1 (Confirmado)"
    
    if not confirmacion: return # Solo opera si hay confirmación ICT

    # 2. Ejecutar estrategias en H1 para el disparo
    atr = calc_atr(df_h1).iloc[-1]
    
    for nombre, func in [("ICT", est_ict_fvg), ("ALEX", est_alex_ruiz), ("BOLL", est_bollinger)]:
        res, px = func(df_h1)
        if res:
            señales.append({"est": nombre, "dir": res, "px": px})

    if not señales: return

    # 3. Lógica de agrupamiento y envío
    for d en ["COMPRA", "VENTA"]:
        coincidentes = [s for s in señales if s["dir"] == d]
        if not coincidentes: continue
        
        # Filtro de repetición
        id_msg = f"{ticker}_{d}_{len(coincidentes)}"
        if ultima_direccion_enviada.get(ticker) == id_msg: continue

        # Datos para el formato (usamos la primera estrategia para los precios base)
        base = coincidentes[0]
        px_ent = round(base["px"], 5)
        distancia = atr * 2
        sl = round(px_ent - distancia if d == "COMPRA" else px_ent + distancia, 5)
        tp1 = round(px_ent + (distancia * 1.5) if d == "COMPRA" else px_ent - (distancia * 1.5), 5)
        tp2 = round(px_ent + (distancia * 3) if d == "COMPRA" else px_ent - (distancia * 3), 5)
        tp3 = round(px_ent + (distancia * 5) if d == "COMPRA" else px_ent - (distancia * 5), 5)

        # Generar mensaje con tu nuevo formato
        msg = formato_senal_limpia(
            par=nombre_claro,
            direccion=d,
            precio_entrada=px_ent,
            sl=sl,
            tp1=tp1, tp2=tp2, tp3=tp3,
            temporalidad=confirmacion,
            alerta=(len(coincidentes) >= 2)
        )
        
        enviar_telegram(msg)
        ultima_direccion_enviada[ticker] = id_msg

# -------------------------------------------------------------------
# BUCLE
# -------------------------------------------------------------------
print("Bot actualizado con formato limpio e ICT Limit.")
while True:
    ahora = datetime.now(TZ)
    if HORA_INICIO <= ahora.hour < HORA_FIN:
        if ahora.minute in [14, 29, 44, 59] and ahora.second == 30:
            for ticker, nombre_claro in ASSETS_MAP.items():
                procesar_activo(ticker, nombre_claro)
                time.sleep(0.3)
            time.sleep(40)
    time.sleep(1)
