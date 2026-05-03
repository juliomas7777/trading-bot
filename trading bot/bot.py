#!/usr/bin/env python3
# =============================================================================
# BOT DE SEÑALES TRADING ARMONICO + SMART MONEY + SENTIMIENTO DE MERCADO
# Version: 3.0 | Multi-activo | Multi-temporalidad | Telegram
# =============================================================================
# INSTALACION: pip install requests pandas numpy schedule
# =============================================================================

import requests
import pandas as pd
import numpy as np
import schedule
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# -------------------------------------------------
# CONFIGURACION - EDITA SOLO ESTAS LINEAS
# -------------------------------------------------
TELEGRAM_TOKEN   = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y"
TELEGRAM_CHAT_ID = "541470482"
NEWSAPI_KEY      = "46340e54ba564f729daa48f10a32fbc1"

# -------------------------------------------------
# ACTIVOS DE QUANTFURY
# -------------------------------------------------
SYMBOLS = {
    "CRYPTO": [
        "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","ADAUSDT",
        "XRPUSDT","DOTUSDT","AVAXUSDT","MATICUSDT","LINKUSDT",
        "LTCUSDT","UNIUSDT","ATOMUSDT","NEARUSDT","APTUSDT"
    ],
    "FOREX": [
        "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD",
        "NZDUSD","USDCAD","EURJPY","GBPJPY","EURGBP"
    ],
    "INDICES": [
        "US30","SPX500","NAS100","GER40","UK100","JPN225"
    ],
    "COMMODITIES": [
        "XAUUSD","XAGUSD","USOIL","NATGAS"
    ],
    "STOCKS": [
        "AAPL","TSLA","MSFT","NVDA","AMZN","META","GOOGL"
    ]
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# =============================================================================
# 1. OBTENCION DE DATOS
# =============================================================================

def get_binance(symbol, interval, limit=300):
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        if r.status_code != 200:
            return None
        df = pd.DataFrame(r.json(), columns=[
            "ts","open","high","low","close","volume",
            "ct","qv","trades","tbb","tbq","ign"
        ])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["ts"] = pd.to_datetime(df["ts"], unit="ms")
        df.set_index("ts", inplace=True)
        return df
    except Exception as e:
        log.error(f"Binance {symbol} {interval}: {e}")
        return None

def get_yahoo(symbol, interval, limit=300):
    try:
        imap = {"5m":"5m","15m":"15m","1h":"60m","4h":"60m","1d":"1d"}
        pmap = {"5m":"5d","15m":"10d","60m":"30d","1d":"1y"}
        yf_i = imap.get(interval, "15m")
        per  = pmap.get(yf_i, "10d")
        sym  = _yahoo_sym(symbol)
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
            params={"interval": yf_i, "range": per},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        if r.status_code != 200:
            return None
        res = r.json()["chart"]["result"][0]
        q   = res["indicators"]["quote"][0]
        df  = pd.DataFrame({
            "ts": pd.to_datetime(res["timestamp"], unit="s"),
            "open": q["open"], "high": q["high"],
            "low": q["low"], "close": q["close"], "volume": q["volume"]
        })
        df.dropna(inplace=True)
        df.set_index("ts", inplace=True)
        return df.tail(limit)
    except Exception as e:
        log.error(f"Yahoo {symbol} {interval}: {e}")
        return None

def _yahoo_sym(s):
    fx = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD",
          "EURJPY","GBPJPY","EURGBP","AUDCAD","AUDNZD","CADCHF","CHFJPY",
          "EURCAD","EURCHF","GBPAUD","GBPCAD","NZDCAD","NZDJPY"]
    idx = {"US30":"^DJI","SPX500":"^GSPC","NAS100":"^IXIC","GER40":"^GDAXI",
           "UK100":"^FTSE","JPN225":"^N225","FRA40":"^FCHI","AUS200":"^AXJO"}
    cmd = {"XAUUSD":"GC=F","XAGUSD":"SI=F","USOIL":"CL=F","NATGAS":"NG=F","UKOIL":"BZ=F"}
    if s in fx:  return s[:3]+s[3:]+"=X"
    if s in idx: return idx[s]
    if s in cmd: return cmd[s]
    return s

