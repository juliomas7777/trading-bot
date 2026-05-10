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

# Filtro específico para MACD (Divisas USD y Cryptos seleccionadas)
CRYPTO_MACD = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD"]

# Set para evitar señales duplicadas
señales_enviadas = set()

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
    payload = {
        "chat_id": CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "Markdown"
    }
    try: 
        requests.post(url, data=payload, timeout=10)
    except Exception as e: 
        pass

def obtener_datos(simbolo, tf="15m"):
    intervalos = {
        "1m": "1m", 
        "5m": "5m", 
        "15m": "15m", 
        "1h": "1h", 
        "4h": "1h" # Usamos 1h para reconstruir 4h
    }
    
    intervalo_real = intervalos.get(tf, '15m')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo_real}&range=5d"
    
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        
        df = pd.DataFrame({
            "open": q["open"], 
            "high": q["high"], 
            "low": q["low"], 
            "close": q["close"]
        }, index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ))
        
        df = df.dropna()
        return df
    except Exception as e: 
        return None

# ===================================================================
# ESTRATEGIA 1: ICT ALEX RUIZ (M15 + H4)
# ===================================================================
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None:
        return None
    if len(df_15m) < 50: 
        return None
        
    df = df_15m.copy()
    df_h4 = df_4h.copy()
    ts = df.index[-1]
    
    # Cálculo de la apertura semanal
    df['week'] = df.index.isocalendar().week
    current_week = df['week'].iloc[-1]
    df_weekly = df[df['week'] == current_week]
    
    if df_weekly.empty: 
        return None
        
    weekly_open = df_weekly['open'].iloc[0]
    current_price = df['close'].iloc[-1]
    
    # Tendencia H4 basada en los últimos altos y bajos
    h4_high_now = df_h4['high'].iloc[-1]
    h4_high_prev = df_h4['high'].iloc[-2]
    h4_low_now = df_h4['low'].iloc[-1]
    h4_low_prev = df_h4['low'].iloc[-2]
    
    h4_trend = None
    if h4_high_now > h4_high_prev: 
        h4_trend = "COMPRA"
    elif h4_low_now < h4_low_prev: 
        h4_trend = "VENTA"
    
    # Confirmación de Sesgo (Bias)
    bias = None
    if current_price < weekly_open and h4_trend == "COMPRA": 
        bias = "COMPRA"
    elif current_price > weekly_open and h4_trend == "VENTA": 
        bias = "VENTA"
    
    if bias is None: 
        return None

    # Cálculo de rangos
    r_high = df['high'].tail(30).max()
    r_low = df['low'].tail(30).min()
    rango = r_high - r_low
    
    if rango <= 0: 
        return None

    # Zonas OTE
    if bias == "COMPRA":
        entry_min = r_high - (rango * 0.79)
        entry_max = r_high - (rango * 0.62)
        
        if current_price >= entry_min and current_price <= entry_max:
            tp = r_high + (rango * 0.272)
            return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(tp, 5), ts
            
    elif bias == "VENTA":
        entry_min = r_low + (rango * 0.62)
        entry_max = r_low + (rango * 0.79)
        
        if current_price >= entry_min and current_price <= entry_max:
            tp = r_low - (rango * 0.272)
            return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(tp, 5), ts
            
    return None

