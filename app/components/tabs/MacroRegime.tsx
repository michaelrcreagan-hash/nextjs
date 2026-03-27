'use client'

import { useEffect, useState, useCallback } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

interface MacroData {
  vix: { current: number; changePercent: number; change: number }
  dxy: { current: number; changePercent: number; change: number }
  tnx: { current: number; changePercent: number; change: number }
  spy: { current: number; changePercent: number; change: number; sma200: number }
  spyVsSMA: number
  regimeScore: number
  netLiquidity: number
  timestamp: number
}

function regimeLabel(score: number) {
  if (score <= 25) return { label: 'EXTREME RISK-OFF', color: '#ef4444', bg: 'bg-red-500/20', border: 'border-red-500' }
  if (score <= 45) return { label: 'RISK-OFF', color: '#f97316', bg: 'bg-orange-500/20', border: 'border-orange-500' }
  if (score <= 60) return { label: 'TRANSITION', color: '#eab308', bg: 'bg-yellow-500/20', border: 'border-yellow-500' }
  if (score <= 80) return { label: 'RISK-ON', color: '#22c55e', bg: 'bg-green-500/20', border: 'border-green-500' }
  return { label: 'EXTREME RISK-ON', color: '#4ade80', bg: 'bg-emerald-400/20', border: 'border-emerald-400' }
}

function Indicator({ label, value, change, changeLabel, good, bad }: {
  label: string; value: string; change: number; changeLabel: string; good: (c: number) => boolean; bad: (c: number) => boolean
}) {
  const isGood = good(change)
  const isBad = bad(change)
  const color = isGood ? '#10b981' : isBad ? '#ef4444' : '#94a3b8'
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4">
      <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-bold text-slate-100 font-mono">{value}</div>
      <div className="text-sm mt-1 font-mono" style={{ color }}>
        {change > 0 ? '+' : ''}{changeLabel}
      </div>
    </div>
  )
}

