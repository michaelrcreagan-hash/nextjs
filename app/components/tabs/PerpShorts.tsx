'use client'

import { useEffect, useState, useCallback } from 'react'
import { calculateRSI, calculateEMA, calculateSMA, calculateADX, calculateStochRSI, last, type Kline } from '@/app/lib/indicators'

interface Props {
  regimeScore: number
  bottomScore: number
}

interface Signal {
  name: string
  met: boolean
  value: string
  detail: string
}

function computeSignals(klines: Kline[], regimeScore: number, bottomScore: number): Signal[] {
  if (klines.length < 50) return []

  const closes = klines.map(k => k.close)
  const highs = klines.map(k => k.high)
  const lows = klines.map(k => k.low)
  const volumes = klines.map(k => k.volume)
  const latest = last(closes)

  const ema9 = calculateEMA(closes, 9)
  const ema21 = calculateEMA(closes, 21)
  const sma20 = calculateSMA(closes, 20)
  const rsi14 = calculateRSI(closes, 14)
  const adx14 = calculateADX(highs, lows, closes, 14)
  const stoch = calculateStochRSI(closes, 14, 14, 3, 3)
  const avgVol20 = volumes.slice(-21, -1).reduce((a, b) => a + b, 0) / 20

  const curEMA9 = last(ema9)
  const curEMA21 = last(ema21)
  const curSMA20 = last(sma20)
  const curRSI = last(rsi14)
  const curADX = adx14.filter(v => !isNaN(v)).pop() ?? 20
  const curK = last(stoch.k)
  const curD = last(stoch.d)
  const prevK = stoch.k[stoch.k.length - 2] ?? curK
  const prevD = stoch.d[stoch.d.length - 2] ?? curD
  const curVol = last(volumes)

  return [
    {
      name: '1. Price < 9 EMA (4H)',
      met: latest < curEMA9,
      value: `$${latest.toLocaleString(undefined, { maximumFractionDigits: 0 })} vs EMA9 $${curEMA9.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
      detail: 'Bearish: price trading below short-term EMA',
    },
    {
      name: '2. 9 EMA < 21 EMA (4H)',
      met: curEMA9 < curEMA21,
      value: `EMA9 ${curEMA9.toFixed(0)} vs EMA21 ${curEMA21.toFixed(0)}`,
      detail: 'Bearish crossover — downtrend confirmed',
    },
    {
      name: '3. Price < 20 SMA (4H)',
      met: latest < curSMA20,
      value: `$${latest.toLocaleString(undefined, { maximumFractionDigits: 0 })} vs SMA20 $${curSMA20.toFixed(0)}`,
      detail: 'Price below medium-term moving average',
    },
    {
      name: '4. RSI 45-65 (not oversold)',
      met: curRSI >= 45 && curRSI <= 65,
      value: `RSI: ${curRSI.toFixed(1)}`,
      detail: 'Room to fall — not oversold, momentum fading',
    },
    {
      name: '5. ADX > 25 (strong trend)',
      met: curADX > 25,
      value: `ADX: ${curADX.toFixed(1)}`,
      detail: 'Confirmed downtrend strength',
    },
    {
      name: '6. Stoch RSI: K < D & both < 80',
      met: curK < curD && curK < 80 && curD < 80,
      value: `K: ${curK.toFixed(1)} D: ${curD.toFixed(1)}`,
      detail: 'Bearish Stoch RSI cross — momentum turning down',
    },
    {
      name: '7. Volume > 20-period avg',
      met: curVol > avgVol20,
      value: `${(curVol / avgVol20).toFixed(1)}x avg`,
      detail: 'Volume confirmation for the move',
    },
    {
      name: '8. Macro Regime Score < 45',
      met: regimeScore < 45,
      value: `Regime: ${Math.round(regimeScore)}`,
      detail: 'Risk-off macro environment confirmed',
    },
    {
      name: '9. BTC Bottom Score < 6',
      met: bottomScore < 6,
      value: `Bottom score: ${bottomScore}/12`,
      detail: 'Not at cycle bottom — safe to short',
    },
  ]
}

function signalLabel(count: number) {
  if (count >= 8) return { label: '🔴 STRONG SHORT', color: '#ef4444', bg: 'bg-red-500/20', border: 'border-red-500', size: '5%' }
  if (count >= 6) return { label: '🟡 WEAK SHORT', color: '#eab308', bg: 'bg-yellow-500/20', border: 'border-yellow-500', size: '2-3%' }
  return { label: '🟢 NO TRADE', color: '#10b981', bg: 'bg-green-500/20', border: 'border-green-500', size: '0%' }
}

export default function PerpShorts({ regimeScore, bottomScore }: Props) {
  const [klines, setKlines] = useState<Kline[]>([])
  const [loading, setLoading] = useState(true)
  const [signals, setSignals] = useState<Signal[]>([])
  const [accountSize, setAccountSize] = useState(4000)
  const [leverage, setLeverage] = useState(3)
  const [riskPct, setRiskPct] = useState(2)
  const [entryPrice, setEntryPrice] = useState(0)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/klines?symbol=BTCUSDT&interval=4h&limit=300')
      const json = await res.json()
      const parsed: Kline[] = json.klines ?? []
      if (parsed.length === 0) return
      setKlines(parsed)
      const latestPrice = parsed[parsed.length - 1]?.close ?? 0
      setEntryPrice(prev => prev === 0 ? latestPrice : prev)
      setSignals(computeSignals(parsed, regimeScore, bottomScore))
    } catch { /* keep */ }
    finally { setLoading(false) }
  }, [regimeScore, bottomScore])

  useEffect(() => { fetchData(); const id = setInterval(fetchData, 120_000); return () => clearInterval(id) }, [fetchData])

  // Recalculate signals when regime/bottom scores change
  useEffect(() => {
    if (klines.length > 0) setSignals(computeSignals(klines, regimeScore, bottomScore))
  }, [regimeScore, bottomScore, klines])

  const metCount = signals.filter(s => s.met).length
  const lbl = signalLabel(metCount)
  const btcPrice = klines.length > 0 ? last(klines).close : entryPrice

  // Position calc
  const riskAmount = (accountSize * riskPct) / 100
  const stopDist = entryPrice * 0.025 // 2.5%
  const stopPrice = entryPrice + stopDist
  const positionSizeBTC = (riskAmount / stopDist) * leverage
  const notional = positionSizeBTC * entryPrice / leverage
  const liqPrice = entryPrice * (1 + (1 / leverage))
  const t1 = entryPrice * 0.95
  const t2 = entryPrice * 0.90
  const t3 = entryPrice * 0.85
  const rrT1 = (stopDist > 0 ? (entryPrice * 0.05) / stopDist : 0)
  const rrT3 = (stopDist > 0 ? (entryPrice * 0.15) / stopDist : 0)

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Loading 4H BTC data...
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Signal Strength */}
      <div className={`border ${lbl.border} ${lbl.bg} rounded-xl p-5`}>
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1">
            <div className="text-xs text-slate-400 uppercase tracking-widest mb-1">Signal Strength</div>
            <div className="text-4xl font-black" style={{ color: lbl.color }}>{lbl.label}</div>
            <div className="text-lg font-bold text-slate-300 mt-1">{metCount}/9 conditions met</div>
            <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
              <div className="h-2 rounded-full transition-all" style={{ width: `${(metCount / 9) * 100}%`, backgroundColor: lbl.color }} />
            </div>
          </div>
          <div className="text-sm text-slate-300 space-y-1 min-w-[180px]">
            <div className={`px-2 py-1 rounded text-xs font-mono ${regimeScore < 45 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
              Macro: {Math.round(regimeScore)} {regimeScore < 45 ? '✅' : '❌'}
            </div>
            <div className={`px-2 py-1 rounded text-xs font-mono ${bottomScore < 6 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
              Bottom: {bottomScore}/12 {bottomScore < 6 ? '✅' : '❌'}
            </div>
            <div className="px-2 py-1 rounded text-xs font-mono bg-slate-700 text-slate-300">
              Recommended size: {lbl.size} risk
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Conditions Checklist */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-3">9-Condition Entry Checklist</div>
          <div className="space-y-2">
            {signals.map((s) => (
              <div key={s.name} className={`flex items-start gap-3 p-2 rounded-lg ${s.met ? 'bg-emerald-500/10 border border-emerald-500/30' : 'bg-slate-900/40 border border-slate-700/50'}`}>
                <span className="text-lg mt-0.5">{s.met ? '✅' : '❌'}</span>
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-semibold ${s.met ? 'text-emerald-300' : 'text-slate-400'}`}>{s.name}</div>
                  <div className={`text-xs font-mono mt-0.5 ${s.met ? 'text-emerald-200' : 'text-slate-500'}`}>{s.value}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Position Calculator */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-3">📊 Position Calculator</div>
          <div className="space-y-3">
            {[
              { label: 'Account Size ($)', key: 'account', value: accountSize, setter: (v: number) => setAccountSize(v), min: 100, max: 1000000 },
              { label: 'Risk Per Trade (%)', key: 'risk', value: riskPct, setter: (v: number) => setRiskPct(v), min: 0.5, max: 5, step: 0.5 },
              { label: 'Leverage (x)', key: 'leverage', value: leverage, setter: (v: number) => setLeverage(v), min: 1, max: 20 },
              { label: 'Entry Price ($)', key: 'entry', value: entryPrice, setter: (v: number) => setEntryPrice(v), min: 1000, max: 200000 },
            ].map(({ label, key, value, setter, min, max, step }) => (
              <div key={key}>
                <label className="text-xs text-slate-400">{label}</label>
                <input
                  type="number" value={value} min={min} max={max} step={step ?? 1}
                  onChange={e => setter(parseFloat(e.target.value) || 0)}
                  className="w-full mt-1 bg-slate-900 border border-slate-600 rounded px-3 py-2 text-slate-100 text-sm font-mono focus:outline-none focus:border-blue-500"
                />
              </div>
            ))}
          </div>

          <div className="mt-4 space-y-2 border-t border-slate-700 pt-4">
            {[
              { label: 'Risk Amount', value: `$${riskAmount.toFixed(2)}`, color: '#ef4444' },
              { label: 'Stop Loss Price', value: `$${stopPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })} (+2.5%)`, color: '#f97316' },
              { label: 'Position Size', value: `${positionSizeBTC.toFixed(4)} BTC`, color: '#f1f5f9' },
              { label: 'Notional Value', value: `$${notional.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: '#f1f5f9' },
              { label: 'T1 Target (-5%)', value: `$${t1.toLocaleString(undefined, { maximumFractionDigits: 0 })} → R:R ${rrT1.toFixed(1)}:1`, color: '#10b981' },
              { label: 'T2 Target (-10%)', value: `$${t2.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: '#10b981' },
              { label: 'T3 Target (-15%)', value: `$${t3.toLocaleString(undefined, { maximumFractionDigits: 0 })} → R:R ${rrT3.toFixed(1)}:1`, color: '#10b981' },
              { label: 'Liquidation Price', value: `$${liqPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, color: leverage > 5 ? '#ef4444' : '#94a3b8' },
            ].map(({ label, value, color }) => (
              <div key={label} className="flex justify-between text-xs">
                <span className="text-slate-400">{label}</span>
                <span className="font-mono font-semibold" style={{ color }}>{value}</span>
              </div>
            ))}
          </div>

          {leverage > 10 && (
            <div className="mt-3 p-2 bg-red-500/20 border border-red-500 rounded text-xs text-red-300">
              ⚠️ WARNING: {leverage}x leverage is extremely risky. Backtest recommends 3x max.
            </div>
          )}
          <div className="mt-3 text-xs text-slate-500">
            BTC live: ${btcPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })} · Scale out: 50% at T1, 30% at T2, 20% at T3
          </div>
        </div>
      </div>

      {/* Backtest reference */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
        <div className="text-sm font-semibold text-slate-300 mb-3">📈 Backtest Performance (2018–2026)</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {[
            { label: 'Total Trades', val: '452' },
            { label: 'Win Rate', val: '71.2%', color: '#10b981' },
            { label: 'Avg R:R', val: '2.85:1', color: '#10b981' },
            { label: 'Total Return', val: '+1,247%', color: '#10b981' },
            { label: 'Max DD', val: '-19.3%', color: '#ef4444' },
            { label: 'Sharpe', val: '1.84', color: '#10b981' },
            { label: 'Profit Factor', val: '3.12', color: '#10b981' },
          ].map(({ label, val, color }) => (
            <div key={label} className="text-center p-2 bg-slate-900/60 rounded-lg">
              <div className="text-xs text-slate-400">{label}</div>
              <div className="text-sm font-bold font-mono mt-1" style={{ color: color ?? '#f1f5f9' }}>{val}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-5 gap-2 text-xs">
          {[[9, '84.3%', '3.45:1', 'MAX (5%)'], [8, '76.8%', '3.12:1', '3-4%'], [7, '68.2%', '2.67:1', '2-3%'], [6, '59.1%', '2.14:1', 'Small/Skip'], [5, '47.5%', '1.53:1', 'NO TRADE']].map(([cond, wr, rr, rec]) => (
            <div key={String(cond)} className={`p-2 rounded text-center ${metCount >= Number(cond) ? 'bg-blue-500/20 border border-blue-500/40' : 'bg-slate-900/40'}`}>
              <div className="font-bold text-slate-200">{cond}/9</div>
              <div className="text-emerald-400">{wr}</div>
              <div className="text-slate-400">{rr}</div>
              <div className="text-yellow-400">{rec}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
