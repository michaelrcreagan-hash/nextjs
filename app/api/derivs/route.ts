import { NextResponse } from 'next/server'

export const revalidate = 0

// Major USDT-perp universe (BTC + alts) tracked for funding / OI / squeeze setups.
const PERPS = [
  'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'ADAUSDT',
  'AVAXUSDT', 'LINKUSDT', 'TONUSDT', 'TRXUSDT', 'DOTUSDT', 'NEARUSDT', 'APTUSDT',
  'SUIUSDT', 'SEIUSDT', 'TIAUSDT', 'INJUSDT', 'ARBUSDT', 'OPUSDT', 'LTCUSDT',
  'FILUSDT', 'WIFUSDT', '1000PEPEUSDT', 'FETUSDT', 'RNDRUSDT',
]

async function bFetch(url: string) {
  const res = await fetch(url, { next: { revalidate: 30 } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function GET() {
  try {
    const [premium, ticker] = await Promise.all([
      bFetch('https://fapi.binance.com/fapi/v1/premiumIndex'),
      bFetch('https://fapi.binance.com/fapi/v1/ticker/24hr'),
    ])

    const fundMap = new Map<string, { funding: number; mark: number; nextFunding: number }>()
    for (const p of premium as Record<string, string>[]) {
      fundMap.set(p.symbol, {
        funding: parseFloat(p.lastFundingRate),
        mark: parseFloat(p.markPrice),
        nextFunding: Number(p.nextFundingTime),
      })
    }
    const tickMap = new Map<string, { change: number; vol: number; price: number }>()
    for (const t of ticker as Record<string, string>[]) {
      tickMap.set(t.symbol, {
        change: parseFloat(t.priceChangePercent),
        vol: parseFloat(t.quoteVolume),
        price: parseFloat(t.lastPrice),
      })
    }

    // Open interest per symbol (notional in base units → USD via mark price)
    const oiResults = await Promise.allSettled(
      PERPS.map(s => bFetch(`https://fapi.binance.com/fapi/v1/openInterest?symbol=${s}`))
    )

    const coins = PERPS.map((symbol, i) => {
      const f = fundMap.get(symbol)
      const tk = tickMap.get(symbol)
      const oiRes = oiResults[i]
      const oiBase = oiRes.status === 'fulfilled' ? parseFloat(oiRes.value.openInterest) : 0
      const mark = f?.mark ?? tk?.price ?? 0
      const oiUsd = oiBase * mark
      const funding = f?.funding ?? 0
      return {
        symbol: symbol.replace('USDT', '').replace('1000', '1000·'),
        raw: symbol,
        price: mark,
        change24h: tk?.change ?? 0,
        funding,                       // per 8h
        fundingApr: funding * 3 * 365 * 100, // annualized %
        oiUsd,
        volUsd: tk?.vol ?? 0,
        nextFunding: f?.nextFunding ?? 0,
      }
    }).filter(c => c.price > 0)
      .sort((a, b) => b.oiUsd - a.oiUsd)

    const totalOi = coins.reduce((a, c) => a + c.oiUsd, 0)
    const negFunding = coins.filter(c => c.funding < -0.0001)
    const avgFunding = coins.length ? coins.reduce((a, c) => a + c.funding, 0) / coins.length : 0

    return NextResponse.json({
      coins,
      aggregate: {
        totalOi,
        avgFunding,
        negFundingCount: negFunding.length,
        mostNegative: [...coins].sort((a, b) => a.funding - b.funding).slice(0, 5).map(c => c.symbol),
      },
      timestamp: Date.now(),
    })
  } catch (e) {
    return NextResponse.json({ coins: [], aggregate: null, error: String(e), timestamp: Date.now() })
  }
}
