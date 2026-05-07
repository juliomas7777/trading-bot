import { useState, useEffect } from "react";

// --- Types -------------------------------------------------------
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
  timeframes: string[];
  entryTf: string;
  strategies: Record<string, "COMPRA" | "VENTA" | null>;
  time: string;
}

// --- Constants ---------------------------------------------------
// Tus credenciales configuradas:
const TG_TOKEN = "8634623188:AAGzszzc3rDt1xR3RGy5SuotJkMixTihU-Y";
const CHAT_ID = "541470482";

const HORA_INICIO = { h: 7,  m: 0 };
const HORA_FIN    = { h: 22, m: 0 };
const SCORE_MIN   = 65;
const RR_MIN      = 2.0;

const ASSETS: Record<string, string[]> = {
  FOREX:    ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDJPY=X", "EURGBP=X"],
  CRYPTO:   ["BTC-USD",  "ETH-USD",  "SOL-USD",  "BNB-USD"],
  ACCIONES: ["NVDA",     "TSLA",     "SPY",       "QQQ",     "AAPL"],
  MATERIAS: ["GC=F",     "SI=F",     "CL=F"],
};

const STRATEGIES = [
  { key: "tendencia_ema",        label: "EMA 20/50/200",       icon: "📊", weight: 20 },
  { key: "order_block_smc",     label: "Order Block SMC",     icon: "🏦", weight: 15 },
  { key: "divergencia_rsi",     label: "Divergencia RSI",     icon: "🔀", weight: 15 },
  { key: "stoch_rsi",            label: "Stochastic RSI",      icon: "📉", weight: 10 },
  { key: "bollinger",            label: "Bollinger Bands",     icon: "🎯", weight: 10 },
  { key: "patron_velas",         label: "Patrón de Velas",     icon: "🕯️", weight: 10 },
  { key: "soporte_resistencia", label: "Soporte/Resistencia", icon: "🧱", weight: 10 },
  { key: "macd_cruce",           label: "MACD Cruce",           icon: "⚡", weight:  5 },
  { key: "canal_regresion",      label: "Canal Regresión",      icon: "📐", weight:  5 },
];

const CAT_STYLE: Record<string, string> = {
  FOREX:    "bg-blue-500/10   border-blue-500/30   text-blue-300",
  CRYPTO:   "bg-orange-500/10 border-orange-500/30 text-orange-300",
  ACCIONES: "bg-violet-500/10 border-violet-500/30 text-violet-300",
  MATERIAS: "bg-green-500/10  border-green-500/30  text-green-300",
};

// --- Helpers -----------------------------------------------------
function getCET() {
  const now = new Date();
  return new Date(now.getTime() + now.getTimezoneOffset() * 60000 + 3600000);
}

function inSchedule(d: Date) {
  const t = d.getHours() * 60 + d.getMinutes();
  return t >= HORA_INICIO.h * 60 && t <= HORA_FIN.h * 60;
}

