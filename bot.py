import time
import requests
import pandas as pd
import numpy as np
import pytz
from datetime import datetime

# -------------------------------------------------------------------
# CONFIGURACIÓN GLOBAL
# -------------------------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"
TZ = pytz.timezone("Europe/Madrid")
HORA_INICIO = 7
HORA_FIN = 22

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

señales_enviadas = set()

# -------------------------------------------------------------------
# FORMATO VISUAL TELEGRAM
# -------------------------------------------------------------------
def generar_mensaje_telegram(par, direccion, ent, sl, tp1, tp2=None, tp3=None, nombre_est="", marco="", tipo_orden="MARKET"):
    if direccion == 1 or "COMPRA" in str(direccion).upper() or "LONG" in str(direccion).upper():
        cabecera = f"🔵🔵 {tipo_orden} 🔵🔵\n🟢 COMPRA (LONG) 🟢"
    else:
        cabecera = f"🔵🔵 {tipo_orden} 🔵🔵\n🔴 VENTA (SHORT) 🔴"

    alerta_par = f"⚠️⚠️⚠️ **¡¡{par}!!** ⚠️⚠️⚠️" if par == "GBP/USD" else f"📈 **ACTIVO: {par.upper()}**"
    
    mensaje = (
        f"{cabecera}\n\n"
        f"🧠 **ESTRATEGIA:** `{nombre_est}`\n"
        f"⏳ **MARCO:** `{marco}`\n"
        f"{alerta_par}\n\n"
        f"📍 **ORDEN:** `{tipo_orden}`\n"
        f"🚀 **ENTRADA:** **{ent}**\n"
        f"🛡️ **STOP LOSS:** **{sl}**\n"
        f"🎯 **TP 1:** **{tp1}**\n"
    )
    if tp2: mensaje += f"🎯 **TP 2:** **{tp2}**\n"
    if tp3: mensaje += f"🎯 **TP 3:** **{tp3}**\n"
    
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **VELA CERRADA:** `{datetime.now(TZ).strftime('%H:%M:%S')}`"
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# -------------------------------------------------------------------
# OBTENCIÓN DE DATOS
# -------------------------------------------------------------------
def obtener_datos(simbolo, tf="15m"):
    intervalos = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalos.get(tf, '15m')}&range=5d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        data = r.json()["chart"]["result"][0]
        q = data["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"], "close": q["close"]
        }, index=pd.to_datetime(data["timestamp"], unit='s', utc=True).tz_convert(TZ)).dropna()
        if tf == "4h": df = df.iloc[::4, :].copy()
        return df
    except: return None

# -------------------------------------------------------------------
# ESTRATEGIA 1: ICT ALEX RUIZ (M15 + H4)
# -------------------------------------------------------------------
def est_ict_alex_m15(df_15m, df_4h):
    if df_15m is None or df_4h is None or len(df_15m) < 40: return None
    df = df_15m.iloc[:-1].copy()
    df_h4 = df_4h.iloc[:-1].copy()
    ts = df.index[-1]
    
    weekly_open = df.iloc[0]['open']
    current_price = df.iloc[-1]['close']
    h4_trend = "COMPRA" if df_h4.iloc[-1]['high'] > df_h4.iloc[-2]['high'] else "VENTA"
    
    bias = "COMPRA" if current_price < weekly_open and h4_trend == "COMPRA" else "VENTA" if current_price > weekly_open and h4_trend == "VENTA" else None
    if not bias: return None

    r_high, r_low = df['high'].tail(30).max(), df['low'].tail(30).min()
    rango = r_high - r_low
    
    if bias == "COMPRA" and (r_high - (rango * 0.79)) <= current_price <= (r_high - (rango * 0.62)):
        return "COMPRA", round(current_price, 5), round(r_low, 5), round(r_high, 5), round(r_high + (rango * 0.27), 5), ts
    elif bias == "VENTA" and (r_low + (rango * 0.62)) <= current_price <= (r_low + (rango * 0.79)):
        return "VENTA", round(current_price, 5), round(r_high, 5), round(r_low, 5), round(r_low - (rango * 0.27), 5), ts
    return None

