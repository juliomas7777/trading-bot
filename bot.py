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
COOLDOWN_MINUTOS = 120 

# -------------------------------------------------------------------
# ACTIVOS CORREGIDOS (QUANTFURY)
# -------------------------------------------------------------------
ASSETS = {
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X", "USDCHF=X", "AUDUSD=X", "NZDUSD=X"],
    "CRYPTO_10": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "DOT-USD", "MATIC-USD", "LTC-USD", "LINK-USD", "AVAX-USD"],
    "MATERIAS_PRIMAS": ["GC=F", "SI=F", "CL=F", "HG=F", "NG=F"]
}

historial_senales = {}

# -------------------------------------------------------------------
# FUNCIONES TÉCNICAS
# -------------------------------------------------------------------
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}, timeout=10)
    except: pass

def obtener_datos(simbolo):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval=1h&range=30d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}).dropna()
        return df.tail(200).reset_index(drop=True)
    except: return None

def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

# -------------------------------------------------------------------
# LAS 3 ESTRATEGIAS INDEPENDIENTES (Parámetros Originales)
# -------------------------------------------------------------------

def est_alex_ruiz(df):
    ema50 = df["close"].ewm(span=50).mean()
    sma200 = df["close"].rolling(200).mean()
    c, o, l, h = df["close"].iloc[-1], df["open"].iloc[-1], df["low"].iloc[-1], df["high"].iloc[-1]
    if c > sma200.iloc[-1] and l <= ema50.iloc[-1] and c > o:
        return "COMPRA", 1.4, 1.5
    if c < sma200.iloc[-1] and h >= ema50.iloc[-1] and c < o:
        return "VENTA", 1.4, 1.5
    return None, None, None

def est_ict_fvg(df):
    h1, l1, h3, l3 = df["high"].iloc[-3], df["low"].iloc[-3], df["high"].iloc[-1], df["low"].iloc[-1]
    if l3 > h1:
        return "COMPRA", 2.0, 2.0
    if h3 < l1:
        return "VENTA", 2.0, 2.0
    return None, None, None

def est_bollinger_rsi(df):
    m, s = df["close"].rolling(20).mean(), df["close"].rolling(20).std()
    upper, lower = m + s*2, m - s*2
    d = df["close"].diff()
    g, ps = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (g / ps.replace(0, np.nan))))
    if df["close"].iloc[-1] < lower.iloc[-1] and rsi.iloc[-1] < 30:
        return "COMPRA", 1.2, 2.0
    if df["close"].iloc[-1] > upper.iloc[-1] and rsi.iloc[-1] > 70:
        return "VENTA", 1.2, 2.0
    return None, None, None

MODULOS_ESTRATEGIA = [
    ("ALEX RUIZ", est_alex_ruiz),
    ("ICT FVG", est_ict_fvg),
    ("BOLLINGER + RSI", est_bollinger_rsi)
]

# -------------------------------------------------------------------
# MOTOR DE EJECUCIÓN
# -------------------------------------------------------------------
def procesar_activo(simbolo):
    df = obtener_datos(simbolo)
    if df is None: return

    for nombre_est, func in MODULOS_ESTRATEGIA:
        id_senal = f"{simbolo}_{nombre_est}"
        resultado, m_sl, m_tp = func(df)
        
        if resultado:
            ahora = datetime.now()
            if id_senal in historial_senales:
                if (ahora - historial_senales[id_senal]).total_seconds() < COOLDOWN_MINUTOS * 60:
                    continue

            px = df["close"].iloc[-1]
            atr = calc_atr(df).iloc[-1]
            distancia_sl = atr * m_sl
            sl = px - distancia_sl if resultado == "COMPRA" else px + distancia_sl
            tp = px + (distancia_sl * m_tp) if resultado == "COMPRA" else px - (distancia_sl * m_tp)
            
            historial_senales[id_senal] = ahora
            
            msg = (f"🚀 <b>ESTRATEGIA: {nombre_est}</b>\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"📊 <b>Activo:</b> {simbolo}\n"
                   f"📢 <b>Señal:</b> {resultado}\n"
                   f"💰 <b>Precio Entrada:</b> {round(px, 5)}\n"
                   f"🛑 <b>Stop Loss:</b> {round(sl, 5)}\n"
                   f"🎯 <b>Take Profit:</b> {round(tp, 5)}\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"⏰ <i>Hora: {ahora.strftime('%H:%M:%S')}</i>")
            enviar_telegram(msg)

print("Bot Operativo: 10 Cryptos + Forex + Materias Primas Quantfury")
while True:
    h = datetime.now(TZ).hour
    if HORA_INICIO <= h < HORA_FIN:
        for cat in ASSETS:
            for s in ASSETS[cat]:
                procesar_activo(s)
                time.sleep(1)
    time.sleep(300)
