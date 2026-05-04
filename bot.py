#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          HARMONIC PATTERN BOT - QUANTFURY SIGNALS PARA TELEGRAM             ║
║         Patrones: Gartley, Bat, Butterfly, Crab, Shark, Cypher              ║
║         Temporalidades: 1H, 15MIN, 5MIN  |  RSI + Fibonacci                 ║
║                    @TuBotTelegram  v2.0                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════
#  INSTALACIÓN:
#  pip install -r requirements.txt
# ═══════════════════════════════════════════════════════

import os
import time
import math
import logging
import schedule
import threading
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import asyncio

# ═══════════════════════════════════════════════════════
#           ⚙️  CONFIGURACIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI")
CHAT_ID         = os.getenv("CHAT_ID", "TU_CHAT_ID_AQUI")

SCAN_INTERVAL_MINUTES = 5
RSI_PERIOD            = 14
RSI_OVERBOUGHT        = 70
RSI_OVERSOLD          = 30
TOLERANCE             = 0.08  # 8% tolerancia en ratios Fibonacci

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
#   📋  ACTIVOS QUANTFURY (2000+ activos cubiertos)
# ═══════════════════════════════════════════════════════

# ── CRYPTO (Patrones: Butterfly, Crab, Shark) ──
CRYPTO_ASSETS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","MATICUSDT",
    "LTCUSDT","LINKUSDT","UNIUSDT","ATOMUSDT","ETCUSDT",
    "XLMUSDT","VETUSDT","FILUSDT","TRXUSDT","EOSUSDT",
    "AAVEUSDT","SNXUSDT","COMPUSDT","MKRUSDT","YFIUSDT",
    "SUSHIUSDT","1INCHUSDT","GRTUSDT","RUNEUSDT","ICPUSDT",
    "ALGOUSDT","NEARUSDT","FTMUSDT","SANDUSDT","MANAUSDT",
    "AXSUSDT","GALAUSDT","APEUSDT","GMTUSDT","OPUSDT",
    "ARBUSDT","LDOUSDT","STXUSDT","INJUSDT","SUIUSDT",
    "SEIUSDT","TIAUSDT","JUPUSDT","WIFUSDT","BONKUSDT",
]

# ── ACCIONES USA (Patrones: Gartley, Bat, Cypher, Butterfly) ──
STOCKS_US = [
    "AAPL","MSFT","GOOGL","AMZN","TSLA","NVDA","META","NFLX",
    "AMD","INTC","BABA","SHOP","SQ","PYPL","UBER","LYFT",
    "SPOT","SNAP","PINS","RBLX","COIN","GME","AMC","PLTR",
    "RIVN","LCID","NIO","XPEV","LI","BIDU","JD","PDD",
    "MELI","SE","JPM","BAC","GS","MS","C","WFC","V","MA",
    "AXP","WMT","TGT","COST","HD","MCD","SBUX","NKE",
    "DIS","CMCSA","T","VZ","TMUS","PFE","JNJ","ABBV",
    "MRK","BMY","AMGN","GILD","BA","CAT","GE","HON",
    "MMM","LMT","RTX","XOM","CVX","COP","SLB","HAL",
]

# ── ETFs (Patrones: Gartley, Bat, Cypher, Butterfly) ──
ETFS = [
    "SPY","QQQ","IWM","DIA","VOO","VTI","VEA","VWO",
    "GLD","SLV","USO","UNG","TLT","IEF","SHY","BND",
    "AGG","HYG","LQD","XLF","XLK","XLE","XLV","XLI",
    "XLC","XLY","XLP","ARKK","ARKG","ARKW","ARKF",
    "SOXL","TQQQ","SQQQ","FXI","KWEB","EEM","EWJ","EWZ",
]

# ── FUTUROS (Patrones: Gartley, Bat, Cypher, Butterfly) ──
FUTURES = [
    "ES=F","NQ=F","YM=F","RTY=F","NKD=F",
    "GC=F","SI=F","HG=F","PL=F","PA=F",
    "CL=F","BZ=F","NG=F","RB=F","HO=F",
    "ZC=F","ZW=F","ZS=F","ZL=F","ZM=F",
    "BTC=F","ETH=F",
]

