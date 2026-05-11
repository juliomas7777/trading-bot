import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# ===================================================================
# CONFIGURACIÓN GLOBAL Y DICCIONARIOS
# ===================================================================
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

ASSETS_MAP = {
    "BTC-USD": "BITCOIN", 
    "ETH-USD": "ETHEREUM", 
    "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", 
    "ADA-USD": "CARDANO", 
    "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", 
    "LTC-USD": "LITECOIN", 
    "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", 
    "SPY": "S&P 500", 
    "QQQ": "NASDAQ 100", 
    "^GDAXI": "DAX 40", 
    "NVDA": "NVIDIA",
    "EURUSD=X": "EUR/USD", 
    "GBPUSD=X": "GBP/USD", 
    "USDJPY=X": "USD/JPY", 
    "USDCAD=X": "USD/CAD", 
    "USDCHF=X": "USD/CHF", 
    "AUDUSD=X": "AUD/USD", 
    "NZDUSD=X": "NZD/USD", 
    "GC=F": "ORO"
}

CRYPTO_MACD = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]
señales_enviadas = set()

# Sesión HTTP persistente para evitar bloqueos de IP en Yahoo
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# ===================================================================
# FUNCIONES DE TELEGRAM Y OBTENCIÓN DE DATOS
# ===================================================================
def generar_mensaje_telegram(par, direccion, ent, sl, tp1, tp2=None, tp3=None, nombre_est="", marco="", tipo_orden="MARKET"):
    if "LIMIT" in tipo_orden:
        cabecera = "🔵🔵 LIMIT ORDER 🔵🔵\n"
    else:
        cabecera = "⚡ MARKET ORDER ⚡\n"
    
    if direccion == 1 or "COMPRA" in str(direccion).upper() or "LONG" in str(direccion).upper():
        cabecera += "🟢 COMPRA (LONG) 🟢"
    else:
        cabecera += "🔴 VENTA (SHORT) 🔴"

    if par == "GBP/USD":
        alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️"
    else:
        alerta_par = f"📈 **ACTIVO: {par.upper()}**"
    
    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_est}`\n"
        f"⏳ **MARCO:** `{marco}`\n"
        f"{alerta_par}\n\n"
        f"🚀 **ENTRADA:** **{ent}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    
    if tp2 is not None: 
        mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    if tp3 is not None: 
        mensaje += f"🎯 **TARGET 3:** **{tp3}**\n"
    
    hora_actual = datetime.now(TZ).strftime('%H:%M:%S')
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **ANTICIPACIÓN (3s):** `{hora_actual}`"
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try: 
        session.post(url, data=payload, timeout=5)
    except Exception: 
        pass

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    intervalo_real = intervalos.get(tf, '15m')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo_real}&range=5d"
    
    try:
        r = session.get(url, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }, index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ))
        
        return df.dropna()
    except Exception: 
        return None

# ===================================================================
# ESTRATEGIA 1: ICT ALEX RUIZ (M15 + H4)
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50:
        return None
        
    df = df_15m.copy()
    df_h4 = df_4h.copy()
    ts = df.index[-1]
    
    df['week'] = df.index.isocalendar().week
    current_week = df['week'].iloc[-1]
    df_weekly = df[df['week'] == current_week]
    
    if df_weekly.empty: 
        return None
        
    weekly_open = df_weekly['open'].iloc[0]
    current_price = df['close'].iloc[-1]
    
    h4_trend = "COMPRA" if df_h4['high'].iloc[-1] > df_h4['high'].iloc[-2] else ("VENTA" if df_h4['low'].iloc[-1] < df_h4['low'].iloc[-2] else None)
    
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else ("VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None)
    if bias is None: return None

    r_high = df['high'].tail(30).max()
    r_low = df['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None

    if bias == "COMPRA":
        if (r_high - (rango * 0.79)) <= current_price <= (r_high - (rango * 0.62)):
            return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.272), 5), ts
    elif bias == "VENTA":
        if (r_low + (rango * 0.62)) <= current_price <= (r_low + (rango * 0.79)):
            return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.272), 5), ts
    return None

# ===================================================================
# ESTRATEGIA 2: ICT 1 MINUTO
# ===================================================================
def est_ict_1minuto(df_1m):
    if df_1m is None or len(df_1m) < 60: return None
    df = df_1m.copy()
    ts = df.index[-1]

    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['Swing_High'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())]
    df['Swing_Low'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())]
    df['Last_Swing_High'] = df['Swing_High'].ffill()
    df['Last_Swing_Low'] = df['Swing_Low'].ffill()
    
    estado_long, estado_short = 0, 0
    min_impulso_L, max_impulso_L, max_impulso_S, min_impulso_S = 0, 0, 0, 0

    for i in range(15, len(df)):
        c_open, c_close, c_low, c_high = df['open'].iloc[i], df['close'].iloc[i], df['low'].iloc[i], df['high'].iloc[i]
        ema_50, l_high, l_low = df['EMA_50'].iloc[i], df['Last_Swing_High'].iloc[i], df['Last_Swing_Low'].iloc[i]
        tol, buf, max_r = c_close * 0.0008, c_close * 0.0004, c_close * 0.03 

        if estado_long > 0 and c_low < min_impulso_L: estado_long = 0
        if estado_short > 0 and c_high > max_impulso_S: estado_short = 0

        # LONG
        if estado_long == 0:
            if c_close > l_high: estado_long, min_impulso_L, max_impulso_L = 1, l_low, c_high
        elif estado_long == 1:
            if c_high > max_impulso_L: max_impulso_L = c_high 
            rango_L = max_impulso_L - min_impulso_L
            if rango_L > max_r: estado_long = 0; continue
            fib0618_L = max_impulso_L - (rango_L * 0.618)
            if c_low <= fib0618_L and abs(fib0618_L - ema_50) <= tol: estado_long = 2 
        elif estado_long == 2:
            fib075_L = max_impulso_L - ((max_impulso_L - min_impulso_L) * 0.75)
            if c_close < fib075_L: estado_long = 0; continue
            if c_close > ema_50 and c_open <= ema_50:
                if i == len(df) - 1: return "COMPRA", round(c_close, 5), round(fib075_L - buf, 5), round(max_impulso_L, 5), ts
                estado_long = 0 

        # SHORT
        if estado_short == 0:
            if c_close < l_low: estado_short, max_impulso_S, min_impulso_S = 1, l_high, c_low
        elif estado_short == 1:
            if c_low < min_impulso_S: min_impulso_S = c_low 
            rango_S = max_impulso_S - min_impulso_S
            if rango_S > max_r: estado_short = 0; continue
            fib0618_S = min_impulso_S + (rango_S * 0.618)
            if c_high >= fib0618_S and abs(fib0618_S - ema_50) <= tol: estado_short = 2 
        elif estado_short == 2:
            fib075_S = min_impulso_S + ((max_impulso_S - min_impulso_S) * 0.75)
            if c_close > fib075_S: estado_short = 0; continue
            if c_close < ema_50 and c_open >= ema_50:
                if i == len(df) - 1: return "VENTA", round(c_close, 5), round(fib075_S + buf, 5), round(min_impulso_S, 5), ts
                estado_short = 0 
    return None

# ===================================================================
# ESTRATEGIA 3: MACD 2.0 COMPLETADA
# ===================================================================
def est_estrategia_precision(df_menor, df_mayor, ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001):
    df_htf, df_ltf = df_mayor.copy(), df_menor.copy()
    
    df_htf['EMA_100_HTF'] = df_htf['close'].ewm(span=ema_period, adjust=False).mean()
    df_htf['Trend_HTF'] = np.where(df_htf['close'] > df_htf['EMA_100_HTF'], 1, -1)
    df_htf['Resistencia_HTF'] = df_htf['high'].rolling(window=pivot_window).max().shift(1)
    df_htf['Soporte_HTF'] = df_htf['low'].rolling(window=pivot_window).min().shift(1)
    
    df_htf['Touch_Resistencia'] = np.where(abs(df_htf['high'] - df_htf['Resistencia_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    df_htf['Touch_Soporte'] = np.where(abs(df_htf['low'] - df_htf['Soporte_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    
    df_combined = pd.merge_asof(df_ltf.sort_index(), df_htf[['EMA_100_HTF', 'Trend_HTF', 'Touch_Resistencia', 'Touch_Soporte']].sort_index(), left_index=True, right_index=True, direction='backward')
    
    macd_line = df_combined['close'].ewm(span=macd_fast, adjust=False).mean() - df_combined['close'].ewm(span=macd_slow, adjust=False).mean()
    signal_line = macd_line.ewm(span=macd_sign, adjust=False).mean()
    
    df_combined['MACD_Cross'] = np.where((macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1)), 1, 
                                np.where((macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1)), -1, 0))
    
    df_combined['Vela_Verde'] = df_combined['close'] > df_combined['open']
    df_combined['Vela_Roja'] = df_combined['close'] < df_combined['open']
    
    df_combined['Signal'] = 0
    df_combined['Entry_Price'] = np.nan
    df_combined['Stop_Loss'] = np.nan
    df_combined['Take_Profit'] = np.nan
    
    cond_long = (df_combined['Trend_HTF'] == 1) & (df_combined['Touch_Soporte']) & (df_combined['MACD_Cross'] == 1) & (df_combined['Vela_Verde'])
    cond_short = (df_combined['Trend_HTF'] == -1) & (df_combined['Touch_Resistencia']) & (df_combined['MACD_Cross'] == -1) & (df_combined['Vela_Roja'])
    
    df_combined.loc[cond_long, 'Signal'] = 1
    df_combined.loc[cond_long, 'Entry_Price'] = df_combined['close']
    df_combined.loc[cond_long, 'Stop_Loss'] = df_combined['EMA_100_HTF']
    df_combined.loc[cond_long, 'Take_Profit'] = df_combined['close'] + ((df_combined['close'] - df_combined['EMA_100_HTF']) * rr_ratio)
    
    df_combined.loc[cond_short, 'Signal'] = -1
    df_combined.loc[cond_short, 'Entry_Price'] = df_combined['close']
    df_combined.loc[cond_short, 'Stop_Loss'] = df_combined['EMA_100_HTF']
    df_combined.loc[cond_short, 'Take_Profit'] = df_combined['close'] - ((df_combined['EMA_100_HTF'] - df_combined['close']) * rr_ratio)
    
    return df_combined

# ===================================================================
# BUCLE PRINCIPAL ROBUSTO (SIN BLOQUEOS)
# ===================================================================
print("🤖 BOT INICIADO - 3 Estrategias - Escaneo robusto")
enviar_telegram("🤖 **Bot Quantfury Desplegado y Activo en Railway**")

while True:
    try:
        ahora = datetime.now(TZ)
        
        # Ampliamos ventana: arranca en el segundo 55 para dar tiempo a procesar los 22 pares
        if ahora.second >= 55:
            
            for ticker, nombre in ASSETS_MAP.items():
                if "-USD" in ticker or (HORA_INICIO <= ahora.hour < HORA_FIN):
                    
                    # Para evitar descargar datos innecesarios, solo bajamos lo que toca en este minuto
                    es_minuto_macd = (ahora.minute % 5 == 4 or ahora.minute % 5 == 0) and (ticker in CRYPTO_MACD or "USD" in ticker)
                    es_minuto_alex = (ahora.minute % 15 == 14 or ahora.minute % 15 == 0)
                    
                    d1m = obtener_datos(ticker, "1m")
                    
                    # 1. ICT 1 MINUTO
                    if d1m is not None:
                        res2 = est_ict_1minuto(d1m)
                        if res2:
                            id2 = f"{ticker}_1MIN_{res2[4].strftime('%H:%M')}"
                            if id2 not in señales_enviadas:
                                enviar_telegram(generar_mensaje_telegram(nombre, res2[0], res2[1], res2[2], res2[3], nombre_est="ICT 1 Minuto", marco="1M"))
                                señales_enviadas.add(id2)
                    
                    # 2. ICT ALEX RUIZ (M15)
                    if es_minuto_alex:
                        d15m, d4h = obtener_datos(ticker, "15m"), obtener_datos(ticker, "4h")
                        res1 = est_ict_alex_m15(d15m, d4h)
                        if res1:
                            id1 = f"{ticker}_ALEX_{res1[5].strftime('%H:%M')}"
                            if id1 not in señales_enviadas:
                                enviar_telegram(generar_mensaje_telegram(nombre, res1[0], res1[1], res1[2], res1[3], res1[4], nombre_est="ICT Alex Ruiz", marco="15M/4H"))
                                señales_enviadas.add(id1)
                                
                    # 3. MACD 2.0 (M5)
                    if es_minuto_macd:
                        d5m, d15m_macd = obtener_datos(ticker, "5m"), obtener_datos(ticker, "15m")
                        if d5m is not None and d15m_macd is not None:
                            df_macd = est_estrategia_precision(d5m, d15m_macd)
                            if len(df_macd) > 1 and df_macd.iloc[-1]['Signal'] != 0:
                                v = df_macd.iloc[-1]
                                id3 = f"{ticker}_MACD_{df_macd.index[-1].strftime('%H:%M')}"
                                if id3 not in señales_enviadas:
                                    enviar_telegram(generar_mensaje_telegram(nombre, v['Signal'], round(v['Entry_Price'],5), round(v['Stop_Loss'],5), round(v['Take_Profit'],5), nombre_est="MACD 2.0 MTF", marco="5M/15M", tipo_orden="LIMIT"))
                                    señales_enviadas.add(id3)
                    
                    # Pausa ultracorta para no ahogar la sesión HTTP
                    time.sleep(0.1)
            
            # Duerme hasta el próximo minuto para no repetir peticiones
            time.sleep(10)
            
        time.sleep(1)
        if len(señales_enviadas) > 500: señales_enviadas.clear()
        
    except Exception as e:
        time.sleep(5) # Si hay un corte de red general, espera 5 segundos antes de reintentar