def get_data(symbol, market, interval, limit=300):
    if market == "CRYPTO":
        return get_binance(symbol, interval, limit)
    return get_yahoo(symbol, interval, limit)

# =============================================================================
# 2. INDICADORES
# =============================================================================

def calc_indicators(df):
    if df is None or len(df) < 50:
        return None
    c = df["close"]; h = df["high"]; l = df["low"]; v = df["volume"]
    d = c.diff()
    g = d.where(d>0,0).rolling(14).mean()
    ls = (-d.where(d<0,0)).rolling(14).mean()
    df["rsi"] = 100 - (100/(1+g/(ls+1e-10)))
    e12 = c.ewm(span=12).mean(); e26 = c.ewm(span=26).mean()
    df["macd"] = e12 - e26
    df["macd_sig"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]
    for p in [20,50,200]: df[f"ema{p}"] = c.ewm(span=p).mean()
    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    s20 = c.rolling(20).mean(); std20 = c.rolling(20).std()
    df["bb_up"] = s20+2*std20; df["bb_lo"] = s20-2*std20
    df["vol_ma"] = v.rolling(20).mean()
    df["vol_ratio"] = v/(df["vol_ma"]+1e-10)
    l14 = l.rolling(14).min(); h14 = h.rolling(14).max()
    df["stk"] = 100*(c-l14)/(h14-l14+1e-10)
    pdm = h.diff(); mdm = -l.diff()
    pdm[pdm<0]=0; mdm[mdm<0]=0
    atr14 = tr.rolling(14).mean()
    pdi = 100*(pdm.rolling(14).mean()/(atr14+1e-10))
    mdi = 100*(mdm.rolling(14).mean()/(atr14+1e-10))
    dx  = 100*(pdi-mdi).abs()/(pdi+mdi+1e-10)
    df["adx"] = dx.rolling(14).mean()
    df["cvd"] = (v*np.sign(c-c.shift())).cumsum()
    return df

# =============================================================================
# 3. ESTRUCTURA DE MERCADO
# =============================================================================

def swing_points(df, w=5):
    highs=[]; lows=[]
    for i in range(w, len(df)-w):
        if df["high"].iloc[i]==df["high"].iloc[i-w:i+w+1].max():
            highs.append((i, df["high"].iloc[i]))
        if df["low"].iloc[i]==df["low"].iloc[i-w:i+w+1].min():
            lows.append((i, df["low"].iloc[i]))
    return {"highs": highs, "lows": lows}

def market_structure(df):
    if df is None or len(df)<30:
        return {"trend":"RANGE","bos":False,"choch":False,"zone":"NEUTRAL"}
    sw = swing_points(df)
    H  = sw["highs"]; L = sw["lows"]
    trend="RANGE"; bos=False; choch=False
    if len(H)>=2 and len(L)>=2:
        hh = H[-1][1]>H[-2][1]; hl = L[-1][1]>L[-2][1]
        lh = H[-1][1]<H[-2][1]; ll = L[-1][1]<L[-2][1]
        if hh and hl:   trend="BULLISH"
        elif lh and ll: trend="BEARISH"
        last = df["close"].iloc[-1]
        if trend=="BULLISH" and last>H[-1][1]: bos=True
        if trend=="BEARISH" and last<L[-1][1]: bos=True
        if trend=="BULLISH" and ll: choch=True
        if trend=="BEARISH" and hh: choch=True
    hi50 = df["high"].tail(50).max()
    lo50 = df["low"].tail(50).min()
    mid  = (hi50+lo50)/2
    zone = "PREMIUM" if df["close"].iloc[-1]>mid else "DISCOUNT"
    return {"trend":trend,"bos":bos,"choch":choch,"zone":zone,"highs":H,"lows":L}

