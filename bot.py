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

# -------------------------------------------------------------------
# ACTIVOS
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

ultima_direccion_enviada = {}

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
        if tf == "4h": df = df.iloc[::4, :].copy() 
        return df.tail(200).reset_index(drop=True)
    except: return None

def calc_atr(df, p=14):
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

# -------------------------------------------------------------------
# ESTRATEGIAS
# -------------------------------------------------------------------
def est_alex_ruiz(df_h1, df_h4):
    sma200_h4 = df_h4["close"].rolling(200).mean().iloc[-1]
    tendencia_h4 = "ALTA" if df_h4["close"].iloc[-1] > sma200_h4 else "BAJA"
    ema50, sma200 = df_h1["close"].ewm(span=50).mean(), df_h1["close"].rolling(200).mean()
    c, o, l, h = df_h1["close"].iloc[-1], df_h1["open"].iloc[-1], df_h1["low"].iloc[-1], df_h1["high"].iloc[-1]
    if tendencia_h4 == "ALTA" and (c > sma200.iloc[-1] and l <= ema50.iloc[-1] and c > o):
        return "COMPRA", 1.4, [1.5, 3.0, 5.0], "MARKET"
    if tendencia_h4 == "BAJA" and (c < sma200.iloc[-1] and h >= ema50.iloc[-1] and c < o):
        return "VENTA", 1.4, [1.5, 3.0, 5.0], "MARKET"
    return None, None, None, None

def est_ict_fvg(df_h1, df_h4):
    h1, l1, h3, l3 = df_h1["high"].iloc[-3], df_h1["low"].iloc[-3], df_h1["high"].iloc[-1], df_h1["low"].iloc[-1]
    tipo, px_ent = None, None
    if l3 > h1: tipo, px_ent = "COMPRA", h1 + (l3 - h1) / 2
    elif h3 < l1: tipo, px_ent = "VENTA", l1 - (l1 - h3) / 2
    if tipo:
        dir_h4 = "COMPRA" if df_h4["close"].iloc[-1] > df_h4["open"].iloc[-1] else "VENTA"
        if tipo == dir_h4: return tipo, 2.0, [2.0, 4.0, 6.0], f"<b>ICT limit</b> ({round(px_ent, 5)})"
    return None, None, None, None

def est_bollinger_rsi(df_h1, df_h4):
    m, s = df_h1["close"].rolling(20).mean(), df_h1["close"].rolling(20).std()
    upper, lower = m + s*2, m - s*2
    d = df_h1["close"].diff()
    rsi = 100 - (100 / (1 + (d.clip(lower=0).rolling(14).mean() / (-d.clip(upper=0)).rolling(14).mean().replace(0, np.nan))))
    rsi4 = (df_h4["close"].diff().clip(lower=0).rolling(14).mean() / df_h4["close"].diff().abs().rolling(14).mean()) * 100
    if df_h1["close"].iloc[-1] < lower.iloc[-1] and rsi.iloc[-1] < 30 and rsi4.iloc[-1] < 50: return "COMPRA", 1.2, [1.2, 2.0, 3.0], "MARKET"
    if df_h1["close"].iloc[-1] > upper.iloc[-1] and rsi.iloc[-1] > 70 and rsi4.iloc[-1] > 50: return "VENTA", 1.2, [1.2, 2.0, 3.0], "MARKET"
    return None, None, None, None

MODULOS = [("ALEX RUIZ", est_alex_ruiz), ("ICT FVG", est_ict_fvg), ("BOLLINGER + RSI", est_bollinger_rsi)]

# -------------------------------------------------------------------
# PROCESAMIENTO CON AGRUPACIÓN
# -------------------------------------------------------------------
def procesar_activo(ticker, nombre_claro):
    df_h1 = obtener_datos(ticker, "1h")
    df_h4 = obtener_datos(ticker, "4h")
    if df_h1 is None or df_h4 is None: return

    res_compra = []
    res_venta = []
    
    # 1. Analizar todas las estrategias para este activo
    for nombre_est, func in MODULOS:
        res, m_sl, tps, ejec = func(df_h1, df_h4)
        if res == "COMPRA":
            res_compra.append({"est": nombre_est, "m_sl": m_sl, "tps": tps, "ejec": ejec})
        elif res == "VENTA":
            res_venta.append({"est": nombre_est, "m_sl": m_sl, "tps": tps, "ejec": ejec})

    # 2. Función para disparar mensajes
    def disparar(lista_señales, direccion):
        num = len(lista_señales)
        if num == 0: return
        
        # Filtro: No repetir la misma confluencia en el mismo activo
        id_msg = f"{ticker}_{direccion}_{num}"
        if ultima_direccion_enviada.get(ticker) == id_msg: return

        px_mercado = df_h1["close"].iloc[-1]
        atr = calc_atr(df_h1).iloc[-1]

        # Construcción del Mensaje
        header = "⚠️⚠️⚠️⚠️\n" if num >= 2 else "🔔 <b>NUEVA SEÑAL</b>\n"
        sub_header = f"<b>CONFLUENCIA: {num} ESTRATEGIAS</b>\n" if num >= 2 else ""
        
        msg = f"{header}{sub_header}"
        msg += f"📊 <b>ACTIVO: {nombre_claro}</b>\n"
        msg += f"📢 <b>DIRECCIÓN: {direccion}</b>\n"
        msg += "━━━━━━━━━━━━━━━━\n"

        for s in lista_señales:
            ent = px_mercado if "limit" not in s["ejec"] else float(s["ejec"].split("(")[1].split(")")[0])
            sl = ent - (atr * s["m_sl"]) if direccion == "COMPRA" else ent + (atr * s["m_sl"])
            msg += f"🚀 <b>{s['est']}</b>\n"
            msg += f"└ Ejec: {s['ejec']}\n"
            msg += f"└ SL Sugerido: {round(sl, 5)}\n\n"

        msg += "━━━━━━━━━━━━━━━━\n"
        msg += f"💡 <i>Precio actual: {round(px_mercado, 5)}</i>"
        
        enviar_telegram(msg)
        ultima_direccion_enviada[ticker] = id_msg

    # Disparar si hay algo
    disparar(res_compra, "COMPRA")
    disparar(res_venta, "VENTA")

# -------------------------------------------------------------------
# BUCLE PRINCIPAL
# -------------------------------------------------------------------
print("Bot Inteligente activo. Agrupando señales coincidentes...")

while True:
    ahora = datetime.now(TZ)
    if HORA_INICIO <= ahora.hour < HORA_FIN:
        if ahora.minute in [14, 29, 44, 59] and ahora.second == 30:
            for ticker, nombre_claro in ASSETS_MAP.items():
                procesar_activo(ticker, nombre_claro)
                time.sleep(0.3)
            time.sleep(40) 
    time.sleep(1)
