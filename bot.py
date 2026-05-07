import React, { useState, useEffect } from "react";

// --- Types --------------------------------------------
interface Signal {
  id: number;
  symbol: string;
  category: string;
  direction: "COMPRA" | "VENTA";
  score: number;
  entry: number;
  sl: number;
  tp: number;
  rr: number;
  atr: number;
  timeframes: string[];
  entryTf: string;
  strategies: Record<string, "COMPRA" | "VENTA" | null>;
  time: string;
}

// --- Constants -----------------------------------------
const HORA_INICIO = { h: 7, m: 0 };
const HORA_FIN = { h: 22, m: 0 };
const SCORE_MIN = 65;
const RR_MIN = 2.0;
const COOLDOWN = 90;
const TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y";
const CHAT_ID = "541470482";

const ASSETS: Record<string, string[]> = {
  FOREX: ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDJPY=X", "EURGBP=X"],
  CRYPTO: ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
  ACCIONES: ["NVDA", "TSLA", "SPY", "QQQ", "AAPL"],
  MATERIAS: ["GC=F", "SI=F", "CL=F"],
};

const STRATEGIES = [
  { key: "tendencia_ema", label: "EMA 20/50/200 Tendencia", icon: "📊", weight: 20 },
  { key: "order_block_smc", label: "Order Block SMC", icon: "🏦", weight: 15 },
  { key: "divergencia_rsi", label: "Divergencia RSI", icon: "🔀", weight: 15 },
  { key: "stoch_rsi", label: "Stochastic RSI", icon: "📉", weight: 10 },
  { key: "bollinger", label: "Bandas de Bollinger", icon: "🎯", weight: 10 },
  { key: "patron_velas", label: "Patrón de Velas", icon: "🕯️", weight: 10 },
  { key: "soporte_resistencia", label: "Soporte/Resistencia", icon: "🧱", weight: 10 },
  { key: "macd_cruce", label: "MACD Cruce", icon: "⚡", weight: 5 },
  { key: "canal_regresion", label: "Canal Regresión", icon: "📐", weight: 5 },
];

const CATEGORY_BG: Record<string, string> = {
  FOREX: "bg-blue-500/10 border-blue-500/30 text-blue-300",
  CRYPTO: "bg-orange-500/10 border-orange-500/30 text-orange-300",
  ACCIONES: "bg-violet-500/10 border-violet-500/30 text-violet-300",
  MATERIAS: "bg-green-500/10 border-green-500/30 text-green-300",
};

// --- Helpers ------------------------------------------
function getCETTime() {
  const now = new Date();
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + 3600000); // +1h CET
}

function isWithinSchedule(cet: Date): boolean {
  const h = cet.getHours();
  const m = cet.getMinutes();
  const totalMin = h * 60 + m;
  const start = HORA_INICIO.h * 60 + HORA_INICIO.m;
  const end = HORA_FIN.h * 60 + HORA_FIN.m;
  return totalMin >= start && totalMin <= end;
}

