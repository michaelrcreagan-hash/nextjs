import { NextResponse } from 'next/server'

// Glassnode: on-chain analytics — requires GLASSNODE_API_KEY
// Free tier supports limited metrics; MVRV requires Standard or higher
async function glassnodeMetric(path: string): Promise<number | null> {
  const key = process.env.GLASSNODE_API_KEY
  if (!key) return null
  const since = Math.floor((Date.now() - 3 * 86400000) / 1000)
  const url = `https://api.glassnode.com/v1/metrics/${path}?a=BTC&i=24h&api_key=${key}&limit=2&s=${since}`
  try {
    const res = await fetch(url, { next: { revalidate: 3600 } })
    if (!res.ok) return null
    const data = await res.json()
    if (!Array.isArray(data) || data.length === 0) return null
    return data[data.length - 1]?.v ?? null
  } catch { return null }
}

// Alternative.me Fear & Greed Index — free, no key
async function fetchFearGreed(): Promise<{ value: number; label: string } | null> {
  try {
    const res = await fetch('https://api.alternative.me/fng/?limit=1', { next: { revalidate: 3600 } })
    if (!res.ok) return null
    const data = await res.json()
    const item = data?.data?.[0]
    if (!item) return null
    return { value: parseInt(item.value, 10), label: item.value_classification as string }
  } catch { return null }
}

// CoinGecko: price + market cap — free, no key (rate limit: 10-30 req/min)
async function fetchCoinGecko(): Promise<{ price: number; marketCap: number } | null> {
  try {
    const res = await fetch(
      'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true',
      { next: { revalidate: 300 } }
    )
    if (!res.ok) return null
    const data = await res.json()
    return {
      price: data?.bitcoin?.usd ?? 0,
      marketCap: data?.bitcoin?.usd_market_cap ?? 0,
    }
  } catch { return null }
}

// Realized price proxy: exponential-decay average of Binance daily closes (~365-day half-life)
// This approximates the average on-chain cost basis without a paid API
async function estimateRealizedPrice(): Promise<number | null> {
  try {
    const res = await fetch(
      'https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=500',
      { next: { revalidate: 3600 } }
    )
    if (!res.ok) return null
    const raw: unknown[][] = await res.json()
    const closes = raw.map(k => parseFloat(String(k[4])))
    const k = 1 / 365 // half-life ~1 year
    let realized = closes[0]
    for (let i = 1; i < closes.length; i++) realized = closes[i] * k + realized * (1 - k)
    return Math.round(realized)
  } catch { return null }
}

export async function GET() {
  const hasGlassnode = !!process.env.GLASSNODE_API_KEY

  const [mvrvResult, realizedGlass, fearGreedResult, cgResult, realizedEst] = await Promise.allSettled([
    glassnodeMetric('market/mvrv'),
    glassnodeMetric('market/price_realized_usd'),
    fetchFearGreed(),
    fetchCoinGecko(),
    estimateRealizedPrice(),
  ])

  const mvrvGlass = mvrvResult.status === 'fulfilled' ? mvrvResult.value : null
  const realizedGlassVal = realizedGlass.status === 'fulfilled' ? realizedGlass.value : null
  const fearGreed = fearGreedResult.status === 'fulfilled' ? fearGreedResult.value : null
  const cg = cgResult.status === 'fulfilled' ? cgResult.value : null
  const realizedEstVal = realizedEst.status === 'fulfilled' ? realizedEst.value : null

  const price = cg?.price ?? 0
  const realizedPrice = realizedGlassVal ?? realizedEstVal

  // Compute MVRV from realized price when Glassnode isn't available
  const mvrv = mvrvGlass ?? (realizedPrice && price > 0 ? Math.round((price / realizedPrice) * 100) / 100 : null)

  return NextResponse.json({
    mvrv,
    realizedPrice,
    fearGreed,
    price,
    marketCap: cg?.marketCap ?? null,
    hasGlassnode,
    realizedSource: realizedGlassVal ? 'glassnode' : realizedEstVal ? 'estimated' : null,
    mvrvSource: mvrvGlass ? 'glassnode' : realizedPrice ? 'computed' : null,
    timestamp: Date.now(),
  })
}
