'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import dynamic from 'next/dynamic'

const DailyBrief = dynamic(() => import('./tabs/DailyBrief'), { ssr: false })
const MacroRegime = dynamic(() => import('./tabs/MacroRegime'), { ssr: false })
const BTCCycle = dynamic(() => import('./tabs/BTCCycle'), { ssr: false })
const CryptoDerivs = dynamic(() => import('./tabs/CryptoDerivs'), { ssr: false })
const PerpShorts = dynamic(() => import('./tabs/PerpShorts'), { ssr: false })
const AltcoinSqueeze = dynamic(() => import('./tabs/AltcoinSqueeze'), { ssr: false })
const AIStocks = dynamic(() => import('./tabs/AIStocks'), { ssr: false })
const OptionsFlow = dynamic(() => import('./tabs/OptionsFlow'), { ssr: false })
const TradeTracker = dynamic(() => import('./tabs/TradeTracker'), { ssr: false })

const TABS = [
  { id: 0, label: '📋 Daily Brief', short: 'Brief' },
  { id: 1, label: '🌍 Macro Regime', short: 'Macro' },
  { id: 2, label: '₿ BTC Cycle', short: 'Cycle' },
  { id: 3, label: '⚡ Perps & Futures', short: 'Perps' },
  { id: 4, label: '📉 Short Signals', short: 'Shorts' },
  { id: 5, label: '🪙 Altcoin Squeeze', short: 'Alts' },
  { id: 6, label: '🤖 AI Stocks', short: 'AI' },
  { id: 7, label: '📊 Options Flow', short: 'Options' },
  { id: 8, label: '💰 Trade Tracker', short: 'Tracker' },
]

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState(0)
  const [btcPrice, setBtcPrice] = useState<number>(0)
  const [btcChange, setBtcChange] = useState<number>(0)
  const [regimeScore, setRegimeScore] = useState(50)
  const [bottomScore, setBottomScore] = useState(3)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const prevPriceRef = useRef(0)
  const binanceBlockedRef = useRef(false)

  // Live BTC price via WebSocket — Binance when reachable, auto-fallback to Coinbase
  // (US-accessible) when Binance is geo-blocked or unreachable.
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const openCoinbase = () => {
      const ws = new WebSocket('wss://ws-feed.exchange.coinbase.com')
      wsRef.current = ws
      ws.onopen = () => { setConnected(true); ws.send(JSON.stringify({ type: 'subscribe', product_ids: ['BTC-USD'], channels: ['ticker'] })) }
      ws.onerror = () => { try { ws.close() } catch { /* noop */ } }
      ws.onclose = () => { setConnected(false); setTimeout(connectWS, 3000) }
      ws.onmessage = (e) => {
        const d = JSON.parse(e.data)
        if (d.type === 'ticker' && d.price) {
          const price = parseFloat(d.price)
          const open = parseFloat(d.open_24h)
          setBtcPrice(price)
          if (open) setBtcChange(((price - open) / open) * 100)
          prevPriceRef.current = price
        }
      }
    }

    if (binanceBlockedRef.current) { openCoinbase(); return }

    const ws = new WebSocket('wss://stream.binance.com:9443/ws/btcusdt@miniTicker')
    wsRef.current = ws
    let opened = false, fellBack = false
    const goCoinbase = () => { if (fellBack) return; fellBack = true; binanceBlockedRef.current = true; try { ws.close() } catch { /* noop */ }; openCoinbase() }
    const fallback = setTimeout(() => { if (!opened) goCoinbase() }, 4000)
    ws.onopen = () => { opened = true; clearTimeout(fallback); setConnected(true) }
    ws.onerror = () => { try { ws.close() } catch { /* noop */ } }
    ws.onclose = () => { clearTimeout(fallback); setConnected(false); if (!opened) goCoinbase(); else setTimeout(connectWS, 3000) }
    ws.onmessage = (e) => {
      const d = JSON.parse(e.data)
      const price = parseFloat(d.c)
      const open = parseFloat(d.o)
      setBtcPrice(price)
      setBtcChange(((price - open) / open) * 100)
      prevPriceRef.current = price
    }
  }, [])

  useEffect(() => {
    connectWS()
    return () => { wsRef.current?.close() }
  }, [connectWS])

  // Fetch regime score from macro API
  useEffect(() => {
    fetch('/api/macro')
      .then(r => r.json())
      .then(d => { if (d.regimeScore != null) setRegimeScore(d.regimeScore) })
      .catch(() => {})
    const id = setInterval(() => {
      fetch('/api/macro').then(r => r.json()).then(d => { if (d.regimeScore != null) setRegimeScore(d.regimeScore) }).catch(() => {})
    }, 60_000)
    return () => clearInterval(id)
  }, [])

  const priceUp = btcChange >= 0
  const signalColor = regimeScore <= 45 && bottomScore < 6 ? '#ef4444' : regimeScore <= 60 ? '#eab308' : '#10b981'
  const signalLabel = regimeScore <= 45 && bottomScore < 6 ? 'SHORT BIAS' : regimeScore <= 60 ? 'NEUTRAL' : 'LONG BIAS'

  return (
    <div className="min-h-screen bg-[#080d14] text-slate-100 flex flex-col">
      {/* Top Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center gap-4 px-4 py-3 flex-wrap">
          {/* Logo */}
          <div className="flex items-center gap-2 mr-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-sm font-black">⚡</div>
            <span className="font-black text-sm text-slate-100 hidden sm:block">EDGE TERMINAL</span>
          </div>

          {/* BTC Price */}
          <div className="flex items-baseline gap-2">
            <span className="text-xs text-slate-500 font-mono">BTC/USDT</span>
            <span className={`text-xl font-black font-mono ${priceUp ? 'text-emerald-400' : 'text-red-400'}`}>
              {btcPrice > 0 ? `$${btcPrice.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : 'Loading...'}
            </span>
            {btcPrice > 0 && (
              <span className={`text-sm font-bold font-mono px-1.5 py-0.5 rounded ${priceUp ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                {priceUp ? '+' : ''}{btcChange.toFixed(2)}%
              </span>
            )}
          </div>

          {/* Live indicator */}
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
            <span className="text-xs text-slate-500">{connected ? 'LIVE' : 'RECONNECTING'}</span>
          </div>

          {/* Regime + Bottom quick status */}
          <div className="flex gap-3 ml-auto flex-wrap">
            <div className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1">
              <span className="text-slate-500">Regime:</span>{' '}
              <span className="font-bold font-mono" style={{ color: regimeScore <= 45 ? '#ef4444' : regimeScore <= 60 ? '#eab308' : '#10b981' }}>
                {Math.round(regimeScore)}
              </span>
            </div>
            <div className="text-xs bg-slate-800 border border-slate-700 rounded px-2 py-1">
              <span className="text-slate-500">Bottom:</span>{' '}
              <span className="font-bold font-mono text-blue-400">{bottomScore}/12</span>
            </div>
            <div className="text-xs px-2 py-1 rounded font-bold" style={{ backgroundColor: `${signalColor}20`, color: signalColor, border: `1px solid ${signalColor}40` }}>
              {signalLabel}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-t border-slate-800 overflow-x-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 min-w-[80px] px-3 py-2.5 text-xs font-semibold transition-all whitespace-nowrap border-b-2 ${
                activeTab === tab.id
                  ? 'text-blue-400 border-blue-400 bg-blue-500/10'
                  : 'text-slate-400 border-transparent hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.short}</span>
            </button>
          ))}
        </div>
      </header>

      {/* Tab Content */}
      <main className="flex-1 overflow-auto p-4 lg:p-6">
        {activeTab === 0 && <DailyBrief />}
        {activeTab === 1 && <MacroRegime />}
        {activeTab === 2 && <BTCCycle onBottomScore={setBottomScore} />}
        {activeTab === 3 && <CryptoDerivs />}
        {activeTab === 4 && <PerpShorts regimeScore={regimeScore} bottomScore={bottomScore} />}
        {activeTab === 5 && <AltcoinSqueeze />}
        {activeTab === 6 && <AIStocks />}
        {activeTab === 7 && <OptionsFlow />}
        {activeTab === 8 && <TradeTracker />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 px-4 py-2 text-xs text-slate-600 flex justify-between flex-wrap gap-2">
        <span>⚠️ Educational tool only — not financial advice. Always use stop-losses and risk 2% max per trade.</span>
        <span>BTC · Altcoins · AI Bottleneck Stocks · Perps + Options · Live</span>
      </footer>
    </div>
  )
}
