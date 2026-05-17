import os
import re
from telethon import TelegramClient, events
import MetaTrader5 as mt5
import google.generativeai as genai

# ==========================================
# CONFIGURACIÓN DE TUS CREDENCIALES
# ==========================================
# Tus datos de Telegram obtenidos
API_ID = 541470482  
API_HASH = '46340e54ba564f729daa48f10a32fbc1'  
# Tu clave API de Gemini que acabas de crear
GEMINI_KEY = 'AIzaSyBl9owl3E9o015rmYcVD8yOSV-E0d12FY8'  

# Canal de señales gratuito (Oro)
CANALES_TARGET = 'ssfgold' 

# Configurar la IA de Google
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

# Conectar con MetaTrader 5
if not mt5.initialize():
    print("❌ Error al conectar con MetaTrader 5. Asegúrate de tener MT5 abierto.")
    mt5.shutdown()
    quit()

print("✅ Conectado correctamente a MetaTrader 5")

client = TelegramClient('sesion_bot', API_ID, API_HASH)

def consultar_ia_traductora(texto_mensaje):
    """La IA analiza el mensaje de Telegram para extraer la operación limpia"""
    prompt = f"""
    Eres un asistente experto en trading. Analiza el siguiente mensaje enviado a un canal de señales de Oro (XAUUSD).
    Tu tarea es extraer los datos clave y devolverlos ESTRICTAMENTE en formato de texto plano con la siguiente estructura (si es una señal válida):
    ACCION: [COMPRA o VENTA]
    SL: [Precio de Stop Loss]
    TP: [Precio de Take Profit]

    Mensaje a analizar:
    \"{texto_mensaje}\"

    Si el mensaje NO es una señal de trading (es solo charla, capturas de ganancias, publicidad o resultados), responde únicamente con la palabra: IGNORED
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Error al consultar la IA: {e}")
        return "IGNORED"

def enviar_a_mt5(orden_limpia):
    """Procesa el texto de la IA y ejecuta la orden real en MetaTrader 5"""
    try:
        lineas = orden_limpia.split('\n')
        datos = {}
        for linea in lineas:
            if ':' in linea:
                k, v = linea.split(':', 1)
                datos[k.strip()] = v.strip()

        accion = datos.get('ACCION')
        sl = float(datos.get('SL', 0))
        tp = float(datos.get('TP', 0))
        
        symbol = "XAUUSD"
        # Seleccionar el tipo de orden según la IA
        tipo_orden = mt5.ORDER_TYPE_BUY if accion == "COMPRA" else mt5.ORDER_TYPE_SELL
        precio_actual = mt5.symbol_info_tick(symbol).ask if tipo_orden == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).bid

        solicitud = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,  # Lote mínimo de prueba para cuenta demo
            "type": tipo_orden,
            "price": precio_actual,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 12345,
            "comment": "Orden IA Gemini",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILL_IOC,
        }

        resultado_operacion = mt5.order_send(solicitud)
        if resultado_operacion.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"-> 🟢 ¡ORDEN ENVIADA CON ÉXITO! {accion} {symbol}")
        else:
            print(f"❌ Error al ejecutar en MT5: {resultado_operacion.comment}")
    except Exception as e:
        print(f"❌ Error al procesar el envío a MT5: {e}")

@client.on(events.NewMessage(chats=CANALES_TARGET))
async def recibir_mensajes(event):
    texto = event.message.message
    if not texto: return
    
    print("\n-- Mensaje entrante detectado, consultando a Gemini... --")
    orden_limpia = consultar_ia_traductora(texto)
    
    if "ACCION" in orden_limpia and "SL" in orden_limpia:
        print(f"📟 IA detectó señal válida:\n{orden_limpia}")
        enviar_a_mt5(orden_limpia)
    else:
        print("📥 IA analizó el mensaje: Es charla informativa, resultados o spam -> Ignorado.")

print("==================================================")
print("  BOT INTELIGENTE TRABAJANDO CON IA (GEMINI)      ")
print("  ESCUCHANDO TU GRUPO GRATUITO DE ORO EN TIEMPO REAL ")
print("==================================================")

client.start()
client.run_until_disconnected()
