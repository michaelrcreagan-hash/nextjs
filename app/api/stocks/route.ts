import { NextResponse } from 'next/server'
import {
  calculateRSI, calculateDMI, calculateATR, calculateRVOL, calculateSMA, lastValid, last,
} from '@/app/lib/indicators'
import {
  WATCHLIST, SYMBOLS, PHASES, type BottleneckPhase,
  fundamentalComposite, technicalScore, buildTradePlan, buildOptionsPlay,
  compositeRank, type FundamentalInputs,
} from '@/app/lib/aiStocks'
import { hasFmp, fmpGet } from '@/app/lib/providers'

export const revalidate = 0

interface Chart {
  closes: number[]; highs: number[]; lows: number[]; volumes: number[]
  price: number; prevClose: number; changePct: number
}
interface Extra { fin?: FundamentalInputs; earningsTs?: number | null; finSource: 'fmp' | 'proxy' }

const HYPERSCALERS = ['MSFT', 'GOOGL', 'AMZN', 'META', 'ORCL']

// ---------------------------------------------------------------------------
// Keyless source: Yahoo Finance (charts + best-effort quote)
// ---------------------------------------------------------------------------
async function yhFetch(url: string) {
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', Accept: 'application/json' },
    next: { revalidate: 60 },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
async function yahooChart(symbol: string): Promise<Chart | null> {
  try {
    const j = await yhFetch(`https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=1y`)
    const r = j?.chart?.result?.[0]; const q = r?.indicators?.quote?.[0]
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

// ---------------------------------------------------------------------------
// Keyed source: Financial Modeling Prep (charts + real Layer-3 fundamentals + transcripts)
// ---------------------------------------------------------------------------
interface FmpBar { date: string; open: number; high: number; low: number; close: number; volume: number }
async function fmpChart(symbol: string): Promise<Chart | null> {
  try {
    const j = await fmpGet<{ historical?: FmpBar[] }>(`/api/v3/historical-price-full/${symbol}`, { timeseries: 300 }, 60)
    const hist = (j.historical ?? []).slice().reverse() // FMP returns newest-first
    if (hist.length < 30) return null
    const closes = hist.map(b => b.close), highs = hist.map(b => b.high), lows = hist.map(b => b.low), volumes = hist.map(b => b.volume)
    const price = last(closes), prevClose = closes[closes.length - 2] ?? price
    return { closes, highs, lows, volumes, price, prevClose, changePct: ((price - prevClose) / prevClose) * 100 }
  } catch { return null }
}

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)))
function norm(pct: number, lo: number, hi: number) { return clamp(((pct - lo) / (hi - lo)) * 100) }

// Real Layer-3 inputs from FMP analyst estimates (guidance) + earnings surprises (beat-and-raise).
async function fmpFundamentals(symbol: string, m30: number, m60: number, m90: number, eps?: number): Promise<Extra> {
  try {
    const [est, surp, quote] = await Promise.allSettled([
      fmpGet<Record<string, number>[]>(`/api/v3/analyst-estimates/${symbol}`, { period: 'annual', limit: 4 }, 3600),
      fmpGet<Record<string, number>[]>(`/api/v3/earnings-surprises/${symbol}`, {}, 3600),
      fmpGet<Record<string, number | string>[]>(`/api/v3/quote/${symbol}`, {}, 60),
    ])

    // Guidance quality — FY+1 estimated EPS growth vs trailing EPS
    let guidanceQuality = norm(m90, -25, 40)
    if (est.status === 'fulfilled' && est.value?.length) {
      const sorted = [...est.value].sort((a, b) => String(a.date).localeCompare(String(b.date)))
      const fwd = sorted.find(e => new Date(String(e.date)).getFullYear() >= new Date().getFullYear())?.estimatedEpsAvg
      const trailing = eps ?? Number((quote.status === 'fulfilled' && quote.value?.[0]?.eps) || 0)
      if (fwd && trailing > 0) guidanceQuality = norm(((fwd - trailing) / trailing) * 100, -5, 35)
    }

    // Beat-and-raise — consistency + magnitude of last 4 quarterly EPS beats
    let beatAndRaise = clamp((m30 > 0 ? 55 : 30) + m30 * 0.4)
    if (surp.status === 'fulfilled' && surp.value?.length) {
      const recent = surp.value.slice(0, 4)
      let beats = 0, mag = 0, n = 0
      for (const s of recent) {
        const act = Number(s.actualEarningResult), estv = Number(s.estimatedEarning)
        if (!estv) continue
        n++; if (act > estv) beats++
        mag += ((act - estv) / Math.abs(estv)) * 100
      }
      if (n) beatAndRaise = clamp((beats / n) * 60 + Math.min(40, (mag / n) * 4))
    }

    // EPS-revision momentum — price-trend proxy (exact 30/60/90d estimate deltas require
    // FMP's estimate-history endpoint / SPG as-of-date feed; documented in .env.example)
    const epsRevision = clamp(norm(m30, -12, 18) * 0.5 + norm(m60, -18, 28) * 0.3 + norm(m90, -25, 40) * 0.2)

    const earningsAnn = quote.status === 'fulfilled' ? quote.value?.[0]?.earningsAnnouncement : null
    const earningsTs = earningsAnn ? new Date(String(earningsAnn)).getTime() : null

    return { fin: { guidanceQuality, epsRevision, beatAndRaise }, earningsTs, finSource: 'fmp' }
  } catch {
    return { finSource: 'proxy' }
  }
}

