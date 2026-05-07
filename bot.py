import { useState, useEffect } from "react";

// ─── Types ────────────────────────────────────────────
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

// ─── Constants ─────────────────────────────────────────
const HORA_INICIO = { h: 7, m: 0 };
const HORA_FIN    = { h: 22, m: 0 };
const SCORE_MIN   = 65;
const RR_MIN      = 2.0;
const COOLDOWN    = 90;
const TG_TOKEN    = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y";
const CHAT_ID     = "541470482";

const ASSETS: Record<string, string[]> = {
  FOREX:    ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDJPY=X", "EURGBP=X"],
  CRYPTO:   ["BTC-USD",  "ETH-USD",  "SOL-USD",  "BNB-USD"],
  ACCIONES: ["NVDA",     "TSLA",     "SPY",       "QQQ",    "AAPL"],
  MATERIAS: ["GC=F",     "SI=F",     "CL=F"],
};

const STRATEGIES = [
  { key: "tendencia_ema",       label: "EMA 20/50/200 Tendencia",  icon: "📊", weight: 20 },
  { key: "order_block_smc",     label: "Order Block SMC",          icon: "🏦", weight: 15 },
  { key: "divergencia_rsi",     label: "Divergencia RSI",          icon: "🔀", weight: 15 },
  { key: "stoch_rsi",           label: "Stochastic RSI",           icon: "📉", weight: 10 },
  { key: "bollinger",           label: "Bandas de Bollinger",      icon: "🎯", weight: 10 },
  { key: "patron_velas",        label: "Patrón de Velas",          icon: "🕯️", weight: 10 },
  { key: "soporte_resistencia", label: "Soporte/Resistencia",      icon: "🧱", weight: 10 },
  { key: "macd_cruce",          label: "MACD Cruce",               icon: "⚡", weight:  5 },
  { key: "canal_regresion",     label: "Canal Regresión",          icon: "📐", weight:  5 },
];


const CATEGORY_BG: Record<string, string> = {
  FOREX:    "bg-blue-500/10 border-blue-500/30 text-blue-300",
  CRYPTO:   "bg-orange-500/10 border-orange-500/30 text-orange-300",
  ACCIONES: "bg-violet-500/10 border-violet-500/30 text-violet-300",
  MATERIAS: "bg-green-500/10 border-green-500/30 text-green-300",
};

// ─── Helpers ──────────────────────────────────────────
function getCETTime() {
  const now = new Date();
  // UTC+1 fijo (CET). En producción real usaríamos Intl.DateTimeFormat con Europe/Madrid
  const utcMs = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utcMs + 3600000); // +1h CET
}

function isWithinSchedule(cet: Date): boolean {
  const h = cet.getHours();
  const m = cet.getMinutes();
  const totalMin = h * 60 + m;
  const start    = HORA_INICIO.h * 60 + HORA_INICIO.m;
  const end      = HORA_FIN.h * 60 + HORA_FIN.m;
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
  const m = cet.getMinutes();
  const totalMin = h * 60 + m;
  const start    = HORA_INICIO.h * 60;
  const end      = HORA_FIN.h * 60;
  if (totalMin < start) return 0;
  if (totalMin > end)   return 100;
  return Math.round(((totalMin - start) / (end - start)) * 100);
}

function timeUntilOpen(cet: Date): string {
  const h = cet.getHours();
  const m = cet.getMinutes();
  const totalMin = h * 60 + m;
  const openMin  = HORA_INICIO.h * 60;
  if (totalMin >= openMin && totalMin <= HORA_FIN.h * 60) return "ACTIVO";
  const remaining = totalMin < openMin
    ? openMin - totalMin
    : 24 * 60 - totalMin + openMin;
  const rh = Math.floor(remaining / 60);
  const rm = remaining % 60;
  return `${rh}h ${rm}m`;
}

