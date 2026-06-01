'use client'

import { useEffect, useState, useCallback, Fragment } from 'react'
import { actionFor, type BottleneckPhase } from '@/app/lib/aiStocks'

interface Plan { entry: number; stop: number; tp1: number; tp2: number; tp3: number; rr1: number }
interface Opt { structure: string; legs: string; dte: string; rationale: string }
interface Row {
  symbol: string; name: string; category: string; subTheme: string; phases?: BottleneckPhase[]
  ok: boolean; price: number; changePct: number
  rsi?: number; adx?: number; plusDI?: number; minusDI?: number; rvol?: number; atr?: number
  m30?: number; m60?: number; m90?: number
  fundamental?: number; technical?: number; techNotes?: string[]; rank?: number
  fin?: { guidanceQuality: number; epsRevision: number; beatAndRaise: number }
  plan?: Plan; options?: Opt; daysToEarnings?: number | null; catalystSoon?: boolean
}
interface PhaseScore {
  id: BottleneckPhase; label: string; short: string; emoji: string; order: number
  thesis: string; keywords: string[]; momentum: number; members: number
}
interface Data { rows: Row[]; okCount: number; phaseScores: PhaseScore[]; activePhase: BottleneckPhase; timestamp: number }

const fmt = (n: number, d = 2) => n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d })