// Layer 2 — pull latest hyperscaler transcripts and map language to the bottleneck phase table.
async function classifyTranscripts(): Promise<{ phase: BottleneckPhase | null; counts: Record<string, number>; source: string }> {
  const counts: Record<string, number> = Object.fromEntries(PHASES.map(p => [p.id, 0]))
  let any = false
  const year = new Date().getFullYear()
  const pickLatest = (a: { date?: string; content?: string }[]) =>
    (Array.isArray(a) && a.length ? [...a].sort((x, y2) => String(y2.date).localeCompare(String(x.date)))[0]?.content ?? '' : '')
  await Promise.all(HYPERSCALERS.map(async (sym) => {
    let text = ''
    try {
      // Batch earnings-call transcripts for a year live on FMP v4
      const arr = await fmpGet<{ date?: string; content?: string }[]>(`/api/v4/batch_earning_call_transcript/${sym}`, { year }, 86400)
      text = pickLatest(arr).slice(0, 60000)
      if (!text) {
        const arrPrev = await fmpGet<{ date?: string; content?: string }[]>(`/api/v4/batch_earning_call_transcript/${sym}`, { year: year - 1 }, 86400)
        text = pickLatest(arrPrev).slice(0, 60000)
      }
    } catch { /* skip company */ }
    if (!text) return
    any = true
    const low = text.toLowerCase()
    for (const p of PHASES) for (const kw of p.keywords) {
      const m = low.match(new RegExp(kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'))
      if (m) counts[p.id] += m.length
    }
  }))
  if (!any) return { phase: null, counts, source: 'none' }
  const phase = (Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null) as BottleneckPhase | null
  return { phase, counts, source: 'fmp' }
}

function momentum(closes: number[], n: number) {
  if (closes.length <= n) return 0
  const a = closes[closes.length - 1 - n], b = last(closes)
  return a ? ((b - a) / a) * 100 : 0
}

export async function GET() {
  const useFmp = hasFmp()

  const charts = useFmp
    ? await Promise.all(SYMBOLS.map(fmpChart))
    : await Promise.all(SYMBOLS.map(yahooChart))

  // Best-effort batch quote (Yahoo) for fundamentals when FMP is not connected
  let yQuotes: Record<string, Record<string, number>> = {}
  if (!useFmp) {
    try {
      const qj = await yhFetch(`https://query1.finance.yahoo.com/v7/finance/quote?symbols=${SYMBOLS.join(',')}`)
      const arr: Record<string, number>[] = qj?.quoteResponse?.result ?? []
      yQuotes = Object.fromEntries(arr.map(q => [String(q['symbol']), q]))
    } catch { /* proxies only */ }
  }

  // Pre-compute momentum so fundamentals fetch can reuse it
  const moms = charts.map(c => c ? { m30: momentum(c.closes, 21), m60: momentum(c.closes, 42), m90: momentum(c.closes, 63) } : null)

  // Real fundamentals (FMP) per symbol, in parallel; transcripts in parallel too
  const [extras, transcripts] = await Promise.all([
    Promise.all(WATCHLIST.map(async (t, i) => {
      const c = charts[i], mm = moms[i]
      if (useFmp && c && mm) return fmpFundamentals(t.symbol, mm.m30, mm.m60, mm.m90)
      return { finSource: 'proxy' as const }
    })),
    useFmp ? classifyTranscripts() : Promise.resolve({ phase: null as BottleneckPhase | null, counts: {} as Record<string, number>, source: 'none' as const }),
  ])

  const now = Date.now()
  const phaseMom: Record<BottleneckPhase, number[]> = { gpu_scarcity: [], networking: [], power_cooling: [], inference: [], custom_asic: [] }

  const rows = WATCHLIST.map((t, i) => {
    const c = charts[i]
    if (!c) return { symbol: t.symbol, name: t.name, category: t.category, subTheme: t.subTheme, ok: false as const, price: 0, changePct: 0 }
    const mm = moms[i]!
    const ex = extras[i]
    const yq = yQuotes[t.symbol] ?? {}

    const rsi = lastValid(calculateRSI(c.closes, 14))
    const dmi = calculateDMI(c.highs, c.lows, c.closes, 14)
    const adx = lastValid(dmi.adx), plusDI = lastValid(dmi.plusDI), minusDI = lastValid(dmi.minusDI)
    const atr = lastValid(calculateATR(c.highs, c.lows, c.closes, 14))
    const rvol = calculateRVOL(c.volumes, 20)
    const sma50 = lastValid(calculateSMA(c.closes, 50))
    const tech = technicalScore({ adx, plusDI, minusDI, rsi, rvol })

    // Fundamentals: real (FMP) when available, else proxy from price/eps
    let fin: FundamentalInputs
    if (ex.fin) {
      fin = ex.fin
    } else {
      const epsF = Number(yq['epsForward']) || 0, epsT = Number(yq['epsTrailingTwelveMonths']) || 0
      const epsGrowth = epsT > 0 ? ((epsF - epsT) / Math.abs(epsT)) * 100 : NaN
      fin = {
        guidanceQuality: isNaN(epsGrowth) ? clamp((norm(mm.m90, -20, 40) + (c.price > sma50 ? 70 : 35)) / 2) : norm(epsGrowth, -5, 35),
        epsRevision: clamp(norm(mm.m30, -12, 18) * 0.5 + norm(mm.m60, -18, 28) * 0.3 + norm(mm.m90, -25, 40) * 0.2),
        beatAndRaise: clamp((c.price > sma50 ? 60 : 30) + norm(mm.m30, -10, 20) * 0.4),
      }
    }
    const fundamental = fundamentalComposite(fin)
    const rank = compositeRank(fundamental, tech.score)
    const plan = buildTradePlan(c.price, atr)
    const opt = buildOptionsPlay(c.price, tech.score, fundamental)

    const ets = ex.earningsTs ?? (Number(yq['earningsTimestamp']) ? Number(yq['earningsTimestamp']) * 1000 : null)
    const daysToEarnings = ets ? Math.round((ets - now) / 86_400_000) : null
    const catalystSoon = daysToEarnings != null && daysToEarnings >= 0 && daysToEarnings <= 10

    t.phases.forEach(p => phaseMom[p].push(mm.m30))

    return {
      symbol: t.symbol, name: t.name, category: t.category, subTheme: t.subTheme, phases: t.phases, ok: true as const,
      price: +c.price.toFixed(2), changePct: +c.changePct.toFixed(2),
      rsi: +rsi.toFixed(1), adx: +adx.toFixed(1), plusDI: +plusDI.toFixed(1), minusDI: +minusDI.toFixed(1),
      rvol: +rvol.toFixed(2), atr: +atr.toFixed(2),
      m30: +mm.m30.toFixed(1), m60: +mm.m60.toFixed(1), m90: +mm.m90.toFixed(1),
      fundamental, technical: tech.score, techNotes: tech.notes, rank, fin, finSource: ex.finSource,
      plan, options: opt, daysToEarnings, catalystSoon,
    }
  })

  // Layer 2 — momentum-based phase + transcript-based phase
  const phaseScores = PHASES.map(p => {
    const arr = phaseMom[p.id]
    const avg = arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
    return { id: p.id, label: p.label, short: p.short, emoji: p.emoji, order: p.order,
      thesis: p.thesis, keywords: p.keywords, momentum: +avg.toFixed(2), members: arr.length,
      transcriptMentions: transcripts.counts[p.id] ?? 0 }
  })
  const momentumPhase = [...phaseScores].sort((a, b) => b.momentum - a.momentum)[0]?.id ?? 'gpu_scarcity'
  const activePhase = transcripts.phase ?? momentumPhase

  return NextResponse.json({
    rows,
    okCount: rows.filter(r => r.ok).length,
    phaseScores,
    activePhase,
    momentumPhase,
    transcriptPhase: transcripts.phase,
    dataSource: useFmp ? 'fmp' : 'yahoo',
    transcriptSource: transcripts.source,
    timestamp: now,
  })
}
