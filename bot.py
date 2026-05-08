import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta

# -------------------------------------------------------------------
# CONFIGURACION
# -------------------------------------------------------------------
TG_TOKEN   = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID    = "541470482"

HORA_INICIO = 7
HORA_FIN    = 22
TZ          = pytz.timezone("Europe/Madrid")

# Configuración de Estrategia
MINIMO_ESTRATEGIAS_ACTIVAS = 5
ATR_SL   = 1.4
TP1_MULT = 1.5
TP2_MULT = 2.5
TP3_MULT = 4.0
ADX_MIN  = 20
COOLDOWN = 120

# -------------------------------------------------------------------
# ACTIVOS (SOLO USD Y NOMBRES PARA HUMANOS)
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
    "FOREX_USD":[
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCAD=X", "USDCHF=X", "AUDUSD=X", "NZDUSD=X"
    ],
    "CRYPTO":[
        "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"
    ],
    "ACCIONES_US":[
        "NVDA", "TSLA", "AAPL", "AMZN", "MSFT", "META", "GOOGL"
    ],
    "MATERIAS_PRIMAS":[
        "GC=F", "SI=F", "CL=F", "HG=F", "NG=F"
    ],
}

TIMEFRAMES =["5m", "15m", "1h", "4h"]

ultima_senal = {}
historial    =[]
reporte_hecho = False

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES (TELEGRAM, DATOS, SESIONES)
# -------------------------------------------------------------------
def enviar_telegram(mensaje):
    url     = "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("Error Telegram: " + str(e))

def en_horario():
    ahora = datetime.now(TZ).hour
    return HORA_INICIO <= ahora < HORA_FIN

def sesion_activa(tipo):
    h = datetime.utcnow().hour
    m = datetime.utcnow().minute
    if tipo == "CRYPTO": return True
    if tipo == "ACCIONES_US": return (14 <= h <= 20)
    if tipo == "MATERIAS_PRIMAS": return (13 <= h <= 19)
    return True # Forex USD

def cooldown_ok(simbolo):
    if simbolo not in ultima_senal: return True
    minutos = (datetime.now() - ultima_senal[simbolo]).total_seconds() / 60
    return minutos >= COOLDOWN

def obtener_datos(simbolo, tf, limite=250):
    rangos = {"5m": "5d", "15m": "15d", "1h": "60d", "4h": "60d"}
    rango  = rangos.get(tf, "30d")
    url    = "https://query1.finance.yahoo.com/v8/finance/chart/" + simbolo + "?interval=" + tf + "&range=" + rango
    try:
        r  = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        js = r.json()
        d  = js["chart"]["result"][0]
        q  = d["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open":   q["open"],
            "high":   q["high"],
            "low":    q["low"],
            "close":  q["close"],
            "volume": q.get("volume", [0] * len(q["close"])),
        }).dropna(subset=["open", "high", "low", "close"])
        if tf in ["1h", "4h"]: df = df.iloc[:-1]
        return df.tail(limite).reset_index(drop=True)
    except Exception as e:
        print("  [datos] " + simbolo + " " + tf + ": " + str(e))
        return None

# -------------------------------------------------------------------
# INDICADORES
# -------------------------------------------------------------------
def calc_atr(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_rsi(serie, p=14):
    d = serie.diff(); g = d.clip(lower=0).rolling(p).mean(); ps = (-d.clip(upper=0)).rolling(p).mean()
    rs = g / ps.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(serie):
    e12 = serie.ewm(span=12, adjust=False).mean(); e26 = serie.ewm(span=26, adjust=False).mean()
    linea = e12 - e26; senal = linea.ewm(span=9, adjust=False).mean()
    return linea, senal, linea - senal

def calc_adx(df, p=14):
    h, l, cp = df["high"], df["low"], df["close"].shift(1)
    hp, lm = h - h.shift(1), l.shift(1) - l
    dmp = hp.where((hp > lm) & (hp > 0), 0.0); dmm = lm.where((lm > hp) & (lm > 0), 0.0)
    tr_s = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1).rolling(p).mean()
    dip = 100 * dmp.rolling(p).mean() / tr_s.replace(0, np.nan)
    dim = 100 * dmm.rolling(p).mean() / tr_s.replace(0, np.nan)
    dx = 100 * (dip - dim).abs() / (dip + dim).replace(0, np.nan)
    return dx.rolling(p).mean()