# -------------------------------------------------------------------
# ESTRATEGIA 2: MACD 2.0 (TU CÓDIGO CON TODOS LOS PARÁMETROS)
# -------------------------------------------------------------------
def est_estrategia_precision(df_menor: pd.DataFrame, df_mayor: pd.DataFrame, 
                             ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, 
                             rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001):
    
    # PASO 1 Y 2: HTF
    df_htf = df_mayor.copy()
    df_ltf = df_menor.copy()
    
    df_htf['EMA_100_HTF'] = df_htf['close'].ewm(span=ema_period, adjust=False).mean()
    df_htf['Trend_HTF'] = np.where(df_htf['close'] > df_htf['EMA_100_HTF'], 1, -1)
    
    df_htf['Resistencia_HTF'] = df_htf['high'].rolling(window=pivot_window).max().shift(1)
    df_htf['Soporte_HTF'] = df_htf['low'].rolling(window=pivot_window).min().shift(1)
    
    df_htf['Touch_Resistencia'] = np.where(abs(df_htf['high'] - df_htf['Resistencia_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    df_htf['Touch_Soporte'] = np.where(abs(df_htf['low'] - df_htf['Soporte_HTF']) / df_htf['close'] <= tolerance_pct, True, False)
    
    df_htf_signals = df_htf[['EMA_100_HTF', 'Trend_HTF', 'Touch_Resistencia', 'Touch_Soporte']]
    
    # PASO 3: MERGE
    df_combined = pd.merge_asof(df_ltf.sort_index(), df_htf_signals.sort_index(), 
                                left_index=True, right_index=True, direction='backward')
    
    # PASO 4: LTF (MACD)
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

    # PASO 5: GESTIÓN
    df_combined['Signal'] = 0
    df_combined['Entry_Price'] = np.nan
    df_combined['Stop_Loss'] = np.nan
    df_combined['Take_Profit'] = np.nan
    
    cond_long = (
        (df_combined['Trend_HTF'] == 1) & 
        (df_combined['Touch_Soporte'] == True) & 
        (df_combined['MACD_Cross'] == 1) & 
        (df_combined['Vela_Verde'] == True)
    )
    
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

# -------------------------------------------------------------------
# BUCLE PRINCIPAL
# -------------------------------------------------------------------
print("🤖 Bot Dual Activo: ICT Alex Ruiz (M15) + MACD Ruiz (M5/M15)")

while True:
    ahora = datetime.now(TZ)
    for ticker, nombre in ASSETS_MAP.items():
        if "-USD" in ticker or (HORA_INICIO <= ahora.hour < HORA_FIN):
            
            d5m = obtener_datos(ticker, "5m")
            d15m = obtener_datos(ticker, "15m")
            d4h = obtener_datos(ticker, "4h")
            
            # --- 1. ICT ALEX RUIZ ---
            res_ict = est_ict_alex_m15(d15m, d4h)
            if res_ict:
                # res_ict[-1] es el timestamp de la vela cerrada
                id_ict = f"{ticker}_ICT_{res_ict[5].strftime('%Y-%m-%d_%H:%M')}"
                if id_ict not in señales_enviadas:
                    msg = generar_mensaje_telegram(nombre, res_ict[0], res_ict[1], res_ict[2], res_ict[3], res_ict[4], None, "ICT Alex Ruiz", "15M / 4H", "MARKET")
                    enviar_telegram(msg)
                    señales_enviadas.add(id_ict)

            # --- 2. MACD + MTF + S/R ---
            if d5m is not None and d15m is not None:
                # Usamos los parámetros exactos de tu código
                df_macd = est_estrategia_precision(d5m, d15m, ema_period=100, macd_fast=12, macd_slow=26, macd_sign=9, rr_ratio=2.0, pivot_window=20, tolerance_pct=0.001)
                
                # Revisamos la vela que acaba de cerrar (la penúltima en el dataframe)
                if len(df_macd) > 2:
                    ultima_vela = df_macd.iloc[-2]
                    if ultima_vela['Signal'] != 0:
                        ts_macd = df_macd.index[-2]
                        id_macd = f"{ticker}_MACD_{ts_macd.strftime('%Y-%m-%d_%H:%M')}"
                        
                        if id_macd not in señales_enviadas:
                            msg_macd = generar_mensaje_telegram(
                                nombre, 
                                ultima_vela['Signal'], 
                                round(ultima_vela['Entry_Price'], 5), 
                                round(ultima_vela['Stop_Loss'], 5), 
                                round(ultima_vela['Take_Profit'], 5), 
                                "MACD", 
                                "5M / 15M", 
                                "LIMIT ORDER"
                            )
                            enviar_telegram(msg_macd)
                            señales_enviadas.add(id_macd)
            
            time.sleep(0.5) # Evitar Rate Limit de Yahoo

    # Limpieza de memoria
    if len(señales_enviadas) > 500: señales_enviadas.clear()
    time.sleep(30)