# =============================================================================
# 4. LIQUIDEZ
# =============================================================================

def detect_liquidity(df):
    res = {"eq_hi":False,"eq_lo":False,"bsl":0.0,"ssl":0.0,
           "sh_bull":False,"sh_bear":False,"score":0}
    if df is None or len(df)<20: return res
    h20 = df["high"].tail(20); l20 = df["low"].tail(20)
    tol = df["atr"].iloc[-1]*0.3 if "atr" in df.columns else 0
    mxh = h20.max()
    if (h20>=mxh-tol).sum()>=2: res["eq_hi"]=True; res["ssl"]=mxh; res["score"]+=1
    mxl = l20.min()
    if (l20<=mxl+tol).sum()>=2: res["eq_lo"]=True; res["bsl"]=mxl; res["score"]+=1
    last = df.iloc[-1]
    body = abs(last["open"]-last["close"])
    wu   = last["high"]-max(last["open"],last["close"])
    wd   = min(last["open"],last["close"])-last["low"]
    if body>0 and wu>body*2.5: res["sh_bull"]=True; res["score"]+=2
    if body>0 and wd>body*2.5: res["sh_bear"]=True; res["score"]+=2
    return res

# =============================================================================
# 5. WYCKOFF
# =============================================================================

def wyckoff_phase(df):
    res = {"phase":"UNKNOWN","spring":False,"upthrust":False,"score":0}
    if df is None or len(df)<50: return res
    rec = df.tail(30); v = rec["volume"]; c = rec["close"]
    vm = v.mean(); vs = v.std()
    pr = (rec["high"].max()-rec["low"].min())/rec["close"].mean()
    vt = v.iloc[-10:].mean()/(v.iloc[:10].mean()+1e-10)
    if   pr<0.05 and vt<0.85:  res["phase"]="ACCUMULATION"; res["score"]+=2
    elif pr<0.05 and vt>1.15:  res["phase"]="DISTRIBUTION";  res["score"]+=2
    elif c.iloc[-1]>c.iloc[-10]: res["phase"]="MARKUP";      res["score"]+=1
    else:                        res["phase"]="MARKDOWN";     res["score"]+=1
    last = df.iloc[-1]; pl = df["low"].tail(20).iloc[:-1].min()
    if last["low"]<pl and last["close"]>pl and last["volume"]>vm+vs:
        res["spring"]=True; res["score"]+=3
    ph = df["high"].tail(20).iloc[:-1].max()
    if last["high"]>ph and last["close"]<ph and last["volume"]>vm+vs:
        res["upthrust"]=True; res["score"]+=3
    return res

# =============================================================================
# 6. PATRONES ARMONICOS
# =============================================================================

HR = {
    "GARTLEY":   {"XAB":(0.618,0.618),"ABC":(0.382,0.886),"BCD":(1.272,1.618),"XAD":(0.786,0.786),"tol":0.07},
    "BAT":       {"XAB":(0.382,0.500),"ABC":(0.382,0.886),"BCD":(1.618,2.618),"XAD":(0.886,0.886),"tol":0.07},
    "BUTTERFLY": {"XAB":(0.786,0.786),"ABC":(0.382,0.886),"BCD":(1.618,2.618),"XAD":(1.272,1.618),"tol":0.07},
    "CRAB":      {"XAB":(0.382,0.618),"ABC":(0.382,0.886),"BCD":(2.240,3.618),"XAD":(1.618,1.618),"tol":0.07},
    "SHARK":     {"XAB":(0.446,0.618),"ABC":(1.130,1.618),"BCD":(1.618,2.240),"XAD":(0.886,1.130),"tol":0.08},
    "CYPHER":    {"XAB":(0.382,0.618),"ABC":(1.130,1.414),"BCD":(0.786,0.786),"XAD":(0.786,0.786),"tol":0.07}
}

