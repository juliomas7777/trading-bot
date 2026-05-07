# ==========================================
# 📈 EXTENSOR DE FIBONACCI DE 3 PUNTOS (TP1 = 1.0)
# ==========================================
def calcular_extension_fibo_final(p1, p2, p3, tipo):
    # p1: Inicio del rechazo | p2: Punto medio (V) | p3: Extremo actual
    distancia = abs(p1 - p2)
    
    if tipo == "BULL": # Lógica para la W
        tp1 = p3 + (distancia * 1.0)   # <--- TU NIVEL 1 PARA TP1
        tp2 = p3 + (distancia * 1.618)
        sl = p3 - (distancia * 0.4)    # SL protegido por debajo del canal
    else: # Lógica para la M
        tp1 = p3 - (distancia * 1.0)   # <--- TU NIVEL 1 PARA TP1
        tp2 = p3 - (distancia * 1.618)
        sl = p3 + (distancia * 0.4)    # SL protegido por encima del canal
        
    return tp1, tp2, sl

# ==========================================
# 📡 MENSAJE DE SEÑAL FINAL (PRECISIÓN QUANTFURY)
# ==========================================
async def enviar_señal_fibo(bot, sym, tf, titulo, info):
    emoji = "🔴" if "M" in titulo else "🟢"
    msg = (
        f"{emoji} **ORDEN MARKET: {titulo}** {emoji}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"**ACTIVO:** `{sym}` | **TF:** `5 MIN` (Observación)\n"
        f"**ESTADO:** Canal Reseteado ✅\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🚀 **ENTRADA MARKET:** `{info['p']:.5f}`\n"
        f"🛑 **STOP LOSS:** `{info['sl']:.5f}`\n"
        f"🎯 **TP 1 (NIVEL 1.0):** `{info['tp1']:.5f}`\n"
        f"💎 **TP 2 (NIVEL 1.61):** `{info['tp2']:.5f}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚠️ *Si el precio rompe el canal, el bot buscará una nueva estructura.*"
    )
    await bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
