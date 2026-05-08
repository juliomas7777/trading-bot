import os
import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Cargar variables de entorno de forma segura
load_dotenv()

# -------------------------------------------------------------------
# CONFIGURACION
# -------------------------------------------------------------------
TG_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

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
    "GC=F": "ORO (Gold)",
    "SI=F": "PLATA (Silver)",
    "CL=F": "PETROLEO WTI",
    "HG=F": "COBRE",
    "NG=F": "GAS NATURAL",
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCAD=X": "USD/CAD",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "NZDUSD=X": "NZD/USD"
}

ASSETS = {
    "FOREX_USD": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X", "USDCHF=X", "AUDUSD=X", "NZDUSD=X"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"],
    "ACCIONES_US": ["NVDA", "TSLA", "AAPL", "AMZN", "MSFT", "META", "GOOGL"],
    "MATERIAS_PRIMAS": ["GC=F", "SI=F", "CL=F", "HG=F", "NG=F"],
}

TIMEFRAMES = ["5m", "15m", "1h", "4h"]

ultima_senal = {}
historial = []
reporte_hecho = False

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------------
def enviar_telegram(mensaje):
    if not TG_TOKEN or not CHAT_ID:
        print("Error: No se encontraron los tokens de Telegram en el archivo .env")
        return
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
    h = datetime.now(timezone.utc).hour
    if tipo == "CRYPTO": return True
    if tipo == "ACCIONES_US": return (14 <= h <= 21)
    if tipo == "MATERIAS_PRIMAS": return (13 <= h <= 20)
    return True

def cooldown_ok(simbolo):
    if simbolo not in ultima_senal: return True
    minutos = (datetime.now() - ultima_senal[simbolo]).total_seconds() / 60
    return minutos >= COOLDOWN

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
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "close": q["close"],
            "volume": q.get("volume", [0] * len(q["close"])),
        }).dropna()
        if tf in ["1h", "4h"]:
            df = df.iloc[:-1]
        return df.tail(limite).reset_index(drop=True)
    except Exception as e:
        print(f" [datos] {simbolo} {tf}: {e}")
        return None

# -------------------------------------------------------------------
# INDICADORES (CÁLCULOS MATEMÁTICOS)
# -------------------------------------------------------------------
def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_rsi(serie, p=14):
    d = serie.diff()
    g = d.clip(lower=0).rolling(p).mean()
    ps = (-d.clip(upper=0)).rolling(p).mean()
    rs = g / ps.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(serie):
    e12 = serie.ewm(span=12, adjust=False).mean()
    e26 = serie.ewm(span=26, adjust=False).mean()
    linea = e12 - e26
    senal = linea.ewm(span=9, adjust=False).mean()
    return linea, senal, linea - senal

def calc_adx(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    hp, lm = h - h.shift(1), l.shift(1) - l
    dmp = hp.where((hp > lm) & (hp > 0), 0.0)
    dmm = lm.where((lm > hp) & (lm > 0), 0.0)
    tr_s = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1).rolling(p).mean()
    dip = 100 * dmp.rolling(p).mean() / tr_s.replace(0, np.nan)
    dim = 100 * dmm.rolling(p).mean() / tr_s.replace(0, np.nan)
    dx = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    return dx.rolling(p).mean()

def calc_ema(serie, p):
    return serie.ewm(span=p, adjust=False).mean()

def calc_bollinger(df, p=20, d=2.0):
    med = df["close"].rolling(p).mean()
    std = df["close"].rolling(p).std()
    return med + d * std, med, med - d * std

def calc_stoch_rsi(df, p=14):
    rsi_s = calc_rsi(df["close"], p)
    min_r, max_r = rsi_s.rolling(p).min(), rsi_s.rolling(p).max()
    stoch = (rsi_s - min_r) / (max_r - min_r).replace(0, np.nan) * 100
    k = stoch.rolling(3).mean()
    return k, k.rolling(3).mean()