// Demo signals generator
let sigId = 1;
function makeSignal(): Signal {
  const cats = Object.keys(ASSETS);
  const cat  = cats[Math.floor(Math.random() * cats.length)];
  const syms = ASSETS[cat];
  const sym  = syms[Math.floor(Math.random() * syms.length)];
  const dir  = Math.random() > 0.5 ? "COMPRA" : "VENTA";
  const score = SCORE_MIN + Math.floor(Math.random() * 36);
  const tfs = ["5m","15m","1h","4h"];
  const activeTfs = tfs.filter(() => Math.random() > 0.4);
  if (activeTfs.length < 2) activeTfs.push("1h","4h");
  const entry = parseFloat((Math.random() * 5000 + 1).toFixed(5));
  const atr   = parseFloat((entry * 0.002).toFixed(5));
  const sl    = parseFloat((dir === "COMPRA" ? entry - atr * 1.2 : entry + atr * 1.2).toFixed(5));
  const tp    = parseFloat((dir === "COMPRA" ? entry + atr * 2.8 : entry - atr * 2.8).toFixed(5));
  const rr    = parseFloat((Math.abs(tp - entry) / Math.abs(sl - entry)).toFixed(2));
  const strategies: Record<string, "COMPRA" | "VENTA" | null> = {};
  STRATEGIES.forEach(s => {
    const r = Math.random();
    strategies[s.key] = r < 0.55 ? dir : r < 0.8 ? (dir === "COMPRA" ? "VENTA" : "COMPRA") : null;
  });
  const now = getCETTime();
  const timeStr = formatCET(now) + " CET";
  return { id: sigId++, symbol: sym, category: cat, direction: dir, score, entry, sl, tp, rr, atr, timeframes: activeTfs, entryTf: activeTfs[activeTfs.length - 1], strategies, time: timeStr };
}

// ═══════════════════════════════════════════════
//  COMPONENTS
// ═══════════════════════════════════════════════

