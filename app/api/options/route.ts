import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export interface OptionStrike {
  strike: number
  callOI: number
  putOI: number
  callVol: number
  putVol: number
  iv: number
}

const YH_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
  'Accept': 'application/json',
}

// Yahoo Finance options chain — free, no API key, nearest expiry
async function fetchYahooOptions(symbol: string): Promise<OptionStrike[] | null> {
  const url = `https://query1.finance.yahoo.com/v7/finance/options/${symbol}`
  const res = await fetch(url, { headers: YH_HEADERS, next: { revalidate: 300 } })
  if (!res.ok) return null

  const data = await res.json()
  const result = data?.optionChain?.result?.[0]
  if (!result) return null

  const calls: Record<string, number>[] = result.calls ?? []
  const puts: Record<string, number>[] = result.puts ?? []

  const strikeMap = new Map<number, OptionStrike>()

  for (const c of calls) {
    const strike = c.strike
    if (!strike) continue
    strikeMap.set(strike, {
      strike,
      callOI: c.openInterest ?? 0,
      putOI: 0,
      callVol: c.volume ?? 0,
      putVol: 0,
      iv: Math.round((c.impliedVolatility ?? 0) * 100 * 10) / 10,
    })
  }

  for (const p of puts) {
    const strike = p.strike
    if (!strike) continue
    const existing = strikeMap.get(strike)
    if (existing) {
      existing.putOI = p.openInterest ?? 0
      existing.putVol = p.volume ?? 0
      if (!existing.iv) existing.iv = Math.round((p.impliedVolatility ?? 0) * 100 * 10) / 10
    } else {
      strikeMap.set(strike, {
        strike,
        callOI: 0,
        putOI: p.openInterest ?? 0,
        callVol: 0,
        putVol: p.volume ?? 0,
        iv: Math.round((p.impliedVolatility ?? 0) * 100 * 10) / 10,
      })
    }
  }

  const chain = Array.from(strikeMap.values())
    .filter(s => s.strike > 0)
    .sort((a, b) => a.strike - b.strike)

  return chain.length > 0 ? chain : null
}

// Polygon.io options snapshot — higher quality data, requires POLYGON_API_KEY
// Free Starter tier: 5 req/min, 15-min delayed data
async function fetchPolygonOptions(symbol: string): Promise<OptionStrike[] | null> {
  const key = process.env.POLYGON_API_KEY
  if (!key) return null

  const today = new Date().toISOString().slice(0, 10)
  const threeMonths = new Date(Date.now() + 90 * 86400000).toISOString().slice(0, 10)
  const url = `https://api.polygon.io/v3/snapshot/options/${symbol}?limit=250&expiration_date.gte=${today}&expiration_date.lte=${threeMonths}&apiKey=${key}`

  const res = await fetch(url, { next: { revalidate: 300 } })
  if (!res.ok) return null

  const data = await res.json()
  const results: Record<string, unknown>[] = data?.results ?? []
  if (!results.length) return null

  const strikeMap = new Map<number, OptionStrike>()

  for (const opt of results) {
    const details = opt.details as Record<string, unknown> | undefined
    const strike = details?.strike_price as number | undefined
    const type = details?.contract_type as string | undefined
    if (!strike || !type) continue

    const day = opt.day as Record<string, number> | undefined
    const oi = (opt.open_interest as number) ?? 0
    const vol = day?.volume ?? 0
    const iv = Math.round(((opt.implied_volatility as number) ?? 0) * 100 * 10) / 10

    const entry = strikeMap.get(strike) ?? { strike, callOI: 0, putOI: 0, callVol: 0, putVol: 0, iv: 0 }
    if (type === 'call') { entry.callOI += oi; entry.callVol += vol }
    else { entry.putOI += oi; entry.putVol += vol }
    if (!entry.iv && iv) entry.iv = iv
    strikeMap.set(strike, entry)
  }

  const chain = Array.from(strikeMap.values()).sort((a, b) => a.strike - b.strike)
  return chain.length > 0 ? chain : null
}

// Spot price for the symbol
async function fetchSpot(symbol: string): Promise<number> {
  try {
    const url = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${encodeURIComponent(symbol)}`
    const res = await fetch(url, { headers: YH_HEADERS, next: { revalidate: 60 } })
    if (!res.ok) return 0
    const data = await res.json()
    return data?.quoteResponse?.result?.[0]?.regularMarketPrice ?? 0
  } catch { return 0 }
}

export async function GET(request: NextRequest) {
  const symbol = request.nextUrl.searchParams.get('symbol') ?? 'IBIT'

  try {
    // Polygon gives better multi-expiry aggregated data; Yahoo Finance is the free fallback
    const [chain, spot] = await Promise.all([
      fetchPolygonOptions(symbol).then(r => r ?? fetchYahooOptions(symbol)),
      fetchSpot(symbol),
    ])

    if (!chain || chain.length === 0) {
      return NextResponse.json({
        chain: [],
        spot,
        isReal: false,
        source: 'none',
        symbol,
        timestamp: Date.now(),
      })
    }

    const source = process.env.POLYGON_API_KEY ? 'polygon' : 'yahoo'
    return NextResponse.json({ chain, spot, isReal: true, source, symbol, timestamp: Date.now() })
  } catch {
    return NextResponse.json({ chain: [], spot: 0, isReal: false, source: 'error', symbol, timestamp: Date.now() })
  }
}
