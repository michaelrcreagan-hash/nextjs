import { NextResponse } from 'next/server'
import { hasCoinapi, coinapiBinancePerpMetric } from '@/app/lib/providers'

export const revalidate = 0

interface DerivInfo { funding: number; shortLiqUsd: number; longLiqUsd: number; oiChange: number }

// Per-symbol derivatives map: CoinAPI funding (cross-exchange, US-accessible) when keyed,
// else Binance funding. Liquidation / OI-change fields aren't exposed by CoinAPI's current
// metrics, so C2/C7 fall back to their volume/price proxies.
async function getDerivMap(): Promise<{ map: Map<string, DerivInfo>; source: string }> {
  const map = new Map<string, DerivInfo>()
  if (hasCoinapi()) {
    try {
      const funding = await coinapiBinancePerpMetric('DERIVATIVES_FUNDING_RATE_CURRENT')
      for (const [sym, f] of funding) map.set(sym, { funding: f, shortLiqUsd: 0, longLiqUsd: 0, oiChange: 0 })
      if (map.size) return { map, source: 'coinapi' }
    } catch { /* fall through to Binance */ }
  }
  try {
    const prem = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex', { next: { revalidate: 60 } }).then(r => r.json()) as Record<string, string>[]
    for (const p of prem) {
      if (p.symbol?.endsWith('USDT')) {
        map.set(p.symbol.replace('USDT', '').toUpperCase(), { funding: parseFloat(p.lastFundingRate), shortLiqUsd: 0, longLiqUsd: 0, oiChange: 0 })
      }
    }
  } catch { /* none */ }
  return { map, source: map.size ? 'binance' : 'none' }
}

// Static reference sets used by the V3 squeeze model
const KOREAN = new Set(['XRP', 'TRX', 'SOL', 'DOGE', 'ADA', 'SAND', 'STX', 'INJ', 'SEI', 'TIA', 'NEAR', 'APT', 'HBAR', 'ALGO'])
const REPEAT_SQUEEZE = new Set(['DOGE', 'WIF', 'PEPE', 'INJ', 'TIA', 'SEI', 'PYTH', 'JUP'])
const CATALYSTS: Record<string, { score: number; note: string }> = {
  SOL: { score: 1.5, note: 'ETF / network upgrade flow' },
  TIA: { score: 1.0, note: 'Restaking / airdrop cycle' },
  INJ: { score: 1.0, note: 'Buyback burn auctions' },
  SUI: { score: 1.0, note: 'Ecosystem incentives' },
  SEI: { score: 0.75, note: 'v2 throughput catalysts' },
}
const NARRATIVE: Record<string, string> = {
  SOL: 'L1 / High-perf', SUI: 'L1 / Move', SEI: 'L1 / Trading', NEAR: 'L1 / AI',
  TIA: 'Modular DA', INJ: 'DeFi / Appchain', RNDR: 'AI / DePIN', FET: 'AI / Agents',
  RENDER: 'AI / DePIN', WIF: 'Memecoin', PEPE: 'Memecoin', DOGE: 'Memecoin',
  ARB: 'L2 / Scaling', OP: 'L2 / Scaling', LINK: 'Oracle / RWA', APT: 'L1 / Move',
}

interface Gecko {
  symbol: string; name: string; current_price: number; market_cap: number
  total_volume: number; price_change_percentage_24h: number
  price_change_percentage_7d_in_currency?: number; ath_change_percentage: number
}

