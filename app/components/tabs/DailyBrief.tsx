'use client'

import { useEffect, useState, useCallback } from 'react'

interface BiasFactor { label: string; bull: boolean | null; detail: string; weight: number }
interface Bias { price: number; biasScore: number; label: string; factors: BiasFactor[]; funding: number; adx: number }
interface Macro { regimeScore: number; vix: { current: number }; dxy: { changePercent: number } }
interface StockRow {
  symbol: string; ok: boolean; price: number; changePct: number; rank?: number; fundamental?: number
  technical?: number; subTheme?: string; m30?: number; daysToEarnings?: number | null; catalystSoon?: boolean
  fin?: { epsRevision: number }; options?: { structure: string; legs: string }; rvol?: number
}
interface Phase { id: string; label: string; emoji: string; momentum: number }
interface Stocks { rows: StockRow[]; phaseScores: Phase[]; activePhase: string }
interface Alt { symbol: string; score: number; change24h: number; funding: number | null; narrative: string; redFlags: string[] }
interface Alts { coins: Alt[]; btcChange: number }
interface Deriv { symbol: string; funding: number; oiUsd: number }
interface Derivs { coins: Deriv[] }

function regimeLabel(s: number) {
  if (s <= 25) return { t: 'EXTREME RISK-OFF', c: '#ef4444' }
  if (s <= 45) return { t: 'RISK-OFF', c: '#f97316' }
  if (s <= 60) return { t: 'TRANSITION', c: '#eab308' }
  if (s <= 80) return { t: 'RISK-ON', c: '#22c55e' }
  return { t: 'EXTREME RISK-ON', c: '#4ade80' }
}

