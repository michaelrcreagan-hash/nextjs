import { NextResponse } from 'next/server'
import { calculateEMA, calculateRSI, calculateDMI, parseBinanceKlines, last, lastValid } from '@/app/lib/indicators'

export const revalidate = 0

async function klines(symbol: string, interval: string, limit: number) {
  const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`, { next: { revalidate: 30 } })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return parseBinanceKlines(await res.json())
}

// Daily Bias Framework: HTF trend (1D) + intraday momentum (4H) + perp funding.
// Produces a -100..+100 bias score with a directional label.
export async function GET() {
  try {
    const [d1, h4, prem] = await Promise.all([
      klines('BTCUSDT', '1d', 260),
      klines('BTCUSDT', '4h', 200),
      fetch('https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT', { next: { revalidate: 30 } }).then(r => r.json()).catch(() => null),
    ])

    const dCloses = d1.map(k => k.close)
    const price = last(dCloses)
    const ema20 = lastValid(calculateEMA(dCloses, 20))
    const ema50 = lastValid(calculateEMA(dCloses, 50))
    const ema200 = lastValid(calculateEMA(dCloses, 200))
    const rsiD = lastValid(calculateRSI(dCloses, 14))
    const dmiD = calculateDMI(d1.map(k => k.high), d1.map(k => k.low), dCloses, 14)
    const adxD = lastValid(dmiD.adx), pdi = lastValid(dmiD.plusDI), mdi = lastValid(dmiD.minusDI)

    const hCloses = h4.map(k => k.close)
    const ema9h = lastValid(calculateEMA(hCloses, 9))
    const ema21h = lastValid(calculateEMA(hCloses, 21))
    const rsiH = lastValid(calculateRSI(hCloses, 14))

    const funding = prem ? parseFloat(prem.lastFundingRate) : 0

    const factors: { label: string; bull: boolean | null; detail: string; weight: number }[] = [
      { label: 'Price vs 1D EMA20', bull: price > ema20, detail: `${price > ema20 ? 'above' : 'below'} ${ema20.toFixed(0)}`, weight: 15 },
      { label: 'Price vs 1D EMA50', bull: price > ema50, detail: `${price > ema50 ? 'above' : 'below'} ${ema50.toFixed(0)}`, weight: 15 },
      { label: 'Price vs 1D EMA200', bull: price > ema200, detail: `${price > ema200 ? 'above' : 'below'} ${ema200.toFixed(0)} (macro trend)`, weight: 20 },
      { label: 'EMA20 > EMA50 (1D)', bull: ema20 > ema50, detail: ema20 > ema50 ? 'bullish stack' : 'bearish stack', weight: 10 },
      { label: '1D DMI direction', bull: pdi > mdi, detail: `+DI ${pdi.toFixed(0)} / -DI ${mdi.toFixed(0)} · ADX ${adxD.toFixed(0)}`, weight: 12 },
      { label: '1D RSI regime', bull: rsiD >= 50, detail: `RSI ${rsiD.toFixed(0)}`, weight: 8 },
      { label: '4H EMA9 > EMA21', bull: ema9h > ema21h, detail: ema9h > ema21h ? 'intraday up' : 'intraday down', weight: 10 },
      { label: '4H RSI', bull: rsiH >= 50, detail: `RSI ${rsiH.toFixed(0)}`, weight: 5 },
      { label: 'Perp funding', bull: funding < 0.0001 ? true : funding > 0.0004 ? false : null, detail: `${(funding * 100).toFixed(3)}% /8h`, weight: 5 },
    ]

    let score = 0, totalW = 0
    for (const f of factors) {
      if (f.bull === null) continue
      totalW += f.weight
      score += (f.bull ? 1 : -1) * f.weight
    }
    const biasScore = totalW ? Math.round((score / totalW) * 100) : 0
    const label =
      biasScore >= 50 ? 'STRONG LONG BIAS' :
      biasScore >= 20 ? 'LONG BIAS' :
      biasScore > -20 ? 'NEUTRAL / CHOP' :
      biasScore > -50 ? 'SHORT BIAS' : 'STRONG SHORT BIAS'

    return NextResponse.json({
      price, biasScore, label, factors,
      levels: { ema20, ema50, ema200 }, funding, adx: adxD,
      timestamp: Date.now(),
    })
  } catch (e) {
    return NextResponse.json({ price: 0, biasScore: 0, label: 'UNAVAILABLE', factors: [], error: String(e), timestamp: Date.now() })
  }
}