def calc_ema(serie, p): return serie.ewm(span=p, adjust=False).mean()

def calc_bollinger(df, p=20, d=2.0):
    med = df["close"].rolling(p).mean(); std = df["close"].rolling(p).std()
    return med + d * std, med, med - d * std

def calc_stoch_rsi(df, p=14):
    rsi_s = calc_rsi(df["close"], p); min_r, max_r = rsi_s.rolling(p).min(), rsi_s.rolling(p).max()
    stoch = (rsi_s - min_r) / (max_r - min_r).replace(0, np.nan) * 100
    k = stoch.rolling(3).mean(); d_l = k.rolling(3).mean()
    return k, d_l

def calc_pivotes(df, n=5):
    highs, lows = df["high"].values, df["low"].values
    res, sop = [],[]
    for i in range(n, len(df) - n):
        if all(highs[i] >= highs[i-j] for j in range(1, n+1)) and all(highs[i] >= highs[i+j] for j in range(1, n+1)): res.append(highs[i])
        if all(lows[i] <= lows[i-j] for j in range(1, n+1)) and all(lows[i] <= lows[i+j] for j in range(1, n+1)): sop.append(lows[i])
    return {"res": sorted(set(res))[-4:], "sop": sorted(set(sop))[:4]}

# -------------------------------------------------------------------
# ESTRATEGIAS
# -------------------------------------------------------------------

def est_estrategia_video(df):
    """
    Estrategia extraída del análisis del vídeo de Alex Ruiz.
    Usa EMA50, SMA200, MACD y Acción del precio (Envolventes / Breakout visual).
    """
    if len(df) < 200: return None
    
    close_p = df["close"]
    open_p  = df["open"]
    high_p  = df["high"]
    low_p   = df["low"]
    
    # 1. Indicadores principales
    ema50  = close_p.ewm(span=50, adjust=False).mean()
    sma200 = close_p.rolling(window=200).mean() # Especifica claramente que es SIMPLE
    macd_line, macd_sig, macd_hist = calc_macd(close_p)
    
    # Manejo de nulos para seguridad
    if pd.isna(sma200.iloc[-1]) or pd.isna(macd_hist.iloc[-1]): return None
    
    # 2. Tolerancia del pullback basada en ATR
    atr_val = calc_atr(df, 14).iloc[-1]
    tol = atr_val * 0.4 if not pd.isna(atr_val) else 0.001
    
    # Valores actuales y vela anterior
    c0, c1 = close_p.iloc[-1], close_p.iloc[-2]
    o0, o1 = open_p.iloc[-1], open_p.iloc[-2]
    l0, l1 = low_p.iloc[-1], low_p.iloc[-2]
    h0, h1 = high_p.iloc[-1], high_p.iloc[-2]
    
    # 3. Modelado de Ruptura de Diagonal/Patrón (Envolventes)
    envolvente_alcista = (c1 < o1) and (c0 > o0) and (c0 >= o1) and (o0 <= c1)
    envolvente_bajista = (c1 > o1) and (c0 < o0) and (c0 <= o1) and (o0 >= c1)
    
    hist0, hist1 = macd_hist.iloc[-1], macd_hist.iloc[-2]
    ema50_0, sma200_0 = ema50.iloc[-1], sma200.iloc[-1]
    ema50_1, sma200_1 = ema50.iloc[-2], sma200.iloc[-2]

    # Lógica de COMPRA
    if c0 > sma200_0: # Tendencia macro Alcista
        # Condición de Pullback (toca o casi toca EMA50 o SMA200)
        pullback = (abs(l0 - ema50_0) < tol) or (abs(l1 - ema50_1) < tol) or \
                   (abs(l0 - sma200_0) < tol) or (abs(l1 - sma200_1) < tol)
        
        # Confirmaciones: Envolvente (gatillo) y Momentum MACD subiendo
        if pullback and envolvente_alcista and (hist0 > hist1):
            return "COMPRA"

    # Lógica de VENTA
    if c0 < sma200_0: # Tendencia macro Bajista
        pullback = (abs(h0 - ema50_0) < tol) or (abs(h1 - ema50_1) < tol) or \
                   (abs(h0 - sma200_0) < tol) or (abs(h1 - sma200_1) < tol)
                   
        if pullback and envolvente_bajista and (hist0 < hist1):
            return "VENTA"
            
    return None