def fib(a,b,c):
    if abs(a-b)<1e-10: return 0
    return abs(c-b)/abs(a-b)

def w_in(v, lo, hi, tol):
    return lo-tol <= v <= hi+tol

def pat_confidence(xab,abc,bcd,xad,r):
    t=r["tol"]; sc=[]
    for val,targets in [(xab,r["XAB"]),(xad,r["XAD"])]:
        sc.append(max(0,1-min(abs(val-t) for t in targets)/t))
    for val,(lo,hi) in [(abc,r["ABC"]),(bcd,r["BCD"])]:
        mid=(lo+hi)/2; sc.append(max(0,1-abs(val-mid)/((hi-lo)/2+t)))
    return round(np.mean(sc)*100,1)

def scan_harmonics(df, market):
    found = []
    if df is None or len(df)<50: return found
    sw   = swing_points(df)
    pats = (["BUTTERFLY","CRAB","SHARK"] if market=="CRYPTO"
            else ["GARTLEY","BAT","CYPHER"] if market in ["FOREX","INDICES"]
            else ["GARTLEY","BAT","BUTTERFLY","CRAB"])
    pts  = ([(i,p,"H") for i,p in sw["highs"]]+
            [(i,p,"L") for i,p in sw["lows"]])
    pts.sort(key=lambda x: x[0])
    if len(pts)<5: return found
    rec = pts[-8:]
    for pi in range(len(rec)-4):
        X,A,B,C,D = rec[pi],rec[pi+1],rec[pi+2],rec[pi+3],rec[pi+4]
        xp,ap,bp,cp,dp = X[1],A[1],B[1],C[1],D[1]
        bull = X[2]=="L" and A[2]=="H" and B[2]=="L" and C[2]=="H" and D[2]=="L"
        bear = X[2]=="H" and A[2]=="L" and B[2]=="H" and C[2]=="L" and D[2]=="H"
        if not (bull or bear): continue
        xab=fib(xp,ap,bp); abc=fib(ap,bp,cp); bcd=fib(bp,cp,dp); xad=fib(xp,ap,dp)
        for name in pats:
            r=HR[name]; t=r["tol"]
            if (w_in(xab,r["XAB"][0],r["XAB"][1],t) and
                w_in(abc,r["ABC"][0],r["ABC"][1],t) and
                w_in(bcd,r["BCD"][0],r["BCD"][1],t) and
                w_in(xad,r["XAD"][0],r["XAD"][1],t)):
                found.append({
                    "pattern": name,
                    "direction": "BUY" if bull else "SELL",
                    "D_point": dp, "X_point": xp,
                    "confidence": pat_confidence(xab,abc,bcd,xad,r)
                })
    return found

# =============================================================================
# 7. MULTI-TEMPORALIDAD
# =============================================================================

