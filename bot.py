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
# ACTIVOS CON NOMENCLATURA CLARA
# -------------------------------------------------------------------
ASSETS_MAP = {
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "^GDAXI": "DAX 40", "NVDA": "NVIDIA",
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY", "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

historial_senales = {}

# -------------------------------------------------------------------
# FUNCIONES TÉCNICAS
# -------------------------------------------------------------------
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}, timeout=10)
    except: pass

def obtener_datos(simbolo, tf="1h"):
    # tf puede ser 1h o 4h
    intervalo = "1h" if tf == "1h" else "1h" # Yahoo no siempre da 4h limpia, simulamos con agregación si fuera necesario
    rango = "30d" if tf == "1h" else "60d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range={rango}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}).dropna()
        if tf == "4h":
            # Agrupamos de 4 en 4 para simular H4 real
            df = df.iloc[::4, :].copy()
        return df.tail(200).reset_index(drop=True)
    except: return None

def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

# -------------------------------------------------------------------
# ESTRATEGIAS CON CORRELACIÓN DE TIMEFRAMES
# -------------------------------------------------------------------

def est_alex_ruiz(df_h1, df_h4):
    # Tendencia H4
    sma200_h4 = df_h4["close"].rolling(200).mean().iloc[-1]
    tendencia_h4 = "ALTA" if df_h4["close"].iloc[-1] > sma200_h4 else "BAJA"
    
    # Señal H1
    ema50 = df_h1["close"].ewm(span=50).mean()
    sma200 = df_h1["close"].rolling(200).mean()
    c, o, l, h = df_h1["close"].iloc[-1], df_h1["open"].iloc[-1], df_h1["low"].iloc[-1], df_h1["high"].iloc[-1]
    
    if c > sma200.iloc[-1] and l <= ema50.iloc[-1] and c > o and tendencia_h4 == "ALTA":
        return "COMPRA", 1.4, 1.5, 2 # Resultado, SL, TP, Coincidencias (H1+H4)
    if c < sma200.iloc[-1] and h >= ema50.iloc[-1] and c < o and tendencia_h4 == "BAJA":
        return "VENTA", 1.4, 1.5, 2
    return None, None, None, 0

def est_ict_fvg(df_h1, df_h4):
    h1, l1, h3, l3 = df_h1["high"].iloc[-3], df_h1["low"].iloc[-3], df_h1["high"].iloc[-1], df_h1["low"].iloc[-1]
    # Filtro H4: El cierre actual debe estar a favor de la vela de 4H anterior
    fvg_h1 = None
    if l3 > h1: fvg_h1 = "COMPRA"
    if h3 < l1: fvg_h1 = "VENTA"
    
    if fvg_h1:
        dir_h4 = "COMPRA" if df_h4["close"].iloc[-1] > df_h4["open"].iloc[-1] else "VENTA"
        coincide = 2 if fvg_h1 == dir_h4 else 1
        return fvg_h1, 2.0, 2.0, coincide
    return None, None, None, 0

def est_bollinger_rsi(df_h1, df_h4):
    m, s = df_h1["close"].rolling(20).mean(), df_h1["close"].rolling(20).std()
    upper, lower = m + s*2, m - s*2
    d = df_h1["close"].diff()
    g, ps = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (g / ps.replace(0, np.nan))))
    
    res = None
    if df_h1["close"].iloc[-1] < lower.iloc[-1] and rsi.iloc[-1] < 30: res = "COMPRA"
    if df_h1["close"].iloc[-1] > upper.iloc[-1] and rsi.iloc[-1] > 70: res = "VENTA"
    
    if res:
        # RSI H4 para evitar contratendencia fuerte
        d4 = df_h4["close"].diff()
        g4, ps4 = d4.clip(lower=0).rolling(14).mean(), (-d4.clip(upper=0)).rolling(14).mean()
        rsi4 = 100 - (100 / (1 + (g4 / ps4.replace(0, np.nan))))
        coincide = 2 if (res == "COMPRA" and rsi4.iloc[-1] < 50) or (res == "VENTA" and rsi4.iloc[-1] > 50) else 1
        return res, 1.2, 2.0, coincide
    return None, None, None, 0

MODULOS = [("ALEX RUIZ", est_alex_ruiz), ("ICT FVG", est_ict_fvg), ("BOLLINGER + RSI", est_bollinger_rsi)]

# -------------------------------------------------------------------
# MOTOR
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_h1 = obtener_datos(ticker, "1h")
    df_h4 = obtener_datos(ticker, "4h")
    if df_h1 is None or df_h4 is None: return

    for nombre_est, func in MODULOS:
        id_senal = f"{ticker}_{nombre_est}"
        resultado, m_sl, m_tp, coinc_tf = func(df_h1, df_h4)
        
        if resultado:
            ahora = datetime.now()
            if id_senal in historial_senales:
                if (ahora - historial_senales[id_senal]).total_seconds() < COOLDOWN_MINUTOS * 60:
                    continue

            px = df_h1["close"].iloc[-1]
            atr = calc_atr(df_h1).iloc[-1]
            distancia_sl = atr * m_sl
            sl = px - distancia_sl if resultado == "COMPRA" else px + distancia_sl
            tp = px + (distancia_sl * m_tp) if resultado == "COMPRA" else px - (distancia_sl * m_tp)
            
            historial_senales[id_senal] = ahora
            
            msg = (f"🚀 <b>ESTRATEGIA: {nombre_est}</b>\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"📊 <b>Activo:</b> {nombre_claro}\n"
                   f"⏱ <b>Timeframe:</b> H1 (Confirmación en H4)\n"
                   f"🔗 <b>Coincidencia TF:</b> {coinc_tf} de 2\n"
                   f"📢 <b>Señal:</b> {resultado}\n"
                   f"💰 <b>Precio:</b> {round(px, 5)}\n"
                   f"🛑 <b>SL:</b> {round(sl, 5)} | 🎯 <b>TP:</b> {round(tp, 5)}\n"
                   f"━━━━━━━━━━━━━━━━")
            enviar_telegram(msg)

print("Bot Iniciado: Correlación H1/H4 activada...")
while True:
    h = datetime.now(TZ).hour
    if HORA_INICIO <= h < HORA_FIN:
        for ticker, nombre_claro in ASSETS_MAP.items():
            procesar_activo(ticker, nombre_claro)
            time.sleep(1)
    time.sleep(300)
