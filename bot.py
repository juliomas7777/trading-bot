import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta, timezone

# -------------------------------------------------------------------
# CONFIGURACION - PEGA TUS DATOS AQUI
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

HORA_INICIO = 7
HORA_FIN = 22
TZ = pytz.timezone("Europe/Madrid")

# Configuración de Estrategia
MINIMO_ESTRATEGIAS_ACTIVAS = 5
ATR_SL = 1.4
TP1_MULT = 1.5
TP2_MULT = 2.5
TP3_MULT = 4.0
ADX_MIN = 20
COOLDOWN = 120

# -------------------------------------------------------------------
# ACTIVOS
# -------------------------------------------------------------------
NOMBRES_HUMANOS = {
    "GC=F": "ORO (Gold)", "SI=F": "PLATA (Silver)", "CL=F": "PETROLEO WTI",
    "HG=F": "COBRE", "NG=F": "GAS NATURAL", "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", "USDCAD=X": "USD/CAD",
    "USDCHF=X": "USD/CHF", "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD"
}

ASSETS = {
    "FOREX_USD": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X", "USDCHF=X", "AUDUSD=X", "NZDUSD=X"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"],
    "ACCIONES_US": ["NVDA", "TSLA", "AAPL", "AMZN", "MSFT", "META", "GOOGL"],
    "MATERIAS_PRIMAS": ["GC=F", "SI=F", "CL=F", "HG=F", "NG=F"],
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]
ultima_senal, historial = {}, []
reporte_hecho = False

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------------
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

def en_horario():
    ahora = datetime.now(TZ).hour
    return HORA_INICIO <= ahora < HORA_FIN

def sesion_activa(tipo):
    h = datetime.now(timezone.utc).hour # Corregido para evitar DeprecationWarning
    if tipo == "CRYPTO": return True
    if tipo == "ACCIONES_US": return (14 <= h <= 21)
    if tipo == "MATERIAS_PRIMAS": return (13 <= h <= 20)
    return True

def obtener_datos(simbolo, tf, limite=250):
    rangos = {"5m": "5d", "15m": "15d", "1h": "60d", "4h": "60d"}
    rango = rangos.get(tf, "30d")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={tf}&range={rango}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        js = r.json()
        d = js["chart"]["result"][0]
        q = d["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }).dropna()
        if tf in ["1h", "4h"]: df = df.iloc[:-1]
        return df.tail(limite).reset_index(drop=True)
    except: return None

# -------------------------------------------------------------------
# INDICADORES Y ESTRATEGIAS (Lógica Matemática)
# -------------------------------------------------------------------
def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_rsi(serie, p=14):
    d = serie.diff()
    g, ps = d.clip(lower=0).rolling(p).mean(), (-d.clip(upper=0)).rolling(p).mean()
    rs = g / ps.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(serie):
    e12, e26 = serie.ewm(span=12).mean(), serie.ewm(span=26).mean()
    linea = e12 - e26
    return linea, linea.ewm(span=9).mean(), linea - (linea.ewm(span=9).mean())

def calc_adx(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    hp, lm = h - h.shift(1), l.shift(1) - l
    tr_s = pd.concat([h-l, (h-cp).abs(), (l-cp).abs()], axis=1).max(axis=1).rolling(p).mean()
    dip = 100 * hp.where((hp > lm) & (hp > 0), 0).rolling(p).mean() / tr_s.replace(0, np.nan)
    dim = 100 * lm.where((lm > hp) & (lm > 0), 0).rolling(p).mean() / tr_s.replace(0, np.nan)
    dx = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    return dx.rolling(p).mean()

# Estrategias simplificadas para máxima ejecución
def est_estrategia_video(df):
    if len(df) < 200: return None
    ema50, sma200 = df["close"].ewm(span=50).mean(), df["close"].rolling(200).mean()
    _, _, m_hist = calc_macd(df["close"])
    c, o, l, h = df["close"].iloc[-1], df["open"].iloc[-1], df["low"].iloc[-1], df["high"].iloc[-1]
    if c > sma200.iloc[-1] and abs(l - ema50.iloc[-1]) < (calc_atr(df).iloc[-1]) and c > o: return "COMPRA"
    if c < sma200.iloc[-1] and abs(h - ema50.iloc[-1]) < (calc_atr(df).iloc[-1]) and c < o: return "VENTA"
    return None

def est_ict(df):
    atr = calc_atr(df).iloc[-1]
    for i in range(3, 8):
        h1, l1, h3, l3 = df["high"].iloc[-i-1], df["low"].iloc[-i-1], df["high"].iloc[-i+1], df["low"].iloc[-i+1]
        if l3 > h1 and abs(df["close"].iloc[-i] - df["open"].iloc[-i]) > atr: return "COMPRA"
        if h3 < l1 and abs(df["close"].iloc[-i] - df["open"].iloc[-i]) > atr: return "VENTA"
    return None

def est_adx(df):
    val = calc_adx(df).iloc[-1]
    if val > ADX_MIN:
        return "COMPRA" if df["close"].iloc[-1] > df["close"].ewm(span=50).mean().iloc[-1] else "VENTA"
    return None

def est_rsi(df):
    r = calc_rsi(df["close"]).iloc[-1]
    return "COMPRA" if r < 35 else ("VENTA" if r > 65 else None)

def est_bollinger(df):
    med = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    if df["close"].iloc[-1] < (med - std * 2).iloc[-1]: return "COMPRA"
    if df["close"].iloc[-1] > (med + std * 2).iloc[-1]: return "VENTA"
    return None

ESTRATEGIAS = [
    ("Video Alex", est_estrategia_video), ("ICT FVG", est_ict), 
    ("ADX Trend", est_adx), ("RSI Levels", est_rsi), ("Bollinger", est_bollinger)
]

# -------------------------------------------------------------------
# MOTOR DE ANALISIS
# -------------------------------------------------------------------
def analizar_activo(simbolo, tipo):
    votos = []
    for tf in TIMEFRAMES:
        df = obtener_datos(simbolo, tf)
        if df is not None:
            for n, f in ESTRATEGIAS:
                res = f(df)
                if res: votos.append(res)
    
    if len(votos) >= MINIMO_ESTRATEGIAS_ACTIVAS:
        final = "COMPRA" if votos.count("COMPRA") > votos.count("VENTA") else "VENTA"
        px = obtener_datos(simbolo, "1h")["close"].iloc[-1]
        return f"<b>{simbolo}</b>\nDirección: {final}\nPrecio: {px}\nEstrategias coinciden: {len(votos)}"
    return None

print("Bot Iniciado...")
enviar_telegram("🚀 <b>Bot Activo v3.2 (Sin errores de librerías)</b>")

while True:
    try:
        if en_horario():
            for tipo, simbolos in ASSETS.items():
                if sesion_activa(tipo):
                    for s in simbolos:
                        res = analizar_activo(s, tipo)
                        if res: 
                            enviar_telegram(res)
                            time.sleep(2)
        time.sleep(300)
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(60)