export default function AIStocks() {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [phaseFilter, setPhaseFilter] = useState<BottleneckPhase | 'all'>('all')
  const [updated, setUpdated] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch('/api/stocks')
      const j = await r.json()
      setData(j); setUpdated(new Date().toLocaleTimeString())
    } catch { /* keep */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchData(); const id = setInterval(fetchData, 90_000); return () => clearInterval(id) }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Loading AI watchlist & computing setups...
    </div>
  )
  if (!data) return <div className="text-slate-400 text-center p-8">Failed to load AI stocks data</div>

  const ranked = [...data.rows].filter(r => r.ok)
    .filter(r => phaseFilter === 'all' || r.phases?.includes(phaseFilter))
    .sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0))
  const active = data.phaseScores.find(p => p.id === data.activePhase)
  const topSetups = ranked.slice(0, 3)

  return (
    <div className="space-y-6">
      {/* Layer 2 — Bottleneck Rotation */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="text-sm font-semibold text-slate-200">⚙️ Layer 2 — Hyperscaler CapEx Bottleneck Rotation</div>
          <div className="text-xs text-slate-500">Active constraint inferred from basket momentum · {updated}</div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {data.phaseScores.sort((a, b) => a.order - b.order).map(p => {
            const isActive = p.id === data.activePhase
            return (
              <button key={p.id} onClick={() => setPhaseFilter(phaseFilter === p.id ? 'all' : p.id)}
                className={`text-left p-3 rounded-lg border transition-all ${isActive ? 'border-blue-500 bg-blue-500/15' : phaseFilter === p.id ? 'border-emerald-500 bg-emerald-500/10' : 'border-slate-700 bg-slate-900/40 hover:bg-slate-800'}`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-200">{p.emoji} {p.short}</span>
                  <span className="text-[10px] text-slate-500">#{p.order}</span>
                </div>
                <div className={`text-sm font-mono font-bold mt-1 ${p.momentum >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {p.momentum >= 0 ? '+' : ''}{p.momentum.toFixed(1)}%
                </div>
                <div className="text-[10px] text-slate-500">{p.members} names · 1M</div>
                {isActive && <div className="text-[10px] text-blue-400 font-bold mt-1">● LIVE LEADER</div>}
              </button>
            )
          })}
        </div>
        {active && (
          <div className="mt-3 text-xs text-slate-300 bg-slate-900/50 border border-slate-700 rounded-lg p-3">
            <span className="font-bold text-blue-400">{active.emoji} {active.label}:</span> {active.thesis}
            <div className="mt-1.5 text-slate-500">Transcript tells: {active.keywords.slice(0, 8).map(k => `“${k}”`).join(' · ')}</div>
          </div>
        )}
      </div>

      {/* Top setups by composite */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {topSetups.map((r, i) => {
          const a = actionFor(r.rank ?? 0)
          return (
            <div key={r.symbol} className="bg-slate-800/60 border border-slate-700 rounded-xl p-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-lg font-black text-slate-100">#{i + 1} {r.symbol}</span>
                  <span className="text-xs text-slate-500 ml-2">{r.subTheme}</span>
                </div>
                <span className="text-xs font-bold px-2 py-0.5 rounded" style={{ backgroundColor: `${a.color}20`, color: a.color }}>{a.label}</span>
              </div>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-xl font-mono font-bold text-slate-100">${fmt(r.price)}</span>
                <span className={`text-sm font-mono ${(r.changePct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {(r.changePct ?? 0) >= 0 ? '+' : ''}{fmt(r.changePct ?? 0)}%
                </span>
              </div>
              <div className="flex gap-3 mt-2 text-xs">
                <span className="text-slate-400">Composite <b className="text-slate-100 font-mono">{r.rank}</b></span>
                <span className="text-slate-400">Fund <b className="text-slate-100 font-mono">{r.fundamental}</b></span>
                <span className="text-slate-400">Tech <b className="text-slate-100 font-mono">{r.technical}</b></span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Layers 1/3/4 — Watchlist table */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-slate-700 flex-wrap gap-2">
          <div className="text-sm font-semibold text-slate-200">🎯 Layer 1/3/4 — Watchlist · Fundamental + Technical Composite</div>
          <div className="flex items-center gap-2">
            {phaseFilter !== 'all' && (
              <button onClick={() => setPhaseFilter('all')} className="text-xs text-blue-400 hover:underline">clear phase filter</button>
            )}
            <span className="text-xs text-slate-500">{ranked.length} names</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr className="text-left">
                <th className="p-2 font-medium">Ticker</th>
                <th className="p-2 font-medium text-right">Price</th>
                <th className="p-2 font-medium text-right">24h</th>
                <th className="p-2 font-medium text-right hidden md:table-cell">ADX</th>
                <th className="p-2 font-medium text-right hidden md:table-cell">DMI</th>
                <th className="p-2 font-medium text-right hidden lg:table-cell">RSI</th>
                <th className="p-2 font-medium text-right hidden lg:table-cell">RVOL</th>
                <th className="p-2 font-medium text-right">Fund</th>
                <th className="p-2 font-medium text-right">Tech</th>
                <th className="p-2 font-medium text-right">Comp</th>
                <th className="p-2 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(r => {
                const a = actionFor(r.rank ?? 0)
                const open = expanded === r.symbol
                const bull = (r.plusDI ?? 0) > (r.minusDI ?? 0)
                return (
                  <Fragment key={r.symbol}>
                    <tr onClick={() => setExpanded(open ? null : r.symbol)}
                      className={`border-b border-slate-800 cursor-pointer hover:bg-slate-800/60 ${open ? 'bg-slate-800/60' : ''}`}>
                      <td className="p-2">
                        <div className="font-bold text-slate-100">{r.symbol} {r.catalystSoon && <span title="Earnings ≤10d">📅</span>}</div>
                        <div className="text-[10px] text-slate-500">{r.category}</div>
                      </td>
                      <td className="p-2 text-right font-mono text-slate-200">${fmt(r.price)}</td>
                      <td className={`p-2 text-right font-mono ${(r.changePct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{(r.changePct ?? 0) >= 0 ? '+' : ''}{fmt(r.changePct ?? 0)}%</td>
                      <td className="p-2 text-right font-mono hidden md:table-cell text-slate-300">{fmt(r.adx ?? 0, 0)}</td>
                      <td className={`p-2 text-right font-mono hidden md:table-cell ${bull ? 'text-emerald-400' : 'text-red-400'}`}>{bull ? '▲' : '▼'}</td>
                      <td className="p-2 text-right font-mono hidden lg:table-cell text-slate-300">{fmt(r.rsi ?? 0, 0)}</td>
                      <td className={`p-2 text-right font-mono hidden lg:table-cell ${(r.rvol ?? 0) >= 1.5 ? 'text-emerald-400' : 'text-slate-300'}`}>{fmt(r.rvol ?? 0, 1)}×</td>
                      <td className="p-2 text-right font-mono text-slate-300">{r.fundamental}</td>
                      <td className="p-2 text-right font-mono text-slate-300">{r.technical}</td>
                      <td className="p-2 text-right font-mono font-bold text-slate-100">{r.rank}</td>
                      <td className="p-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap" style={{ backgroundColor: `${a.color}20`, color: a.color }}>{a.label}</span></td>
                    </tr>
                    {open && r.plan && r.options && (
                      <tr className="bg-slate-900/60 border-b border-slate-800">
                        <td colSpan={11} className="p-3">
                          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                            {/* Trade plan */}
                            <div>
                              <div className="text-xs font-semibold text-slate-300 mb-2">📐 Trade Plan (ATR-anchored)</div>
                              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
                                <span className="text-slate-500">Entry</span><span className="text-slate-100 text-right">${fmt(r.plan.entry)}</span>
                                <span className="text-slate-500">Stop</span><span className="text-red-400 text-right">${fmt(r.plan.stop)}</span>
                                <span className="text-slate-500">TP1 (R:R {r.plan.rr1})</span><span className="text-emerald-400 text-right">${fmt(r.plan.tp1)}</span>
                                <span className="text-slate-500">TP2</span><span className="text-emerald-400 text-right">${fmt(r.plan.tp2)}</span>
                                <span className="text-slate-500">TP3</span><span className="text-emerald-400 text-right">${fmt(r.plan.tp3)}</span>
                                <span className="text-slate-500">ATR(14)</span><span className="text-slate-300 text-right">${fmt(r.atr ?? 0)}</span>
                              </div>
                            </div>
                            {/* Options */}
                            <div>
                              <div className="text-xs font-semibold text-slate-300 mb-2">🎟️ Options Play</div>
                              <div className="text-xs space-y-1">
                                <div><span className="text-slate-500">Structure: </span><span className="text-blue-400 font-semibold">{r.options.structure}</span></div>
                                <div><span className="text-slate-500">Legs: </span><span className="text-slate-100 font-mono">{r.options.legs}</span></div>
                                <div><span className="text-slate-500">DTE: </span><span className="text-slate-100">{r.options.dte}</span></div>
                                <div className="text-slate-400">{r.options.rationale}</div>
                              </div>
                            </div>
                            {/* Fundamentals + tech notes */}
                            <div>
                              <div className="text-xs font-semibold text-slate-300 mb-2">🧪 Layer 3 Screen + Signals</div>
                              <div className="grid grid-cols-3 gap-2 text-[11px] mb-2">
                                <div className="bg-slate-800 rounded p-1.5 text-center"><div className="text-slate-500">Guide</div><div className="font-mono text-slate-200">{r.fin?.guidanceQuality}</div></div>
                                <div className="bg-slate-800 rounded p-1.5 text-center"><div className="text-slate-500">EPS Rev</div><div className="font-mono text-slate-200">{r.fin?.epsRevision}</div></div>
                                <div className="bg-slate-800 rounded p-1.5 text-center"><div className="text-slate-500">B&amp;R</div><div className="font-mono text-slate-200">{r.fin?.beatAndRaise}</div></div>
                              </div>
                              <ul className="text-[11px] text-slate-400 space-y-0.5">
                                {(r.techNotes ?? []).map((n, i) => <li key={i}>• {n}</li>)}
                                <li className="text-slate-500">30/60/90d: {fmt(r.m30 ?? 0, 0)}% / {fmt(r.m60 ?? 0, 0)}% / {fmt(r.m90 ?? 0, 0)}%</li>
                                {r.daysToEarnings != null && r.daysToEarnings >= 0 && <li className="text-amber-400">📅 Earnings in {r.daysToEarnings}d</li>}
                              </ul>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-[11px] text-slate-600 bg-slate-900/40 border border-slate-800 rounded-lg p-3">
        <b>Data notes:</b> Prices, ADX/DMI/RSI/RVOL/ATR and 30/60/90-day momentum are computed live from daily candles.
        EPS-revision momentum, guidance quality and beat-and-raise are proxied from price/EPS trend where a paid estimates feed
        (SPG as-of-date) is not connected — wire those endpoints into <code>/api/stocks</code> to upgrade Layer 3 to exact revisions.
        Bottleneck phase is inferred from live basket momentum; pair with the transcript keyword tells above.
      </div>
    </div>
  )
}