def calc_pivotes(df, n=5):
    highs, lows = df["high"].values, df["low"].values
    res, sop = [], []
    for i in range(n, len(df) - n):
        if all(highs[i] >= highs[i-j] for j in range(1, n+1)) and all(highs[i] >= highs[i+j] for j in range(1, n+1)):
            res.append(highs[i])
        if all(lows[i] <= lows[i-j] for j in range(1, n+1)) and all(lows[i] <= lows[i+j] for j in range(1, n+1)):
            sop.append(lows[i])
    return {"res": sorted(set(res))[-4:], "sop": sorted(set(sop))[:4]}

# -------------------------------------------------------------------
# ESTRATEGIAS LÓGICAS
# -------------------------------------------------------------------
def est_estrategia_video(df):
    if len(df) < 200: return None
    close_p, open_p, high_p, low_p = df["close"], df["open"], df["high"], df["low"]
    ema50, sma200 = calc_ema(close_p, 50), close_p.rolling(200).mean()
    _, _, macd_hist = calc_macd(close_p)
    atr_val = calc_atr(df).iloc[-1]
    tol = atr_val * 1.0
    c0, c1, o0, o1, l0, l1, h0, h1 = close_p.iloc[-1], close_p.iloc[-2], open_p.iloc[-1], open_p.iloc[-2], low_p.iloc[-1], low_p.iloc[-2], high_p.iloc[-1], high_p.iloc[-2]
    
    envolvente_alcista = (c1 < o1 and c0 > o0 and o0 <= c1 and c0 >= o1)
    envolvente_bajista = (c1 > o1 and c0 < o0 and o0 >= c1 and c0 <= o1)

    if c0 > sma200.iloc[-1]:
        if (abs(l0 - ema50.iloc[-1]) < tol or abs(l1 - ema50.iloc[-2]) < tol) and envolvente_alcista and macd_hist.iloc[-1] > macd_hist.iloc[-2]:
            return "COMPRA"
    if c0 < sma200.iloc[-1]:
        if (abs(h0 - ema50.iloc[-1]) < tol or abs(h1 - ema50.iloc[-2]) < tol) and envolvente_bajista and macd_hist.iloc[-1] < macd_hist.iloc[-2]:
            return "VENTA"
    return None

def est_ict(df):
    if len(df) < 15: return None
    atr_val = calc_atr(df).iloc[-1]
    for i in range(3, 11):
        idx1, idx2, idx3 = -(i + 1), -i, -(i - 1)
        h1, l1, h3, l3 = df["high"].iloc[idx1], df["low"].iloc[idx1], df["high"].iloc[idx3], df["low"].iloc[idx3]
        cuerpo2 = abs(df["close"].iloc[idx2] - df["open"].iloc[idx2])
        if l3 > h1 and cuerpo2 >= atr_val:
            if df["low"].iloc[-1] <= l3 and df["close"].iloc[-1] >= h1: return "COMPRA"
        if h3 < l1 and cuerpo2 >= atr_val:
            if df["high"].iloc[-1] >= h3 and df["close"].iloc[-1] <= l1: return "VENTA"
    return None

def est_ema(df):
    if len(df) < 200: return None
    close = df["close"]
    e20, e50, e200 = calc_ema(close, 20), calc_ema(close, 50), calc_ema(close, 200)
    atr_val = calc_atr(df).iloc[-1]
    tol = atr_val * 0.5
    if e20.iloc[-1] > e50.iloc[-1] > e200.iloc[-1]:
        if any(abs(df["low"].iloc[-j] - e20.iloc[-j]) < tol for j in range(1, 4)) and close.iloc[-1] > e20.iloc[-1]:
            return "COMPRA"
    if e20.iloc[-1] < e50.iloc[-1] < e200.iloc[-1]:
        if any(abs(df["high"].iloc[-j] - e20.iloc[-j]) < tol for j in range(1, 4)) and close.iloc[-1] < e20.iloc[-1]:
            return "VENTA"
    return None

def est_adx(df):
    val = calc_adx(df).iloc[-1]
    if pd.isna(val) or val < ADX_MIN: return None
    return "COMPRA" if calc_ema(df["close"], 20).iloc[-1] > calc_ema(df["close"], 50).iloc[-1] else "VENTA"

