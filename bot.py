import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACIÓN
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

# Aquí tienes 22 activos. ¡Añade los 11 que faltan aquí dentro si quieres 33!
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

# Memoria del bot para evitar repeticiones (Filtro Anti-Spam)
ultima_señal_enviada = {}

# -------------------------------------------------------------------
# FORMATO VISUAL TELEGRAM (DISEÑO MÁS GRANDE Y EN NEGRITA)
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, precio_entrada, sl, tp1, tp2, tp3, nombre_estrategia):
    cabecera = "🟢🟢🟢🟢🟢🟢\n🟢 COMPRA 🟢\n🟢🟢🟢🟢🟢🟢" if direccion.upper() == "COMPRA" else "🔴🔴🔴🔴🔴🔴\n🔴 VENTA 🔴\n🔴🔴🔴🔴🔴🔴"

    if par == "GBP/USD":
        alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️"
    else:
        alerta_par = f"📈 **ACTIVO: {par.upper()}**"

    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_estrategia}`\n"
        f"{alerta_par}\n\n"
        f"🚀 **ENTRADA:** **{precio_entrada}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🎯 **TARGET 1:** **{tp1}**\n"
    )
    
    if tp2 is not None:
        mensaje += f"🎯 **TARGET 2:** **{tp2}**\n"
    if tp3 is not None:
        mensaje += f"🎯 **TARGET 3:** **{tp3}**\n"
        
    mensaje += (
        f"━━━━━━━━━━━━━━━\n\n"
        f"🕒 **DETECTADA:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
    )
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

# -------------------------------------------------------------------
# OBTENCIÓN DE DATOS (AÑADIDO SOPORTE PARA 5 MINUTOS)
# -------------------------------------------------------------------
def obtener_datos(simbolo, tf="15m"):
    if tf == "5m":
        intervalo = "5m"
    elif tf == "15m":
        intervalo = "15m"
    else:
        intervalo = "1h" # Para H4 cogemos de 1h y lo agrupamos luego
        
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo}&range=60d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "datetime": pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ),
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }).dropna()
        
        if tf == "4h": 
            df = df.iloc[::4, :].copy() 
            
        return df.tail(100).reset_index(drop=True)
    except: 
        return None

# -------------------------------------------------------------------
# ESTRATEGIA 1: ICT ALEX RUIZ (Usa M15 y H4)
# -------------------------------------------------------------------
def est_estrategia_ict_alex(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 50: return None, None, None, None, None, None
    df_15m['week'] = df_15m['datetime'].dt.isocalendar().week
    weekly_open = df_15m[df_15m['week'] == df_15m['week'].iloc[-1]]['open'].iloc[0]
    current_price = df_15m['close'].iloc[-1]
    
    h4_trend = "COMPRA" if (df_4h['high'].iloc[-1] > df_4h['high'].iloc[-2]) else "VENTA" if (df_4h['low'].iloc[-1] < df_4h['low'].iloc[-2]) else None
    bias = "COMPRA" if (current_price < weekly_open and h4_trend == "COMPRA") else "VENTA" if (current_price > weekly_open and h4_trend == "VENTA") else None
    if not bias: return None, None, None, None, None, None

    r_high, r_low = df_15m['high'].tail(30).max(), df_15m['low'].tail(30).min()
    rango = r_high - r_low
    if rango <= 0: return None, None, None, None, None, None

    if bias == "COMPRA":
        if (r_high - (rango * 0.79)) <= current_price <= (r_high - (rango * 0.62)):
            return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.272), 5), round(r_high + (rango * 0.618), 5)
    elif bias == "VENTA":
        if (r_low + (rango * 0.62)) <= current_price <= (r_low + (rango * 0.79)):
            return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.272), 5), round(r_low - (rango * 0.618), 5)
    
    return None, None, None, None, None, None

# -------------------------------------------------------------------
# ESTRATEGIA 2: EMA 50 (CÓDIGO INTACTO)
# -------------------------------------------------------------------
def estrategia_alex_ruiz_bot(df):
    # Calcular la Media Móvil Exponencial de 50 periodos (EMA 50)
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Identificación de Fractales (Swings)
    df['Swing_High'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())]
    df['Swing_Low'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())]
    
    df['Last_Swing_High'] = df['Swing_High'].ffill()
    df['Last_Swing_Low'] = df['Swing_Low'].ffill()
    
    df['Signal_Long'] = False
    df['Signal_Short'] = False
    df['Entry_Price'] = np.nan
    df['Stop_Loss'] = np.nan
    df['Take_Profit'] = np.nan

    estado_long = 0 
    estado_short = 0
    min_impulso_L = max_impulso_L = 0
    max_impulso_S = min_impulso_S = 0

    for i in range(10, len(df)):
        current_open = df['open'].iloc[i]
        current_close = df['close'].iloc[i]
        current_low = df['low'].iloc[i]
        current_high = df['high'].iloc[i]
        ema_50 = df['EMA_50'].iloc[i]
        
        last_high = df['Last_Swing_High'].iloc[i]
        last_low = df['Last_Swing_Low'].iloc[i]

        tol_confluencia = current_close * 0.001 
        buffer_sl = current_close * 0.0005 

        # LÓGICA LONG
        if estado_long == 0 and current_close > last_high:
            estado_long = 1
            min_impulso_L = last_low
            max_impulso_L = current_high
        elif estado_long == 1:
            if current_high > max_impulso_L:
                max_impulso_L = current_high 
            rango = max_impulso_L - min_impulso_L
            fib_0618 = max_impulso_L - (rango * 0.618)
            confluencia_ema = abs(fib_0618 - ema_50) <= tol_confluencia
            if current_low <= fib_0618 and confluencia_ema:
                estado_long = 2 
        elif estado_long == 2:
            rango = max_impulso_L - min_impulso_L
            fib_075 = max_impulso_L - (rango * 0.75)
            if current_close < fib_075:
                estado_long = 0 
                continue
            vela_cierra_sobre_ema = current_close > ema_50
            vela_abrio_bajo_ema = current_open <= ema_50 
            if vela_cierra_sobre_ema and vela_abrio_bajo_ema:
                df.at[df.index[i], 'Signal_Long'] = True
                df.at[df.index[i], 'Entry_Price'] = current_close 
                df.at[df.index[i], 'Stop_Loss'] = fib_075 - buffer_sl 
                df.at[df.index[i], 'Take_Profit'] = max_impulso_L     
                estado_long = 0 

        # LÓGICA SHORT
        if estado_short == 0 and current_close < last_low:
            estado_short = 1
            max_impulso_S = last_high
            min_impulso_S = current_low
        elif estado_short == 1:
            if current_low < min_impulso_S:
                min_impulso_S = current_low 
            rango = max_impulso_S - min_impulso_S
            fib_0618 = min_impulso_S + (rango * 0.618)
            confluencia_ema = abs(fib_0618 - ema_50) <= tol_confluencia
            if current_high >= fib_0618 and confluencia_ema:
                estado_short = 2 
        elif estado_short == 2:
            rango = max_impulso_S - min_impulso_S
            fib_075 = min_impulso_S + (rango * 0.75)
            if current_close > fib_075:
                estado_short = 0 
                continue
            vela_cierra_bajo_ema = current_close < ema_50
            vela_abrio_sobre_ema = current_open >= ema_50 
            if vela_cierra_bajo_ema and vela_abrio_sobre_ema:
                df.at[df.index[i], 'Signal_Short'] = True
                df.at[df.index[i], 'Entry_Price'] = current_close 
                df.at[df.index[i], 'Stop_Loss'] = fib_075 + buffer_sl 
                df.at[df.index[i], 'Take_Profit'] = min_impulso_S     
                estado_short = 0 

    return df

# Adaptador de la EMA 50 (Garantiza VELAS CERRADAS)
def adaptador_ema_50(df_5m, dummy=None):
    if df_5m is None or len(df_5m) < 50: return None, None, None, None, None, None
    
    # ⚠️ EL SECRETO: Le quitamos la última fila [:-1] porque esa vela de 5M aún se está moviendo.
    # Así garantizamos que evalúa solo al CIERRE exacto de la vela.
    df_cerradas = df_5m.iloc[:-1].copy()
    
    # Evaluamos el dataframe con la estrategia exacta
    df_analizado = estrategia_alex_ruiz_bot(df_cerradas)
    
    # Miramos si la *última vela ya cerrada* generó señal
    ultima_vela = df_analizado.iloc[-1]
    
    if ultima_vela['Signal_Long']:
        return "COMPRA", round(ultima_vela['Entry_Price'], 5), round(ultima_vela['Stop_Loss'], 5), round(ultima_vela['Take_Profit'], 5), None, None
    elif ultima_vela['Signal_Short']:
        return "VENTA", round(ultima_vela['Entry_Price'], 5), round(ultima_vela['Stop_Loss'], 5), round(ultima_vela['Take_Profit'], 5), None, None
        
    return None, None, None, None, None, None

# -------------------------------------------------------------------
# MOTOR DE PROCESAMIENTO
# -------------------------------------------------------------------
def procesar_estrategia(ticker, nombre_claro, strategy_func, strat_name, df_menor, df_mayor):
    # Llamamos a la estrategia correspondiente
    res = strategy_func(df_menor, df_mayor) 
    
    if res and res[0]:
        dir, ent, sl, tp1, tp2, tp3 = res
        id_señal = f"{ticker}_{strat_name}_{dir}_{ent}"
        
        # Filtro de señales duplicadas
        if ultima_señal_enviada.get(f"{ticker}_{strat_name}") != id_señal:
            enviar_telegram(generar_mensaje_telegram(nombre_claro, dir, ent, sl, tp1, tp2, tp3, strat_name))
            ultima_señal_enviada[f"{ticker}_{strat_name}"] = id_señal
            print(f"[{datetime.now(TZ).strftime('%H:%M:%S')}] Señal enviada: {nombre_claro} ({strat_name})")

# -------------------------------------------------------------------
# BUCLE PRINCIPAL (REACCIÓN INSTANTÁNEA MULTI-ESTRATEGIA)
# -------------------------------------------------------------------
print("Bot en ejecución DUAL: Escaneo continuo. Velas de 5m y 15m.")
while True:
    ahora = datetime.now(TZ)
    
    for ticker, nombre in ASSETS_MAP.items():
        es_crypto = "-USD" in ticker
        # Si es crypto o estamos en horario comercial
        if es_crypto or (HORA_INICIO <= ahora.hour < HORA_FIN):
            
            # Descargamos los datos para las distintas temporalidades
            df_5m = obtener_datos(ticker, "5m")
            df_15m = obtener_datos(ticker, "15m")
            df_4h = obtener_datos(ticker, "4h")
            
            # Ejecutar Estrategia 1 (ICT) -> Usa M15 y H4
            procesar_estrategia(ticker, nombre, est_estrategia_ict_alex, "ICT Alex Ruiz", df_15m, df_4h)
            
            # Ejecutar Estrategia 2 (EMA 50) -> Usa M5 (solo velas cerradas)
            procesar_estrategia(ticker, nombre, adaptador_ema_50, "EMA 50 + Fractales (M5)", df_5m, None)
            
            time.sleep(0.3) # Evitar que Yahoo Finance nos bloquee
            
    time.sleep(60) # Descanso de 1 minuto