function fmtTime(d: Date) {
  return d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
function fmtDate(d: Date) {
  return d.toLocaleDateString("es-ES", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
}

let _id = 1;
function makeSignal(): Signal {
  const cat  = Object.keys(ASSETS)[Math.floor(Math.random() * 4)];
  const sym  = ASSETS[cat][Math.floor(Math.random() * ASSETS[cat].length)];
  const dir  = Math.random() > 0.5 ? "COMPRA" : "VENTA" as const;
  const score = SCORE_MIN + Math.floor(Math.random() * 30);
  const tfs = ["5m","15m","1h","4h"].filter(() => Math.random() > 0.4);
  if (tfs.length < 2) tfs.push("1h","4h");
  const entry = parseFloat((Math.random() * 5000 + 1).toFixed(5));
  const atr   = parseFloat((entry * 0.002).toFixed(5));
  const sl = parseFloat((dir === "COMPRA" ? entry - atr * 1.2 : entry + atr * 1.2).toFixed(5));
  const tp = parseFloat((dir === "COMPRA" ? entry + atr * 2.8 : entry - atr * 2.8).toFixed(5));
  const rr = parseFloat((Math.abs(tp - entry) / Math.abs(sl - entry)).toFixed(2));
  const strats: Record<string, "COMPRA" | "VENTA" | null> = {};
  STRATEGIES.forEach(s => {
    const r = Math.random();
    strats[s.key] = r < 0.6 ? dir : r < 0.8 ? (dir === "COMPRA" ? "VENTA" : "COMPRA") : null;
  });
  return { id: _id++, symbol: sym, category: cat, direction: dir, score, entry, sl, tp, rr, timeframes: tfs, entryTf: tfs[tfs.length - 1], strategies: strats, time: fmtTime(getCET()) + " CET" };
}

// --- Score Ring --------------------------------------------------
function ScoreRing({ score }: { score: number }) {
  const r     = 28;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = score >= 80 ? "#22c55e" : score >= 65 ? "#eab308" : "#ef4444";
  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width="72" height="72" className="-rotate-90">
        <circle cx="36" cy="36" r={r} fill="none" stroke="#1e293b" strokeWidth="6" />
        <circle cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${fill} ${circ}`} strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.6s ease" }} />
      </svg>
      <span className="absolute text-sm font-bold" style={{ color }}>{score}</span>
    </div>
  );
}

// --- Strategy Row ------------------------------------------------
function StratRow({ icon, label, dir, target }: { icon: string; label: string; dir: "COMPRA" | "VENTA" | null; target: "COMPRA" | "VENTA" }) {
  return (
    <div className="flex items-center gap-2 py-1 border-b border-slate-700/40 last:border-0">
      <span className="w-5 text-center text-sm">{icon}</span>
      <span className="flex-1 text-xs text-slate-300">{label}</span>
      {dir === null
        ? <span className="text-slate-500 text-xs">⚪ —</span>
        : dir === target
          ? <span className="text-green-400 text-xs font-semibold">✅ {dir}</span>
          : <span className="text-red-400 text-xs font-semibold">❌ {dir}</span>}
    </div>
  );
}

// --- Signal Card -------------------------------------------------
function SignalCard({ sig, onClose }: { sig: Signal; onClose: () => void }) {
  const buy = sig.direction === "COMPRA";
  const dirBg = buy ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30";
  const dirColor = buy ? "text-green-400" : "text-red-400";
  return (
    <div className={`rounded-2xl border ${dirBg} p-4 flex flex-col gap-3 shadow-lg relative animate-fade-in`}>
      <button onClick={onClose} className="absolute top-3 right-3 text-slate-500 hover:text-slate-200 text-lg">✕</button>

      <div className="flex items-center gap-3">
        <span className="text-2xl">{buy ? "🟢" : "🔴"}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`font-bold text-lg ${dirColor}`}>{sig.direction}</span>
            <span className="font-mono font-bold text-white">{sig.symbol}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${CAT_STYLE[sig.category]}`}>{sig.category}</span>
          </div>
          <div className="text-xs text-slate-400">🕐 {sig.time}</div>
        </div>
        <ScoreRing score={sig.score} />
      </div>

      <div className="flex gap-1 flex-wrap">
        {sig.timeframes.map(tf => (
          <span key={tf} className={`text-xs px-2 py-0.5 rounded border font-mono ${
            tf === sig.entryTf
              ? "bg-yellow-500/20 border-yellow-500/50 text-yellow-300 font-bold"
              : "bg-slate-700/50 border-slate-600/40 text-slate-300"
          }`}>
            {tf === sig.entryTf ? `⭐ ${tf.toUpperCase()}` : tf.toUpperCase()}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "💰 Entrada", val: sig.entry,  cls: "bg-slate-800/60 border-slate-700/40",    txt: "text-white"   },
          { label: "🛑 SL",      val: sig.sl,     cls: "bg-red-900/20   border-red-800/30",      txt: "text-red-400" },
          { label: "🎯 TP",      val: sig.tp,     cls: "bg-green-900/20 border-green-800/30",    txt: "text-green-400" },
        ].map(({ label, val, cls, txt }) => (
          <div key={label} className={`rounded-xl ${cls} border p-2 text-center`}>
            <div className="text-xs text-slate-400 mb-1">{label}</div>
            <div className={`font-mono text-sm font-semibold ${txt}`}>{val}</div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 bg-slate-800/40 rounded-xl px-3 py-2 border border-slate-700/30">
        <span className="text-xs text-slate-400">⚖️ Riesgo / Beneficio</span>
        <span className={`ml-auto font-bold text-sm ${sig.rr >= RR_MIN ? "text-green-400" : "text-yellow-400"}`}>{sig.rr}:1</span>
      </div>

      <div className="rounded-xl bg-slate-900/60 border border-slate-700/30 p-3">
        <div className="text-xs text-slate-400 font-semibold mb-2 uppercase tracking-wide">Confirmaciones</div>
        {STRATEGIES.map(s => (
          <StratRow key={s.key} icon={s.icon} label={s.label} dir={sig.strategies[s.key] ?? null} target={sig.direction} />
        ))}
      </div>
    </div>
  );
}

// --- Stats Bar ---------------------------------------------------
function StatsBar({ signals }: { signals: Signal[] }) {
  const buys  = signals.filter(s => s.direction === "COMPRA").length;
  const sells = signals.filter(s => s.direction === "VENTA").length;
  const avgScore = signals.length ? Math.round(signals.reduce((a, s) => a + s.score, 0) / signals.length) : 0;
  const avgRR    = signals.length ? (signals.reduce((a, s) => a + s.rr, 0) / signals.length).toFixed(2) : "—";

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: "Señales",    value: signals.length, sub: "total",       color: "text-white"        },
        { label: "COMPRA",     value: buys,           sub: "en cola",     color: "text-green-400"    },
        { label: "VENTA",      value: sells,          sub: "en cola",     color: "text-red-400"      },
        { label: "Score Avg",  value: avgScore || "—",sub: `R/R ${avgRR}`,color: "text-yellow-400"   },
      ].map(({ label, value, sub, color }) => (
        <div key={label} className="bg-slate-800/40 border border-slate-700/40 rounded-2xl p-3 text-center">
          <div className={`text-2xl font-bold ${color}`}>{value}</div>
          <div className="text-xs text-slate-400 mt-0.5">{label}</div>
          <div className="text-xs text-slate-500">{sub}</div>
        </div>
      ))}
    </div>
  );
}