def mtf_analysis(symbol, market):
    tfs = {
        "1d":  ("1d",  4),
        "4h":  ("4h" if market=="CRYPTO" else "60m", 3),
        "1h":  ("1h" if market=="CRYPTO" else "60m", 2),
        "15m": ("15m", 1.5),
        "5m":  ("5m",  1)
    }
    results={}; ob=0; oe=0; tw=0
    for name,(iv,w) in tfs.items():
        df = get_data(symbol, market, iv)
        if df is None: continue
        df = calc_indicators(df)
        if df is None: continue
        ms  = market_structure(df)
        liq = detect_liquidity(df)
        wyc = wyckoff_phase(df)
        last = df.iloc[-1]
        bs=0; se=0
        if ms["trend"]=="BULLISH": bs+=2
        if ms["trend"]=="BEARISH": se+=2
        if ms["bos"]:
            if ms["trend"]=="BULLISH": bs+=1
            else: se+=1
        if ms["choch"]:
            if ms["trend"]=="BEARISH": bs+=1
            else: se+=1
        if ms["zone"]=="DISCOUNT": bs+=1
        if ms["zone"]=="PREMIUM":  se+=1
        if last["rsi"]<35:         bs+=1
        if last["rsi"]>65:         se+=1
        if last["macd_hist"]>0:    bs+=1
        if last["macd_hist"]<0:    se+=1
        if wyc["spring"]:          bs+=2
        if wyc["upthrust"]:        se+=2
        ob+=bs*w; oe+=se*w; tw+=w
        results[name]={
            "trend":ms["trend"],"rsi":round(last["rsi"],1),
            "adx":round(last["adx"],1),"wyckoff":wyc["phase"],
            "spring":wyc["spring"],"upthrust":wyc["upthrust"],
            "bos":ms["bos"],"choch":ms["choch"],"zone":ms["zone"],
            "liq":liq["score"],"bs":bs,"se":se,
            "close":round(last["close"],8),"atr":round(last["atr"],8),
            "vol":round(last["vol_ratio"],2)
        }
    nb=ob/(tw+1e-10); ne=oe/(tw+1e-10)
    if   nb>ne*1.3: dom="BUY";  cpct=round(min(100,nb/(nb+ne+1e-10)*100),1)
    elif ne>nb*1.3: dom="SELL"; cpct=round(min(100,ne/(nb+ne+1e-10)*100),1)
    else:           dom="NEUTRAL"; cpct=50.0
    return {"timeframes":results,"dominant":dom,"confluence_pct":cpct,"bull":round(nb,2),"bear":round(ne,2)}

# =============================================================================
# 8. SENTIMIENTO
# =============================================================================

def get_sentiment(symbol):
    res={"fg":50,"sent":"NEUTRAL","news_risk":False,"news":[],"score":0}
    try:
        r=requests.get("https://api.alternative.me/fng/?limit=1",timeout=8)
        if r.status_code==200:
            v=int(r.json()["data"][0]["value"])
            res["fg"]=v
            if v>=60: res["sent"]="GREED"; res["score"]+=1
            elif v<=40: res["sent"]="FEAR"; res["score"]+=1
    except: pass
    try:
        sym=symbol.replace("USDT","").replace("USD","").replace("=X","")
        r=requests.get("https://newsapi.org/v2/everything",
            params={"q":f"{sym} trading news","sortBy":"publishedAt",
                    "pageSize":10,"language":"en",
                    "from":(datetime.now()-timedelta(hours=4)).isoformat(),
                    "apiKey":NEWSAPI_KEY}, timeout=10)
        if r.status_code==200:
            kwds=["crash","ban","hack","regulation","lawsuit","sec",
                  "collapse","bankrupt","fraud","war","sanction","recession"]
            for a in r.json().get("articles",[])[:5]:
                txt=(a.get("title","")+a.get("description","")).lower()
                if any(k in txt for k in kwds):
                    res["news_risk"]=True
                    res["news"].append(a.get("title",""))
    except: pass
    return res

# =============================================================================
# 9. NIVELES DE TRADING
# =============================================================================

def trade_levels(df, direction, pattern, market):
    last=df.iloc[-1]; atr=last["atr"]; close=last["close"]
    rf={"CRYPTO":2.0,"FOREX":1.5,"INDICES":1.8,"COMMODITIES":1.6,"STOCKS":1.7}.get(market,1.5)
    dp=pattern.get("D_point",close)
    if direction=="BUY":
        otype="LIMIT" if dp<close*0.995 else "MARKET"
        entry=round(dp*1.002,8) if otype=="LIMIT" else close
        sl=round(entry-atr*rf,8)
        tp1=round(entry+atr*rf*1.5,8); tp2=round(entry+atr*rf*3.0,8)
        rr1=round((tp1-entry)/(entry-sl+1e-10),2)
        rr2=round((tp2-entry)/(entry-sl+1e-10),2)
    else:
        otype="LIMIT" if dp>close*1.005 else "MARKET"
        entry=round(dp*0.998,8) if otype=="LIMIT" else close
        sl=round(entry+atr*rf,8)
        tp1=round(entry-atr*rf*1.5,8); tp2=round(entry-atr*rf*3.0,8)
        rr1=round((entry-tp1)/(sl-entry+1e-10),2)
        rr2=round((entry-tp2)/(sl-entry+1e-10),2)
    return {"type":otype,"entry":entry,"sl":sl,"tp1":tp1,"tp2":tp2,"rr1":rr1,"rr2":rr2}

