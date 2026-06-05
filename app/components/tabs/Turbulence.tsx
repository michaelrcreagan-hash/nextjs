'use client'

import { useEffect, useState, useCallback, Fragment } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'

interface PredStat { name: string; lag: number; corr: number }
interface Asset {
  asset: string; ok: boolean
  currentVol?: number; forecast?: number | null; regime?: string
  r2?: number | null; oosCorr?: number | null; bestCorr?: number
  topLags?: PredStat[]; predictors?: PredStat[]; n?: number; asOf?: string
}
interface Data {
  assets: Asset[]; elevated: number; predictorsUsed: string[]; fredEnabled: boolean
  config: { window: number; horizon: number; maxLag: number; target: string }
  timestamp: number; error?: string
}

const sigColor = (r?: string) => (r === 'HIGH TURBULENCE' ? '#ef4444' : '#22c55e')

export default function Turbulence() {
  const [data, setData] = useState<Data | null>(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [updated, setUpdated] = useState('')

  const fetchData = useCallback(async () => {
    try { const r = await fetch('/api/turbulence'); const j = await r.json(); setData(j); setUpdated(new Date().toLocaleTimeString()) }
    catch { /* keep */ } finally { setLoading(false) }
  }, [])
  useEffect(() => { fetchData(); const id = setInterval(fetchData, 300_000); return () => clearInterval(id) }, [fetchData])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">
      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
      Fitting turbulence models (optimal-lag OLS)...
    </div>
  )
  const ok = (data?.assets ?? []).filter(a => a.ok)
  if (!data || ok.length === 0) return (
    <div className="text-slate-400 text-center p-8">Turbulence model unavailable{data?.error ? ` (${data.error})` : ''}. Needs daily price history (Yahoo) + BTC.</div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className={`border rounded-xl p-5 ${data.elevated > 0 ? 'border-red-500/50 bg-red-500/10' : 'border-emerald-500/40 bg-emerald-500/10'}`}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="text-sm text-slate-400 uppercase tracking-widest">Turbulence Regime</div>
            <div className="text-3xl font-black mt-1" style={{ color: data.elevated > 0 ? '#ef4444' : '#22c55e' }}>
              {data.elevated > 0 ? `⚠️ ${data.elevated} / ${ok.length} ELEVATED` : '✓ ALL NORMAL'}
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Forward {data.config.horizon}d realized-vol forecast vs current · {data.config.window}d vol window · lags 0–{data.config.maxLag}
            </div>
          </div>
          <div className="text-xs text-slate-400 text-right space-y-1">
            <div>Predictors: {data.predictorsUsed.join(' · ')}</div>
            <div>
              <span className={`px-1.5 py-0.5 rounded font-bold ${data.fredEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-700 text-slate-400'}`}>
                {data.fredEnabled ? 'FRED macro ON' : 'market-only (set FRED_API_KEY)'}
              </span>
            </div>
            <div className="text-slate-600">Updated {updated}</div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
        <div className="p-3 border-b border-slate-700 text-sm font-semibold text-slate-200">
          🌀 Turbulence Model — forecast &amp; regime by asset
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500 border-b border-slate-700">
              <tr className="text-left">
                <th className="p-2">Asset</th>
                <th className="p-2 text-right">Current Vol</th>
                <th className="p-2 text-right">Forecast (5d)</th>
                <th className="p-2">Signal</th>
                <th className="p-2 text-right hidden sm:table-cell">In-Sample R²</th>
                <th className="p-2 text-right hidden md:table-cell">OOS Corr</th>
                <th className="p-2 hidden lg:table-cell">Top Lags (|corr|)</th>
              </tr>
            </thead>
            <tbody>
              {ok.map(a => {
                const open = expanded === a.asset
                const chartData = (a.predictors ?? []).map(p => ({ name: `${p.name} (L${p.lag})`, corr: p.corr }))
                  .sort((x, y) => x.corr - y.corr)
                return (
                  <Fragment key={a.asset}>
                    <tr onClick={() => setExpanded(open ? null : a.asset)}
                      className={`border-b border-slate-800 cursor-pointer hover:bg-slate-800/60 ${open ? 'bg-slate-800/60' : ''}`}>
                      <td className="p-2 font-bold text-slate-100">{a.asset}</td>
                      <td className="p-2 text-right font-mono text-slate-300">{a.currentVol?.toFixed(1)}%</td>
                      <td className="p-2 text-right font-mono font-bold" style={{ color: sigColor(a.regime) }}>{a.forecast != null ? `${a.forecast.toFixed(1)}%` : '—'}</td>
                      <td className="p-2"><span className="text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap" style={{ backgroundColor: `${sigColor(a.regime)}20`, color: sigColor(a.regime) }}>{a.regime}</span></td>
                      <td className="p-2 text-right font-mono hidden sm:table-cell text-slate-300">{a.r2 != null ? a.r2.toFixed(2) : '—'}</td>
                      <td className={`p-2 text-right font-mono hidden md:table-cell ${(a.oosCorr ?? 0) >= 0.1 ? 'text-emerald-400' : (a.oosCorr ?? 0) < 0 ? 'text-red-400' : 'text-slate-400'}`}>{a.oosCorr != null ? a.oosCorr.toFixed(2) : '—'}</td>
                      <td className="p-2 hidden lg:table-cell text-slate-400 font-mono">{(a.topLags ?? []).map(t => `${t.name}@${t.lag}`).join(', ')}</td>
                    </tr>
                    {open && (
                      <tr className="bg-slate-900/60 border-b border-slate-800">
                        <td colSpan={7} className="p-3">
                          <div className="text-xs text-slate-400 mb-2">
                            Max correlation of each predictor with {a.asset} turbulence, at its optimal lead (lag, trading days). Fit on {a.n} rows · as of {a.asOf}.
                          </div>
                          <ResponsiveContainer width="100%" height={Math.max(140, chartData.length * 26)}>
                            <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                              <XAxis type="number" domain={[-1, 1]} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                              <YAxis type="category" dataKey="name" width={92} tick={{ fill: '#94a3b8', fontSize: 11 }} />
                              <ReferenceLine x={0} stroke="#475569" />
                              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f1f5f9', fontSize: 12 }} formatter={(v) => [Number(v).toFixed(3), 'corr']} />
                              <Bar dataKey="corr" radius={2}>
                                {chartData.map((d, i) => <Cell key={i} fill={d.corr >= 0 ? '#10b981' : '#ef4444'} />)}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
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
        <b>Model:</b> turbulence = annualized {data.config.window}d realized vol; each predictor is lead-lagged 0–{data.config.maxLag}d to its max |corr|
        with the forward {data.config.horizon}d turbulence, then an OLS forecasts next-period turbulence. <b>HIGH TURBULENCE</b> = forecast &gt; 1.25× current
        → consider trimming size or hedging with GLD/TLT. Liquidity (Fed net-liquidity proxy), CPI and PCE are pulled from FRED when <code>FRED_API_KEY</code>
        is set; otherwise the model runs market-only (BTC/VIX/10Y/DXY/Oil + VIX z-score). OOS Corr is a recent 15% hold-out check, not a guarantee.
      </div>
    </div>
  )
}