export default function DailyBrief() {
  const [bias, setBias] = useState<Bias | null>(null)
  const [macro, setMacro] = useState<Macro | null>(null)
  const [stocks, setStocks] = useState<Stocks | null>(null)
  const [alts, setAlts] = useState<Alts | null>(null)
  const [derivs, setDerivs] = useState<Derivs | null>(null)
  const [updated, setUpdated] = useState('')

  const fetchAll = useCallback(async () => {
    const get = (u: string) => fetch(u).then(r => r.json()).catch(() => null)
    const [b, m, s, a, d] = await Promise.all([
      get('/api/daily-bias'), get('/api/macro'), get('/api/stocks'), get('/api/altcoins'), get('/api/derivs'),
    ])
    if (b) setBias(b); if (m) setMacro(m); if (s) setStocks(s); if (a) setAlts(a); if (d) setDerivs(d)
    setUpdated(new Date().toLocaleTimeString())
  }, [])

  useEffect(() => { fetchAll(); const id = setInterval(fetchAll, 90_000); return () => clearInterval(id) }, [fetchAll])

  const okStocks = (stocks?.rows ?? []).filter(r => r.ok)
  const topSetups = [...okStocks].sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0)).slice(0, 5)
  const epsLeaders = [...okStocks].sort((a, b) => (b.fin?.epsRevision ?? 0) - (a.fin?.epsRevision ?? 0)).slice(0, 5)
  const catalysts = okStocks.filter(r => r.catalystSoon).sort((a, b) => (a.daysToEarnings ?? 99) - (b.daysToEarnings ?? 99))
  const optionsAlerts = topSetups.filter(r => (r.technical ?? 0) >= 65 && (r.rvol ?? 0) >= 1.3)
  const activePhase = stocks?.phaseScores.find(p => p.id === stocks.activePhase)
  const topAlts = (alts?.coins ?? []).filter(c => c.score >= 6.5 && c.redFlags.length === 0).slice(0, 6)
  const fundingAlerts = [...(derivs?.coins ?? [])].sort((a, b) => a.funding - b.funding).filter(c => c.funding < -0.0001).slice(0, 6)
  const reg = macro ? regimeLabel(macro.regimeScore) : null

  const Card = ({ title, children, sub }: { title: string; children: React.ReactNode; sub?: string }) => (
    <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-slate-200">{title}</div>
        {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
      </div>
      {children}
    </div>
  )

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="text-lg font-black text-slate-100">📋 Daily Brief</div>
          <div className="text-xs text-slate-500">One-screen synthesis across BTC · altcoins · AI bottleneck stocks — {new Date().toLocaleDateString()}</div>
        </div>
        <div className="text-xs text-slate-500">Updated {updated}</div>
      </div>

      {/* Top regime strip: Daily Bias + Risk On/Off */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Daily Bias Framework */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-200 mb-2">🧭 BTC Daily Bias Framework</div>
          {bias ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-black font-mono" style={{ color: bias.biasScore > 20 ? '#10b981' : bias.biasScore < -20 ? '#ef4444' : '#eab308' }}>
                  {bias.biasScore > 0 ? '+' : ''}{bias.biasScore}
                </span>
                <span className="text-lg font-bold" style={{ color: bias.biasScore > 20 ? '#10b981' : bias.biasScore < -20 ? '#ef4444' : '#eab308' }}>{bias.label}</span>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">BTC ${bias.price.toLocaleString(undefined, { maximumFractionDigits: 0 })} · ADX {bias.adx.toFixed(0)} · funding {(bias.funding * 100).toFixed(3)}%</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3 gap-y-1 mt-3">
                {bias.factors.map(f => (
                  <div key={f.label} className="flex items-center gap-2 text-[11px]">
                    <span>{f.bull === null ? '⚪' : f.bull ? '🟢' : '🔴'}</span>
                    <span className="text-slate-400 flex-1 truncate">{f.label}</span>
                    <span className="text-slate-500 font-mono">{f.detail}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="text-slate-500 text-sm">Loading bias…</div>}
        </div>

        {/* Risk On/Off */}
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-200 mb-2">🌡️ Risk-On / Risk-Off Regime</div>
          {macro && reg ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-black font-mono" style={{ color: reg.c }}>{Math.round(macro.regimeScore)}</span>
                <span className="text-lg font-bold" style={{ color: reg.c }}>{reg.t}</span>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">VIX {macro.vix.current.toFixed(1)} · DXY {macro.dxy.changePercent >= 0 ? '+' : ''}{macro.dxy.changePercent.toFixed(2)}%</div>
              <div className="w-full bg-slate-700 rounded-full h-2 mt-3"><div className="h-2 rounded-full" style={{ width: `${macro.regimeScore}%`, backgroundColor: reg.c }} /></div>
              <div className="text-xs text-slate-400 mt-3">
                {macro.regimeScore <= 45 ? 'Risk-off — favor quality, tighten risk, options over spot for AI; spot bias defensive on crypto.'
                  : macro.regimeScore <= 60 ? 'Transition — selective; size down, demand confirmation.'
                  : 'Risk-on — green light for trend setups; spot + leveraged longs in favor.'}
              </div>
            </>
          ) : <div className="text-slate-500 text-sm">Loading regime…</div>}
        </div>
      </div>

      {/* Bottleneck status */}
      {activePhase && (
        <div className="bg-blue-500/10 border border-blue-500/40 rounded-xl p-4">
          <div className="text-sm font-semibold text-slate-200">⚙️ Bottleneck Status</div>
          <div className="text-base font-bold text-blue-300 mt-1">{activePhase.emoji} Active constraint: {activePhase.label} ({activePhase.momentum >= 0 ? '+' : ''}{activePhase.momentum.toFixed(1)}% 1M basket)</div>
          <div className="flex gap-2 mt-2 flex-wrap">
            {stocks?.phaseScores.map(p => (
              <span key={p.id} className={`text-[11px] px-2 py-0.5 rounded font-mono ${p.id === stocks.activePhase ? 'bg-blue-500/30 text-blue-200' : 'bg-slate-800 text-slate-400'}`}>
                {p.emoji} {p.label.split(' ')[0]} {p.momentum >= 0 ? '+' : ''}{p.momentum.toFixed(1)}%
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top AI setups */}
        <Card title="🎯 Top AI Setups (by composite)" sub="Layer 4 ranked">
          <div className="space-y-1.5">
            {topSetups.map((r, i) => (
              <div key={r.symbol} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-4">{i + 1}.</span>
                  <span className="font-bold text-slate-100 w-14">{r.symbol}</span>
                  <span className="text-slate-500 truncate hidden sm:inline">{r.subTheme}</span>
                </div>
                <div className="flex items-center gap-3 font-mono">
                  <span className={`${(r.changePct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{(r.changePct ?? 0) >= 0 ? '+' : ''}{(r.changePct ?? 0).toFixed(1)}%</span>
                  <span className="text-slate-400">F{r.fundamental}/T{r.technical}</span>
                  <span className="text-blue-400 font-bold">{r.rank}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* EPS revision leaders */}
        <Card title="📈 EPS Revision Momentum Leaders" sub="Layer 3 · 30/60/90d">
          <div className="space-y-1.5">
            {epsLeaders.map((r, i) => (
              <div key={r.symbol} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 w-4">{i + 1}.</span>
                  <span className="font-bold text-slate-100 w-14">{r.symbol}</span>
                </div>
                <div className="flex items-center gap-2 flex-1 mx-3">
                  <div className="flex-1 bg-slate-700 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-emerald-500" style={{ width: `${r.fin?.epsRevision ?? 0}%` }} /></div>
                </div>
                <span className="font-mono text-emerald-400 w-8 text-right">{r.fin?.epsRevision ?? 0}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Catalysts within 10 days */}
        <Card title="📅 Catalysts Within 10 Days" sub="earnings">
          {catalysts.length ? (
            <div className="space-y-1.5">
              {catalysts.map(r => (
                <div key={r.symbol} className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-100">{r.symbol} <span className="text-slate-500 font-normal">{r.subTheme}</span></span>
                  <span className="font-mono text-amber-400">in {r.daysToEarnings}d</span>
                </div>
              ))}
            </div>
          ) : <div className="text-xs text-slate-500">No earnings within 10 days in the watchlist.</div>}
        </Card>

        {/* Options flow alerts */}
        <Card title="🎟️ Options Flow Alerts" sub="strong trend + RVOL">
          {optionsAlerts.length ? (
            <div className="space-y-1.5">
              {optionsAlerts.map(r => (
                <div key={r.symbol} className="text-xs flex items-center justify-between">
                  <span className="font-bold text-slate-100">{r.symbol}</span>
                  <span className="text-blue-400">{r.options?.structure}</span>
                  <span className="font-mono text-slate-400">{r.options?.legs}</span>
                </div>
              ))}
            </div>
          ) : <div className="text-xs text-slate-500">No high-conviction options triggers right now (need Tech≥65 &amp; RVOL≥1.3×).</div>}
        </Card>

        {/* Top crypto squeeze */}
        <Card title="🪙 Top Crypto Squeeze Setups" sub="APEX V3 ≥6.5">
          {topAlts.length ? (
            <div className="space-y-1.5">
              {topAlts.map(c => (
                <div key={c.symbol} className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-100 w-16">{c.symbol} <span className="text-slate-500 font-normal">{c.narrative}</span></span>
                  <span className={`font-mono ${c.change24h >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{c.change24h >= 0 ? '+' : ''}{c.change24h.toFixed(1)}%</span>
                  <span className="font-mono text-emerald-400 font-bold">{c.score.toFixed(1)}</span>
                </div>
              ))}
            </div>
          ) : <div className="text-xs text-slate-500">No qualified squeeze setups (≥6.5, no red flags).</div>}
        </Card>

        {/* Funding alerts */}
        <Card title="⚡ Negative Funding Alerts" sub="shorts paying longs">
          {fundingAlerts.length ? (
            <div className="space-y-1.5">
              {fundingAlerts.map(c => (
                <div key={c.symbol} className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-100">{c.symbol}</span>
                  <span className="font-mono text-emerald-400">{(c.funding * 100).toFixed(4)}%/8h</span>
                </div>
              ))}
            </div>
          ) : <div className="text-xs text-slate-500">No deeply negative funding right now.</div>}
        </Card>
      </div>

      <div className="text-[11px] text-slate-600 bg-slate-900/40 border border-slate-800 rounded-lg p-3">
        Brief auto-refreshes every 90s. Daily bias = BTC HTF trend + momentum + funding · Risk regime = VIX/DXY/yields/breadth.
        Cross-check the dedicated tabs before executing. Educational tool — not financial advice.
      </div>
    </div>
  )
}