# ── FOREX / DIVISAS (Patrones: Gartley, Bat, Cypher, Butterfly) ──
FOREX_PAIRS = [
    "EURUSD=X","GBPUSD=X","JPY=X","CHFUSD=X","AUDUSD=X",
    "NZDUSD=X","CADUSD=X","EURGBP=X","EURJPY=X","GBPJPY=X",
    "AUDJPY=X","CADJPY=X","CHFJPY=X","NZDJPY=X","EURAUD=X",
    "EURCAD=X","EURCHF=X","GBPAUD=X","GBPCAD=X","GBPCHF=X",
    "AUDCAD=X","AUDCHF=X","AUDNZD=X","NZDCAD=X","NZDCHF=X",
    "MXN=X","BRL=X",
]

# ═══════════════════════════════════════════════════════
#   📐  RATIOS FIBONACCI - PATRONES ARMÓNICOS
# ═══════════════════════════════════════════════════════

HARMONIC_PATTERNS = {
    # ─── CRYPTO ───────────────────────────────────────
    "Butterfly": {
        "XAB": (0.786, 0.786),
        "ABC": (0.382, 0.886),
        "BCD": (1.618, 2.618),
        "XAD": (1.272, 1.618),
        "assets": ["CRYPTO","STOCKS","ETF","FUTURES","FOREX"],
        "emoji": "butterfly"
    },
    "Crab": {
        "XAB": (0.382, 0.618),
        "ABC": (0.382, 0.886),
        "BCD": (2.240, 3.618),
        "XAD": (1.618, 1.618),
        "assets": ["CRYPTO"],
        "emoji": "crab"
    },
    "Shark": {
        "XAB": (0.382, 0.618),
        "ABC": (1.128, 1.618),
        "BCD": (1.618, 2.236),
        "XAD": (0.886, 1.128),
        "assets": ["CRYPTO"],
        "emoji": "shark"
    },
    # ─── STOCKS / ETF / FUTUROS / FOREX ───────────────
    "Gartley": {
        "XAB": (0.618, 0.618),
        "ABC": (0.382, 0.886),
        "BCD": (1.272, 1.618),
        "XAD": (0.786, 0.786),
        "assets": ["STOCKS","ETF","FUTURES","FOREX"],
        "emoji": "target"
    },
    "Bat": {
        "XAB": (0.382, 0.500),
        "ABC": (0.382, 0.886),
        "BCD": (1.618, 2.618),
        "XAD": (0.886, 0.886),
        "assets": ["STOCKS","ETF","FUTURES","FOREX"],
        "emoji": "bat"
    },
    "Cypher": {
        "XAB": (0.382, 0.618),
        "ABC": (1.272, 1.414),
        "BCD": (0.786, 0.786),
        "XAD": (0.786, 0.786),
        "assets": ["STOCKS","ETF","FUTURES","FOREX"],
        "emoji": "lightning"
    },
}

TIMEFRAMES = ["5m", "15m", "1h"]
TIMEFRAME_LABELS = {
    "5m":  "5 Minutos",
    "15m": "15 Minutos",
    "1h":  "1 Hora",
}

# ═══════════════════════════════════════════════════════
#   📊  FUENTES DE DATOS GRATUITAS
# ═══════════════════════════════════════════════════════

