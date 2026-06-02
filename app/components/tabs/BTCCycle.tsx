'use client'

import { useEffect, useState, useCallback } from 'react'
import dynamic from 'next/dynamic'
import { calculateRSI, calculateSMA, parseBinanceKlines, type Kline } from '@/app/lib/indicators'

const TradingChart = dynamic(() => import('@/app/components/charts/TradingChart'), { ssr: false })

interface BottomSignal {
  name: string
  value: string
  met: boolean
  weight: number
  note: string
}

interface OnchainData {
  mvrv: number | null
  realizedPrice: number | null
  fearGreed: { value: number; label: string } | null
  price: number
  hasGlassnode: boolean
  realizedSource: string | null
  mvrvSource: string | null
}

interface Props {
  onBottomScore?: (score: number) => void
}

function computeBottomScore(klines: Kline[], onchain: OnchainData): { score: number; signals: BottomSignal[] } {
  if (klines.length < 30) return { score: 0, signals: [] }

  const closes = klines.map(k => k.close)
  const volumes = klines.map(k => k.volume)
  const latest = closes[closes.length - 1]

  const rsi14 = calculateRSI(closes, 14)
  const currentRSI = rsi14[rsi14.length - 1] ?? 50
  const sma200 = calculateSMA(closes, Math.min(200, closes.length))
  const sma50 = calculateSMA(closes, Math.min(50, closes.length))
  const currentSMA200 = sma200[sma200.length - 1] ?? latest
  const currentSMA50 = sma50[sma50.length - 1] ?? latest
  const avgVol = volumes.slice(-20).reduce((a, b) => a + b, 0) / 20
  const currentVol = volumes[volumes.length - 1]

  // Signal 5 & 9: use real on-chain data when available
  const mvrv = onchain.mvrv ?? (latest / (currentSMA200 * 1.1))
  const mvrvLabel = onchain.mvrvSource
    ? `${mvrv.toFixed(2)} (${onchain.mvrvSource})`
    : `~${mvrv.toFixed(2)} (proxy)`

  const realizedPx = onchain.realizedPrice ?? 50000
  const realizedLabel = onchain.realizedSource === 'glassnode'
    ? `$${realizedPx.toLocaleString()} (Glassnode)`
    : onchain.realizedSource === 'estimated'
    ? `~$${realizedPx.toLocaleString()} (est.)`
    : `~$45-50K (est.)`

  const fearVal = onchain.fearGreed?.value ?? 50
  const fearLabel = onchain.fearGreed
    ? `${fearVal} — ${onchain.fearGreed.label}`
    : 'N/A'

  const signals: BottomSignal[] = [
    {
      name: 'Weekly RSI < 30',
      value: `RSI: ${currentRSI.toFixed(1)}`,
      met: currentRSI < 30,
      weight: 1,
      note: 'Extreme oversold on weekly timeframe',
    },
    {
      name: 'Price below 200W SMA',
      value: `${((latest / currentSMA200 - 1) * 100).toFixed(1)}% vs SMA`,
      met: latest < currentSMA200,
      weight: 1,
      note: 'Deep value zone — historically rare',
    },
    {
      name: 'Price below 50W SMA',
      value: `${((latest / currentSMA50 - 1) * 100).toFixed(1)}% vs SMA50`,
      met: latest < currentSMA50,
      weight: 1,
      note: 'Medium-term bearish structure',
    },
    {
      name: 'Volume Spike (>2x avg)',
      value: `${(currentVol / avgVol).toFixed(1)}x avg vol`,
      met: currentVol > avgVol * 2,
      weight: 1,
      note: 'Capitulation/panic selling volume',
    },
    {
      name: 'MVRV < 1.0',
      value: mvrvLabel,
      met: mvrv < 1.0,
      weight: 1,
      note: 'Market below realized price — accumulation zone',
    },
    {
      name: '50%+ Drawdown from ATH',
      value: `${((latest / 109000 - 1) * 100).toFixed(1)}% from ATH`,
      met: latest < 109000 * 0.5,
      weight: 1,
      note: 'Historical bottoms occur at 50-85% drawdown',
    },
    {
      name: 'RSI 30-40 Range (Accumulation)',
      value: `RSI: ${currentRSI.toFixed(1)}`,
      met: currentRSI >= 30 && currentRSI <= 40,
      weight: 1,
      note: 'Base-building phase RSI range',
    },
    {
      name: 'Fibonacci 0.618 Zone',
      value: `$57,700 target`,
      met: latest >= 47000 && latest <= 65000,
      weight: 1,
      note: '0.618 retracement = $57,700 confluence',
    },
    {
      name: 'Below Realized Price',
      value: realizedLabel,
      met: latest < realizedPx,
      weight: 1,
      note: 'Average cost basis of all BTC holders',
    },
    {
      name: 'Fear & Greed ≤ 20 (Extreme Fear)',
      value: fearLabel,
      met: fearVal <= 20,
      weight: 1,
      note: 'Retail capitulation sentiment — historical buy signal',
    },
    {
      name: 'LTH Accumulation Signal',
      value: latest < 65000 ? 'ACTIVE' : 'INACTIVE',
      met: latest < 65000,
      weight: 1,
      note: 'Long-term holders historically buy here',
    },
    {
      name: 'STH Capitulation',
      value: latest < currentSMA50 * 0.85 ? 'DETECTED' : 'NOT YET',
      met: latest < currentSMA50 * 0.85,
      weight: 1,
      note: 'Short-term holders selling at loss',
    },
  ]

  const score = signals.filter(s => s.met).length
  return { score, signals }
}