export default function MacroRegime() {
  const [data, setData] = useState<MacroData | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/macro')
      const json = await res.json()
      setData(json)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch { /* use cached */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, 60_000)
    return () => clearInterval(id)
  }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Loading macro data...
    </div>
  )

  if (!data) return <div className="text-slate-400 text-center p-8">Failed to load macro data</div>

  const regime = regimeLabel(data.regimeScore)
  const action = data.regimeScore <= 45
    ? '🔴 SHORT BIAS ACTIVE — Macro confirms risk-off environment. Proceed to BTC Cycle & Short Signal tabs.'
    : data.regimeScore <= 60
    ? '🟡 TRANSITION — Reduce short exposure. Monitor for direction change.'
    : '🟢 RISK-ON — Close shorts. Consider long bias or neutral positioning.'

  const radarData = [
    { subject: 'VIX', value: Math.max(0, Math.min(100, 100 - (data.vix.current - 12) * 2)) },
    { subject: 'DXY', value: Math.max(0, Math.min(100, 50 - data.dxy.changePercent * 10)) },
    { subject: '10Y', value: Math.max(0, Math.min(100, 50 - data.tnx.changePercent * 5)) },
    { subject: 'SPY/200', value: Math.max(0, Math.min(100, 50 + data.spyVsSMA * 3)) },
    { subject: 'Liquidity', value: Math.max(0, Math.min(100, 50 + data.netLiquidity * 5)) },
  ]

  const scoreBar = (score: number) => (
    <div className="w-full bg-slate-700 rounded-full h-3 mt-2">
      <div
        className="h-3 rounded-full transition-all duration-700"
        style={{ width: `${score}%`, backgroundColor: regime.color }}
      />
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header Score */}
      <div className={`border ${regime.border} ${regime.bg} rounded-xl p-6 flex flex-col md:flex-row md:items-center gap-6`}>
        <div className="flex-1">
          <div className="text-sm text-slate-400 uppercase tracking-widest mb-1">Macro Regime Score</div>
          <div className="flex items-baseline gap-4">
            <span className="text-7xl font-black font-mono" style={{ color: regime.color }}>{Math.round(data.regimeScore)}</span>
            <span className="text-2xl font-bold" style={{ color: regime.color }}>/100</span>
          </div>
          {scoreBar(data.regimeScore)}
          <div className="mt-3 text-lg font-bold" style={{ color: regime.color }}>{regime.label}</div>
          <div className="text-xs text-slate-400 mt-1">Updated: {lastUpdate}</div>
        </div>
        <div className="flex-1 text-sm text-slate-300 bg-slate-800/60 rounded-lg p-4 border border-slate-700">
          <div className="font-semibold text-slate-200 mb-2">📋 Recommendation</div>
          {action}
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div>Score 0-25 → MAX SHORT aggression</div>
            <div>Score 26-45 → Active shorting</div>
            <div>Score 46-60 → Reduce shorts</div>
            <div>Score 61+ → Close shorts / go long</div>
          </div>
        </div>
      </div>

      {/* Indicator Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Indicator
          label="VIX (Fear Gauge)"
          value={data.vix.current.toFixed(2)}
          change={data.vix.changePercent}
          changeLabel={`${data.vix.changePercent > 0 ? '+' : ''}${data.vix.changePercent.toFixed(2)}%`}
          good={c => c < 0}
          bad={c => c > 0}
        />
        <Indicator
          label="DXY (Dollar Index)"
          value={data.dxy.current.toFixed(2)}
          change={data.dxy.changePercent}
          changeLabel={`${data.dxy.changePercent > 0 ? '+' : ''}${data.dxy.changePercent.toFixed(2)}%`}
          good={c => c < 0}
          bad={c => c > 0}
        />
        <Indicator
          label="10Y Treasury Yield"
          value={`${data.tnx.current.toFixed(2)}%`}
          change={data.tnx.changePercent}
          changeLabel={`${data.tnx.changePercent > 0 ? '+' : ''}${data.tnx.changePercent.toFixed(2)}%`}
          good={c => c < 0}
          bad={c => c > 0}
        />
        <div className="bg-slate-800/60 border border-slate-700 rounded-lg p-4">
          <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">SPY vs 200D SMA</div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {data.spy.current.toFixed(0)}
          </div>
          <div className="text-sm mt-1 font-mono" style={{ color: data.spyVsSMA > 0 ? '#10b981' : '#ef4444' }}>
            {data.spyVsSMA > 0 ? '+' : ''}{data.spyVsSMA.toFixed(1)}% vs SMA
          </div>
          <div className="text-xs text-slate-500 mt-1">200D SMA: {data.spy.sma200.toFixed(0)}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Radar Chart */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-3">Regime Components (higher = bullish)</div>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#334155" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 12 }} />
              <Radar dataKey="value" stroke={regime.color} fill={regime.color} fillOpacity={0.2} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f1f5f9' }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Score breakdown */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4 space-y-3">
          <div className="text-sm font-semibold text-slate-300 mb-3">Component Scores</div>
          {[
            { label: 'VIX Level', val: data.vix.current < 18 ? 'BULLISH' : data.vix.current > 28 ? 'BEARISH' : 'NEUTRAL', sub: `${data.vix.current.toFixed(1)} (${data.vix.current < 18 ? 'low fear' : data.vix.current > 35 ? 'extreme fear' : 'elevated'})` },
            { label: 'Dollar (DXY)', val: data.dxy.changePercent < -0.3 ? 'BULLISH' : data.dxy.changePercent > 0.3 ? 'BEARISH' : 'NEUTRAL', sub: `${data.dxy.changePercent > 0 ? '+' : ''}${data.dxy.changePercent.toFixed(2)}% today` },
            { label: '10Y Yields', val: data.tnx.changePercent < -1 ? 'BULLISH' : data.tnx.changePercent > 1 ? 'BEARISH' : 'NEUTRAL', sub: `${data.tnx.current.toFixed(2)}% (${data.tnx.changePercent > 0 ? '+' : ''}${data.tnx.changePercent.toFixed(2)}%)` },
            { label: 'Equity Breadth', val: data.spyVsSMA > 2 ? 'BULLISH' : data.spyVsSMA < -2 ? 'BEARISH' : 'NEUTRAL', sub: `SPY ${data.spyVsSMA > 0 ? '+' : ''}${data.spyVsSMA.toFixed(1)}% above 200D MA` },
          ].map(({ label, val, sub }) => (
            <div key={label} className="flex items-center justify-between">
              <div>
                <div className="text-sm text-slate-300">{label}</div>
                <div className="text-xs text-slate-500">{sub}</div>
              </div>
              <span className={`text-xs font-bold px-2 py-1 rounded ${val === 'BULLISH' ? 'bg-emerald-500/20 text-emerald-400' : val === 'BEARISH' ? 'bg-red-500/20 text-red-400' : 'bg-slate-600 text-slate-400'}`}>
                {val}
              </span>
            </div>
          ))}
          <div className="mt-2 pt-2 border-t border-slate-700 text-xs text-slate-500">
            Net Fed Liquidity: <span className={data.netLiquidity < 0 ? 'text-red-400' : 'text-emerald-400'}>
              {data.netLiquidity > 0 ? '+' : ''}{data.netLiquidity.toFixed(1)}% (Fed BS - TGA - RRP proxy)
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
