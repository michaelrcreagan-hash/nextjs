import { type Kline, parseBinanceKlines } from './indicators'
import { hasCoinapi, coinapiGet } from './providers'

export type KlineSource = 'binance' | 'coinbase' | 'coinapi' | 'none'

// Coinbase Exchange supported granularities (seconds). No native 4h → use 6h as a
// close substitute on the fallback path; weekly is aggregated from daily.
const CB_GRAN: Record<string, number> = { '1h': 3600, '4h': 21600, '6h': 21600, '1d': 86400, '1w': 86400 }
const CA_PERIOD: Record<string, string> = { '1h': '1HRS', '4h': '4HRS', '6h': '6HRS', '1d': '1DAY', '1w': '7DAY' }

function aggregate(kl: Kline[], n: number): Kline[] {
  const out: Kline[] = []
  for (let i = 0; i < kl.length; i += n) {
    const chunk = kl.slice(i, i + n)
    if (!chunk.length) continue
    out.push({
      time: chunk[0].time, open: chunk[0].open,
      high: Math.max(...chunk.map(c => c.high)), low: Math.min(...chunk.map(c => c.low)),
      close: chunk[chunk.length - 1].close, volume: chunk.reduce((a, c) => a + c.volume, 0),
    })
  }
  return out
}

async function fromBinance(symbol: string, interval: string, limit: number): Promise<Kline[]> {
  const r = await fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`, { next: { revalidate: 30 } })
  if (!r.ok) throw new Error(`binance ${r.status}`)
  return parseBinanceKlines(await r.json())
}

async function fromCoinbase(symbol: string, interval: string, limit: number): Promise<Kline[]> {
  const base = symbol.replace('USDT', '').replace('USD', '')
  const weekly = interval === '1w'
  const gran = weekly ? 86400 : (CB_GRAN[interval] ?? 86400)
  const r = await fetch(`https://api.exchange.coinbase.com/products/${base}-USD/candles?granularity=${gran}`, {
    headers: { 'User-Agent': 'edge-terminal', Accept: 'application/json' }, next: { revalidate: 30 },
  })
  if (!r.ok) throw new Error(`coinbase ${r.status}`)
  // Coinbase: [ time, low, high, open, close, volume ] newest-first
  const raw = await r.json() as number[][]
  let kl: Kline[] = raw
    .map(c => ({ time: c[0], low: c[1], high: c[2], open: c[3], close: c[4], volume: c[5] }))
    .sort((a, b) => a.time - b.time)
  if (weekly) kl = aggregate(kl, 7)
  return kl.slice(-limit)
}

interface CoinapiBar { time_period_start: string; price_open: number; price_high: number; price_low: number; price_close: number; volume_traded: number }
async function fromCoinapiOhlcv(symbol: string, interval: string, limit: number): Promise<Kline[]> {
  const base = symbol.replace('USDT', '').replace('USD', '')
  const period = CA_PERIOD[interval] ?? '1DAY'
  const rows = await coinapiGet<CoinapiBar[]>(`/v1/ohlcv/COINBASE_SPOT_${base}_USD/history`, { period_id: period, limit }, 120)
  return (rows ?? []).map(r => ({
    time: Math.floor(new Date(r.time_period_start).getTime() / 1000),
    open: r.price_open, high: r.price_high, low: r.price_low, close: r.price_close, volume: r.volume_traded,
  })).sort((a, b) => a.time - b.time)
}

// Resilient OHLCV: Binance → Coinbase → CoinAPI (last resort). Always returns the
// best available source so charts/indicators keep working when one venue is blocked.
export async function getKlines(symbol = 'BTCUSDT', interval = '1d', limit = 300): Promise<{ klines: Kline[]; source: KlineSource }> {
  try { const k = await fromBinance(symbol, interval, limit); if (k.length) return { klines: k, source: 'binance' } } catch { /* next */ }
  try { const k = await fromCoinbase(symbol, interval, limit); if (k.length) return { klines: k, source: 'coinbase' } } catch { /* next */ }
  if (hasCoinapi()) { try { const k = await fromCoinapiOhlcv(symbol, interval, limit); if (k.length) return { klines: k, source: 'coinapi' } } catch { /* next */ } }
  return { klines: [], source: 'none' }
}