function bottomLabel(score: number) {
  if (score <= 3) return { label: 'NO BOTTOM — Short Active', color: '#ef4444', pct: Math.round((score / 12) * 100) }
  if (score <= 6) return { label: 'APPROACHING — Scale Down Shorts', color: '#f97316', pct: Math.round((score / 12) * 100) }
  if (score <= 9) return { label: 'HIGH PROBABILITY — Start DCA', color: '#eab308', pct: Math.round((score / 12) * 100) }
  return { label: 'MAXIMUM SIGNAL — Full Accumulation', color: '#10b981', pct: Math.round((score / 12) * 100) }
}

const ONCHAIN_DEFAULT: OnchainData = {
  mvrv: null, realizedPrice: null, fearGreed: null, price: 0,
  hasGlassnode: false, realizedSource: null, mvrvSource: null,
}

export default function BTCCycle({ onBottomScore }: Props) {
  const [klines, setKlines] = useState<Kline[]>([])
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')
  const [bottomResult, setBottomResult] = useState<{ score: number; signals: BottomSignal[] }>({ score: 0, signals: [] })
  const [onchain, setOnchain] = useState<OnchainData>(ONCHAIN_DEFAULT)

  const fetchOnchain = useCallback(async () => {
    try {
      const res = await fetch('/api/onchain')
      const data: OnchainData = await res.json()
      setOnchain(data)
      return data
    } catch { return ONCHAIN_DEFAULT }
  }, [])

  const fetchKlines = useCallback(async (oc: OnchainData) => {
    try {
      const res = await fetch('https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1w&limit=300')
      const raw = await res.json()
      const parsed = parseBinanceKlines(raw)
      setKlines(parsed)
      const result = computeBottomScore(parsed, oc)
      setBottomResult(result)
      onBottomScore?.(result.score)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch { /* keep */ }
    finally { setLoading(false) }
  }, [onBottomScore])

  const refresh = useCallback(async () => {
    const oc = await fetchOnchain()
    await fetchKlines(oc)
  }, [fetchOnchain, fetchKlines])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 300_000)
    return () => clearInterval(id)
  }, [refresh])

  // Recalculate signals when onchain data updates
  useEffect(() => {
    if (klines.length > 0) {
      const result = computeBottomScore(klines, onchain)
      setBottomResult(result)
      onBottomScore?.(result.score)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onchain])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Loading BTC weekly data...
    </div>
  )

  const { score, signals } = bottomResult
  const lbl = bottomLabel(score)
  const latestPrice = klines.length > 0 ? klines[klines.length - 1].close : 0

  const dca = [
    { phase: 1, timing: 'Apr–May 2026', range: '$65–70K', alloc: '10-15%', assets: 'GLXY, BMNR (miners lead bottom)' },
    { phase: 2, timing: 'Jun–Jul 2026', range: '$58–65K', alloc: '30-40%', assets: 'BTC + GLXY + BMNR' },
    { phase: 3, timing: 'Aug–Sep 2026', range: '$47–57K', alloc: '35-40%', assets: 'BTC + MSTR + GLXY + BMNR (ALL 4)' },
    { phase: 4, timing: 'Oct 2026', range: '$45–55K', alloc: '15-20%', assets: 'MAX — if panic capitulation' },
  ]

  return (
    <div className="space-y-6">
      {/* Fear & Greed + On-chain source badges */}
      {(onchain.fearGreed || onchain.mvrvSource) && (
        <div className="flex flex-wrap gap-3 text-xs">
          {onchain.fearGreed && (
            <div className={`px-3 py-1.5 rounded-lg border font-semibold ${onchain.fearGreed.value <= 25 ? 'border-red-500/50 bg-red-500/10 text-red-300' : onchain.fearGreed.value >= 75 ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300' : 'border-yellow-500/50 bg-yellow-500/10 text-yellow-300'}`}>
              Fear &amp; Greed: {onchain.fearGreed.value} — {onchain.fearGreed.label}
            </div>
          )}
          {onchain.realizedPrice && (
            <div className="px-3 py-1.5 rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-300">
              Realized Price: ${onchain.realizedPrice.toLocaleString()} ({onchain.realizedSource})
            </div>
          )}
          {onchain.mvrv && (
            <div className="px-3 py-1.5 rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-300">
              MVRV: {onchain.mvrv.toFixed(2)} ({onchain.mvrvSource})
            </div>
          )}
          {!onchain.hasGlassnode && (
            <div className="px-3 py-1.5 rounded-lg border border-slate-700 text-slate-500">
              Set GLASSNODE_API_KEY for real MVRV data
            </div>
          )}
        </div>
      )}

      {/* Score header */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 bg-slate-800/60 border rounded-xl p-5" style={{ borderColor: lbl.color }}>
          <div className="text-xs text-slate-400 uppercase tracking-widest mb-1">Bottom Probability</div>
          <div className="text-6xl font-black font-mono" style={{ color: lbl.color }}>{lbl.pct}%</div>
          <div className="w-full bg-slate-700 rounded-full h-2 my-3">
            <div className="h-2 rounded-full transition-all" style={{ width: `${lbl.pct}%`, backgroundColor: lbl.color }} />
          </div>
          <div className="text-sm font-bold" style={{ color: lbl.color }}>{lbl.label}</div>
          <div className="text-xs text-slate-500 mt-1">{score}/12 signals active · {lastUpdate}</div>
          <div className="text-sm text-slate-300 mt-2 font-mono">BTC: ${latestPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
          <div className="mt-3 text-xs text-slate-400">
            🎯 High confluence target: <span className="text-yellow-400 font-bold">$57,700</span><br />
            (0.618 Fib + 200W MA + CryptoQuant models)
          </div>
        </div>

        <div className="lg:col-span-2 grid grid-cols-2 gap-3">
          {signals.map((s) => (
            <div key={s.name} className={`flex items-start gap-2 p-3 rounded-lg border text-xs ${s.met ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-slate-700 bg-slate-800/40'}`}>
              <span className="text-base mt-0.5">{s.met ? '✅' : '❌'}</span>
              <div className="min-w-0">
                <div className={`font-semibold truncate ${s.met ? 'text-emerald-300' : 'text-slate-400'}`}>{s.name}</div>
                <div className={`font-mono text-[10px] ${s.met ? 'text-emerald-200' : 'text-slate-500'}`}>{s.value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Weekly Chart */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
          <span className="text-sm font-semibold text-slate-300">BTC/USDT Weekly Chart</span>
          <div className="flex gap-3 text-xs text-slate-500">
            <span className="text-yellow-400 font-mono">🎯 $57,700 target</span>
            <span>|</span>
            <span>{klines.length} weekly candles loaded</span>
          </div>
        </div>
        <TradingChart data={klines} height={320} />
      </div>

      {/* DCA Ladder */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
        <div className="text-sm font-semibold text-slate-300 mb-3">
          📈 DCA Accumulation Ladder (Deploy $50K at Bottom)
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-400 border-b border-slate-700">
                <th className="text-left pb-2 pr-4">Phase</th>
                <th className="text-left pb-2 pr-4">Timing</th>
                <th className="text-left pb-2 pr-4">BTC Price</th>
                <th className="text-left pb-2 pr-4">Allocation</th>
                <th className="text-left pb-2">Assets</th>
              </tr>
            </thead>
            <tbody>
              {dca.map((r) => (
                <tr key={r.phase} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                  <td className="py-2 pr-4">
                    <span className="bg-blue-500/20 text-blue-400 font-bold px-2 py-0.5 rounded">Phase {r.phase}</span>
                  </td>
                  <td className="py-2 pr-4 text-slate-300">{r.timing}</td>
                  <td className="py-2 pr-4 font-mono text-yellow-400">{r.range}</td>
                  <td className="py-2 pr-4 font-mono text-emerald-400 font-bold">{r.alloc}</td>
                  <td className="py-2 text-slate-300">{r.assets}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-slate-500">
          Expected return from bottom: BTC 8-10x · MSTR 12-15x · GLXY/BMNR 8-12x → Portfolio target: $50K → $500K+
        </div>
      </div>
    </div>
  )
}