# =============================================================================
# 10. CALIDAD DE SEÑAL
# =============================================================================

def signal_quality(mtf, liq, wyc, sent, pattern):
    sc=0; mx=0; det={}
    mtf_sc=min(30,mtf["confluence_pct"]*0.3); sc+=mtf_sc; mx+=30; det["mtf"]=round(mtf_sc,1)
    pat_sc=min(20,pattern["confidence"]*0.2);  sc+=pat_sc; mx+=20; det["pat"]=round(pat_sc,1)
    tf15=mtf["timeframes"].get("15m",{})
    ms_sc=(5 if tf15.get("bos") else 0)+(5 if tf15.get("choch") else 0)+(5 if tf15.get("zone") in ["DISCOUNT","PREMIUM"] else 0)
    sc+=ms_sc; mx+=15; det["ms"]=ms_sc
    lq_sc=min(15,liq["score"]*3);  sc+=lq_sc; mx+=15; det["liq"]=lq_sc
    wy_sc=min(10,wyc["score"]*2);  sc+=wy_sc; mx+=10; det["wyc"]=wy_sc
    se_sc=0; dir=pattern.get("direction","")
    if dir=="BUY"  and sent.get("sent")=="FEAR":  se_sc+=5
    if dir=="SELL" and sent.get("sent")=="GREED": se_sc+=5
    if sent.get("fg",50)!=50: se_sc+=5
    sc+=se_sc; mx+=10; det["sent"]=se_sc
    pct=round((sc/mx)*100,1) if mx>0 else 0
    det["total"]=round(sc,1); det["max"]=mx; det["pct"]=pct
    return pct, det

# =============================================================================
# 11. MENSAJE TELEGRAM
# =============================================================================

def send_tg(msg):
    try:
        r=requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"},
            timeout=10
        )
        return r.status_code==200
    except Exception as e:
        log.error(f"TG error: {e}"); return False

def build_msg(symbol,market,pat,levels,mtf,wyc,sent,quality,det):
    dir=pat["direction"]
    arrow="COMPRA (BUY)" if dir=="BUY" else "VENTA (SELL)"
    clr="&#x1F7E2;" if dir=="BUY" else "&#x1F534;"
    emk={"CRYPTO":"&#x1FA99;","FOREX":"&#x1F4B1;","INDICES":"&#x1F4CA;","COMMODITIES":"&#x1F947;","STOCKS":"&#x1F4C8;"}.get(market,"&#x1F4CC;")
    otype="MARKET" if levels["type"]=="MARKET" else "LIMIT"
    tfs=""
    for tf,d in mtf["timeframes"].items():
        em="&#x1F7E2;" if d["trend"]=="BULLISH" else ("&#x1F534;" if d["trend"]=="BEARISH" else "&#x1F7E1;")
        tfs+=f"  {em} {tf.upper()}: {d['trend']} | RSI {d['rsi']} | ADX {d['adx']}\n"
    wyc_t=wyc.get("phase","N/A")
    if wyc.get("spring"): wyc_t+=" + SPRING"
    if wyc.get("upthrust"): wyc_t+=" + UPTHRUST"
    fg_t=sent.get("sent","NEUTRAL"); fg_v=sent.get("fg",50)
    return f"""
{clr} <b>{arrow}</b> {clr}
{emk} <b>Activo:</b> {symbol} ({market})
&#x1F4D0; <b>Patron:</b> {pat["pattern"]}
&#x2B50; <b>Calidad:</b> {quality}%

<b>Tipo orden:</b> {otype}
<b>Entrada:</b>   {levels["entry"]}
<b>Stop Loss:</b>  {levels["sl"]}
<b>TP1:</b>        {levels["tp1"]} (RR {levels["rr1"]}:1)
<b>TP2:</b>        {levels["tp2"]} (RR {levels["rr2"]}:1)

<b>Confluencia MTF:</b> {mtf["confluence_pct"]}%
{tfs}
<b>Wyckoff:</b> {wyc_t}
<b>Sentimiento:</b> {fg_t} (F&G: {fg_v}/100)

<b>Puntuacion:</b>
  MTF: {det.get("mtf",0)} | Patron: {det.get("pat",0)}
  Estructura: {det.get("ms",0)} | Liquidez: {det.get("liq",0)}
  Wyckoff: {det.get("wyc",0)} | Sentiment: {det.get("sent",0)}

&#x26A0; Riesgo maximo: 1-2% del capital
&#x1F550; {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}
""".strip()

