// ============================================================================
// AI BOTTLENECK STOCK FRAMEWORK (Wolff / Aschenbrenner portfolio model)
// Layer 1 — Watchlist Universe   ·  Layer 2 — Bottleneck Rotation
// Layer 3 — Fundamental Screen   ·  Layer 4 — Technical Setup + Options
// ============================================================================

export type BottleneckPhase =
  | 'gpu_scarcity'
  | 'networking'
  | 'power_cooling'
  | 'inference'
  | 'custom_asic'

export interface PhaseDef {
  id: BottleneckPhase
  order: number
  label: string
  short: string
  emoji: string
  // transcript language that signals this phase is the live constraint
  keywords: string[]
  thesis: string
}

// Layer 2 — Hyperscaler CapEx Bottleneck Rotation phase table.
// The constraint migrates down the stack as each layer is relieved.
export const PHASES: PhaseDef[] = [
  {
    id: 'gpu_scarcity', order: 1, label: 'GPU / Accelerator Scarcity', short: 'GPU', emoji: '🟥',
    keywords: ['supply constrained', 'gpu allocation', 'demand outstripping supply', 'sold out', 'capacity', 'h100', 'h200', 'blackwell', 'wafer', 'foundry allocation', 'lead times'],
    thesis: 'Compute is the binding constraint. Overweight accelerator + foundry/equipment names; demand visibility is maximal.',
  },
  {
    id: 'networking', order: 2, label: 'Networking / Interconnect', short: 'Network', emoji: '🟧',
    keywords: ['networking', 'interconnect', 'optical', 'ethernet', 'infiniband', 'scale-out', 'scale-up', 'co-packaged', 'nvlink', 'bandwidth', 'fabric', 'switch'],
    thesis: 'Clusters scale faster than the fabric. Overweight switching, optics and SerDes/connectivity silicon.',
  },
  {
    id: 'power_cooling', order: 3, label: 'Power / Cooling / Datacenter', short: 'Power', emoji: '🟨',
    keywords: ['power', 'megawatt', 'gigawatt', 'grid', 'electricity', 'cooling', 'liquid cooling', 'thermal', 'datacenter shell', 'energization', 'substation', 'ppa', 'nuclear'],
    thesis: 'Energy + thermals gate deployment. Overweight power producers, electrical/cooling and datacenter infra.',
  },
  {
    id: 'inference', order: 4, label: 'Inference / Utilization', short: 'Inference', emoji: '🟩',
    keywords: ['inference', 'tokens', 'utilization', 'cost per token', 'efficiency', 'monetization', 'agents', 'serving', 'latency', 'throughput'],
    thesis: 'Build-out shifts to monetization. Overweight platforms with inference demand + efficiency / memory bandwidth.',
  },
  {
    id: 'custom_asic', order: 5, label: 'Custom Silicon / ASIC', short: 'ASIC', emoji: '🟦',
    keywords: ['custom silicon', 'asic', 'in-house', 'tpu', 'trainium', 'inferentia', 'maia', 'mtia', 'accelerator design', 'xpu', 'tape-out'],
    thesis: 'Hyperscalers internalize compute. Overweight merchant ASIC design partners + IP / connectivity.',
  },
]

export interface Ticker {
  symbol: string
  name: string
  category: 'Semiconductors' | 'Hyperscaler' | 'AI Infrastructure' | 'Power' | 'Memory' | 'Custom Silicon'
  subTheme: string
  // phases this name is most levered to (used for rotation overweighting)
  phases: BottleneckPhase[]
}