def est_rsi_div(df):
    rsi_s, px = calc_rsi(df["close"]), df["close"]
    if px.iloc[-5:].min() < px.iloc[-12:-5].min() and rsi_s.iloc[-5:].min() > rsi_s.iloc[-12:-5].min() and rsi_s.iloc[-1] < 48: return "COMPRA"
    if px.iloc[-5:].max() > px.iloc[-12:-5].max() and rsi_s.iloc[-5:].max() < rsi_s.iloc[-12:-5].max() and rsi_s.iloc[-1] > 52: return "VENTA"
    return None

def est_stoch_rsi(df):
    k, d = calc_stoch_rsi(df)
    if k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 40: return "COMPRA"
    if k.iloc[-2] > d.iloc[-2] and k.iloc[-1] < d.iloc[-1] and k.iloc[-1] > 60: return "VENTA"
    return None

def est_bollinger(df):
    sup, _, inf = calc_bollinger(df)
    px, rsi_v = df["close"].iloc[-1], calc_rsi(df["close"]).iloc[-1]
    if (px <= inf.iloc[-1] and rsi_v < 35): return "COMPRA"
    if (px >= sup.iloc[-1] and rsi_v > 65): return "VENTA"
    return None

def est_velas(df):
    v, v_ant = df.iloc[-1], df.iloc[-2]
    atr_v = calc_atr(df).iloc[-1]
    cuerpo = abs(v["close"] - v["open"])
    if v["close"] > v["open"] and v_ant["close"] < v_ant["open"] and v["close"] >= v_ant["open"] and cuerpo >= atr_v * 0.6: return "COMPRA"
    if v["close"] < v["open"] and v_ant["close"] > v_ant["open"] and v["close"] <= v_ant["open"] and cuerpo >= atr_v * 0.6: return "VENTA"
    return None

def est_sr(df):
    niveles, px, tol = calc_pivotes(df), df["close"].iloc[-1], calc_atr(df).iloc[-1] * 0.4
    if any(abs(px - s) <= tol for s in niveles["sop"]): return "COMPRA"
    if any(abs(px - r) <= tol for r in niveles["res"]): return "VENTA"
    return None

def est_macd(df):
    m, s, h = calc_macd(df["close"])
    if m.iloc[-2] < s.iloc[-2] and m.iloc[-1] > s.iloc[-1] and h.iloc[-1] > 0: return "COMPRA"
    if m.iloc[-2] > s.iloc[-2] and m.iloc[-1] < s.iloc[-1] and h.iloc[-1] < 0: return "VENTA"
    return None

def est_canal(df):
    precios = df["close"].values[-60:]
    x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea = slope * x + intercept
    desv = np.std(precios - linea)
    if precios[-1] <= (linea[-1] - desv * 2.0) and slope > 0: return "COMPRA"
    if precios[-1] >= (linea[-1] + desv * 2.0) and slope < 0: return "VENTA"
    return None

ESTRATEGIAS = [
    ("Estrategia Alex Ruiz", est_estrategia_video), ("Estrategia ICT (FVG)", est_ict),
    ("EMA 20/50/200", est_ema), ("ADX Fuerza", est_adx), ("Divergencia RSI", est_rsi_div),
    ("Stochastic RSI", est_stoch_rsi), ("Bollinger Bands", est_bollinger),
    ("Patron de Velas", est_velas), ("Soporte/Resistencia", est_sr),
    ("MACD Cruce", est_macd), ("Canal Regresion", est_canal)
]

# -------------------------------------------------------------------
# MOTOR DE ANALISIS Y GESTIÓN
# -------------------------------------------------------------------
def analizar_df(df):
    resultados = {n: f(df) for n, f in ESTRATEGIAS}
    activas = {k: v for k, v in resultados.items() if v is not None}
    if len(activas) < MINIMO_ESTRATEGIAS_ACTIVAS: return None, resultados
    direcciones = set(activas.values())
    return (list(direcciones)[0], resultados) if len(direcciones) == 1 else (None, resultados)

