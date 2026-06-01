'use client'

import { useEffect, useState, useCallback } from 'react'

interface Coin {
  symbol: string; raw: string; price: number; change24h: number
  funding: number; fundingApr: number; oiUsd: number; volUsd: number; nextFunding: number
}
interface Agg { totalOi: number; avgFunding: number; negFundingCount: number; mostNegative: string[] }
interface Data { coins: Coin[]; aggregate: Agg | null; timestamp: number; error?: string }

const usd = (n: number) => n >= 1e9 ? `$${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M` : `$${n.toFixed(0)}`
const px = (n: number) => n >= 1 ? `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : `$${n.toPrecision(3)}`

export default function CryptoDerivs() {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [updated, setUpdated] = useState('')

  const fetchData = useCallback(async () => {
    try { const r = await fetch('/api/derivs'); const j = await r.json(); setData(j); setUpdated(new Date().toLocaleTimeString()) }
    catch { /* keep */ } finally { setLoading(false) }
  }, [])
  useEffect(() => { fetchData(); const id = setInterval(fetchData, 45_000); return () => clearInterval(id) }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Loading perps funding &amp; open interest...
    </div>
  )
  if (!data || data.coins.length === 0) return (
    <div className="text-slate-400 text-center p-8">Derivatives feed unavailable{data?.error ? ` (${data.error})` : ''}. Source: Binance Futures.</div>
  )

  const a = data.aggregate
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-slate-400">⚡ Perps & Futures · funding + open interest (Coinglass-style)</div>
        <a href="https://www.coinglass.com/LiquidationData" target="_blank" rel="noreferrer" className="text-xs text-blue-400 hover:underline">↗ CoinGlass liquidation heatmap</a>
      </div>

      {a && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Tracked OI', val: usd(a.totalOi), color: '#3b82f6' },
            { label: 'Avg funding /8h', val: `${(a.avgFunding * 100).toFixed(4)}%`, color: a.avgFunding < 0 ? '#10b981' : '#ef4444' },
            { label: 'Negative funding', val: `${a.negFundingCount} coins`, color: '#22c55e' },
            { label: 'Most negative', val: a.mostNegative.slice(0, 3).join(' '), color: '#eab308' },
          ].map(s => (
            <div key={s.label} className="bg-slate-800/60 border border-slate-700 rounded-lg p-3 text-center">
              <div className="text-xs text-slate-500">{s.label}</div>
              <div className="text-lg font-black font-mono mt-1" style={{ color: s.color }}>{s.val}</div>
            </div>
          ))}
        </div>
      )}

      <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-slate-700">
          <div className="text-sm font-semibold text-slate-200">Funding &amp; Open Interest — major perps</div>
          <div className="text-xs text-slate-500">{updated} · negative funding = shorts pay longs (squeeze fuel)</div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr className="text-left">
                <th className="p-2">Symbol</th>
                <th className="p-2 text-right">Price</th>
                <th className="p-2 text-right">24h</th>
                <th className="p-2 text-right">Funding /8h</th>
                <th className="p-2 text-right hidden sm:table-cell">Funding APR</th>
                <th className="p-2 text-right">Open Interest</th>
                <th className="p-2 text-right hidden md:table-cell">24h Vol</th>
              </tr>
            </thead>
            <tbody>
              {data.coins.map(c => (
                <tr key={c.raw} className="border-b border-slate-800 hover:bg-slate-800/40">
                  <td className="p-2 font-bold text-slate-100">{c.symbol}</td>
                  <td className="p-2 text-right font-mono text-slate-200">{px(c.price)}</td>
                  <td className={`p-2 text-right font-mono ${c.change24h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.change24h >= 0 ? '+' : ''}{c.change24h.toFixed(2)}%</td>
                  <td className={`p-2 text-right font-mono ${c.funding < 0 ? 'text-emerald-400' : c.funding > 0.0004 ? 'text-red-400' : 'text-slate-300'}`}>{(c.funding * 100).toFixed(4)}%</td>
                  <td className={`p-2 text-right font-mono hidden sm:table-cell ${c.fundingApr < 0 ? 'text-emerald-400' : 'text-slate-400'}`}>{c.fundingApr.toFixed(1)}%</td>
                  <td className="p-2 text-right font-mono text-slate-200">{usd(c.oiUsd)}</td>
                  <td className="p-2 text-right font-mono hidden md:table-cell text-slate-400">{usd(c.volUsd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-[11px] text-slate-600 bg-slate-900/40 border border-slate-800 rounded-lg p-3">
        Funding &amp; OI are live from Binance USDⓈ-M futures. For liquidation clusters / heatmaps (CoinGlass requires an API key),
        use the CoinGlass link above and feed cluster levels into the Altcoin Squeeze T1 targets.
      </div>
    </div>
  )
}