// Layer 1 — ~25 pre-seeded tickers across the AI value chain.
export const WATCHLIST: Ticker[] = [
  // Semiconductors / accelerators
  { symbol: 'NVDA', name: 'NVIDIA', category: 'Semiconductors', subTheme: 'GPU / accelerators', phases: ['gpu_scarcity', 'inference'] },
  { symbol: 'AMD', name: 'Advanced Micro Devices', category: 'Semiconductors', subTheme: 'GPU / MI accelerators', phases: ['gpu_scarcity', 'inference'] },
  { symbol: 'TSM', name: 'Taiwan Semiconductor', category: 'Semiconductors', subTheme: 'Leading-edge foundry', phases: ['gpu_scarcity', 'custom_asic'] },
  { symbol: 'ASML', name: 'ASML Holding', category: 'Semiconductors', subTheme: 'EUV litho equipment', phases: ['gpu_scarcity'] },
  { symbol: 'ARM', name: 'Arm Holdings', category: 'Semiconductors', subTheme: 'Compute IP / cores', phases: ['inference', 'custom_asic'] },
  // Custom silicon / connectivity
  { symbol: 'AVGO', name: 'Broadcom', category: 'Custom Silicon', subTheme: 'Custom ASIC + networking', phases: ['custom_asic', 'networking'] },
  { symbol: 'MRVL', name: 'Marvell Technology', category: 'Custom Silicon', subTheme: 'Custom ASIC + optical DSP', phases: ['custom_asic', 'networking'] },
  { symbol: 'ALAB', name: 'Astera Labs', category: 'Custom Silicon', subTheme: 'Connectivity / PCIe-CXL', phases: ['networking'] },
  { symbol: 'CRDO', name: 'Credo Technology', category: 'Custom Silicon', subTheme: 'SerDes / AECs', phases: ['networking'] },
  // Networking
  { symbol: 'ANET', name: 'Arista Networks', category: 'AI Infrastructure', subTheme: 'Datacenter switching', phases: ['networking'] },
  // Hyperscalers
  { symbol: 'MSFT', name: 'Microsoft', category: 'Hyperscaler', subTheme: 'Azure + Maia ASIC', phases: ['inference', 'custom_asic'] },
  { symbol: 'GOOGL', name: 'Alphabet', category: 'Hyperscaler', subTheme: 'GCP + TPU', phases: ['custom_asic', 'inference'] },
  { symbol: 'AMZN', name: 'Amazon', category: 'Hyperscaler', subTheme: 'AWS + Trainium', phases: ['custom_asic', 'inference'] },
  { symbol: 'META', name: 'Meta Platforms', category: 'Hyperscaler', subTheme: 'CapEx + MTIA', phases: ['gpu_scarcity', 'custom_asic'] },
  { symbol: 'ORCL', name: 'Oracle', category: 'Hyperscaler', subTheme: 'OCI / RPO backlog', phases: ['gpu_scarcity', 'power_cooling'] },
  // AI infrastructure / systems
  { symbol: 'VRT', name: 'Vertiv Holdings', category: 'AI Infrastructure', subTheme: 'Power + liquid cooling', phases: ['power_cooling'] },
  { symbol: 'SMCI', name: 'Super Micro', category: 'AI Infrastructure', subTheme: 'AI servers / systems', phases: ['gpu_scarcity', 'power_cooling'] },
  { symbol: 'DELL', name: 'Dell Technologies', category: 'AI Infrastructure', subTheme: 'AI servers / ISG', phases: ['gpu_scarcity'] },
  { symbol: 'CRWV', name: 'CoreWeave', category: 'AI Infrastructure', subTheme: 'GPU cloud / neocloud', phases: ['gpu_scarcity', 'inference'] },
  // Power
  { symbol: 'VST', name: 'Vistra', category: 'Power', subTheme: 'Merchant + nuclear power', phases: ['power_cooling'] },
  { symbol: 'CEG', name: 'Constellation Energy', category: 'Power', subTheme: 'Nuclear PPAs', phases: ['power_cooling'] },
  { symbol: 'GEV', name: 'GE Vernova', category: 'Power', subTheme: 'Turbines / grid', phases: ['power_cooling'] },
  { symbol: 'TLN', name: 'Talen Energy', category: 'Power', subTheme: 'Nuclear / datacenter PPAs', phases: ['power_cooling'] },
  // Memory
  { symbol: 'MU', name: 'Micron Technology', category: 'Memory', subTheme: 'HBM / DRAM', phases: ['gpu_scarcity', 'inference'] },
  { symbol: 'WDC', name: 'Western Digital', category: 'Memory', subTheme: 'Enterprise storage', phases: ['inference'] },
]

export const SYMBOLS = WATCHLIST.map(t => t.symbol)
export function tickerMeta(symbol: string) { return WATCHLIST.find(t => t.symbol === symbol) }

// ----------------------------------------------------------------------------
// Layer 3 — Fundamental composite (guidance quality, EPS-revision momentum,
// beat-and-raise trajectory). Inputs are normalized 0-100 sub-scores.
// ----------------------------------------------------------------------------
export interface FundamentalInputs {
  guidanceQuality: number   // 0-100  FY+1/FY+2 estimate strength + beat-and-raise tone
  epsRevision: number       // 0-100  30/60/90d upward revision momentum
  beatAndRaise: number      // 0-100  trajectory of beats followed by raised guides
}

export function fundamentalComposite(f: FundamentalInputs): number {
  // Weighted to favor revision momentum, then guidance, then beat-and-raise.
  return Math.round(f.epsRevision * 0.4 + f.guidanceQuality * 0.35 + f.beatAndRaise * 0.25)
}

// ----------------------------------------------------------------------------
// Layer 4 — Technical setup score from ADX / DMI / RSI / RVOL.
// ----------------------------------------------------------------------------
export interface TechInputs {
  adx: number
  plusDI: number
  minusDI: number
  rsi: number
  rvol: number
}

