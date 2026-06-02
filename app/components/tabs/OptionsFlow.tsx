'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, CartesianGrid, Cell
} from 'recharts'

interface OptionStrike {
  strike: number
  callOI: number
  putOI: number
  callVol: number
  putVol: number
  iv: number
}

interface OptionsApiResponse {
  chain: OptionStrike[]
  spot: number
  isReal: boolean
  source: string
  symbol: string
  timestamp: number
}

// Fallback mock chain when API has no data
function generateMockChain(spot: number, symbol: 'IBIT' | 'MSTR' | 'VIX'): OptionStrike[] {
  const steps = symbol === 'VIX' ? 1 : symbol === 'IBIT' ? 2 : 5
  const range = symbol === 'VIX' ? 15 : symbol === 'IBIT' ? 20 : 50
  const center = Math.round(spot / steps) * steps
  const strikes = []
  for (let i = -range / steps; i <= range / steps; i++) {
    const strike = center + i * steps
    if (strike <= 0) continue
    const dist = Math.abs(strike - spot) / spot
    const atmWeight = Math.exp(-dist * 15)
    const putSkew = strike < spot ? 1.3 : 0.85
    const seed = (strike * 17 + spot * 7) % 100
    strikes.push({
      strike,
      callOI: Math.round((atmWeight * 4000 + seed * 30) * (1 - dist * 0.5)),
      putOI: Math.round((atmWeight * 4500 + seed * 35) * putSkew * (1 - dist * 0.4)),
      callVol: Math.round((atmWeight * 800 + seed * 10) * (1 - dist * 0.6)),
      putVol: Math.round((atmWeight * 950 + seed * 12) * putSkew),
      iv: Math.round((18 + dist * 80 + (strike < spot ? 5 : 0)) * 10) / 10,
    })
  }
  return strikes
}

function calcMaxPain(chain: OptionStrike[]): number {
  let minPain = Infinity, maxPainStrike = 0
  for (const row of chain) {
    let pain = 0
    for (const r2 of chain) {
      if (row.strike > r2.strike) pain += (row.strike - r2.strike) * r2.callOI
      if (row.strike < r2.strike) pain += (r2.strike - row.strike) * r2.putOI
    }
    if (pain < minPain) { minPain = pain; maxPainStrike = row.strike }
  }
  return maxPainStrike
}

const SYMBOLS = ['IBIT', 'MSTR', 'VIX'] as const
type Sym = typeof SYMBOLS[number]

const FALLBACK_SPOT: Record<Sym, number> = { IBIT: 38, MSTR: 315, VIX: 20 }