def est_ema(df):
    if len(df) < 200: return None
    e20, e50, e200, px = calc_ema(df["close"], 20).iloc[-1], calc_ema(df["close"], 50).iloc[-1], calc_ema(df["close"], 200).iloc[-1], df["close"].iloc[-1]
    if px > e20 > e50 > e200: return "COMPRA"
    if px < e20 < e50 < e200: return "VENTA"
    return None

def est_adx(df):
    val = calc_adx(df).iloc[-1]
    if pd.isna(val) or val < ADX_MIN: return None
    e20, e50 = calc_ema(df["close"], 20).iloc[-1], calc_ema(df["close"], 50).iloc[-1]
    return "COMPRA" if e20 > e50 else "VENTA"

def est_rsi_div(df):
    rsi_s, px, n = calc_rsi(df["close"]), df["close"], 12
    if (px.iloc[-5:].min() < px.iloc[-n:-5].min() and rsi_s.iloc[-5:].min() > rsi_s.iloc[-n:-5].min() and rsi_s.iloc[-1] < 48): return "COMPRA"
    if (px.iloc[-5:].max() > px.iloc[-n:-5].max() and rsi_s.iloc[-5:].max() < rsi_s.iloc[-n:-5].max() and rsi_s.iloc[-1] > 52): return "VENTA"
    return None

def est_stoch_rsi(df):
    k, d = calc_stoch_rsi(df)
    kv, dv, kv_a, dv_a = k.iloc[-1], d.iloc[-1], k.iloc[-2], d.iloc[-2]
    if kv_a < dv_a and kv > dv and kv < 40: return "COMPRA"
    if kv_a > dv_a and kv < dv and kv > 60: return "VENTA"
    return None

def est_bollinger(df):
    sup, med, inf = calc_bollinger(df); px, px_ant = df["close"].iloc[-1], df["close"].iloc[-2]
    rsi_v = calc_rsi(df["close"]).iloc[-1]
    if (px <= inf.iloc[-1] and rsi_v < 35) or (px_ant < inf.iloc[-2] and px > inf.iloc[-1]): return "COMPRA"
    if (px >= sup.iloc[-1] and rsi_v > 65) or (px_ant > sup.iloc[-2] and px < sup.iloc[-1]): return "VENTA"
    return None

def est_velas(df):
    v, v_ant, atr_v = df.iloc[-1], df.iloc[-2], calc_atr(df).iloc[-1]
    cuerpo = abs(v["close"] - v["open"])
    if (v["close"] > v["open"] and v_ant["close"] < v_ant["open"] and v["close"] >= v_ant["open"] and cuerpo >= atr_v * 0.6): return "COMPRA"
    if (v["close"] < v["open"] and v_ant["close"] > v_ant["open"] and v["close"] <= v_ant["open"] and cuerpo >= atr_v * 0.6): return "VENTA"
    return None

def est_sr(df):
    niveles, px, atr_v = calc_pivotes(df), df["close"].iloc[-1], calc_atr(df).iloc[-1]
    tol = atr_v * 0.4
    for s in niveles["sop"]:
        if abs(px - s) <= tol: return "COMPRA"
    for r in niveles["res"]:
        if abs(px - r) <= tol: return "VENTA"
    return None

def est_macd(df):
    m, s, h = calc_macd(df["close"])
    if m.iloc[-2] < s.iloc[-2] and m.iloc[-1] > s.iloc[-1] and h.iloc[-1] > 0: return "COMPRA"
    if m.iloc[-2] > s.iloc[-2] and m.iloc[-1] < s.iloc[-1] and h.iloc[-1] < 0: return "VENTA"
    return None