# =============================================================================
# 12. MOTOR PRINCIPAL
# =============================================================================

QUALITY_THRESHOLD = 80.0
COOLDOWN_HOURS    = 4
sent_signals: Dict[str, datetime] = {}

def analyze(symbol, market):
    log.info(f"Analizando {symbol} ({market})...")
    key=f"{symbol}_{market}"
    if key in sent_signals:
        if (datetime.now()-sent_signals[key]).total_seconds()/3600 < COOLDOWN_HOURS:
            return
    df15=get_data(symbol,market,"15m",200)
    if df15 is None or len(df15)<50: return
    df15=calc_indicators(df15)
    if df15 is None: return
    pats=scan_harmonics(df15,market)
    if not pats: return
    mtf=mtf_analysis(symbol,market)
    if mtf["dominant"]=="NEUTRAL": return
    liq=detect_liquidity(df15)
    wyc=wyckoff_phase(df15)
    for pat in pats:
        if pat["direction"]!=mtf["dominant"]: continue
        now=datetime.now(); m=now.minute%240
        sent=get_sentiment(symbol) if (m>=(240-17) or m<=5) else {"fg":50,"sent":"NEUTRAL","news_risk":False}
        if sent.get("news_risk"): log.warning(f"Bloqueado por noticias: {symbol}"); return
        q,det=signal_quality(mtf,liq,wyc,sent,pat)
        log.info(f"  {symbol} {pat['pattern']}: {q}%")
        if q<QUALITY_THRESHOLD: continue
        lvl=trade_levels(df15,pat["direction"],pat,market)
        if lvl["rr1"]<1.5: continue
        msg=build_msg(symbol,market,pat,lvl,mtf,wyc,sent,q,det)
        if send_tg(msg):
            log.info(f"Señal enviada: {symbol} {pat['pattern']} {pat['direction']} Q={q}%")
            sent_signals[key]=datetime.now()
        break

def run_scan():
    log.info(f"ESCANEO INICIADO {datetime.now().strftime('%H:%M:%S')}")
    for market,syms in SYMBOLS.items():
        for sym in syms:
            try: analyze(sym,market); time.sleep(1.5)
            except Exception as e: log.error(f"Error {sym}: {e}")
    log.info("Escaneo completado")

if __name__=="__main__":
    log.info("BOT TRADING INICIADO")
    if "TU_TOKEN" in TELEGRAM_TOKEN: exit("ERROR: Configura TELEGRAM_TOKEN")
    if "TU_CHAT_ID" in TELEGRAM_CHAT_ID: exit("ERROR: Configura TELEGRAM_CHAT_ID")
    send_tg("BOT DE SEÑALES TRADING ACTIVADO\nSistema online y monitoreando mercados")
    run_scan()
    schedule.every(15).minutes.do(run_scan)
    log.info("Escaneo programado cada 15 minutos")
    while True:
        schedule.run_pending()
        time.sleep(30)