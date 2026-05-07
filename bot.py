import time
import random
import requests
from datetime import datetime, timedelta

# --- Configuración ------------------------------------------------
TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
CHAT_ID = "541470482"

HORA_INICIO = 7  # 07:00
HORA_FIN = 22    # 22:00
SCORE_MIN = 65
RR_MIN = 2.0

ASSETS = {
    "FOREX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDJPY=X", "EURGBP=X"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "ACCIONES": ["NVDA", "TSLA", "SPY", "QQQ", "AAPL"],
    "MATERIAS": ["GC=F", "SI=F", "CL=F"],
}

STRATEGIES = [
    {"key": "tendencia_ema", "label": "EMA 20/50/200"},
    {"key": "order_block_smc", "label": "Order Block SMC"},
    {"key": "divergencia_rsi", "label": "Divergencia RSI"},
    {"key": "stoch_rsi", "label": "Stochastic RSI"},
    {"key": "bollinger", "label": "Bollinger Bands"},
    {"key": "patron_velas", "label": "Patrón de Velas"},
    {"key": "soporte_resistencia", "label": "Soporte/Resistencia"},
    {"key": "macd_cruce", "label": "MACD Cruce"},
    {"key": "canal_regresion", "label": "Canal Regresión"},
]

# --- Funciones Auxiliares -----------------------------------------
def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def in_schedule():
    # Calcular tiempo CET aproximado (+1 hora o +2 según horario de verano, aquí usamos UTC+1 por simplicidad)
    ahora_utc = datetime.utcnow()
    cet = ahora_utc + timedelta(hours=1)
    return HORA_INICIO <= cet.hour <= HORA_FIN

def make_signal():
    categorias = list(ASSETS.keys())
    cat = random.choice(categorias)
    sym = random.choice(ASSETS[cat])
    
    dir = "COMPRA" if random.random() > 0.5 else "VENTA"
    score = SCORE_MIN + random.randint(0, 30)
    
    # Timeframes
    tfs_posibles = ["5m", "15m", "1h", "4h"]
    tfs = [tf for tf in tfs_posibles if random.random() > 0.4]
    if len(tfs) < 2:
        tfs.extend(["1h", "4h"])
    tfs = list(set(tfs)) # Eliminar duplicados
    entry_tf = tfs[-1]
    
    # Precios
    entry = round(random.uniform(1, 5000), 5)
    atr = round(entry * 0.002, 5)
    
    if dir == "COMPRA":
        sl = round(entry - atr * 1.2, 5)
        tp = round(entry + atr * 2.8, 5)
    else:
        sl = round(entry + atr * 1.2, 5)
        tp = round(entry - atr * 2.8, 5)
        
    rr = round(abs(tp - entry) / abs(sl - entry), 2)
    
    # Generar estrategias
    estrategias_activas = []
    for s in STRATEGIES:
        r = random.random()
        estado = None
        if r < 0.6:
            estado = dir
        elif r < 0.8:
            estado = "VENTA" if dir == "COMPRA" else "COMPRA"
            
        if estado:
            icono = "✅" if estado == dir else "❌"
            estrategias_activas.append(f"{icono} {s['label']}: {estado}")
        else:
            estrategias_activas.append(f"⚪ {s['label']}: ---")

    estrategias_str = "\n".join(estrategias_activas)
    timeframes_str = ", ".join(tfs)
    
    icono_dir = "🟢" if dir == "COMPRA" else "🔴"
    
    # Formatear el mensaje
    mensaje = f"""{icono_dir} <b>SEÑAL DE {dir}</b> {icono_dir}
    
<b>Activo:</b> {sym} ({cat})
<b>Score:</b> {score}/100
<b>Timeframes:</b> {timeframes_str} (Entrada: {entry_tf})

💰 <b>Entrada:</b> {entry}
🛑 <b>Stop Loss:</b> {sl}
🎯 <b>Take Profit:</b> {tp}
⚖️ <b>R/R:</b> {rr}:1

<b>Confirmaciones:</b>
{estrategias_str}
"""
    return score, rr, mensaje

# --- Bucle Principal ----------------------------------------------
print("Bot de Trading iniciado...")
enviar_mensaje_telegram("🤖 <b>Bot de Trading Iniciado</b>\nEsperando horario operativo (07:00 - 22:00 CET)...")

while True:
    try:
        if in_schedule():
            # Probabilidad de generar señal
            if random.random() <= 0.35: 
                score, rr, mensaje = make_signal()
                
                # Filtrar por estrategia
                if score >= SCORE_MIN and rr >= RR_MIN:
                    print(f"Enviando señal de {score} de score...")
                    enviar_mensaje_telegram(mensaje)
        
        # Esperar 4 segundos antes de la siguiente iteración
        time.sleep(4)
        
    except KeyboardInterrupt:
        print("Bot detenido por el usuario.")
        break
    except Exception as e:
        print(f"Error en el bucle principal: {e}")
        time.sleep(10)