def fetch_ohlcv_binance(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """Datos OHLCV desde Binance (sin API key requerida)."""
    try:
        url    = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        resp   = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","quote_vol","trades","taker_buy_base",
            "taker_buy_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df[["timestamp","open","high","low","close","volume"]]
    except Exception as e:
        logger.error(f"Binance error {symbol} {interval}: {e}")
        return pd.DataFrame()


def fetch_ohlcv_yahoo(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """Datos OHLCV desde Yahoo Finance (sin API key)."""
    try:
        period_map = {"5m": "5d", "15m": "15d", "1h": "60d"}
        period  = period_map.get(interval, "60d")
        url     = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval={interval}&range={period}"
        )
        headers = {"User-Agent": "Mozilla/5.0"}
        resp    = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        j       = resp.json()
        result  = j["chart"]["result"][0]
        ts      = result["timestamp"]
        q       = result["indicators"]["quote"][0]
        df      = pd.DataFrame({
            "timestamp": pd.to_datetime(ts, unit="s"),
            "open":   q["open"],
            "high":   q["high"],
            "low":    q["low"],
            "close":  q["close"],
            "volume": q["volume"],
        }).dropna()
        return df.tail(limit).reset_index(drop=True)
    except Exception as e:
        logger.error(f"Yahoo error {symbol} {interval}: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════
#   📈  CÁLCULO RSI
# ═══════════════════════════════════════════════════════

def calculate_rsi(closes: pd.Series, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    delta    = closes.diff()
    gain     = delta.where(delta > 0, 0.0)
    loss     = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


# ═══════════════════════════════════════════════════════
#   🔍  DETECCIÓN DE PIVOTS (ZIG-ZAG)
# ═══════════════════════════════════════════════════════

def find_pivots(df: pd.DataFrame, order: int = 5) -> list:
    """Encuentra puntos de giro para construir estructuras XABCD."""
    pivots = []
    highs  = df["high"].values
    lows   = df["low"].values
    n      = len(df)

    for i in range(order, n - order):
        is_ph = all(highs[i] >= highs[i-j] for j in range(1, order+1)) and                 all(highs[i] >= highs[i+j] for j in range(1, order+1))
        is_pl = all(lows[i]  <= lows[i-j]  for j in range(1, order+1)) and                 all(lows[i]  <= lows[i+j]  for j in range(1, order+1))
        if is_ph:
            pivots.append({"idx": i, "price": highs[i], "type": "H"})
        elif is_pl:
            pivots.append({"idx": i, "price": lows[i],  "type": "L"})

    # Eliminar pivots consecutivos del mismo tipo (mantener extremo)
    filtered = []
    for p in pivots:
        if filtered and filtered[-1]["type"] == p["type"]:
            if (p["type"] == "H" and p["price"] > filtered[-1]["price"]) or                (p["type"] == "L" and p["price"] < filtered[-1]["price"]):
                filtered[-1] = p
        else:
            filtered.append(p)
    return filtered


# ═══════════════════════════════════════════════════════
#   📐  VERIFICACIÓN DE RATIOS FIBONACCI
# ═══════════════════════════════════════════════════════

def in_range(actual: float, lo: float, hi: float, tol: float) -> bool:
    return lo * (1 - tol) <= actual <= hi * (1 + tol)


def check_pattern(X, A, B, C, D, pat_name: str) -> bool:
    pat = HARMONIC_PATTERNS.get(pat_name)
    if not pat:
        return False
    XA = abs(A - X)
    AB = abs(B - A)
    BC = abs(C - B)
    CD = abs(D - C)
    AD = abs(D - A)
    if 0 in (XA, AB, BC, CD):
        return False
    return (
        in_range(AB/XA, *pat["XAB"], TOLERANCE) and
        in_range(BC/AB, *pat["ABC"], TOLERANCE) and
        in_range(CD/BC, *pat["BCD"], TOLERANCE) and
        in_range(AD/XA, *pat["XAD"], TOLERANCE)
    )


# ═══════════════════════════════════════════════════════
#   🎯  MOTOR DE DETECCIÓN DE PATRONES
# ═══════════════════════════════════════════════════════

def detect_harmonics(df: pd.DataFrame, asset_type: str, symbol: str) -> list:
    signals = []
    if df is None or len(df) < 50:
        return signals

    pivots = find_pivots(df, order=5)
    if len(pivots) < 5:
        return signals

    applicable = {
        n: p for n, p in HARMONIC_PATTERNS.items()
        if asset_type in p["assets"]
    }

    for i in range(len(pivots) - 4):
        pts   = pivots[i:i+5]
        types = [p["type"] for p in pts]
        is_bull = types == ["L","H","L","H","L"]
        is_bear = types == ["H","L","H","L","H"]
        if not is_bull and not is_bear:
            continue

        X,A,B,C,D = [p["price"] for p in pts]

        for pat_name, pat in applicable.items():
            if check_pattern(X, A, B, C, D, pat_name):
                XA = abs(A - X)
                entry = D
                if is_bull:
                    sl  = D - XA * 0.13
                    tp1 = D + XA * 0.382
                    tp2 = D + XA * 0.618
                    order_type = "LIMIT" if pat["emoji"] in ["target","bat"] else "MARKET"
                else:
                    sl  = D + XA * 0.13
                    tp1 = D - XA * 0.382
                    tp2 = D - XA * 0.618
                    order_type = "LIMIT" if pat["emoji"] in ["target","bat"] else "MARKET"

                signals.append({
                    "pattern":    pat_name,
                    "emoji":      pat["emoji"],
                    "direction":  "ALCISTA" if is_bull else "BAJISTA",
                    "is_bull":    is_bull,
                    "entry":      entry,
                    "sl":         sl,
                    "tp1":        tp1,
                    "tp2":        tp2,
                    "order_type": order_type,
                    "symbol":     symbol,
                    "asset_type": asset_type,
                    "X": X, "A": A, "B": B, "C": C, "D": D,
                })
    return signals


# ═══════════════════════════════════════════════════════
#   📩  FORMATO DEL MENSAJE TELEGRAM
# ═══════════════════════════════════════════════════════

EMOJI_MAP = {
    "butterfly": "🦋",
    "crab":      "🦀",
    "shark":     "🦈",
    "target":    "🎯",
    "bat":       "🦇",
    "lightning": "⚡",
}

def format_message(sig: dict, rsi: float, tf: str) -> str:
    dot   = "🟢" if sig["is_bull"] else "🔴"
    dir_t = "📈 ALCISTA" if sig["is_bull"] else "📉 BAJISTA"
    emo   = EMOJI_MAP.get(sig["emoji"], "📐")
    tf_lb = TIMEFRAME_LABELS.get(tf, tf)

    if rsi >= RSI_OVERBOUGHT:
        rsi_s  = f"🔥 SOBRECOMPRADO ({rsi})"
        rsi_v  = "⚠️ RSI sobrecompra — señal alcista con menor confianza" if sig["is_bull"]                  else "✅ RSI confirma SOBRECOMPRADO — señal FUERTE"
    elif rsi <= RSI_OVERSOLD:
        rsi_s  = f"❄️ SOBREVENDIDO ({rsi})"
        rsi_v  = "✅ RSI confirma SOBREVENDIDO — señal FUERTE" if sig["is_bull"]                  else "⚠️ RSI sobreventa — señal bajista con menor confianza"
    else:
        rsi_s  = f"📊 Neutral ({rsi})"
        rsi_v  = "🔵 RSI neutral — operar con precaución"

    asset_labels = {
        "CRYPTO":"🪙 Criptomoneda","STOCKS":"📈 Acción",
        "ETF":"📦 ETF","FUTURES":"📜 Futuro","FOREX":"💱 Divisa"
    }
    a_lb = asset_labels.get(sig["asset_type"], sig["asset_type"])

    p = sig["entry"]
    dec = 0 if p > 1000 else (2 if p > 10 else 5)
    f = f"{{:.{dec}f}}"

    return (
        f"{dot} {emo} *PATRÓN ARMÓNICO DETECTADO* {dot}
"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━
"
        f"🏷 *Activo:* {sig['symbol']}  |  {a_lb}
"
        f"🔶 *Patrón:* {sig['pattern']} {emo}
"
        f"⏱ *Temporalidad:* {tf_lb}
"
        f"📡 *Dirección:* {dir_t}
"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━
"
        f"💰 *NIVELES DE OPERACIÓN:*
"
        f"🎯 *Entrada ({sig['order_type']}):*  {f.format(sig['entry'])}
"
        f"🛑 *Stop Loss:*              {f.format(sig['sl'])}
"
        f"✅ *TP1 (Fib 0.382):*       {f.format(sig['tp1'])}
"
        f"🚀 *TP2 (Fib 0.618):*       {f.format(sig['tp2'])}
"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━
"
        f"📐 *ESTRUCTURA FIBONACCI:*
"
        f"   X = {f.format(sig['X'])}
"
        f"   A = {f.format(sig['A'])}
"
        f"   B = {f.format(sig['B'])}
"
        f"   C = {f.format(sig['C'])}
"
        f"   D = {f.format(sig['D'])}  ← *ZONA PRZ*
"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━
"
        f"{rsi_s}
"
        f"{rsi_v}
"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━
"
        f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')} UTC
"
        f"⚡ _HarmonicBot Pro — Quantfury Signals_
"
        f"⚠️ _No es asesoría financiera. Usa gestión de riesgo._"
    )


# ═══════════════════════════════════════════════════════
#   🔄  ESCÁNER COMPLETO DE ACTIVOS
# ═══════════════════════════════════════════════════════

async def scan_all(bot: Bot):
    logger.info("🔍 Iniciando escaneo completo Quantfury...")
    groups = [
        (CRYPTO_ASSETS,  "CRYPTO",  fetch_ohlcv_binance),
        (STOCKS_US,      "STOCKS",  fetch_ohlcv_yahoo),
        (ETFS,           "ETF",     fetch_ohlcv_yahoo),
        (FUTURES,        "FUTURES", fetch_ohlcv_yahoo),
        (FOREX_PAIRS,    "FOREX",   fetch_ohlcv_yahoo),
    ]
    total_sent = 0
    for assets, atype, fetch_fn in groups:
        for symbol in assets:
            for tf in TIMEFRAMES:
                try:
                    df = fetch_fn(symbol, tf)
                    if df is None or len(df) < 50:
                        continue
                    rsi  = calculate_rsi(df["close"])
                    sigs = detect_harmonics(df, atype, symbol)
                    for sig in sigs:
                        msg = format_message(sig, rsi, tf)
                        await bot.send_message(
                            chat_id    = CHAT_ID,
                            text       = msg,
                            parse_mode = "Markdown"
                        )
                        total_sent += 1
                        logger.info(f"✅ {symbol} | {sig['pattern']} | {tf}")
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error {symbol} {tf}: {e}")
            await asyncio.sleep(0.2)

    summary = (
        f"📊 Escaneo completado\n{total_sent} señal(es) enviada(s)."
        if total_sent > 0 else
        "🔍 Escaneo completado. Sin patrones detectados en este ciclo."
    )
    await bot.send_message(chat_id=CHAT_ID, text=summary)


# ═══════════════════════════════════════════════════════
#   🤖  COMANDOS TELEGRAM
# ═══════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *HarmonicBot Pro — Quantfury Signals*\n\n"
        "Comandos:\n"
        "/scan   — Escaneo manual\n"
        "/status — Estado del bot\n"
        "/help   — Estrategia y patrones\n\n"
        "⏰ Escaneo automático cada 5 minutos.",
        parse_mode="Markdown"
    )

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Iniciando escaneo... puede tardar varios minutos.")
    await scan_all(context.bot)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = len(CRYPTO_ASSETS)+len(STOCKS_US)+len(ETFS)+len(FUTURES)+len(FOREX_PAIRS)
    await update.message.reply_text(
        f"✅ *HarmonicBot Pro — ACTIVO*\n\n"
        f"📊 Activos monitoreados: {total}\n"
        f"  🪙 Crypto: {len(CRYPTO_ASSETS)}\n"
        f"  📈 Acciones: {len(STOCKS_US)}\n"
        f"  📦 ETFs: {len(ETFS)}\n"
        f"  📜 Futuros: {len(FUTURES)}\n"
        f"  💱 Forex: {len(FOREX_PAIRS)}\n\n"
        f"⏱ Temporalidades: 5m | 15m | 1h\n"
        f"📐 Tolerancia Fibonacci: {int(TOLERANCE*100)}%\n"
        f"📊 RSI Sobrecompra:{RSI_OVERBOUGHT} | Sobreventa:{RSI_OVERSOLD}",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *GUÍA DE PATRONES ARMÓNICOS*\n\n"
        "*🪙 CRYPTO → Butterfly 🦋 | Crab 🦀 | Shark 🦈*\n"
        "*📈 STOCKS/ETF/FUT/FX → Gartley 🎯 | Bat 🦇 | Cypher ⚡ | Butterfly 🦋*\n\n"
        "*🟢 VERDE = ALCISTA (Long/Compra)*\n"
        "*🔴 ROJO = BAJISTA (Short/Venta)*\n\n"
        "*📐 Estrategia:*\n"
        "1️⃣ Entra en zona PRZ (punto D)\n"
        "2️⃣ SL = 13% del tramo XA bajo/sobre D\n"
        "3️⃣ TP1 = Fibonacci 0.382 del tramo AD\n"
        "4️⃣ TP2 = Fibonacci 0.618 del tramo AD\n"
        "5️⃣ Valida RSI: Sobreventa=Compra | Sobrecompra=Venta\n"
        "6️⃣ Mayor confianza = patrón en 2-3 temporalidades\n\n"
        "⚠️ _No es asesoría financiera._",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════
#   ▶️  MAIN
# ═══════════════════════════════════════════════════════

def run_scheduler(app):
    async def do_scan():
        async with app:
            await scan_all(app.bot)

    def scheduled():
        asyncio.run(do_scan())

    schedule.every(SCAN_INTERVAL_MINUTES).minutes.do(scheduled)
    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    logger.info("🚀 HarmonicBot Pro iniciando...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help",   cmd_help))

    t = threading.Thread(target=run_scheduler, args=(app,), daemon=True)
    t.start()

    logger.info("✅ Bot activo. Esperando comandos...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
