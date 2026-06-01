import { NextResponse } from 'next/server'
import {
  calculateRSI, calculateDMI, calculateATR, calculateRVOL, calculateSMA, lastValid, last,
} from '@/app/lib/indicators'
import {
  WATCHLIST, SYMBOLS, PHASES, type BottleneckPhase,
  fundamentalComposite, technicalScore, buildTradePlan, buildOptionsPlay,
  compositeRank, type FundamentalInputs,
} from '@/app/lib/aiStocks'

export const revalidate = 0

interface Chart {
  closes: number[]; highs: number[]; lows: number[]; volumes: number[]
  price: number; prevClose: number; changePct: number
}

async function yhFetch(url: string) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      'Accept': 'application/json',
    },
    next: { revalidate: 60 },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

async function fetchChart(symbol: string): Promise<Chart | null> {
  try {
    const j = await yhFetch(`https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=1y`)
    const r = j?.chart?.result?.[0]
    const q = r?.indicators?.quote?.[0]
    if (!q) return null
    const closes = (q.close ?? []).filter((v: number | null) => v != null) as number[]
    const highs = (q.high ?? []).filter((v: number | null) => v != null) as number[]
    const lows = (q.low ?? []).filter((v: number | null) => v != null) as number[]
    const volumes = (q.volume ?? []).filter((v: number | null) => v != null) as number[]
    if (closes.length < 30) return null
    const price = r?.meta?.regularMarketPrice ?? last(closes)
    const prevClose = r?.meta?.chartPreviousClose ?? closes[closes.length - 2] ?? price
    return { closes, highs, lows, volumes, price, prevClose, changePct: ((price - prevClose) / prevClose) * 100 }
  } catch { return null }
}

// Momentum over n trading days (proxy for EPS-revision / price trend)
function momentum(closes: number[], n: number): number {
  if (closes.length <= n) return 0
  const a = closes[closes.length - 1 - n], b = last(closes)
  return a ? ((b - a) / a) * 100 : 0
}
// Map a return to a 0-100 sub-score
function norm(pct: number, lo: number, hi: number): number {
  return Math.max(0, Math.min(100, ((pct - lo) / (hi - lo)) * 100))
}

export async function GET() {
  const charts = await Promise.all(SYMBOLS.map(fetchChart))

  // Best-effort batch quote for fundamentals (eps, earnings dates). Non-fatal.
  let quotes: Record<string, Record<string, number>> = {}
  try {
    const qj = await yhFetch(`https://query1.finance.yahoo.com/v7/finance/quote?symbols=${SYMBOLS.join(',')}`)
    const arr: Record<string, number>[] = qj?.quoteResponse?.result ?? []
    quotes = Object.fromEntries(arr.map(q => [String(q['symbol']), q]))
  } catch { /* proxies only */ }

  const now = Date.now()
  const phaseMom: Record<BottleneckPhase, number[]> = {
    gpu_scarcity: [], networking: [], power_cooling: [], inference: [], custom_asic: [],
  }

  const rows = WATCHLIST.map((t, i) => {
    const c = charts[i]
    const q = quotes[t.symbol] ?? {}
    if (!c) {
      return { symbol: t.symbol, name: t.name, category: t.category, subTheme: t.subTheme,
        ok: false as const, price: 0, changePct: 0 }
    }
    // Technicals
    const rsi = lastValid(calculateRSI(c.closes, 14))
    const dmi = calculateDMI(c.highs, c.lows, c.closes, 14)
    const adx = lastValid(dmi.adx), plusDI = lastValid(dmi.plusDI), minusDI = lastValid(dmi.minusDI)
    const atr = lastValid(calculateATR(c.highs, c.lows, c.closes, 14))
    const rvol = calculateRVOL(c.volumes, 20)
    const sma50 = lastValid(calculateSMA(c.closes, 50))
    const tech = technicalScore({ adx, plusDI, minusDI, rsi, rvol })

    // Momentum (used both for trend & as revision proxy)
    const m30 = momentum(c.closes, 21), m60 = momentum(c.closes, 42), m90 = momentum(c.closes, 63)

    // Layer 3 fundamentals — real eps growth if available, momentum proxies otherwise
    const epsF = Number(q['epsForward']) || 0
    const epsT = Number(q['epsTrailingTwelveMonths']) || 0
    const epsGrowth = epsT > 0 ? ((epsF - epsT) / Math.abs(epsT)) * 100 : NaN
    const guidanceQuality = isNaN(epsGrowth)
      ? Math.round((norm(m90, -20, 40) + (c.price > sma50 ? 70 : 35)) / 2)
      : Math.round(norm(epsGrowth, -5, 35))
    // 30/60/90d upward revision momentum proxy (weighted to recent)
    const epsRevision = Math.round(norm(m30, -12, 18) * 0.5 + norm(m60, -18, 28) * 0.3 + norm(m90, -25, 40) * 0.2)
    // Beat-and-raise trajectory proxy: holding above rising 50DMA after recent strength
    const beatAndRaise = Math.round((c.price > sma50 ? 60 : 30) + norm(m30, -10, 20) * 0.4)
    const fin: FundamentalInputs = {
      guidanceQuality: Math.min(100, guidanceQuality),
      epsRevision: Math.min(100, epsRevision),
      beatAndRaise: Math.min(100, beatAndRaise),
    }
    const fundamental = fundamentalComposite(fin)
    const rank = compositeRank(fundamental, tech.score)

    const plan = buildTradePlan(c.price, atr)
    const opt = buildOptionsPlay(c.price, tech.score, fundamental)

    // Catalyst window (earnings within 10 days)
    const ets = Number(q['earningsTimestamp']) || Number(q['earningsTimestampStart']) || 0
    const daysToEarnings = ets ? Math.round((ets * 1000 - now) / 86_400_000) : null
    const catalystSoon = daysToEarnings != null && daysToEarnings >= 0 && daysToEarnings <= 10

    // Feed phase basket momentum (1-month return)
    t.phases.forEach(p => phaseMom[p].push(m30))

    return {
      symbol: t.symbol, name: t.name, category: t.category, subTheme: t.subTheme, phases: t.phases,
      ok: true as const,
      price: +c.price.toFixed(2), changePct: +c.changePct.toFixed(2),
      rsi: +rsi.toFixed(1), adx: +adx.toFixed(1), plusDI: +plusDI.toFixed(1), minusDI: +minusDI.toFixed(1),
      rvol: +rvol.toFixed(2), atr: +atr.toFixed(2),
      m30: +m30.toFixed(1), m60: +m60.toFixed(1), m90: +m90.toFixed(1),
      fundamental, technical: tech.score, techNotes: tech.notes, rank, fin,
      plan, options: opt,
      daysToEarnings, catalystSoon,
    }
  })

  // Layer 2 — infer active bottleneck phase from basket momentum
  const phaseScores = PHASES.map(p => {
    const arr = phaseMom[p.id]
    const avg = arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
    return { id: p.id, label: p.label, short: p.short, emoji: p.emoji, order: p.order,
      thesis: p.thesis, keywords: p.keywords, momentum: +avg.toFixed(2), members: arr.length }
  })
  const activePhase = [...phaseScores].sort((a, b) => b.momentum - a.momentum)[0]?.id ?? 'gpu_scarcity'

  const okRows = rows.filter(r => r.ok)
  return NextResponse.json({
    rows,
    okCount: okRows.length,
    phaseScores,
    activePhase,
    timestamp: now,
  })
}
