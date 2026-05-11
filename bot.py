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
    
    hora_actual = datetime.now(TZ).strftime('%H:%M:%S')
    mensaje += f"━━━━━━━━━━━━━━━\n\n🕒 **HORA SEÑAL:** `{hora_actual}`"
    return mensaje

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def obtener_datos(simbolo, tf="15m"):
    intervalos = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h"}
    intervalo_real = intervalos.get(tf, '15m')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}?interval={intervalo_real