function formatCET(d: Date): string {
  return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDateCET(d: Date): string {
  return d.toLocaleDateString("es-ES", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

function scheduleProgress(cet: Date): number {
  const h = cet.getHours();
  const totalMin = h * 60 + cet.getMinutes();
  const start = HORA_INICIO.h * 60;
  const end = HORA_FIN.h * 60;
  if (totalMin < start) return 0;
  if (totalMin > end) return 100;
  return Math.round(((totalMin - start) / (end - start)) * 100);
}

function timeUntilOpen(cet: Date): string {
  const totalMin = cet.getHours() * 60 + cet.getMinutes();
  const openMin = HORA_INICIO.h * 60;
  if (totalMin >= openMin && totalMin <= HORA_FIN.h * 60) return "ACTIVO";
  const remaining = totalMin < openMin ? openMin - totalMin : 24 * 60 - totalMin + openMin;
  return `${Math.floor(remaining / 60)}h ${remaining % 60}m`;
}

let sigId = 1;
function makeSignal(): Signal {
  const cats = Object.keys(ASSETS);
  const cat = cats[Math.floor(Math.random() * cats.length)];
  const syms = ASSETS[cat];
  const sym = syms[Math.floor(Math.random() * syms.length)];
  const dir = Math.random() > 0.5 ? "COMPRA" : "VENTA";
  const score = SCORE_MIN + Math.floor(Math.random() * 30);
  const tfs = ["5m", "15m", "1h", "4h"];
  const activeTfs = tfs.filter(() => Math.random() > 0.4);
  if (activeTfs.length < 2) activeTfs.push("1h", "4h");
  const entry = parseFloat((Math.random() * 5000 + 1).toFixed(5));
  const atr = parseFloat((entry * 0.002).toFixed(5));
  const sl = parseFloat((dir === "COMPRA" ? entry - atr * 1.2 : entry + atr * 1.2).toFixed(5));
  const tp = parseFloat((dir === "COMPRA" ? entry + atr * 2.8 : entry - atr * 2.8).toFixed(5));
  const rr = parseFloat((Math.abs(tp - entry) / Math.abs(sl - entry)).toFixed(2));
  const strategies: Record<string, "COMPRA" | "VENTA" | null> = {};
  STRATEGIES.forEach(s => {
    const r = Math.random();
    strategies[s.key] = r < 0.6 ? dir : r < 0.8 ? (dir === "COMPRA" ? "VENTA" : "COMPRA") : null;
  });
  return { id: sigId++, symbol: sym, category: cat, direction: dir, score, entry, sl, tp, rr, atr, timeframes: activeTfs, entryTf: activeTfs[activeTfs.length - 1], strategies, time: formatCET(getCETTime()) + " CET" };
}

// --- COMPONENTS ---------------------------------------

function ScoreRing({ score }: { score: number }) {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = score >= 80 ? "#22c55e" : score >= 65 ? "#eab308" : "#ef4444";
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="72" height="72" className="-rotate-90">
        <circle cx="36" cy="36" r={r} fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <span className="absolute text-sm font-bold" style={{ color }}>{score}</span>
    </div>
  );
}

function StrategyRow({ label, icon, dir, targetDir }: { label: string; icon: string; dir: "COMPRA" | "VENTA" | null; targetDir: "COMPRA" | "VENTA" }) {
  const isMatch = dir === targetDir;
  return (
    <div className="flex items-center gap-2 py-1 border-b border-slate-700/40 last:border-0">
      <span className="text-base w-6 text-center">{icon}</span>
      <span className="flex-1 text-xs text-slate-300">{label}</span>
      {dir === null ? (
        <span className="text-slate-500 text-xs">⚪ —</span>
      ) : isMatch ? (
        <span className="text-green-400 text-xs font-semibold">✅ {dir}</span>
      ) : (
        <span className="text-red-400 text-xs font-semibold">❌ {dir}</span>
      )}
    </div>
  );
}

function SignalCard({ sig, onClose }: { sig: Signal; onClose?: () => void }) {
  const isBuy = sig.direction === "COMPRA";
  const dirColor = isBuy ? "text-green-400" : "text-red-400";
  const dirBg = isBuy ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30";
  return (
    <div className={`rounded-2xl border ${dirBg} p-4 flex flex-col gap-3 shadow-lg relative`}>
      {onClose && (
        <button onClick={onClose} className="absolute top-3 right-3 text-slate-500 hover:text-slate-200 text-lg leading-none">✕</button>
      )}
      <div className="flex items-center gap-3">
        <div className="text-2xl">{isBuy ? "🟢" : "🔴"}</div>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`font-bold text-lg ${dirColor}`}>{sig.direction}</span>
            <span className="font-mono font-bold text-white text-base">{sig.symbol}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${CATEGORY_BG[sig.category]}`}>{sig.category}</span>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">🕐 {sig.time}</div>
        </div>
        <ScoreRing score={sig.score} />
      </div>

      <div className="flex gap-1 flex-wrap">
        {sig.timeframes.map(tf => (
          <span key={tf} className={`text-xs px-2 py-0.5 rounded border font-mono ${tf === sig.entryTf ? "bg-yellow-500/20 border-yellow-500/50 text-yellow-300 font-bold" : "bg-slate-700/50 border-slate-600/40 text-slate-300"}`}>
            {tf === sig.entryTf ? `⭐ ${tf.toUpperCase()}` : tf.toUpperCase()}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-slate-800/60 p-2 text-center border border-slate-700/40">
          <div className="text-xs text-slate-400 mb-1">💰 Entrada</div>
          <div className="font-mono text-sm text-white font-semibold">{sig.entry}</div>
        </div>
        <div className="rounded-xl bg-red-900/20 p-2 text-center border border-red-800/30">
          <div className="text-xs text-slate-400 mb-1">🛑 SL</div>
          <div className="font-mono text-sm text-red-400 font-semibold">{sig.sl}</div>
        </div>
        <div className="rounded-xl bg-green-900/20 p-2 text-center border border-green-800/30">
          <div className="text-xs text-slate-400 mb-1">🎯 TP</div>
          <div className="font-mono text-sm text-green-400 font-semibold">{sig.tp}</div>
        </div>
      </div>

      <div className="rounded-xl bg-slate-900/60 border border-slate-700/30 p-3">
        <div className="text-xs text-slate-400 font-semibold mb-2 uppercase">Confirmaciones</div>
        {STRATEGIES.map(s => (
          <StrategyRow key={s.key} label={s.label} icon={s.icon} dir={sig.strategies[s.key] ?? null} targetDir={sig.direction} />
        ))}
      </div>
    </div>
  );
}

// --- MAIN APP -----------------------------------------

export default function App() {
  const [cet, setCet] = useState(getCETTime());
  const [signals, setSignals] = useState<Signal[]>([]);
  const [botRunning, setBotRunning] = useState(true);

  useEffect(() => {
    const t = setInterval(() => setCet(getCETTime()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (!botRunning) return;
    const interval = setInterval(() => {
      if (!isWithinSchedule(getCETTime())) return;
      if (Math.random() > 0.7) {
        setSignals(prev => [makeSignal(), ...prev].slice(0, 10));
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [botRunning]);

  const active = isWithinSchedule(cet);

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-white p-4">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center justify-between bg-slate-800/40 p-6 rounded-3xl border border-slate-700/50">
          <div>
            <h1 className="text-2xl font-bold">Trading Bot <span className="text-violet-400 text-sm font-mono">v3.0</span></h1>
            <p className="text-slate-400 text-sm">{formatDateCET(cet)}</p>
          </div>
          <button 
            onClick={() => setBotRunning(!botRunning)}
            className={`px-6 py-2 rounded-full font-bold transition-all ${botRunning ? "bg-red-500/20 text-red-400 border border-red-500/40" : "bg-green-500/20 text-green-400 border border-green-500/40"}`}
          >
            {botRunning ? "PAUSAR BOT" : "INICIAR BOT"}
          </button>
        </div>

        <div className="space-y-4">
          {!active && (
            <div className="p-10 text-center bg-slate-800/30 rounded-3xl border border-slate-700/40">
              <span className="text-4xl">😴</span>
              <p className="mt-2 text-slate-400">Fuera de horario operativo (07:00 - 22:00 CET)</p>
            </div>
          )}
          {signals.map(sig => (
            <SignalCard key={sig.id} sig={sig} onClose={() => setSignals(prev => prev.filter(s => s.id !== sig.id))} />
          ))}
        </div>
      </div>
    </div>
  );
}