export default function OptionsFlow() {
  const [activeSymbol, setActiveSymbol] = useState<Sym>('IBIT')
  const [apiData, setApiData] = useState<Record<Sym, OptionsApiResponse | null>>({ IBIT: null, MSTR: null, VIX: null })
  const [vixLevel, setVixLevel] = useState(20.5)
  const [loading, setLoading] = useState(false)
  const [lastUpdate, setLastUpdate] = useState('')

  const fetchOptions = useCallback(async (sym: Sym) => {
    if (apiData[sym]) return // already loaded
    setLoading(true)
    try {
      const res = await fetch(`/api/options?symbol=${sym}`)
      const json: OptionsApiResponse = await res.json()
      setApiData(prev => ({ ...prev, [sym]: json }))
      setLastUpdate(new Date().toLocaleTimeString())
    } catch { /* keep mock */ }
    finally { setLoading(false) }
  }, [apiData])

  useEffect(() => {
    fetchOptions(activeSymbol)
  }, [activeSymbol, fetchOptions])

  useEffect(() => {
    fetch('/api/macro').then(r => r.json()).then(d => {
      if (d.vix?.current) setVixLevel(d.vix.current)
    }).catch(() => {})
  }, [])

  const current = apiData[activeSymbol]
  const spot = current?.spot && current.spot > 0
    ? current.spot
    : activeSymbol === 'VIX' ? vixLevel : FALLBACK_SPOT[activeSymbol]

  const chain: OptionStrike[] = current?.isReal && current.chain.length > 0
    ? current.chain
    : generateMockChain(spot, activeSymbol)

  const isReal = current?.isReal ?? false
  const source = current?.source ?? 'mock'

  const maxPain = calcMaxPain(chain)
  const totalCallOI = chain.reduce((a, r) => a + r.callOI, 0)
  const totalPutOI = chain.reduce((a, r) => a + r.putOI, 0)
  const totalCallVol = chain.reduce((a, r) => a + r.callVol, 0)
  const totalPutVol = chain.reduce((a, r) => a + r.putVol, 0)
  const pcRatioOI = totalPutOI / (totalCallOI || 1)
  const pcRatioVol = totalPutVol / (totalCallVol || 1)

  // Focus view: ±12% from spot
  const nearChain = chain.filter(s => Math.abs(s.strike / spot - 1) <= 0.12)
  const ivSkewData = chain
    .filter(s => Math.abs(s.strike / spot - 1) <= 0.15)
    .map(r => ({ strike: r.strike, iv: r.iv, pct: ((r.strike / spot - 1) * 100).toFixed(1) }))

  const topUnusual = [...chain]
    .filter(r => r.callVol > r.callOI || r.putVol > r.putOI)
    .sort((a, b) => (b.callVol + b.putVol) - (a.callVol + a.putVol))
    .slice(0, 5)

  const pcColor = (ratio: number) => ratio > 1.2 ? '#ef4444' : ratio < 0.8 ? '#10b981' : '#eab308'
  const gexData = nearChain.map(r => ({
    strike: r.strike,
    gex: ((r.callOI - r.putOI) * (r.iv / 100)) | 0,
  }))

  return (
    <div className="space-y-6">
      {/* Symbol selector + source badge */}
      <div className="flex flex-wrap gap-3 items-center">
        {SYMBOLS.map(sym => (
          <button
            key={sym}
            onClick={() => setActiveSymbol(sym)}
            className={`px-4 py-2 rounded-lg text-sm font-bold border transition-all ${activeSymbol === sym ? 'bg-blue-600 border-blue-500 text-white' : 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-500'}`}
          >
            {sym}
          </button>
        ))}
        <div className="flex items-center gap-2 ml-2">
          {loading && <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />}
          <span className={`text-xs px-2 py-1 rounded font-semibold ${isReal ? 'bg-emerald-500/20 text-emerald-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
            {isReal ? `Live · ${source}` : 'Mock data'}
          </span>
          {isReal && <span className="text-xs text-slate-500">{lastUpdate}</span>}
          {!isReal && activeSymbol !== 'VIX' && (
            <span className="text-xs text-slate-500">
              Add POLYGON_API_KEY or Yahoo Finance auto-detected
            </span>
          )}
        </div>
        <div className="text-xs text-slate-500 ml-auto">
          Spot: ${spot.toFixed(activeSymbol === 'IBIT' ? 2 : activeSymbol === 'VIX' ? 2 : 0)}
        </div>
      </div>

      {/* P/C ratios + Max Pain + VIX */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'P/C Ratio (OI)', val: pcRatioOI.toFixed(2), note: pcRatioOI > 1.2 ? 'BEARISH skew' : pcRatioOI < 0.8 ? 'BULLISH skew' : 'Neutral', color: pcColor(pcRatioOI) },
          { label: 'P/C Ratio (Vol)', val: pcRatioVol.toFixed(2), note: pcRatioVol > 1.2 ? 'PUT activity surge' : 'CALL dominated', color: pcColor(pcRatioVol) },
          { label: 'Max Pain', val: `$${maxPain}`, note: `${((maxPain / spot - 1) * 100).toFixed(1)}% from spot`, color: Math.abs(maxPain - spot) / spot < 0.02 ? '#10b981' : '#eab308' },
          { label: 'VIX Level', val: vixLevel.toFixed(2), note: vixLevel < 18 ? 'Low fear' : vixLevel > 30 ? 'High fear — shorts working' : 'Elevated', color: vixLevel > 25 ? '#ef4444' : '#10b981' },
        ].map(({ label, val, note, color }) => (
          <div key={label} className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">{label}</div>
            <div className="text-2xl font-black font-mono" style={{ color }}>{val}</div>
            <div className="text-xs mt-1" style={{ color }}>{note}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* OI Bar Chart */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-3">Open Interest by Strike</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={nearChain} barGap={0}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="strike" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `$${v}`} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} width={45} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f1f5f9', fontSize: 12 }}
                formatter={(v, name) => [(v as number).toLocaleString(), name === 'callOI' ? 'Call OI' : 'Put OI']}
              />
              <ReferenceLine x={spot} stroke="#f1f5f9" strokeDasharray="4 4" label={{ value: 'Spot', fill: '#94a3b8', fontSize: 10 }} />
              <ReferenceLine x={maxPain} stroke="#eab308" strokeDasharray="4 4" label={{ value: 'Max Pain', fill: '#eab308', fontSize: 10 }} />
              <Bar dataKey="callOI" fill="#10b981" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
              <Bar dataKey="putOI" fill="#ef4444" fillOpacity={0.7} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* IV Skew */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-3">IV Skew / Smile</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={ivSkewData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="pct" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `${v}%`} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} width={35} domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f1f5f9', fontSize: 12 }}
                formatter={(v) => [`${(v as number).toFixed(1)}%`, 'IV']}
                labelFormatter={v => `${v}% from spot`}
              />
              <ReferenceLine x="0.0" stroke="#f1f5f9" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="iv" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* GEX Proxy */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-1">Gamma Exposure (GEX) Proxy</div>
          <div className="text-xs text-slate-500 mb-3">+GEX = dealers long gamma (suppresses vol) · -GEX = dealers short gamma (amplifies moves)</div>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={gexData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="strike" tick={{ fill: '#64748b', fontSize: 10 }} tickFormatter={v => `$${v}`} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} width={40} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f1f5f9', fontSize: 12 }} />
              <ReferenceLine y={0} stroke="#475569" />
              <Bar dataKey="gex" radius={[2, 2, 0, 0]}>
                {gexData.map((d, i) => (
                  <Cell key={i} fill={d.gex >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.7} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Unusual Activity */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-300 mb-1">Unusual Activity (Vol &gt; OI)</div>
          <div className="text-xs text-slate-500 mb-3">Potential institutional positioning</div>
          {topUnusual.length > 0 ? (
            <table className="w-full text-xs">
              <thead><tr className="text-slate-400 border-b border-slate-700">
                <th className="text-left pb-2">Strike</th>
                <th className="text-left pb-2">Call Vol</th>
                <th className="text-left pb-2">Call OI</th>
                <th className="text-left pb-2">Put Vol</th>
                <th className="text-left pb-2">IV</th>
              </tr></thead>
              <tbody>
                {topUnusual.map(r => (
                  <tr key={r.strike} className="border-b border-slate-700/40 hover:bg-slate-700/20">
                    <td className="py-1.5 font-mono text-slate-200">${r.strike}</td>
                    <td className={`py-1.5 font-mono ${r.callVol > r.callOI ? 'text-emerald-400 font-bold' : 'text-slate-400'}`}>{r.callVol.toLocaleString()}</td>
                    <td className="py-1.5 font-mono text-slate-400">{r.callOI.toLocaleString()}</td>
                    <td className={`py-1.5 font-mono ${r.putVol > r.putOI ? 'text-red-400 font-bold' : 'text-slate-400'}`}>{r.putVol.toLocaleString()}</td>
                    <td className="py-1.5 font-mono text-blue-400">{r.iv.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-slate-500 text-xs">No unusual activity detected</div>
          )}
          <div className="mt-3 text-xs text-slate-500">
            {isReal
              ? `Data from ${source} · ${new Date(current?.timestamp ?? 0).toLocaleTimeString()}`
              : '⚠️ Simulated. Set POLYGON_API_KEY for live data (free at polygon.io).'}
          </div>
        </div>
      </div>
    </div>
  )
}
