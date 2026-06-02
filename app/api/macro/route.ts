import { NextResponse } from 'next/server'

const FALLBACK = {
  vix: { current: 20.5, changePercent: -2.3, change: -0.48 },
  dxy: { current: 104.2, changePercent: 0.15, change: 0.16 },
  tnx: { current: 4.25, changePercent: 1.2, change: 0.05 },
  spy: { current: 520, changePercent: -0.8, change: -4.2, sma200: 502 },
  spyVsSMA: 3.6,
  regimeScore: 44,
  netLiquidity: { current: null, change4w: null, isReal: false },
  timestamp: Date.now(),
}

function calcRegimeScore(
  vix: number,
  dxyChangePct: number,
  tnxChangePct: number,
  spyVsSMA: number
): number {
  let score = 50
  if (vix < 15) score += 15
  else if (vix < 18) score += 10
  else if (vix < 22) score += 5
  else if (vix < 28) score -= 5
  else if (vix < 35) score -= 12
  else score -= 20
  if (dxyChangePct < -1) score += 10
  else if (dxyChangePct < -0.3) score += 5
  else if (dxyChangePct < 0.3) score += 0
  else if (dxyChangePct < 1) score -= 5
  else score -= 10
  if (tnxChangePct < -3) score += 8
  else if (tnxChangePct < -1) score += 3
  else if (tnxChangePct < 1) score += 0
  else if (tnxChangePct < 3) score -= 5
  else score -= 10
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

// FRED: Federal Reserve Economic Data — for Net Fed Liquidity
// Net Liquidity = WALCL (Fed BS) - WTREGEN (TGA) - RRPONTSYD (RRP)
async function fetchFredSeries(seriesId: string, apiKey: string, limit: number): Promise<number[]> {
  const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${apiKey}&file_type=json&limit=${limit}&sort_order=desc`
  const res = await fetch(url, {
    headers: { 'Accept': 'application/json' },
    next: { revalidate: 3600 },
  })
  if (!res.ok) return []
  const data = await res.json()
  return (data.observations ?? [])
    .filter((o: { value: string }) => o.value !== '.')
    .map((o: { value: string }) => parseFloat(o.value))
}

async function computeNetLiquidity(): Promise<{ current: number | null; change4w: number | null; isReal: boolean }> {
  const key = process.env.FRED_API_KEY
  if (!key) return { current: null, change4w: null, isReal: false }

  try {
    // WALCL & WTREGEN: weekly, millions USD. RRPONTSYD: daily, billions USD
    const [walcl, wtregen, rrp] = await Promise.all([
      fetchFredSeries('WALCL', key, 8),
      fetchFredSeries('WTREGEN', key, 8),
      fetchFredSeries('RRPONTSYD', key, 32),
    ])

    if (!walcl.length || !wtregen.length || !rrp.length) return { current: null, change4w: null, isReal: false }

    // current net liquidity (millions USD)
    const net0 = walcl[0] - wtregen[0] - rrp[0] * 1000
    // 4-week-ago net liquidity
    const net4w =
      (walcl[Math.min(4, walcl.length - 1)] ?? walcl[0]) -
      (wtregen[Math.min(4, wtregen.length - 1)] ?? wtregen[0]) -
      (rrp[Math.min(28, rrp.length - 1)] ?? rrp[0]) * 1000

    const change4w = net4w !== 0 ? Math.round(((net0 - net4w) / Math.abs(net4w)) * 10000) / 100 : 0

    return { current: Math.round(net0), change4w, isReal: true }
  } catch {
    return { current: null, change4w: null, isReal: false }
  }
}

export async function GET() {
  try {
    const [quotesResult, spyHistResult, netLiqResult] = await Promise.allSettled([
      yhFetch('https://query1.finance.yahoo.com/v7/finance/quote?symbols=%5EVIX,DX-Y.NYB,%5ETNX,SPY'),
      yhFetch('https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=1y'),
      computeNetLiquidity(),
    ])

    if (quotesResult.status === 'rejected') {
      return NextResponse.json({ ...FALLBACK, timestamp: Date.now() })
    }

    const quotes: Record<string, unknown>[] = quotesResult.value?.quoteResponse?.result ?? []
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
      const closes: number[] = spyHistResult.value?.chart?.result?.[0]?.indicators?.quote?.[0]?.close ?? []
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

    const netLiquidity = netLiqResult.status === 'fulfilled'
      ? netLiqResult.value
      : FALLBACK.netLiquidity

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
      netLiquidity,
      timestamp: Date.now(),
    })
  } catch {
    return NextResponse.json({ ...FALLBACK, timestamp: Date.now() })
  }
}
