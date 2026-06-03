import { NextResponse } from 'next/server'
import { hasCoinapi, coinapiBinancePerpMetric } from '@/app/lib/providers'

export const revalidate = 0

// Major USDT-perp universe (BTC + alts) tracked for funding / OI / squeeze setups.
const PERPS = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LINK', 'TON', 'TRX',
  'DOT', 'NEAR', 'APT', 'SUI', 'SEI', 'TIA', 'INJ', 'ARB', 'OP', 'LTC', 'FIL',
  'WIF', 'PEPE', 'FET', 'RNDR',
]

interface Coin {
  symbol: string; raw: string; price: number; change24h: number
  funding: number; fundingApr: number; oiUsd: number; volUsd: number; nextFunding: number
}

interface Mkt { price: number; change: number; vol: number }

// CoinGecko: US-accessible spot price / 24h change / volume for the perp universe.
async function geckoMarkets(): Promise<Map<string, Mkt>> {
  const map = new Map<string, Mkt>()
  try {
    const rows = await fetch(
      'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=120&page=1&price_change_percentage=24h',
      { next: { revalidate: 60 } },
    ).then(r => r.json()) as Record<string, number | string>[]
    for (const r of rows) {
      const sym = String(r.symbol).toUpperCase()
      if (!map.has(sym)) map.set(sym, {
        price: Number(r.current_price), change: Number(r.price_change_percentage_24h) || 0, vol: Number(r.total_volume) || 0,
      })
    }
  } catch { /* empty */ }
  return map
}

// --- CoinAPI path: funding + open interest (CoinAPI metrics) × spot price (CoinGecko)
async function fromCoinapi(): Promise<{ coins: Coin[]; source: string }> {
  const [funding, oi, markets] = await Promise.all([
    coinapiBinancePerpMetric('DERIVATIVES_FUNDING_RATE_CURRENT'),
    coinapiBinancePerpMetric('DERIVATIVES_OPEN_INTEREST').catch(() => new Map<string, number>()),
    geckoMarkets(),
  ])
  const coins: Coin[] = PERPS.map(asset => {
    const mk = markets.get(asset)
    const f = funding.get(asset) ?? 0
    const oiBase = oi.get(asset) ?? 0
    const price = mk?.price ?? 0
    return {
      symbol: asset, raw: `${asset}USDT`, price,
      change24h: mk?.change ?? 0, funding: f, fundingApr: f * 3 * 365 * 100,
      oiUsd: oiBase * price, volUsd: mk?.vol ?? 0, nextFunding: 0,
    }
  }).filter(c => c.price > 0 && (c.funding !== 0 || c.oiUsd > 0))
    .sort((a, b) => b.oiUsd - a.oiUsd)
  return { coins, source: 'coinapi' }
}

// --- Binance fallback (keyless; may be geo-restricted in some regions)
async function bFetch(url: string) {
  const res = await fetch(url, { next: { revalidate: 30 } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
async function fromBinance(): Promise<{ coins: Coin[]; source: string }> {
  const symbols = PERPS.map(a => `${a === 'PEPE' ? '1000PEPE' : a}USDT`)
  const [premium, ticker] = await Promise.all([
    bFetch('https://fapi.binance.com/fapi/v1/premiumIndex'),
    bFetch('https://fapi.binance.com/fapi/v1/ticker/24hr'),
  ])
  const fundMap = new Map<string, { funding: number; mark: number; nextFunding: number }>()
  for (const p of premium as Record<string, string>[]) {
    fundMap.set(p.symbol, { funding: parseFloat(p.lastFundingRate), mark: parseFloat(p.markPrice), nextFunding: Number(p.nextFundingTime) })
  }
  const tickMap = new Map<string, { change: number; vol: number; price: number }>()
  for (const t of ticker as Record<string, string>[]) {
    tickMap.set(t.symbol, { change: parseFloat(t.priceChangePercent), vol: parseFloat(t.quoteVolume), price: parseFloat(t.lastPrice) })
  }
  const oiResults = await Promise.allSettled(symbols.map(s => bFetch(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${s}`)))
  const coins: Coin[] = symbols.map((symbol, i) => {
    const f = fundMap.get(symbol); const tk = tickMap.get(symbol)
    const oiRes = oiResults[i]
    const oiBase = oiRes.status === 'fulfilled' ? parseFloat(oiRes.value.openInterest) : 0
    const mark = f?.mark ?? tk?.price ?? 0
    const funding = f?.funding ?? 0
    return {
      symbol: symbol.replace('USDT', '').replace('1000', '1000·'), raw: symbol,
      price: mark, change24h: tk?.change ?? 0, funding, fundingApr: funding * 3 * 365 * 100,
      oiUsd: oiBase * mark, volUsd: tk?.vol ?? 0, nextFunding: f?.nextFunding ?? 0,
    }
  }).filter(c => c.price > 0).sort((a, b) => b.oiUsd - a.oiUsd)
  return { coins, source: 'binance' }
}

export async function GET() {
  let result: { coins: Coin[]; source: string } | null = null
  if (hasCoinapi()) { try { result = await fromCoinapi() } catch { /* fall through */ } }
  if (!result || result.coins.length === 0) { try { result = await fromBinance() } catch { result = null } }

  if (!result || result.coins.length === 0) {
    return NextResponse.json({ coins: [], aggregate: null, source: 'none', timestamp: Date.now() })
  }

  const { coins, source } = result
  const totalOi = coins.reduce((a, c) => a + c.oiUsd, 0)
  const negFunding = coins.filter(c => c.funding < -0.0001)
  const avgFunding = coins.length ? coins.reduce((a, c) => a + c.funding, 0) / coins.length : 0

  return NextResponse.json({
    coins,
    aggregate: {
      totalOi, avgFunding, negFundingCount: negFunding.length,
      mostNegative: [...coins].sort((a, b) => a.funding - b.funding).slice(0, 5).map(c => c.symbol),
    },
    source,
    timestamp: Date.now(),
  })
}