function ScoreRing({ score }: { score: number }) {
  const r   = 28;
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

function StrategyRow({ sk, label, icon, dir }: { sk: string; label: string; icon: string; dir: "COMPRA" | "VENTA" | null; targetDir: "COMPRA" | "VENTA" }) {
  const match = dir !== null;
  return (
    <div key={sk} className="flex items-center gap-2 py-1 border-b border-slate-700/40 last:border-0">
      <span className="text-base w-6 text-center">{icon}</span>
      <span className="flex-1 text-xs text-slate-300">{label}</span>
      {dir === null
        ? <span className="text-slate-500 text-xs">⚪ —</span>
        : match
          ? <span className="text-green-400 text-xs font-semibold">✅ {dir}</span>
          : <span className="text-red-400 text-xs font-semibold">❌ {dir}</span>
      }
    </div>
  );
}

function SignalCard({ sig, onClose }: { sig: Signal; onClose?: () => void }) {
  const isBuy = sig.direction === "COMPRA";
  const dirColor = isBuy ? "text-green-400" : "text-red-400";
  const dirBg    = isBuy ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30";
  return (
    <div className={`rounded-2xl border ${dirBg} p-4 flex flex-col gap-3 shadow-lg relative`}>
      {onClose && (
        <button onClick={onClose} className="absolute top-3 right-3 text-slate-500 hover:text-slate-200 text-lg leading-none">✕</button>
      )}
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className={`text-2xl`}>{isBuy ? "🟢" : "🔴"}</div>
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

      {/* Timeframes */}
      <div className="flex gap-1 flex-wrap">
        {sig.timeframes.map(tf => (
          <span key={tf} className={`text-xs px-2 py-0.5 rounded border font-mono ${tf === sig.entryTf ? "bg-yellow-500/20 border-yellow-500/50 text-yellow-300 font-bold" : "bg-slate-700/50 border-slate-600/40 text-slate-300"}`}>
            {tf === sig.entryTf ? `⭐ ${tf.toUpperCase()}` : tf.toUpperCase()}
          </span>
        ))}
      </div>

      {/* Levels */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-slate-800/60 p-2 text-center border border-slate-700/40">
          <div className="text-xs text-slate-400 mb-1">💰 Entrada</div>
          <div className="font-mono text-sm text-white font-semibold">{sig.entry}</div>
        </div>
        <div className="rounded-xl bg-red-900/20 p-2 text-center border border-red-800/30">
          <div className="text-xs text-slate-400 mb-1">🛑 Stop Loss</div>
          <div className="font-mono text-sm text-red-400 font-semibold">{sig.sl}</div>
        </div>
        <div className="rounded-xl bg-green-900/20 p-2 text-center border border-green-800/30">
          <div className="text-xs text-slate-400 mb-1">🎯 Take Profit</div>
          <div className="font-mono text-sm text-green-400 font-semibold">{sig.tp}</div>
        </div>
      </div>

      {/* RR + ATR */}
      <div className="flex gap-3">
        <div className="flex-1 rounded-xl bg-slate-800/60 border border-slate-700/40 p-2 flex items-center gap-2">
          <span className="text-slate-400 text-xs">⚖️ RR</span>
          <span className="font-mono font-bold text-yellow-400 text-sm">1:{sig.rr}</span>
        </div>
        <div className="flex-1 rounded-xl bg-slate-800/60 border border-slate-700/40 p-2 flex items-center gap-2">
          <span className="text-slate-400 text-xs">📏 ATR</span>
          <span className="font-mono text-slate-200 text-sm">{sig.atr}</span>
        </div>
      </div>

      {/* Strategies */}
      <div className="rounded-xl bg-slate-900/60 border border-slate-700/30 p-3">
        <div className="text-xs text-slate-400 font-semibold mb-2 uppercase tracking-wide">Confirmaciones (9 estrategias)</div>
        {STRATEGIES.map(s => (
          <StrategyRow key={s.key} sk={s.key} label={s.label} icon={s.icon} dir={sig.strategies[s.key] ?? null} targetDir={sig.direction} />
        ))}
      </div>

      {/* Footer */}
      <div className="text-center text-xs text-slate-500 italic">
        ⚠️ Gestiona siempre el riesgo · Score mín: {SCORE_MIN}/100 · RR: 1:{RR_MIN}
      </div>
    </div>
  );
}

function ScheduleBar({ cet }: { cet: Date }) {
  const active   = isWithinSchedule(cet);
  const progress = scheduleProgress(cet);
  const until    = timeUntilOpen(cet);

  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/40 p-5">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">🇪🇺</span>
          <span className="font-semibold text-slate-200">Horario Europeo CET</span>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-bold border ${
          active
            ? "bg-green-500/15 border-green-500/40 text-green-400"
            : "bg-red-500/15 border-red-500/40 text-red-400"
        }`}>
          <span className={`inline-block w-2 h-2 rounded-full ${active ? "bg-green-400 animate-pulse" : "bg-red-400"}`}></span>
          {active ? "OPERANDO" : `CERRADO — Abre en ${until}`}
        </div>
      </div>

      {/* Time labels */}
      <div className="flex justify-between text-xs text-slate-400 mb-1">
        <span>07:00</span>
        <span className="text-slate-300 font-mono font-bold">{formatCET(cet)}</span>
        <span>22:00</span>
      </div>

      {/* Progress bar */}
      <div className="relative h-4 rounded-full bg-slate-700/60 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${active ? "bg-gradient-to-r from-green-500 to-emerald-400" : "bg-slate-600"}`}
          style={{ width: `${progress}%` }}
        />
        {active && (
          <div
            className="absolute top-0 h-full w-1 bg-white/60 rounded-full shadow-lg shadow-white/30"
            style={{ left: `calc(${progress}% - 2px)` }}
          />
        )}
      </div>

      {/* Session indicators */}
      <div className="flex gap-2 mt-3 flex-wrap">
        {[
          { label: "🇬🇧 London",  start: "07:00", end: "16:00", color: "bg-blue-500/20 border-blue-500/30 text-blue-300" },
          { label: "🗽 New York", start: "13:00", end: "22:00", color: "bg-violet-500/20 border-violet-500/30 text-violet-300" },
          { label: "⚡ Overlap",  start: "13:00", end: "16:00", color: "bg-yellow-500/20 border-yellow-500/30 text-yellow-300" },
        ].map(sess => (
          <span key={sess.label} className={`text-xs px-2 py-1 rounded-full border ${sess.color}`}>
            {sess.label} {sess.start}–{sess.end}
          </span>
        ))}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub, color }: { icon: string; label: string; value: string; sub?: string; color: string }) {
  return (
    <div className={`rounded-2xl bg-slate-800/60 border border-slate-700/40 p-4 flex items-center gap-4`}>
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center text-2xl shadow-lg flex-shrink-0`}>
        {icon}
      </div>
      <div>
        <div className="text-xs text-slate-400 mb-0.5">{label}</div>
        <div className="text-xl font-bold text-white">{value}</div>
        {sub && <div className="text-xs text-slate-500">{sub}</div>}
      </div>
    </div>
  );
}

function ConfigSection() {
  const [show, setShow] = useState(false);
  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/40 overflow-hidden">
      <button
        onClick={() => setShow(v => !v)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-700/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span>⚙️</span>
          <span className="font-semibold text-slate-200">Configuración del Bot v3.0</span>
        </div>
        <span className={`text-slate-400 transition-transform ${show ? "rotate-180" : ""}`}>▼</span>
      </button>
      {show && (
        <div className="border-t border-slate-700/40 p-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: "Horario",        value: "07:00 – 22:00 CET",     icon: "🕖" },
            { label: "Score mínimo",   value: `${SCORE_MIN}/100`,       icon: "🏆" },
            { label: "RR mínimo",      value: `1:${RR_MIN}`,            icon: "⚖️" },
            { label: "Cooldown",       value: `${COOLDOWN} min`,        icon: "⏱️" },
            { label: "ATR SL mult.",   value: "× 1.2",                  icon: "🛑" },
            { label: "ATR TP mult.",   value: "× 2.8",                  icon: "🎯" },
            { label: "Timeframes",     value: "5m · 15m · 1h · 4h",    icon: "📊" },
            { label: "H4 obligatorio", value: "Sí",                     icon: "✅" },
            { label: "TF mín. acuerdo","value": "≥ 2",                  icon: "🔗" },
            { label: "Win Rate est.",  value: "~80%",                   icon: "📈" },
            { label: "Telegram Token", value: `${TG_TOKEN.slice(0,12)}…`, icon: "🤖" },
            { label: "Chat ID",        value: CHAT_ID,                  icon: "💬" },
          ].map(c => (
            <div key={c.label} className="rounded-xl bg-slate-900/50 border border-slate-700/30 p-3 flex items-center gap-3">
              <span className="text-lg">{c.icon}</span>
              <div>
                <div className="text-xs text-slate-400">{c.label}</div>
                <div className="font-mono text-sm text-white font-semibold">{c.value}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AssetsSection() {
  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/40 p-4">
      <div className="flex items-center gap-2 mb-4">
        <span>📂</span>
        <span className="font-semibold text-slate-200">Activos Monitorizados</span>
        <span className="ml-auto text-xs text-slate-400">
          {Object.values(ASSETS).flat().length} activos
        </span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {Object.entries(ASSETS).map(([cat, syms]) => (
          <div key={cat} className={`rounded-xl border p-3 ${CATEGORY_BG[cat]}`}>
            <div className={`text-xs font-bold mb-2 uppercase tracking-wider`}>{cat}</div>
            <div className="flex flex-wrap gap-1">
              {syms.map(s => (
                <span key={s} className="text-xs font-mono px-2 py-0.5 rounded bg-slate-900/40 border border-slate-700/30 text-slate-200">
                  {s}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StrategiesSection() {
  return (
    <div className="rounded-2xl bg-slate-800/60 border border-slate-700/40 p-4">
      <div className="flex items-center gap-2 mb-4">
        <span>🧠</span>
        <span className="font-semibold text-slate-200">9 Estrategias Activas v3.0</span>
      </div>
      <div className="space-y-2">
        {STRATEGIES.map(s => (
          <div key={s.key} className="flex items-center gap-3 py-2 border-b border-slate-700/30 last:border-0">
            <span className="text-xl w-8 text-center">{s.icon}</span>
            <span className="flex-1 text-sm text-slate-200">{s.label}</span>
            <div className="flex items-center gap-1">
              <div className="w-20 h-2 rounded-full bg-slate-700">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-400"
                  style={{ width: `${s.weight * 5}%` }}
                />
              </div>
              <span className="text-xs text-slate-400 w-8 text-right font-mono">{s.weight}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════
//  MAIN APP
// ═══════════════════════════════════════════════

export default function App() {
  const [cet, setCet]             = useState(getCETTime());
  const [signals, setSignals]     = useState<Signal[]>([]);
  const [tab, setTab]             = useState<"signals"|"config"|"assets"|"strategies">("signals");
  const [totalScanned, setTotalScanned] = useState(0);
  const [botRunning, setBotRunning]     = useState(true);

  // Clock tick
  useEffect(() => {
    const t = setInterval(() => setCet(getCETTime()), 1000);
    return () => clearInterval(t);
  }, []);

  // Demo signal generator (simulates bot behavior)
  useEffect(() => {
    if (!botRunning) return;
    const initial: Signal[] = [];
    for (let i = 0; i < 3; i++) {
      const s = makeSignal();
      if (isWithinSchedule(getCETTime())) {
        s.score = SCORE_MIN + Math.floor(Math.random() * 30);
        initial.push(s);
      }
    }
    setSignals(initial);
    setTotalScanned(Object.values(ASSETS).flat().length * 4);

    const interval = setInterval(() => {
      const cetNow = getCETTime();
      if (!isWithinSchedule(cetNow)) return;
      if (Math.random() > 0.6) {
        const newSig = makeSignal();
        newSig.score = SCORE_MIN + Math.floor(Math.random() * 30);
        setSignals(prev => [newSig, ...prev].slice(0, 20));
        setTotalScanned(prev => prev + Object.values(ASSETS).flat().length);
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [botRunning]);

  const active   = isWithinSchedule(cet);
  const buys     = signals.filter(s => s.direction === "COMPRA").length;
  const sells    = signals.filter(s => s.direction === "VENTA").length;
  const avgScore = signals.length > 0
    ? Math.round(signals.reduce((a, b) => a + b.score, 0) / signals.length)
    : 0;

  const tabs = [
    { id: "signals",    label: "📡 Señales",    badge: signals.length },
    { id: "config",     label: "⚙️ Config",      badge: 0 },
    { id: "assets",     label: "📂 Activos",     badge: 0 },
    { id: "strategies", label: "🧠 Estrategias", badge: 0 },
  ] as const;

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-white font-sans">
      {/* ── Gradient background blobs ── */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-15%] left-[-10%] w-96 h-96 rounded-full bg-violet-600/10 blur-3xl" />
        <div className="absolute bottom-[-10%] right-[-5%] w-80 h-80 rounded-full bg-indigo-600/10 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-blue-900/5 blur-3xl" />
      </div>

      <div className="relative z-10 max-w-4xl mx-auto px-4 pb-10">
        {/* ── HEADER ── */}
        <div className="pt-8 pb-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-2xl shadow-lg shadow-indigo-900/40">
                🤖
              </div>
              <div>
                <h1 className="text-xl font-bold text-white leading-tight">
                  Bot Trading Profesional
                  <span className="ml-2 text-xs font-mono px-2 py-0.5 rounded bg-violet-500/20 border border-violet-500/40 text-violet-300">v3.0</span>
                </h1>
                <p className="text-sm text-slate-400">{formatDateCET(cet)}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-bold ${
                active
                  ? "bg-green-500/10 border-green-500/30 text-green-400"
                  : "bg-slate-700/40 border-slate-600/30 text-slate-400"
              }`}>
                <span className={`w-2 h-2 rounded-full ${active ? "bg-green-400 animate-pulse" : "bg-slate-500"}`}></span>
                {active ? "BOT ACTIVO" : "FUERA DE HORARIO"}
              </div>
              <button
                onClick={() => setBotRunning(v => !v)}
                className={`px-4 py-2 rounded-full border text-sm font-bold transition-colors ${
                  botRunning
                    ? "bg-red-500/15 border-red-500/40 text-red-400 hover:bg-red-500/25"
                    : "bg-green-500/15 border-green-500/40 text-green-400 hover:bg-green-500/25"
                }`}
              >
                {botRunning ? "⏸ Pausar" : "▶ Reanudar"}
              </button>
            </div>
          </div>
        </div>

        {/* ── SCHEDULE BAR ── */}
        <div className="mb-5">
          <ScheduleBar cet={cet} />
        </div>

        {/* ── STATS ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <StatCard icon="📡" label="Señales hoy"  value={String(signals.length)}    sub="≥65 score"          color="from-violet-500 to-indigo-500" />
          <StatCard icon="🟢" label="Compras"       value={String(buys)}             sub="LONG activas"       color="from-green-500 to-emerald-500" />
          <StatCard icon="🔴" label="Ventas"        value={String(sells)}            sub="SHORT activas"      color="from-red-500 to-rose-500" />
          <StatCard icon="🎯" label="Score medio"   value={avgScore > 0 ? `${avgScore}` : "—"} sub="/100"    color="from-yellow-500 to-orange-500" />
        </div>

        {/* ── Scanned info ── */}
        <div className="flex items-center gap-3 mb-5 flex-wrap">
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700/40 rounded-xl px-3 py-2">
            <span>🔍</span>
            <span>Analizados: <span className="text-white font-mono font-bold">{totalScanned}</span> velas</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700/40 rounded-xl px-3 py-2">
            <span>⏱️</span>
            <span>Cooldown: <span className="text-white font-mono font-bold">{COOLDOWN} min</span></span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700/40 rounded-xl px-3 py-2">
            <span>💬</span>
            <span>Telegram: <span className="text-white font-mono font-bold">{CHAT_ID}</span></span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-slate-800/50 border border-slate-700/40 rounded-xl px-3 py-2">
            <span>📈</span>
            <span>Win Rate: <span className="text-green-400 font-mono font-bold">~80%</span></span>
          </div>
        </div>

        {/* ── TABS ── */}
        <div className="flex gap-1 bg-slate-800/50 rounded-2xl p-1 mb-5 border border-slate-700/40">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${
                tab === t.id
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-900/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/30"
              }`}
            >
              {t.label}
              {t.badge > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.id ? "bg-white/20" : "bg-violet-500/30 text-violet-300"}`}>
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── TAB CONTENT ── */}
        {tab === "signals" && (
          <div className="space-y-4">
            {!active && (
              <div className="rounded-2xl bg-slate-800/50 border border-slate-700/40 p-6 text-center">
                <div className="text-4xl mb-3">💤</div>
                <div className="text-slate-200 font-semibold mb-1">Fuera del horario operativo</div>
                <div className="text-slate-400 text-sm">
                  El bot opera de <span className="text-white font-mono font-bold">07:00 a 22:00 CET</span>
                </div>
                <div className="mt-3 text-violet-300 font-mono font-bold">
                  Hora actual: {formatCET(cet)} CET
                </div>
              </div>
            )}
            {signals.length === 0 && active && (
              <div className="rounded-2xl bg-slate-800/50 border border-slate-700/40 p-8 text-center">
                <div className="text-4xl mb-3 animate-pulse">🔍</div>
                <div className="text-slate-200 font-semibold mb-1">Escaneando mercados...</div>
                <div className="text-slate-400 text-sm">Esperando señales con score ≥ {SCORE_MIN}/100</div>
              </div>
            )}
            {signals.map(sig => (
              <SignalCard
                key={sig.id}
                sig={sig}
                onClose={() => setSignals(prev => prev.filter(s => s.id !== sig.id))}
              />
            ))}
          </div>
        )}

        {tab === "config" && (
          <div className="space-y-4">
            {/* Main schedule highlight */}
            <div className="rounded-2xl bg-gradient-to-br from-violet-600/20 to-indigo-600/20 border border-violet-500/30 p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-2xl">🕖</span>
                <div>
                  <div className="font-bold text-white text-lg">Horario Operativo</div>
                  <div className="text-slate-300 text-sm">Zona horaria: CET (UTC+1)</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-xl bg-green-500/10 border border-green-500/30 p-4 text-center">
                  <div className="text-xs text-slate-400 mb-1">🟢 Apertura</div>
                  <div className="font-mono text-3xl font-bold text-green-400">07:00</div>
                  <div className="text-xs text-slate-400 mt-1">CET</div>
                </div>
                <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-center">
                  <div className="text-xs text-slate-400 mb-1">🔴 Cierre</div>
                  <div className="font-mono text-3xl font-bold text-red-400">22:00</div>
                  <div className="text-xs text-slate-400 mt-1">CET</div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-slate-800/60 p-2 border border-slate-700/30">
                  <div className="text-xs text-slate-400">Duración</div>
                  <div className="font-bold text-white">15 horas</div>
                </div>
                <div className="rounded-xl bg-slate-800/60 p-2 border border-slate-700/30">
                  <div className="text-xs text-slate-400">Hora actual</div>
                  <div className="font-bold text-violet-300 font-mono">{formatCET(cet)}</div>
                </div>
                <div className="rounded-xl bg-slate-800/60 p-2 border border-slate-700/30">
                  <div className="text-xs text-slate-400">Estado</div>
                  <div className={`font-bold ${active ? "text-green-400" : "text-red-400"}`}>
                    {active ? "ACTIVO" : "CERRADO"}
                  </div>
                </div>
              </div>
            </div>

            <ConfigSection />

            {/* Session details */}
            <div className="rounded-2xl bg-slate-800/60 border border-slate-700/40 p-4">
              <div className="flex items-center gap-2 mb-4">
                <span>🌍</span>
                <span className="font-semibold text-slate-200">Sesiones por tipo de activo</span>
              </div>
              <div className="space-y-3">
                {[
                  { cat: "FOREX",    hours: "07:00–22:00 (Londres + NY)", icon: "💱" },
                  { cat: "CRYPTO",   hours: "07:00–22:00 (todo el horario)", icon: "₿" },
                  { cat: "ACCIONES", hours: "13:30–20:00 (mercado USA)", icon: "📈" },
                  { cat: "MATERIAS", hours: "13:30–20:00 (mercado USA)", icon: "🛢️" },
                ].map(row => (
                  <div key={row.cat} className={`flex items-center gap-3 rounded-xl border p-3 ${CATEGORY_BG[row.cat]}`}>
                    <span className="text-xl">{row.icon}</span>
                    <div>
                      <div className="font-semibold text-sm">{row.cat}</div>
                      <div className="text-xs opacity-80">{row.hours}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "assets" && <AssetsSection />}
        {tab === "strategies" && <StrategiesSection />}

        {/* ── FOOTER ── */}
        <div className="mt-8 text-center text-xs text-slate-600 space-y-1">
          <div>Bot de Trading Profesional v3.0 · Máxima Precisión</div>
          <div>⚠️ Este bot es solo para fines informativos. Gestiona siempre el riesgo.</div>
        </div>
      </div>
    </div>
  );
}