def est_canal(df):
    precios = df["close"].values[-60:]; x = np.arange(len(precios))
    slope, intercept = np.polyfit(x, precios, 1)
    linea = slope * x + intercept; desv = np.std(precios - linea); px = precios[-1]
    if px <= (linea[-1] - desv * 2.0) * 1.001 and slope > 0: return "COMPRA"
    if px >= (linea[-1] + desv * 2.0) * 0.999 and slope < 0: return "VENTA"
    return None

ESTRATEGIAS =[
    ("Estrategia Alex Ruiz", est_estrategia_video), # Añadido el sistema del vídeo aquí
    ("EMA 20/50/200", est_ema), ("ADX Fuerza", est_adx), ("Divergencia RSI", est_rsi_div),
    ("Stochastic RSI", est_stoch_rsi), ("Bollinger Bands", est_bollinger), ("Patron de Velas", est_velas),
    ("Soporte/Resistencia", est_sr), ("MACD Cruce", est_macd), ("Canal Regresion", est_canal),
]

# -------------------------------------------------------------------
# MOTOR DE ANALISIS
# -------------------------------------------------------------------
def analizar_df(df):
    resultados = {}
    for nombre, funcion in ESTRATEGIAS:
        try: resultados[nombre] = funcion(df)
        except: resultados[nombre] = None
    activas = {k: v for k, v in resultados.items() if v is not None}
    if len(activas) < MINIMO_ESTRATEGIAS_ACTIVAS: return None, resultados
    direcciones = set(activas.values())
    if len(direcciones) != 1: return None, resultados
    return list(direcciones)[0], resultados

def calcular_posicion(df, direccion):
    px, atr_val, pivotes = df["close"].iloc[-1], calc_atr(df).iloc[-1], calc_pivotes(df)
    if pd.isna(atr_val) or atr_val == 0: return None
    if direccion == "COMPRA":
        sl = min(px - atr_val * ATR_SL, df["low"].iloc[-5:].min())
        riesgo = px - sl
        tp1, tp2, tp3 = px + riesgo * TP1_MULT, px + riesgo * TP2_MULT, px + riesgo * TP3_MULT
        res_v = [r for r in pivotes["res"] if r > px]
        if res_v: tp2 = min(res_v)
    else:
        sl = max(px + atr_val * ATR_SL, df["high"].iloc[-5:].max())
        riesgo = sl - px
        tp1, tp2, tp3 = px - riesgo * TP1_MULT, px - riesgo * TP2_MULT, px - riesgo * TP3_MULT
        sop_v = [s for s in pivotes["sop"] if s < px]
        if sop_v: tp2 = max(sop_v)
    if riesgo <= 0: return None
    return {"entrada": round(px, 5), "sl": round(sl, 5), "tp1": round(tp1, 5), "tp2": round(tp2, 5), "tp3": round(tp3, 5), "rr": round(abs(tp2-px)/riesgo, 2), "atr": round(atr_val, 5)}

def analizar_activo(simbolo, tipo):
    datos, dirs, todos = {}, {}, {}
    for tf in TIMEFRAMES:
        df = obtener_datos(simbolo, tf)
        if df is None or len(df) < 60: continue
        direccion, resultados = analizar_df(df)
        datos[tf], dirs[tf], todos[tf] = df, direccion, resultados
    tfs_ok =[tf for tf, d in dirs.items() if d is not None]
    if len(tfs_ok) < 2: return None
    if len(set(dirs[tf] for tf in tfs_ok)) != 1: return None
    direccion_final = list(set(dirs[tf] for tf in tfs_ok))[0]
    pos = calcular_posicion(datos[tfs_ok[-1]], direccion_final)
    if not pos: return None
    return {"simbolo": simbolo, "tipo": tipo, "direccion": direccion_final, "tfs_ok": tfs_ok, "tf_entrada": tfs_ok[-1], "todos": todos[tfs_ok[-1]], "posicion": pos, "adx": round(calc_adx(datos[tfs_ok[-1]]).iloc[-1], 1), "rsi": round(calc_rsi(datos[tfs_ok[-1]]["close"]).iloc[-1], 1), "hora": datetime.now(TZ).strftime("%d/%m/%Y %H:%M CET")}