export function technicalScore(t: TechInputs): { score: number; notes: string[] } {
  let score = 0
  const notes: string[] = []
  // Trend strength (ADX)
  if (t.adx >= 30) { score += 30; notes.push(`ADX ${t.adx.toFixed(0)} — strong trend`) }
  else if (t.adx >= 20) { score += 18; notes.push(`ADX ${t.adx.toFixed(0)} — building trend`) }
  else { score += 5; notes.push(`ADX ${t.adx.toFixed(0)} — choppy / no trend`) }
  // Direction (DMI)
  if (t.plusDI > t.minusDI) { score += 25; notes.push(`+DI ${t.plusDI.toFixed(0)} > -DI ${t.minusDI.toFixed(0)} — bullish`) }
  else { notes.push(`-DI ${t.minusDI.toFixed(0)} > +DI ${t.plusDI.toFixed(0)} — bearish/avoid longs`) }
  // RSI zone — reward constructive pullbacks (40-60) and momentum (60-70), penalize overbought
  if (t.rsi >= 40 && t.rsi <= 60) { score += 25; notes.push(`RSI ${t.rsi.toFixed(0)} — pullback / re-load zone`) }
  else if (t.rsi > 60 && t.rsi <= 70) { score += 18; notes.push(`RSI ${t.rsi.toFixed(0)} — momentum`) }
  else if (t.rsi > 70) { score += 6; notes.push(`RSI ${t.rsi.toFixed(0)} — overbought, wait for pullback`) }
  else { score += 10; notes.push(`RSI ${t.rsi.toFixed(0)} — oversold, needs reversal`) }
  // Volume confirmation (RVOL)
  if (t.rvol >= 1.5) { score += 20; notes.push(`RVOL ${t.rvol.toFixed(1)}× — strong confirmation`) }
  else if (t.rvol >= 1.0) { score += 12; notes.push(`RVOL ${t.rvol.toFixed(1)}× — adequate`) }
  else { score += 4; notes.push(`RVOL ${t.rvol.toFixed(1)}× — light volume`) }
  return { score: Math.min(100, score), notes }
}

export interface TradePlan {
  entry: number; stop: number; tp1: number; tp2: number; tp3: number; rr1: number
}

// ATR-anchored Entry / Stop / TP ladder.
export function buildTradePlan(price: number, atr: number): TradePlan {
  const a = atr > 0 ? atr : price * 0.02
  const entry = price
  const stop = +(entry - 1.5 * a).toFixed(2)
  const tp1 = +(entry + 2 * a).toFixed(2)
  const tp2 = +(entry + 3.5 * a).toFixed(2)
  const tp3 = +(entry + 5 * a).toFixed(2)
  const rr1 = +((tp1 - entry) / (entry - stop || 1)).toFixed(2)
  return { entry: +entry.toFixed(2), stop, tp1, tp2, tp3, rr1 }
}

export interface OptionsPlay {
  structure: string
  legs: string
  dte: string
  rationale: string
}

// Layer 4 companion — options strategy (long calls / bull call spreads, 30-60 DTE).
export function buildOptionsPlay(price: number, tech: number, composite: number): OptionsPlay {
  const atm = roundStrike(price)
  const otm5 = roundStrike(price * 1.05)
  const otm10 = roundStrike(price * 1.10)
  // High conviction + strong trend → directional long calls; otherwise defined-risk spread.
  if (tech >= 65 && composite >= 60) {
    return {
      structure: 'Long Call (directional)',
      legs: `Buy ${atm}C`,
      dte: '45-60 DTE',
      rationale: 'Strong trend + fundamentals — buy slightly ITM/ATM calls 45-60 DTE for delta + runway.',
    }
  }
  if (tech >= 45) {
    return {
      structure: 'Bull Call Spread (defined risk)',
      legs: `Buy ${atm}C / Sell ${otm10}C`,
      dte: '30-45 DTE',
      rationale: 'Constructive but not extended — finance the long call by selling the +10% strike to cut theta.',
    }
  }
  return {
    structure: 'Wait / Bull Call Spread on confirmation',
    legs: `Watch ${atm}C → ${otm5}C on breakout`,
    dte: '30-45 DTE',
    rationale: 'Setup not confirmed. Stand aside until ADX rises and RVOL > 1.5× on a breakout.',
  }
}

function roundStrike(p: number): number {
  if (p < 50) return Math.round(p)
  if (p < 200) return Math.round(p / 2.5) * 2.5
  if (p < 1000) return Math.round(p / 5) * 5
  return Math.round(p / 10) * 10
}

export function compositeRank(fundamental: number, technical: number): number {
  return Math.round(fundamental * 0.55 + technical * 0.45)
}

export function actionFor(rank: number): { label: string; color: string } {
  if (rank >= 70) return { label: 'TOP SETUP', color: '#10b981' }
  if (rank >= 55) return { label: 'ACTIONABLE', color: '#22c55e' }
  if (rank >= 40) return { label: 'WATCH', color: '#eab308' }
  return { label: 'PASS', color: '#64748b' }
}
