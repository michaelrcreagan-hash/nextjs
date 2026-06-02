import { NextResponse } from 'next/server'
import { hasCoinglass, cgGet, pick } from '@/app/lib/providers'

export const revalidate = 0

// Major USDT-perp universe (BTC + alts) tracked for funding / OI / squeeze setups.
const PERPS = [
  'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT',
  'AVAXUSDT', 'LINKUSDT', 'TONUSDT', 'TRXUSDT', 'DOTUSDT', 'NEARUSDT', 'APTUSDT',
  'SUIUSDT', 'SEIUSDT', 'TIAUSDT', 'INJUSDT', 'ARBUSDT', 'OPUSDT', 'LTCUSDT',
  'FILUSDT', 'WIFUSDT', '1000PEPEUSDT', 'FETUSDT', 'RNDRUSDT',
]

interface Coin {
  symbol: string; raw: string; price: number; change24h: number
  funding: number; fundingApr: number; oiUsd: number; volUsd: number; nextFunding: number
  oiChange24h?: number; longShortRatio?: number; longLiqUsd?: number; shortLiqUsd?: number
}

async function bFetch(url: string) {
  const res = await fetch(url, { next: { revalidate: 30 } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// --- CoinGlass path: aggregated, cross-exchange derivatives incl. liquidations
async function fromCoinglass(): Promise<{ coins: Coin[]; source: string }> {
  const rows = await cgGet<Record<string, unknown>[]>('/api/futures/coins-markets', { per_page: 100 }, 30)
  const coins: Coin[] = (rows ?? []).map((r) => {
    const symbol = String(r.symbol ?? '')
    const funding = pick(r, ['avg_funding_rate_by_oi', 'funding_rate', 'avgFundingRate']) / 100 // v4 returns %
    return {
      symbol, raw: symbol,
      price: pick(r, ['current_price', 'price']),
      change24h: pick(r, ['price_change_percent_24h', 'priceChangePercent24h']),
      funding,
      fundingApr: funding * 3 * 365 * 100,
      oiUsd: pick(r, ['open_interest_usd', 'openInterest', 'oi_usd']),
      volUsd: pick(r, ['volume_usd', 'volume_usd_24h', 'vol_usd']),
      nextFunding: 0,
      oiChange24h: pick(r, ['open_interest_change_percent_24h', 'oi_change_percent_24h']),
      longShortRatio: pick(r, ['long_short_ratio_24h', 'global_long_short_account_ratio'], 0) || undefined,
      longLiqUsd: pick(r, ['long_liquidation_usd_24h', 'longLiquidationUsd24h']),
      shortLiqUsd: pick(r, ['short_liquidation_usd_24h', 'shortLiquidationUsd24h']),
    }
  }).filter(c => c.price > 0 && c.oiUsd > 0)
    .sort((a, b) => b.oiUsd - a.oiUsd)
    .slice(0, 40)
  return { coins, source: 'coinglass' }
}

// --- Binance fallback: per-symbol funding + OI (no liquidation feed)
async function fromBinance(): Promise<{ coins: Coin[]; source: string }> {
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
  const oiResults = await Promise.allSettled(
    PERPS.map(s => bFetch(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${s}`))
  )
  const coins: Coin[] = PERPS.map((symbol, i) => {
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
  try {
    result = hasCoinglass() ? await fromCoinglass() : await fromBinance()
  } catch {
    // If the keyed provider failed, try the keyless fallback before giving up
    try { result = await fromBinance() } catch { result = null }
  }

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
