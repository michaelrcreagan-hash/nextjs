import { NextResponse } from 'next/server'
import { getKlines } from '@/app/lib/klines'
import { hasFred, fredSeries } from '@/app/lib/providers'
import {
  realizedVol, forwardMean, pctChange, shift, rollingZ, optimizeLag, olsFit,
} from '@/app/lib/turbulence'

export const revalidate = 0

const ASSETS = ['SMH', 'QQQ', 'MU', 'VRT', 'GLD', 'TLT']
const MARKET_PREDICTORS: Record<string, string> = {
  VIX: '^VIX', TNX: '^TNX', DXY: 'DX-Y.NYB', OIL: 'CL=F',
}
const WINDOW = 20, HORIZON = 5, MAX_LAG = 63
const FRED_START = '2021-01-01'

interface Series { dates: string[]; closes: number[] }

async function yahooSeries(symbol: string): Promise<Series | null> {
  try {
    const res = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=3y`, {
      headers: { 'User-Agent': 'Mozilla/5.0', Accept: 'application/json' }, next: { revalidate: 3600 },
    })
    if (!res.ok) throw new Error(`${res.status}`)
    const r = (await res.json())?.chart?.result?.[0]
    const ts: number[] = r?.timestamp ?? []
    const closes: (number | null)[] = r?.indicators?.quote?.[0]?.close ?? []
    const dates: string[] = [], vals: number[] = []
    for (let i = 0; i < ts.length; i++) {
      if (closes[i] == null) continue
      dates.push(new Date(ts[i] * 1000).toISOString().slice(0, 10))
      vals.push(closes[i] as number)
    }
    return dates.length ? { dates, closes: vals } : null
  } catch { return null }
}

async function btcSeries(): Promise<Series | null> {
  const { klines } = await getKlines('BTCUSDT', '1d', 1100)
  if (!klines.length) return null
  return { dates: klines.map(k => new Date(k.time * 1000).toISOString().slice(0, 10)), closes: klines.map(k => k.close) }
}

// Reindex a (possibly sparser) series onto base dates with forward-fill + leading back-fill.
function reindex(baseDates: string[], s: Series): number[] {
  const m = new Map(s.dates.map((d, i) => [d, s.closes[i]]))
  const out: number[] = []
  let last = Number.NaN
  for (const d of baseDates) { const v = m.get(d); if (v != null && !Number.isNaN(v)) last = v; out.push(last) }
  const firstValid = out.find(v => !Number.isNaN(v)) ?? Number.NaN
  for (let i = 0; i < out.length && Number.isNaN(out[i]); i++) out[i] = firstValid
  return out
}
function reindexObs(baseDates: string[], obs: { date: string; value: number }[]): number[] {
  return reindex(baseDates, { dates: obs.map(o => o.date), closes: obs.map(o => o.value) })
}

export async function GET() {
  // Fetch everything in parallel
  const symbols = [...ASSETS, ...Object.values(MARKET_PREDICTORS)]
  const [seriesArr, btc, fred] = await Promise.all([
    Promise.all(symbols.map(yahooSeries)),
    btcSeries(),
    (async () => {
      if (!hasFred()) return null
      try {
        const [walcl, tga, rrp, cpi, pce] = await Promise.all([
          fredSeries('WALCL', FRED_START), fredSeries('WTREGEN', FRED_START), fredSeries('RRPONTSYD', FRED_START),
          fredSeries('CPIAUCSL', FRED_START), fredSeries('PCE', FRED_START),
        ])
        return { walcl, tga, rrp, cpi, pce }
      } catch { return null }
    })(),
  ])

  const byName: Record<string, Series | null> = {}
  symbols.forEach((s, i) => { byName[s] = seriesArr[i] })

  // Base calendar = QQQ (or first available equity) trading days
  const base = byName['QQQ'] ?? byName['SMH'] ?? seriesArr.find(Boolean) ?? null
  if (!base) {
    return NextResponse.json({ assets: [], error: 'no market data available', timestamp: Date.now() })
  }
  const baseDates = base.dates

  // Build aligned predictor arrays
  const predictors: Record<string, number[]> = {}
  if (btc) predictors.BTC = reindex(baseDates, btc)
  for (const [name, sym] of Object.entries(MARKET_PREDICTORS)) {
    const s = byName[sym]; if (s) predictors[name] = reindex(baseDates, s)
  }
  if (predictors.VIX) predictors.PC = rollingZ(predictors.VIX, 252)
  let fredEnabled = false
  if (fred) {
    const n = baseDates.length
    const liqW = reindexObs(baseDates, fred.walcl), liqT = reindexObs(baseDates, fred.tga), liqR = reindexObs(baseDates, fred.rrp)
    if (liqW.some(v => !Number.isNaN(v))) {
      predictors.LIQ = liqW.map((w, i) => w - (liqT[i] || 0) - (liqR[i] || 0)) // net liquidity proxy
    }
    const cpi = reindexObs(baseDates, fred.cpi), pce = reindexObs(baseDates, fred.pce)
    if (cpi.some(v => !Number.isNaN(v))) predictors.CPI = cpi
    if (pce.some(v => !Number.isNaN(v))) predictors.PCE = pce
    fredEnabled = predictors.LIQ != null || predictors.CPI != null
    void n
  }

  const out = ASSETS.map(asset => {
    const s = byName[asset]
    if (!s) return { asset, ok: false as const }
    const prices = reindex(baseDates, s)
    const vol = realizedVol(prices, WINDOW)
    const target = forwardMean(vol, HORIZON)
    const assetRetLag1 = shift(pctChange(prices), 1)

    // Optimal lag per predictor + feature columns
    const cols: number[][] = []
    const names: string[] = []
    const predStats: { name: string; lag: number; corr: number }[] = []
    for (const [name, arr] of Object.entries(predictors)) {
      const { lag, corr } = optimizeLag(arr, target, MAX_LAG)
      predStats.push({ name, lag, corr })
      cols.push(shift(arr, lag)); names.push(`${name}_lag${lag}`)
    }
    cols.push(assetRetLag1); names.push('AssetRet_lag1')

    // Assemble complete rows
    const X: number[][] = [], y: number[] = []
    for (let i = 0; i < baseDates.length; i++) {
      if (Number.isNaN(target[i])) continue
      const row = cols.map(c => c[i])
      if (row.some(v => Number.isNaN(v))) continue
      X.push(row); y.push(target[i])
    }
    const model = olsFit(X, y)

    // Latest feature row (target may be NaN there since it's forward-looking)
    let forecast = Number.NaN, lastIdx = -1
    for (let i = baseDates.length - 1; i >= 0; i--) {
      const row = cols.map(c => c[i])
      if (!row.some(v => Number.isNaN(v))) { lastIdx = i; if (model) forecast = model.predict(row); break }
    }
    const currentVol = [...vol].reverse().find(v => !Number.isNaN(v)) ?? Number.NaN
    const regime = !Number.isNaN(forecast) && forecast > currentVol * 1.25 ? 'HIGH TURBULENCE' : 'Normal/Low'

    // Out-of-sample correlation (85/15 split)
    let oosCorr = Number.NaN
    if (X.length > 60) {
      const split = Math.floor(X.length * 0.85)
      const m2 = olsFit(X.slice(0, split), y.slice(0, split))
      if (m2) {
        const pred = X.slice(split).map(r => m2.predict(r)), act = y.slice(split)
        const n = pred.length
        const mp = pred.reduce((a, b) => a + b, 0) / n, ma = act.reduce((a, b) => a + b, 0) / n
        let num = 0, dp = 0, da = 0
        for (let i = 0; i < n; i++) { const a = pred[i] - mp, b = act[i] - ma; num += a * b; dp += a * a; da += b * b }
        oosCorr = dp && da ? num / Math.sqrt(dp * da) : Number.NaN
      }
    }

    const topLags = [...predStats].sort((a, b) => Math.abs(b.corr) - Math.abs(a.corr)).slice(0, 3)
    return {
      asset, ok: true as const,
      currentVol: +currentVol.toFixed(2),
      forecast: Number.isNaN(forecast) ? null : +forecast.toFixed(2),
      regime,
      r2: model ? +model.r2.toFixed(4) : null,
      oosCorr: Number.isNaN(oosCorr) ? null : +oosCorr.toFixed(4),
      bestCorr: +Math.max(...predStats.map(p => Math.abs(p.corr))).toFixed(4),
      topLags, predictors: predStats, n: X.length,
      asOf: baseDates[lastIdx] ?? baseDates[baseDates.length - 1],
    }
  })

  const elevated = out.filter(a => a.ok && a.regime === 'HIGH TURBULENCE').length
  return NextResponse.json({
    assets: out,
    elevated,
    predictorsUsed: Object.keys(predictors),
    fredEnabled,
    config: { window: WINDOW, horizon: HORIZON, maxLag: MAX_LAG, target: 'Turbulence (Realized Vol)' },
    timestamp: Date.now(),
  })
}