# ===================================================================
# ESTRATEGIA 2: ICT 1 MINUTO (MOTOR ANTI-MACRO Y ESTRUCTURA)
# ===================================================================
def est_ict_1minuto(df_1m):
    if df_1m is None:
        return None
    if len(df_1m) < 60: 
        return None
        
    df = df_1m.copy()
    ts = df.index[-1]

    # Indicadores Base
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    df['Swing_High'] = df['high'][(df['high'] == df['high'].rolling(window=5, center=True).max())]
    df['Swing_Low'] = df['low'][(df['low'] == df['low'].rolling(window=5, center=True).min())]
    
    df['Last_Swing_High'] = df['Swing_High'].ffill()
    df['Last_Swing_Low'] = df['Swing_Low'].ffill()
    
    # Variables de Estado extendidas
    estado_long = 0
    estado_short = 0
    
    min_impulso_L = 0
    max_impulso_L = 0
    max_impulso_S = 0
    min_impulso_S = 0

    # Bucle principal de escaneo
    for i in range(15, len(df)):
        c_open = df['open'].iloc[i]
        c_close = df['close'].iloc[i]
        c_low = df['low'].iloc[i]
        c_high = df['high'].iloc[i]
        
        ema_50 = df['EMA_50'].iloc[i]
        l_high = df['Last_Swing_High'].iloc[i]
        l_low = df['Last_Swing_Low'].iloc[i]
        
        tol = c_close * 0.0008 
        buf = c_close * 0.0004
        max_r = c_close * 0.03 

        # Invalidaciones por mechas
        if estado_long > 0:
            if c_low < min_impulso_L: 
                estado_long = 0
                
        if estado_short > 0:
            if c_high > max_impulso_S: 
                estado_short = 0

        # MÁQUINA DE ESTADOS: COMPRA
        if estado_long == 0:
            if c_close > l_high:
                estado_long = 1
                min_impulso_L = l_low
                max_impulso_L = c_high
                
        elif estado_long == 1:
            if c_high > max_impulso_L: 
                max_impulso_L = c_high 
                
            rango_L = max_impulso_L - min_impulso_L
            if rango_L > max_r: 
                estado_long = 0
                continue
                
            fib0618_L = max_impulso_L - (rango_L * 0.618)
            if c_low <= fib0618_L:
                if abs(fib0618_L - ema_50) <= tol: 
                    estado_long = 2 
                    
        elif estado_long == 2:
            rango_L = max_impulso_L - min_impulso_L
            fib075_L = max_impulso_L - (rango_L * 0.75)
            
            if c_close < fib075_L: 
                estado_long = 0
                continue
                
            if c_close > ema_50 and c_open <= ema_50:
                if i == len(df) - 1: 
                    ent = round(c_close, 5)
                    sl = round(fib075_L - buf, 5)
                    tp = round(max_impulso_L, 5)
                    return "COMPRA", ent, sl, tp, ts
                estado_long = 0 

        # MÁQUINA DE ESTADOS: VENTA
        if estado_short == 0:
            if c_close < l_low:
                estado_short = 1
                max_impulso_S = l_high
                min_impulso_S = c_low
                
        elif estado_short == 1:
            if c_low < min_impulso_S: 
                min_impulso_S = c_low 
                
            rango_S = max_impulso_S - min_impulso_S
            if rango_S > max_r: 
                estado_short = 0
                continue
                
            fib0618_S = min_impulso_S + (rango_S * 0.618)
            if c_high >= fib0618_S:
                if abs(fib0618_S - ema_50) <= tol: 
                    estado_short = 2 
                    
        elif estado_short == 2:
            rango_S = max_impulso_S - min_impulso_S
            fib075_S = min_impulso_S + (rango_S * 0.75)
            
            if c_close > fib075_S: 
                estado_short = 0
                continue
                
            if c_close < ema_50 and c_open >= ema_50:
                if i == len(df) - 1: 
                    ent = round(c_close, 5)
                    sl = round(fib075_S + buf, 5)
                    tp = round(min_impulso_S, 5)
                    return "VENTA", ent, sl, tp, ts
                estado_short = 0 
                
    return None

# ===================================================================
# ESTRATEGIA 3: MACD 2.0 PRECISION MULTI-TIMEFRAME
# ===================================================================
def est_estrategia_precision(df_menor: pd.DataFrame, df_mayor: pd.DataFrame, 
                             ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, 
                             rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001):
    
    df_htf = df_mayor.copy()
    df_ltf = df_menor.copy()
    
    # 1. Configuración de Indicadores HTF
    df_htf['EMA_100_HTF'] = df_htf['close'].ewm(span=ema_period, adjust=False).mean()
    
    condicion_tendencia_alcista = df_htf['close'] > df_htf['EMA_100_HTF']
    df_htf['Trend_HTF'] = np.where(condicion_tendencia_alcista, 1, -1)
    
    # 2. Soportes y Resistencias HTF
    df_htf['Resistencia_HTF'] = df_htf['high'].rolling(window=pivot_window).max().shift(1)
    df_htf['Soporte_HTF'] = df_htf['low'].rolling(window=pivot_window).min().shift(1)
    
    distancia_resistencia = abs(df_htf['high'] - df_htf['Resistencia_HTF']) / df_htf['close']
    df_htf['Touch_Resistencia'] = np.where(distancia_resistencia <= tolerance_pct, True, False)
    
    distancia_soporte = abs(df_htf['low'] - df_htf['Soporte_HTF']) / df_htf['close']
    df_htf['Touch_Soporte'] = np.where(distancia_soporte <= tolerance_pct, True, False)
    
    # 3. Fusión de Timeframes
    df_htf_signals = df_htf[['EMA_100_HTF', 'Trend_HTF', 'Touch_Resistencia', 'Touch_Soporte']]
    
    df_combined = pd.merge_asof(
        df_ltf.sort_index(), 
        df_htf_signals.sort_index(), 
        left_index=True, 
        right_index=True, 
        direction='backward'
    )
    
    # 4. Cálculo del MACD en LTF
    ema_fast = df_combined['close'].ewm(span=macd_fast, adjust=False).mean()
    ema_slow = df_combined['close'].ewm(span=macd_slow, adjust=False).mean()
    
    df_combined['MACD_Line'] = ema_fast - ema_slow
    df_combined['Signal_Line'] = df_combined['MACD_Line'].ewm(span=macd_sign, adjust=False).mean()
    
    df_combined['MACD_Cross'] = 0
    
    cruce_alcista = (df_combined['MACD_Line'] > df_combined['Signal_Line']) & (df_combined['MACD_Line'].shift(1) <= df_combined['Signal_Line'].shift(1))
    cruce_bajista = (df_combined['MACD_Line'] < df_combined['Signal_Line']) & (df_combined['MACD_Line'].shift(1) >= df_combined['Signal_Line'].shift(1))
    
    df_combined.loc[cruce_alcista, 'MACD_Cross'] = 1
    df_combined.loc[cruce_bajista, 'MACD_Cross'] = -1

    # 5. Condición de Color de Vela
    df_combined['Vela_Verde'] = df_combined['close'] > df_combined