// --- Setup Guide -------------------------------------------------
function SetupGuide() {
  const [open, setOpen] = useState(false);
  const steps = [
    { icon: "1️⃣", title: "Clona el repositorio", code: "git clone https://github.com/tu-usuario/tu-repo.git" },
    { icon: "2️⃣", title: "Añade los Secrets en GitHub", code: "Settings → Secrets → TG_TOKEN + CHAT_ID" },
    { icon: "3️⃣", title: "Activa GitHub Actions", code: ".github/workflows/trading_bot.yml  (ya incluido)" },
    { icon: "4️⃣", title: "O ejecútalo localmente", code: "pip install -r trading_bot/requirements.txt\npython trading_bot/bot.py" },
  ];
  return (
    <div className="rounded-2xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center justify-between p-4 text-left">
        <div className="flex items-center gap-2">
          <span className="text-lg">🐍</span>
          <span className="font-semibold text-violet-300">Configuración Python / GitHub</span>
        </div>
        <span className="text-slate-400 text-sm">{open ? "▲ ocultar" : "▼ ver guía"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3">
          {steps.map(s => (
            <div key={s.icon} className="rounded-xl bg-slate-900/60 border border-slate-700/40 p-3">
              <div className="flex items-center gap-2 mb-2">
                <span>{s.icon}</span>
                <span className="text-sm font-semibold text-slate-200">{s.title}</span>
              </div>
              <pre className="text-xs text-green-300 bg-black/30 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap">{s.code}</pre>
            </div>
          ))}
          <div className="text-xs text-slate-500 pt-1">
            📄 Archivos generados: <code className="text-violet-300">trading_bot/bot.py</code> · <code className="text-violet-300">bot_single.py</code> · <code className="text-violet-300">.github/workflows/trading_bot.yml</code>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Main App ----------------------------------------------------
export default function App() {
  const [cet, setCet]         = useState(getCET());
  const [signals, setSignals] = useState<Signal[]>([]);
  const [running, setRunning] = useState(true);
  const [tab, setTab]         = useState<"signals" | "guide">("signals");

  useEffect(() => {
    const t = setInterval(() => setCet(getCET()), 1000);
    return () => clearInterval(
