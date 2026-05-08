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
# ACTIVOS (QUANTFURY - NOMENCLATURA CLARA)
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
    intervalo = "1h"
    rango = "30d" if tf == "1h" else "60d"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range={rango}"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        df = pd.DataFrame({"open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]}).dropna()
        if tf == "4h":
            df = df.iloc[::4, :].copy() 
        return df.tail(200).reset_index(drop=True)
    except: return None

def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

# -------------------------------------------------------------------
# ESTRATEGIAS (2/2 + TP ESPECÍFICOS)
# -------------------------------------------------------------------

def est_alex_ruiz(df_h1, df_h4):
    """Estrategia de Tendencia: Busca recorridos largos"""
    sma200_h4 = df_h4["close"].rolling(200).mean().iloc[-1]
    tendencia_h4 = "ALTA" if df_h4["close"].iloc[-1] > sma200_h4 else "BAJA"
    
    ema50 = df_h1["close"].ewm(span=50).mean()
    sma200 = df_h1["close"].rolling(200).mean()
    c, o, l, h = df_h1["close"].iloc[-1], df_h1["open"].iloc[-1], df_h1["low"].iloc[-1], df_h1["high"].iloc[-1]
    
    if tendencia_h4 == "ALTA" and (c > sma200.iloc[-1] and l <= ema50.iloc[-1] and c > o):
        # TP1: 1:1.5 | TP2: 1:3 | TP3: 1:5 (Estructura tendencial)
        return "COMPRA", 1.4, [1.5, 3.0, 5.0]
    if tendencia_h4 == "BAJA" and (c < sma200.iloc[-1] and h >= ema50.iloc[-1] and c < o):
        return "VENTA", 1.4, [1.5, 3.0, 5.0]
    return None, None, None

def est_ict_fvg(df_h1, df_h4):
    """Estrategia Smart Money: Busca desequilibrios rápidos"""
    h1, l1, h3, l3 = df_h1["high"].iloc[-3], df_h1["low"].iloc[-3], df_h1["high"].iloc[-1], df_h1["low"].iloc[-1]
    fvg_h1 = "COMPRA" if l3 > h1 else ("VENTA" if h3 < l1 else None)
    
    if fvg_h1:
        dir_h4 = "COMPRA" if df_h4["close"].iloc[-1] > df_h4["open"].iloc[-1] else "VENTA"
        if fvg_h1 == dir_h4:
            # TP1: 1:2 | TP2: 1:4 | TP3: 1:6 (Expansión FVG)
            return fvg_h1, 2.0, [2.0, 4.0, 6.0]
    return None, None, None

def est_bollinger_rsi(df_h1, df_h4):
    """Estrategia de Reversión: TP más ajustados por ser contratendencia local"""
    m, s = df_h1["close"].rolling(20).mean(), df_h1["close"].rolling(20).std()
    upper, lower = m + s*2, m - s*2
    d = df_h1["close"].diff()
    g, ps = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (g / ps.replace(0, np.nan))))
    
    d4 = df_h4["close"].diff()
    g4, ps4 = d4.clip(lower=0).rolling(14).mean(), (-d4.clip(upper=0)).rolling(14).mean()
    rsi4 = 100 - (100 / (1 + (g4 / ps4.replace(0, np.nan))))
    
    if df_h1["close"].iloc[-1] < lower.iloc[-1] and rsi.iloc[-1] < 30 and rsi4.iloc[-1] < 50:
        # TP1: 1:1.2 | TP2: 1:2 | TP3: 1:3 (Objetivos más cortos por ser reversión)
        return "COMPRA", 1.2, [1.2, 2.0, 3.0]
    if df_h1["close"].iloc[-1] > upper.iloc[-1] and rsi.iloc[-1] > 70 and rsi4.iloc[-1] > 50:
        return "VENTA", 1.2, [1.2, 2.0, 3.0]
    return None, None, None

MODULOS = [("ALEX RUIZ", est_alex_ruiz), ("ICT FVG", est_ict_fvg), ("BOLLINGER + RSI", est_bollinger_rsi)]

# -------------------------------------------------------------------
# MOTOR DE EJECUCIÓN
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_h1 = obtener_datos(ticker, "1h")
    df_h4 = obtener_datos(ticker, "4h")
    if df_h1 is None or df_h4 is None: return

    for nombre_est, func in MODULOS:
        id_senal = f"{ticker}_{nombre_est}"
        resultado, m_sl, lista_tps = func(df_h1, df_h4)
        
        if resultado:
            ahora = datetime.now()
            if id_senal in historial_senales:
                if (ahora - historial_senales[id_senal]).total_seconds() < COOLDOWN_MINUTOS * 60:
                    continue

            px = df_h1["close"].iloc[-1]
            atr = calc_atr(df_h1).iloc[-1]
            
            distancia_sl = atr * m_sl
            sl = px - distancia_sl if resultado == "COMPRA" else px + distancia_sl
            
            # Cálculo de los 3 TPs personalizados por estrategia
            tps_finales = []
            for m_tp in lista_tps:
                tp_val = px + (distancia_sl * m_tp) if resultado == "COMPRA" else px - (distancia_sl * m_tp)
                tps_finales.append(round(tp_val, 5))
            
            historial_senales[id_senal] = ahora
            
            msg = (f"🚀 <b>ESTRATEGIA: {nombre_est}</b>\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"📊 <b>Activo:</b> {nombre_claro}\n"
                   f"⏱ <b>Timeframe:</b> H1 + H4 (2/2)\n"
                   f"📢 <b>Señal:</b> {resultado}\n"
                   f"💰 <b>Entrada:</b> {round(px, 5)}\n"
                   f"🛑 <b>Stop Loss:</b> {round(sl, 5)}\n"
                   f"━━━━━━━━━━━━━━━━\n"
                   f"🎯 <b>TP 1:</b> {tps_finales[0]} (Ratio 1:{lista_tps[0]})\n"
                   f"🎯 <b>TP 2:</b> {tps_finales[1]} (Ratio 1:{lista_tps[1]})\n"
                   f"🎯 <b>TP 3:</b> {tps_finales[2]} (Ratio 1:{lista_tps[2]})\n"
                   f"━━━━━━━━━━━━━━━━")
            enviar_telegram(msg)

print("Bot Avanzado: TPs personalizados por estrategia y filtro 2/2 activado.")
while True:
    h = datetime.now(TZ).hour
    if HORA_INICIO <= h < HORA_FIN:
        for ticker, nombre_claro in ASSETS_MAP.items():
            procesar_activo(ticker, nombre_claro)
            time.sleep(1.5)
    time.sleep(300)
