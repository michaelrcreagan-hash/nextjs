'use client'

import { useEffect, useState, useCallback, Fragment } from 'react'

interface Cond { id: string; label: string; max: number; score: number; detail: string }
interface Coin {
  symbol: string; name: string; price: number; change24h: number; change7d: number
  marketCap: number; volume: number; funding: number | null; narrative: string
  conds: Cond[]; score: number; redFlags: string[]; athChange: number
}
interface Data { coins: Coin[]; btcChange: number; source?: string; timestamp: number; error?: string }

function band(score: number) {
  if (score >= 10.5) return { label: 'MAX CONVICTION', color: '#10b981', action: 'Pilot-load 60% today' }
  if (score >= 8.5) return { label: 'HIGH PROBABILITY', color: '#22c55e', action: 'Pilot 40% or wait 48h' }
  if (score >= 6.5) return { label: 'LOADING / TRIGGER', color: '#eab308', action: 'Trigger entry only' }
  if (score >= 5) return { label: 'MONITOR', color: '#f97316', action: 'Watch daily' }
  return { label: 'NO SETUP', color: '#64748b', action: 'Skip' }
}
const usd = (n: number) => n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M` : `$${n.toFixed(0)}`
const px = (n: number) => n >= 1 ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : `$${n.toPrecision(3)}`

export default function AltcoinSqueeze() {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [updated, setUpdated] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const r = await fetch('/api/altcoins'); const j = await r.json()
      setData(j); setUpdated(new Date().toLocaleTimeString())
    } catch { /* keep */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchData(); const id = setInterval(fetchData, 120_000); return () => clearInterval(id) }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Scanning altcoin universe for short-squeeze setups...
    </div>
  )
  if (!data || data.coins.length === 0) return (
    <div className="text-slate-400 text-center p-8">
      No altcoin data available{data?.error ? ` (${data.error})` : ''}. Source: CoinGecko markets + Binance funding.
    </div>
  )

  const qualified = data.coins.filter(c => c.score >= 6.5 && c.redFlags.length === 0)

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Scanned', val: String(data.coins.length), color: '#f1f5f9' },
          { label: 'Qualified (≥6.5)', val: String(qualified.length), color: '#22c55e' },
          { label: 'BTC 24h', val: `${data.btcChange >= 0 ? '+' : ''}${data.btcChange.toFixed(1)}%`, color: data.btcChange >= 0 ? '#10b981' : '#ef4444' },
          { label: 'Top score', val: data.coins[0]?.score.toFixed(1) ?? '—', color: '#3b82f6' },
        ].map(s => (
          <div key={s.label} className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 text-center">
            <div className="text-xs text-slate-500">{s.label}</div>
            <div className="text-2xl font-black font-mono mt-1" style={{ color: s.color }}>{s.val}</div>
          </div>
        ))}
      </div>

      {data.btcChange < -5 && (
        <div className="bg-red-500/15 border border-red-500 rounded-lg p-3 text-sm text-red-300">
          🚨 BTC down &gt;5% — squeeze entries HALTED per V3 rules. All scores capped at disqualified band.
        </div>
      )}

      {/* Board */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-slate-700">
          <div className="text-sm font-semibold text-slate-200">🪙 APEX-Squeeze V3 — 12-Condition Score (max 12.5)</div>
          <div className="text-xs text-slate-500">{updated}</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr className="text-left">
                <th className="p-2">Token</th>
                <th className="p-2 text-right">Price</th>
                <th className="p-2 text-right">24h</th>
                <th className="p-2 text-right hidden sm:table-cell">7d</th>
                <th className="p-2 text-right hidden md:table-cell">Funding</th>
                <th className="p-2 text-right hidden lg:table-cell">MCap</th>
                <th className="p-2 hidden lg:table-cell">Narrative</th>
                <th className="p-2 text-right">Score</th>
                <th className="p-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {data.coins.map(c => {
                const b = band(c.score)
                const open = expanded === c.symbol
                return (
                  <Fragment key={c.symbol}>
                    <tr onClick={() => setExpanded(open ? null : c.symbol)}
                      className={`border-b border-slate-800 cursor-pointer hover:bg-slate-800/60 ${open ? 'bg-slate-800/60' : ''}`}>
                      <td className="p-2"><span className="font-bold text-slate-100">{c.symbol}</span>{c.redFlags.length > 0 && <span title={c.redFlags.join(', ')}> 🚩</span>}</td>
                      <td className="p-2 text-right font-mono text-slate-200">{px(c.price)}</td>
                      <td className={`p-2 text-right font-mono ${c.change24h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.change24h >= 0 ? '+' : ''}{c.change24h.toFixed(1)}%</td>
                      <td className={`p-2 text-right font-mono hidden sm:table-cell ${c.change7d >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.change7d >= 0 ? '+' : ''}{c.change7d.toFixed(1)}%</td>
                      <td className={`p-2 text-right font-mono hidden md:table-cell ${c.funding == null ? 'text-slate-600' : c.funding < 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.funding == null ? '—' : `${(c.funding * 100).toFixed(3)}%`}</td>
                      <td className="p-2 text-right font-mono hidden lg:table-cell text-slate-300">{usd(c.marketCap)}</td>
                      <td className="p-2 hidden lg:table-cell text-slate-400">{c.narrative}</td>
                      <td className="p-2 text-right"><span className="font-mono font-bold" style={{ color: b.color }}>{c.score.toFixed(1)}</span></td>
                      <td className="p-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap" style={{ backgroundColor: `${b.color}20`, color: b.color }}>{b.label}</span></td>
                    </tr>
                    {open && (
                      <tr className="bg-slate-900/60 border-b border-slate-800">
                        <td colSpan={9} className="p-3">
                          <div className="text-xs text-slate-400 mb-2">{b.action} · Liq-cluster top = T1 target · stop below long-liq cluster</div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
                            {c.conds.map(cn => (
                              <div key={cn.id} className="bg-slate-800 rounded p-1.5 flex items-center justify-between">
                                <div>
                                  <div className="text-[11px] text-slate-300">{cn.id} {cn.label}</div>
                                  <div className="text-[10px] text-slate-500">{cn.detail}</div>
                                </div>
                                <div className="text-[11px] font-mono font-bold" style={{ color: cn.score > 0 ? '#22c55e' : '#64748b' }}>{cn.score}/{cn.max}</div>
                              </div>
                            ))}
                          </div>
                          {c.redFlags.length > 0 && (
                            <div className="mt-2 text-[11px] text-red-300">🚩 Red flags: {c.redFlags.join(' · ')}</div>
                          )}
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
        <b>Method:</b> CoinGecko drives price/mcap/vol/ATH.{' '}
        {data.source === 'coinglass'
          ? 'CoinGlass (key set) drives C1 funding, C2 real OI divergence and C7 24h short-liquidation magnitude — aggregated cross-exchange.'
          : 'Binance perps drive C1 funding (fallback); C2 and C7 use vol/price proxies. Set COINGLASS_API_KEY to upgrade C2 to real OI divergence and C7 to live short-liquidation magnitude.'}
        {' '}C6 catalysts come from the static calendar; C10 unlock needs a manual TokenUnlocks check before sizing.
      </div>
    </div>
  )
}
