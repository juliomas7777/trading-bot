import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACIÓN GLOBAL Y FILTROS
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

# Lista completa de activos
ASSETS_MAP = {
    "BTC-USD": "BITCOIN", "ETH-USD": "ETHEREUM", "SOL-USD": "SOLANA",
    "XRP-USD": "XRP", "ADA-USD": "CARDANO", "DOT-USD": "POLKADOT",
    "MATIC-USD": "POLYGON (MATIC)", "LTC-USD": "LITECOIN", "LINK-USD": "CHAINLINK",
    "AVAX-USD": "AVALANCHE", 
    "SPY": "S&P 500", "QQQ": "NASDAQ 100", "^GDAXI": "DAX 40", "NVDA": "NVIDIA",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY", 
    "USDCAD=X": "USD/CAD", "USDCHF=X": "USD/CHF", "AUDUSD=X": "AUD/USD", 
    "NZDUSD=X": "NZD/USD", "GC=F": "ORO"
}

# Filtros estrictos solicitados para la estrategia MACD
CRYPTO_MACD = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]

señales_enviadas = set()

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES (TELEGRAM Y DATOS)
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, ent, sl, tp1, tp2=None, tp3=None, nombre_est="", marco="", tipo_orden="MARKET"):
    if "LIMIT" in tipo_orden:
        cabecera = "🔵🔵 LIMIT ORDER 🔵🔵\n"
    else:
        cabecera = "⚡ MARKET ORDER ⚡\n"
    
    if direccion == 1 or "COMPRA" in str(direccion).upper() or "LONG" in str(direccion).upper():
        cabecera += "🟢 COMPRA (LONG) 🟢"
    else:
        cabecera += "🔴 VENTA (SHORT) 🔴"

    alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️" if par == "GBP/USD" else f"📈 **ACTIVO: {par.upper()}**"
    
    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_est}`\n"
        f"⏳ **MARCO:** `{marco}`\n"
        f"{alerta_par}\n\n"
        f"🚀 **ENTRADA:** **{ent}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    if tp2: mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    if tp3: mensaje += f"🎯 **TARGET 3:** **{tp3}**\n"
    
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **VELA CERRADA:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalos.get(tf, '15m')}&range=5d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }, index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ)).dropna()
        return df
    except:
        return None

# ===================================================================
# ESTRATEGIA 1: ICT ALEX RUIZ (M15 + H4)
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None
    
    df = df_15m.iloc[:-1].copy()
    df_h4 = df_4h.iloc[:-1].copy()
    ts = df.index[-1]
    
    # Lógica de apertura semanal
    df['week'] = df.index.isocalendar().week
    weekly_open = df[df['week'] == df['week'].iloc[-1]]['open'].iloc[0]
    current_price = df['close'].iloc[-1]
    
    # Tendencia H4 por rotura de máximos/mínimos
    h4_trend = "COMPRA" if (df_h4['high'].iloc[-1] > df_h4['high'].iloc[-2]) else "VENTA" if (df_h4['low'].iloc[-1] < df_h4['low'].iloc[-2]) else None
    
    # Bias de Alex Ruiz
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else "VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None
    
    if not bias: return None

    # Cálculo de Rango y Fibonacci (Ojo: 0.62 y 0.79)
    r_high, r_low = df['high'].tail(30).max(), df['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None

    if bias == "COMPRA" and (r_high - (rango * 0.79)) <= current_price <= (r_high - (rango * 0.62)):
        return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.272), 5), ts
    elif bias == "VENTA" and (r_low + (rango * 0.62)) <= current_price <= (r_low + (rango * 0.79)):
        return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.272), 5), ts
    return None

# ===================================================================
# ESTRATEGIA 2: ICT 1 MINUTO (CON FILTRO ANTI-MACRO Y EMA 50)
# ===================================================================
def est_ict_1minuto(df_1m):
    if df_1m is None or len(df_1m) < 60: return None
    df = df_1m.iloc[:-1].copy()
    ts = df.index[-1]

    # Parámetros e Indicadores
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['Swing_High'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())]
    df['Swing_Low'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())]
    df['Last_Swing_High'] = df['Swing_High'].ffill()
    df['Last_Swing_Low'] = df['Swing_Low'].ffill()
    
    # Máquina de estados para la lógica de entrada
    estado_long = 0; estado_short = 0; min_impulso_L = 0; max_impulso_L = 0; max_impulso_S = 0; min_impulso_S = 0

    for i in range(15, len(df)):
        c_open = df['open'].iloc[i]
        c_close = df['close'].iloc[i]
        c_low = df['low'].iloc[i]
        c_high = df['high'].iloc[i]
        ema_50 = df['EMA_50'].iloc[i]
        l_high = df['Last_Swing_High'].iloc[i]
        l_low = df['Last_Swing_Low'].iloc[i]
        
        # Tolerancias dinámicas
        tol = c_close * 0.001
        buf = c_close * 0.0005
        max_r = c_close * 0.04 

        # Reseteo por invalidación (Mechas largas o cambio estructura)
        if estado_long > 0 and c_low < min_impulso_L: estado_long = 0
        if estado_short > 0 and c_high > max_impulso_S: estado_short = 0

        # Lógica de COMPRA
        if estado_long == 0 and c_close > l_high:
            estado_long, min_impulso_L, max_impulso_L = 1, l_low, c_high
        elif estado_long == 1:
            if c_high > max_impulso_L: max_impulso_L = c_high 
            rango = max_impulso_L - min_impulso_L
            if rango > max_r: estado_long = 0; continue
            fib0618 = max_impulso_L - (rango * 0.618)
            if c_low <= fib0618 and abs(fib0618 - ema_50) <= tol: estado_long = 2 
        elif estado_long == 2:
            fib075 = max_impulso_L - ((max_impulso_L - min_impulso_L) * 0.75)
            if c_close < fib075: estado_long = 0; continue
            if c_close > ema_50 and c_open <= ema_50:
                if i == len(df)-1: 
                    return "COMPRA", round(c_close, 5), round(fib075 - buf, 5), round(max_impulso_L, 5), ts
                estado_long = 0 

        # Lógica de VENTA
        if estado_short == 0 and c_close < l_low:
            estado_short, max_impulso_S, min_impulso_S = 1, l_high, c_low
        elif estado_short == 1:
            if c_low < min_impulso_S: min_impulso_S = c_low 
            rango = max_impulso_S - min_impulso_S
            if rango > max_r: estado_short = 0; continue
            fib0618 = min_impulso_S + (rango * 0.618)
            if c_high >= fib0618 and abs(fib0618 - ema_50) <= tol: estado_short = 2 
        elif estado_short == 2:
            fib075 = min_impulso_S + ((max_impulso_S - min_impulso_S) * 0.75)
            if c_close > fib075: estado_short = 0; continue
            if c_close < ema_50 and c_open >= ema_50:
                if i == len(df)-1: 
                    return "VENTA", round(c_close, 5), round(fib075 + buf, 5), round(min_impulso_S, 5), ts
                estado_short = 0 
    return None

# ===================================================================
# ESTRATEGIA 3: MACD 2.0 (SOPORTE/RESISTENCIA + MTF)
# ===================================================================
def est_estrategia_precision(df_menor: pd.DataFrame, df_mayor: pd.DataFrame, 
                             ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, 
                             rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001):
    # Copias de seguridad
    df_htf = df_mayor.copy()
    df_ltf = df_menor.copy()
    
    # PASO 1: Análisis HTF (15M)
    df_htf['EMA_100_HTF'] = df_htf['close'].ewm(span=ema_period, adjust=False).mean()
    df_htf['Trend_HTF'] = np.where(df_htf['close'] > df_htf['EMA_100_HTF'], 1, -1)
    
    # Soportes y Resistencias Forenses
    df_htf['Resistencia_HTF'] = df_htf['high'].rolling(window=pivot_window).max().shift(1)
    df_htf['Soporte_HTF'] = df_htf['low'].rolling(window=pivot_window).min().shift(1)
    
    df_htf['Touch_Resistencia'] = np.where(abs(df_htf['high'] - df_htf['Resistencia_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    df_htf['Touch_Soporte'] = np.where(abs(df_htf['low'] - df_htf['Soporte_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    
    # Extraer señales HTF para merge
    df_htf_signals = df_htf[['EMA_100_HTF', 'Trend_HTF', 'Touch_Resistencia', 'Touch_Soporte']]
    
    # PASO 2: Sincronización MTF
    df_combined = pd.merge_asof(df_ltf.sort_index(), df_htf_signals.sort_index(), 
                                left_index=True, right_index=True, direction='backward')
    
    # PASO 3: Gatillo MACD (5M)
    ema_fast = df_combined['close'].ewm(span=macd_fast, adjust=False).mean()
    ema_slow = df_combined['close'].ewm(span=macd_slow, adjust=False).mean()
    df_combined['MACD_Line'] = ema_fast - ema_slow
    df_combined['Signal_Line'] = df_combined['MACD_Line'].ewm(span=macd_sign, adjust=False).mean()
    
    df_combined['MACD_Cross'] = 0
    cruce_alcista = (df_combined['MACD_Line'] > df_combined['Signal_Line']) & (df_combined['MACD_Line'].shift(1) <= df_combined['Signal_Line'].shift(1))
    cruce_bajista = (df_combined['MACD_Line'] < df_combined['Signal_Line']) & (df_combined['MACD_Line'].shift(1) >= df_combined['Signal_Line'].shift(1))
    
    df_combined.loc[cruce_alcista, 'MACD_Cross'] = 1
    df_combined.loc[cruce_bajista, 'MACD_Cross'] = -1

    df_combined['Vela_Verde'] = df_combined['close'] > df_combined['open']
    df_combined['Vela_Roja'] = df_combined['close'] < df_combined['open']

    # Resultados finales
    df_combined['Signal'] = 0
    df_combined['Entry_Price'] = np.nan
    df_combined['Stop_Loss'] = np.nan
    df_combined['Take_Profit'] = np.nan
    
    # Condición Alcista
    cond_long = (
        (df_combined['Trend_HTF'] == 1) & 
        (df_combined['Touch_Soporte'] == True) & 
        (df_combined['MACD_Cross'] == 1) & 
        (df_combined['Vela_Verde'] == True)
    )
    
    # Condición Bajista
    cond_short = (
        (df_combined['Trend_HTF'] == -1) & 
        (df_combined['Touch_Resistencia'] == True) & 
        (df_combined['MACD_Cross'] == -1) & 
        (df_combined['Vela_Roja'] == True)
    )
    
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
# BUCLE DE EJECUCIÓN CONTINUA
# ===================================================================
print(f"🚀 Iniciando Bot Triple Estrategia - {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")

while True:
    ahora = datetime.now(TZ)
    for ticker, nombre in ASSETS_MAP.items():
        # Control horario (excepto Cryptos)
        if "-USD" in ticker or (HORA_INICIO <= ahora.hour < HORA_FIN):
            
            # Descarga de datos multi-timeframe
            d1m = obtener_datos(ticker, "1m")
            d5m = obtener_datos(ticker, "5m")
            d15m = obtener_datos(ticker, "15m")
            d4h = obtener_datos(ticker, "4h")
            
            # -------------------------------------------------------
            # 1. EJECUCIÓN ICT ALEX RUIZ (M15 + H4)
            # -------------------------------------------------------
            res1 = est_ict_alex_m15(d15m, d4h)
            if res1:
                id1 = f"{ticker}_ICTALEX_{res1[5].strftime('%Y-%m-%d_%H:%M')}"
                if id1 not in señales_enviadas:
                    msg = generar_mensaje_telegram(nombre, res1[0], res1[1], res1[2], res1[3], res1[4], None, "ICT Alex Ruiz", "15M/4H", "MARKET")
                    enviar_telegram(msg)
                    señales_enviadas.add(id1)

            # -------------------------------------------------------
            # 2. EJECUCIÓN ICT 1 MINUTO (M1)
            # -------------------------------------------------------
            res2 = est_ict_1minuto(d1m)
            if res2:
                id2 = f"{ticker}_ICT1MIN_{res2[4].strftime('%Y-%m-%d_%H:%M')}"
                if id2 not in señales_enviadas:
                    msg = generar_mensaje_telegram(nombre, res2[0], res2[1], res2[2], res2[3], None, None, "ICT 1minuto", "1M", "MARKET")
                    enviar_telegram(msg)
                    señales_enviadas.add(id2)

            # -------------------------------------------------------
            # 3. EJECUCIÓN MACD 2.0 (M5 + M15) - CON FILTROS DE ACTIVO
            # -------------------------------------------------------
            es_divisa_usd = "USD" in ticker and "=X" in ticker
            es_crypto_especifica = ticker in CRYPTO_MACD
            
            if es_divisa_usd or es_crypto_especifica:
                if d5m is not None and d15m is not None:
                    # Todos los parámetros definidos tal cual el original
                    df_macd = est_estrategia_precision(d5m, d15m, ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001)
                    
                    if len(df_macd) > 2:
                        v = df_macd.iloc[-2] # Vela cerrada
                        if v['Signal'] != 0:
                            id3 = f"{ticker}_MACD_{df_macd.index[-2].strftime('%Y-%m-%d_%H:%M')}"
                            if id3 not in señales_enviadas:
                                msg_macd = generar_mensaje_telegram(
                                    nombre, 
                                    v['Signal'], 
                                    round(v['Entry_Price'], 5), 
                                    round(v['Stop_Loss'], 5), 
                                    round(v['Take_Profit'], 5), 
                                    None, None, 
                                    "MACD 2.0", 
                                    "5M / 15M", 
                                    "LIMIT ORDER"
                                )
                                enviar_telegram(msg_macd)
                                señales_enviadas.add(id3)
            
            time.sleep(0.5) # Pausa de seguridad API
            
    # Limpieza de caché de señales y espera de ciclo
    if len(señales_enviadas) > 2000: señales_enviadas.clear()
    time.sleep(30)