def calcular_posicion(df, direccion):
    px, atr_val = df["close"].iloc[-1], calc_atr(df).iloc[-1]
    pivotes = calc_pivotes(df)
    if direccion == "COMPRA":
        sl = min(px - atr_val * ATR_SL, df["low"].iloc[-5:].min())
        riesgo = px - sl
        tp1, tp2, tp3 = px + riesgo * TP1_MULT, px + riesgo * TP2_MULT, px + riesgo * TP3_MULT
    else:
        sl = max(px + atr_val * ATR_SL, df["high"].iloc[-5:].max())
        riesgo = sl - px
        tp1, tp2, tp3 = px - riesgo * TP1_MULT, px - riesgo * TP2_MULT, px - riesgo * TP3_MULT
    return {
        "entrada": round(px, 5), "sl": round(sl, 5), "tp1": round(tp1, 5),
        "tp2": round(tp2, 5), "tp3": round(tp3, 5), "rr": round(abs(tp2 - px) / (riesgo if riesgo > 0 else 1), 2),
        "atr": round(atr_val, 5)
    } if riesgo > 0 else None

def analizar_activo(simbolo, tipo):
    datos, dirs, todos = {}, {}, {}
    for tf in TIMEFRAMES:
        df = obtener_datos(simbolo, tf)
        if df is not None and len(df) >= 200:
            direccion, resultados = analizar_df(df)
            datos[tf], dirs[tf], todos[tf] = df, direccion, resultados
    
    tfs_ok = [tf for tf, d in dirs.items() if d is not None]
    if len(tfs_ok) >= 2 and len(set(dirs[tf] for tf in tfs_ok)) == 1:
        direccion_final = dirs[tfs_ok[0]]
        pos = calcular_posicion(datos[tfs_ok[-1]], direccion_final)
        if pos:
            return {
                "simbolo": simbolo, "tipo": tipo, "direccion": direccion_final,
                "tfs_ok": tfs_ok, "tf_entrada": tfs_ok[-1], "todos": todos[tfs_ok[-1]],
                "posicion": pos, "adx": round(calc_adx(datos[tfs_ok[-1]]).iloc[-1], 1),
                "rsi": round(calc_rsi(datos[tfs_ok[-1]]["close"]).iloc[-1], 1),
                "hora": datetime.now(TZ).strftime("%d/%m/%Y %H:%M CET")
            }
    return None

def formatear_mensaje(r):
    d, p, todos = r["direccion"], r["posicion"], r["todos"]
    nombre = NOMBRES_HUMANOS.get(r["simbolo"], r["simbolo"])
    conf = "\n".join([("✅ " if todos.get(n) == d else ("❌ " if todos.get(n) else "❔ ")) + n for n, _ in ESTRATEGIAS])
    icono = "🟢" if d == "COMPRA" else "🔴"
    return (f"{icono} <b>SENAL DE {d} - {nombre}</b> {icono}\n\n"
            f"<b>Activo:</b> {nombre} ({r['tipo']})\n"
            f"<b>Timeframes OK:</b> {', '.join(r['tfs_ok'])}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"💰 <b>ENTRADA:</b> {p['entrada']}\n"
            f"🛑 <b>STOP LOSS:</b> {p['sl']}\n"
            f"🎯 <b>TP1:</b> {p['tp1']}\n"
            f"🎯 <b>TP2:</b> {p['tp2']}\n"
            f"🎯 <b>TP3:</b> {p['tp3']}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<b>Confirmaciones:</b>\n{conf}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🕒 {r['hora']}")

# -------------------------------------------------------------------
# BUCLE PRINCIPAL
# -------------------------------------------------------------------
print("Bot v3.1 Iniciado...")
enviar_telegram("🚀 <b>Bot de Trading v3.1 ACTIVO</b>")

while True:
    try:
        ahora = datetime.now(TZ)
        if en_horario():
            for tipo, simbolos in ASSETS.items():
                if sesion_activa(tipo):
                    for simbolo in simbolos:
                        if cooldown_ok(simbolo):
                            res = analizar_activo(simbolo, tipo)
                            if res:
                                enviar_telegram(formatear_mensaje(res))
                                ultima_senal[simbolo] = datetime.now()
                            time.sleep(1)
        time.sleep(60)
    except Exception as e:
        print(f"Error General: {e}")
        time.sleep(30)