async function getJSON(url: string, init?: RequestInit) {
  const res = await fetch(url, { next: { revalidate: 60 }, ...init })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function GET() {
  try {
    const [markets, deriv] = await Promise.all([
      getJSON('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=120&page=1&price_change_percentage=24h,7d') as Promise<Gecko[]>,
      getDerivMap(),
    ])
    const derivMap = deriv.map

    const btc = markets.find(m => m.symbol.toUpperCase() === 'BTC')
    const btcChange = btc?.price_change_percentage_24h ?? 0

    const scored = markets
      .filter(m => !['BTC', 'USDT', 'USDC', 'DAI', 'WBTC', 'STETH', 'WETH', 'WSTETH'].includes(m.symbol.toUpperCase()))
      .map(m => {
        const sym = m.symbol.toUpperCase()
        const d = derivMap.get(sym)
        const f = d ? d.funding : null
        const ch7 = m.price_change_percentage_7d_in_currency ?? 0
        const ch24 = m.price_change_percentage_24h ?? 0
        const volMc = m.market_cap ? m.total_volume / m.market_cap : 0
        const conds: { id: string; label: string; max: number; score: number; detail: string }[] = []

        // C1 — negative funding (max 3.5) ⭐
        let c1 = 0, c1d = 'no perp funding data'
        if (f != null) {
          if (f < -0.0005) { c1 = 3.5; c1d = `${(f * 100).toFixed(3)}% — deep negative` }
          else if (f < -0.0001) { c1 = 2.2; c1d = `${(f * 100).toFixed(3)}% — negative` }
          else if (f < 0.0001) { c1 = 0.8; c1d = `${(f * 100).toFixed(3)}% — flat` }
          else { c1 = 0; c1d = `${(f * 100).toFixed(3)}% — positive (crowded long)` }
        }
        conds.push({ id: 'C1', label: 'Negative funding', max: 3.5, score: c1, detail: c1d })

        // C2 — OI divergence / oversold (max 2.0). Uses real OI Δ if a provider supplies it
        // (CoinAPI current metrics don't), else a 7d-trend proxy. OI↑ while price↓ = trapped shorts.
        let c2 = ch7 < -10 ? 2.0 : ch7 < -3 ? 1.3 : ch7 < 3 ? 0.6 : 0
        let c2d = `7d ${ch7.toFixed(1)}%`
        if (d && d.oiChange) {
          c2 = d.oiChange > 5 && ch24 < 0 ? 2.0 : d.oiChange > 0 ? 1.2 : 0.4
          c2d = `OI ${d.oiChange >= 0 ? '+' : ''}${d.oiChange.toFixed(1)}% · price ${ch24.toFixed(1)}%`
        }
        conds.push({ id: 'C2', label: 'OI divergence', max: 2.0, score: c2, detail: c2d })

        // C3 — float compression (max 1.0)
        const c3 = volMc < 0.05 ? 1.0 : volMc < 0.1 ? 0.5 : 0
        conds.push({ id: 'C3', label: 'Float compression', max: 1.0, score: c3, detail: `vol/mc ${(volMc * 100).toFixed(1)}%` })

        // C4 — Korean exchange (max 1.0)
        const c4 = KOREAN.has(sym) ? 1.0 : 0
        conds.push({ id: 'C4', label: 'Korean listing', max: 1.0, score: c4, detail: c4 ? 'Upbit/Bithumb' : '—' })

        // C5 — technical oversold (max 0.8)
        const c5 = ch24 < -8 ? 0.8 : ch24 < -3 ? 0.6 : ch24 < 2 ? 0.3 : 0
        conds.push({ id: 'C5', label: 'Technical oversold', max: 0.8, score: c5, detail: `24h ${ch24.toFixed(1)}%` })

        // C6 — catalyst proximity (max 1.5)
        const cat = CATALYSTS[sym]
        const c6 = cat?.score ?? 0
        conds.push({ id: 'C6', label: 'Catalyst ≤7d', max: 1.5, score: c6, detail: cat?.note ?? '—' })

        // C7 — liquidation cluster (max 1.5). Uses real short-liquidation magnitude if a provider
        // supplies it (CoinAPI current metrics don't), else a liquidity proxy. Short-liq = squeeze fuel.
        let c7 = volMc > 0.15 ? 1.5 : volMc > 0.1 ? 1.0 : 0.5
        let c7d = `liquidity ${(volMc * 100).toFixed(0)}%`
        if (d && (d.shortLiqUsd > 0 || d.longLiqUsd > 0)) {
          const ratio = m.market_cap ? d.shortLiqUsd / m.market_cap : 0
          c7 = ratio > 0.003 ? 1.5 : ratio > 0.001 ? 1.0 : d.shortLiqUsd > d.longLiqUsd ? 0.7 : 0.3
          c7d = `short-liq $${(d.shortLiqUsd / 1e6).toFixed(1)}M (24h)`
        }
        conds.push({ id: 'C7', label: 'Liq cluster', max: 1.5, score: c7, detail: c7d })

        // C8 — narrative sector (max 1.25)
        const narr = NARRATIVE[sym] ?? 'Other'
        const c8 = narr !== 'Other' ? (ch7 > btcChange ? 1.25 : 0.75) : 0.4
        conds.push({ id: 'C8', label: 'Narrative vs BTC', max: 1.25, score: c8, detail: narr })

        // C9 — fundamentals proxy (max 1.25)
        const c9 = volMc > 0.12 ? 1.25 : volMc > 0.06 ? 0.7 : 0.3
        conds.push({ id: 'C9', label: 'Fundamentals', max: 1.25, score: c9, detail: 'volume trend' })

        // C10 — no-unlock screen (max 0.75) — default pass, manual override
        conds.push({ id: 'C10', label: 'No major unlock', max: 0.75, score: 0.75, detail: 'verify on TokenUnlocks' })

        // C11 — macro BTC momentum (max 1.0)
        const c11 = btcChange > 1 ? 1.0 : btcChange >= -1 ? 0.5 : 0
        conds.push({ id: 'C11', label: 'BTC up/flat', max: 1.0, score: c11, detail: `BTC ${btcChange.toFixed(1)}%` })

        // C12 — repeat squeezer (max 0.5)
        const c12 = REPEAT_SQUEEZE.has(sym) ? 0.5 : 0
        conds.push({ id: 'C12', label: 'Repeat squeezer', max: 0.5, score: c12, detail: c12 ? 'prior squeeze' : '—' })

        // Red flags / disqualifiers
        const redFlags: string[] = []
        if (m.ath_change_percentage > -20) redFlags.push('Within 20% of ATH')
        if (f != null && f > 0.0005) redFlags.push('Funding > +0.05% (crowded long)')
        if (btcChange < -5) redFlags.push('BTC crashing >5%')

        let total = conds.reduce((a, c) => a + c.score, 0)
        total = Math.min(total, 12.5)
        if (redFlags.length) total = Math.min(total, 5) // disqualified band

        return {
          symbol: sym, name: m.name, price: m.current_price, change24h: ch24, change7d: ch7,
          marketCap: m.market_cap, volume: m.total_volume, funding: f, narrative: narr,
          conds, score: +total.toFixed(2), redFlags,
          athChange: m.ath_change_percentage,
        }
      })
      .sort((a, b) => b.score - a.score)

    return NextResponse.json({ coins: scored.slice(0, 40), btcChange, source: deriv.source, timestamp: Date.now() })
  } catch (e) {
    return NextResponse.json({ coins: [], btcChange: 0, error: String(e), timestamp: Date.now() })
  }
}