def formatear_mensaje(r):
    d, p, todos = r["direccion"], r["posicion"], r["todos"]
    nombre_activo = NOMBRES_HUMANOS.get(r["simbolo"], r["simbolo"])
    
    # Se reemplaza el círculo blanco problemático por el símbolo de interrogación (?) 
    confirmaciones = "\n".join([("✅ " if todos.get(n) == d else ("❌ " if todos.get(n) is not None else "❔ ")) + n for n, _ in ESTRATEGIAS])
    
    icono_dir = "🟢" if d == "COMPRA" else "🔴"
    return (icono_dir + " <b>SENAL DE " + d + " - " + nombre_activo + "</b> " + icono_dir + "\n\n"
            "<b>Activo:</b> " + nombre_activo + " (" + r["tipo"] + ")\n<b>Timeframes OK:</b> " + ", ".join(r["tfs_ok"]) + "\n"
            "<b>TF Entrada:</b> " + r["tf_entrada"].upper() + "\n"
            "━━━━━━━━━━━━━━━━\n"
            "💰 <b>ENTRADA:</b>    " + str(p["entrada"]) + "\n🛑 <b>STOP LOSS:</b> " + str(p["sl"]) + "\n"
            "🎯 <b>TP1 (40%):</b> " + str(p["tp1"]) + "[1:" + str(TP1_MULT) + "]\n🎯 <b>TP2 (40%):</b> " + str(p["tp2"]) + " [1:" + str(p["rr"]) + "]\n🎯 <b>TP3 (20%):</b> " + str(p["tp3"]) + "[1:" + str(TP3_MULT) + "]\n"
            "━━━━━━━━━━━━━━━━\n"
            "<b>ADX:</b> " + str(r["adx"]) + " | <b>RSI:</b> " + str(r["rsi"]) + "\n<b>ATR:</b> " + str(p["atr"]) + "\n"
            "━━━━━━━━━━━━━━━━\n<b>Confirmaciones (" + str(len(ESTRATEGIAS)) + " sistemas):</b>\n"
            + confirmaciones + "\n━━━━━━━━━━━━━━━━\n"
            "💡 TP1 cierra 40% · TP2 cierra 40% · TP3 cierra 20%\n"
            "🕒 " + r["hora"] + "\n<i>Senal enviada solo cuando TODAS las estrategias coinciden</i>")

# -------------------------------------------------------------------
# BUCLE
# -------------------------------------------------------------------
print("Bot de Trading v3.0 iniciado.")
enviar_telegram("🚀 <b>Bot de Senales v3.0 ACTIVO</b>")

while True:
    try:
        ahora = datetime.now(TZ)
        if ahora.hour == HORA_FIN and not reporte_hecho:
            enviar_telegram("📊 <b>Reporte Diario Finalizado.</b>")
            reporte_hecho = True
        if ahora.hour == HORA_INICIO: reporte_hecho = False
        
        if not en_horario():
            time.sleep(300); continue

        for tipo, simbolos in ASSETS.items():
            if not sesion_activa(tipo): continue
            for simbolo in simbolos:
                if not cooldown_ok(simbolo): continue
                print("[" + datetime.now(TZ).strftime("%H:%M") + "] Analizando " + simbolo + "...")
                resultado = analizar_activo(simbolo, tipo)
                if resultado:
                    enviar_telegram(formatear_mensaje(resultado))
                    ultima_senal[simbolo] = datetime.now()
                    historial.append({"simbolo": simbolo, "dir": resultado["direccion"], "tf": resultado["tf_entrada"], "hora": resultado["hora"], "fecha": str(datetime.now(TZ).date())})
                time.sleep(2)
        time.sleep(60)
    except Exception as e:
        print("Error: " + str(e)); time.sleep(30)
