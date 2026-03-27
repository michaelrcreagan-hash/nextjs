import { NextResponse } from 'next/server'

const FALLBACK = {
  vix: { current: 20.5, changePercent: -2.3, change: -0.48 },
  dxy: { current: 104.2, changePercent: 0.15, change: 0.16 },
  tnx: { current: 4.25, changePercent: 1.2, change: 0.05 },
  spy: { current: 520, changePercent: -0.8, change: -4.2, sma200: 502 },
  spyVsSMA: 3.6,
  regimeScore: 44,
  netLiquidity: -2.3,
  timestamp: Date.now(),
}

function calcRegimeScore(
  vix: number,
  dxyChangePct: number,
  tnxChangePct: number,
  spyVsSMA: number
): number {
  let score = 50

  // VIX (fear gauge)
  if (vix < 15) score += 15
  else if (vix < 18) score += 10
  else if (vix < 22) score += 5
  else if (vix < 28) score -= 5
  else if (vix < 35) score -= 12
  else score -= 20

  // DXY % change (rising dollar = risk-off for crypto)
  if (dxyChangePct < -1) score += 10
  else if (dxyChangePct < -0.3) score += 5
  else if (dxyChangePct < 0.3) score += 0
  else if (dxyChangePct < 1) score -= 5
  else score -= 10

  // 10Y yield % change
  if (tnxChangePct < -3) score += 8
  else if (tnxChangePct < -1) score += 3
  else if (tnxChangePct < 1) score += 0
  else if (tnxChangePct < 3) score -= 5
  else score -= 10

  // SPY vs 200-day SMA
  if (spyVsSMA > 5) score += 10
  else if (spyVsSMA > 1) score += 5
  else if (spyVsSMA > -2) score -= 5
  else if (spyVsSMA > -5) score -= 10
  else score -= 15

  return Math.max(0, Math.min(100, score))
}

async function yhFetch(url: string) {
  const res = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      'Accept': 'application/json',
      'Accept-Language': 'en-US,en;q=0.9',
    },
    next: { revalidate: 60 },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function GET() {
  try {
    const [quotesResult, spyHistResult] = await Promise.allSettled([
      yhFetch(
        'https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EVIX,DX-Y.NYB,%5ETNX,SPY'
      ),
      yhFetch(
        'https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=1y'
      ),
    ])

    if (quotesResult.status === 'rejected') {
      return NextResponse.json({ ...FALLBACK, timestamp: Date.now() })
    }

    const quotes: Record<string, unknown>[] =
      quotesResult.value?.quoteResponse?.result ?? []

    const find = (sym: string) => quotes.find((q) => q['symbol'] === sym) as Record<string, number> | undefined
    const vixQ = find('^VIX')
    const dxyQ = find('DX-Y.NYB')
    const tnxQ = find('^TNX')
    const spyQ = find('SPY')

    const vixCur = vixQ?.regularMarketPrice ?? FALLBACK.vix.current
    const dxyChg = dxyQ?.regularMarketChangePercent ?? FALLBACK.dxy.changePercent
    const tnxChg = tnxQ?.regularMarketChangePercent ?? FALLBACK.tnx.changePercent

    let spy200sma: number | null = null
    if (spyHistResult.status === 'fulfilled') {
      const closes: number[] =
        spyHistResult.value?.chart?.result?.[0]?.indicators?.quote?.[0]?.close ?? []
      const valid = closes.filter(Boolean)
      if (valid.length >= 50) {
        const last200 = valid.slice(-200)
        spy200sma = last200.reduce((a: number, b: number) => a + b, 0) / last200.length
      }
    }

    const spyCur = spyQ?.regularMarketPrice ?? FALLBACK.spy.current
    const sma200 = spy200sma ?? FALLBACK.spy.sma200
    const spyVsSMA = ((spyCur - sma200) / sma200) * 100

    const regimeScore = calcRegimeScore(vixCur, dxyChg, tnxChg, spyVsSMA)

    return NextResponse.json({
      vix: {
        current: vixCur,
        changePercent: vixQ?.regularMarketChangePercent ?? FALLBACK.vix.changePercent,
        change: vixQ?.regularMarketChange ?? FALLBACK.vix.change,
      },
      dxy: {
        current: dxyQ?.regularMarketPrice ?? FALLBACK.dxy.current,
        changePercent: dxyChg,
        change: dxyQ?.regularMarketChange ?? FALLBACK.dxy.change,
      },
      tnx: {
        current: tnxQ?.regularMarketPrice ?? FALLBACK.tnx.current,
        changePercent: tnxChg,
        change: tnxQ?.regularMarketChange ?? FALLBACK.tnx.change,
      },
      spy: {
        current: spyCur,
        changePercent: spyQ?.regularMarketChangePercent ?? FALLBACK.spy.changePercent,
        change: spyQ?.regularMarketChange ?? FALLBACK.spy.change,
        sma200,
      },
      spyVsSMA,
      regimeScore,
      netLiquidity: FALLBACK.netLiquidity,
      timestamp: Date.now(),
    })
  } catch {
    return NextResponse.json({ ...FALLBACK, timestamp: Date.now() })
  }
}
