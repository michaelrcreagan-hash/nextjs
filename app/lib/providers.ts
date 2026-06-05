// ============================================================================
// External data providers, gated behind env-var API keys.
// Set keys in Vercel project env (or .env.local) — see .env.example.
// When a key is absent or a call fails, callers fall back to keyless sources
// (Yahoo / Binance / CoinGecko), so the dashboard always renders.
// ============================================================================

export const FMP_KEY = process.env.FMP_API_KEY ?? ''
// CoinAPI key — accept a few common env-var spellings so it "just works"
export const COINAPI_KEY =
  process.env.COINAPI_KEY ?? process.env.COINAPI_API_KEY ?? process.env.COIN_API_KEY ?? ''
// FRED (St. Louis Fed) — optional macro predictors for the Turbulence model
export const FRED_KEY = process.env.FRED_API_KEY ?? process.env.FRED_KEY ?? ''

export const hasFmp = () => FMP_KEY.length > 0
export const hasCoinapi = () => COINAPI_KEY.length > 0
export const hasFred = () => FRED_KEY.length > 0

const FMP_BASE = 'https://financialmodelingprep.com'
const COINAPI_BASE = 'https://rest.coinapi.io'

// --- Financial Modeling Prep (stocks: quotes, candles, estimates, transcripts)
export async function fmpGet<T = unknown>(
  path: string,
  params: Record<string, string | number> = {},
  revalidate = 60,
): Promise<T> {
  const url = new URL(`${FMP_BASE}${path}`)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v))
  url.searchParams.set('apikey', FMP_KEY)
  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
    next: { revalidate },
  })
  if (!res.ok) throw new Error(`FMP ${res.status} ${path}`)
  return res.json() as Promise<T>
}

// --- CoinAPI.io (crypto market data + derivatives metrics: funding, open interest)
export async function coinapiGet<T = unknown>(
  path: string,
  params: Record<string, string | number> = {},
  revalidate = 120,
): Promise<T> {
  const url = new URL(`${COINAPI_BASE}${path}`)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v))
  const res = await fetch(url.toString(), {
    headers: { 'X-CoinAPI-Key': COINAPI_KEY, Accept: 'application/json' },
    next: { revalidate },
  })
  if (!res.ok) throw new Error(`CoinAPI ${res.status} ${path}`)
  return res.json() as Promise<T>
}

interface CoinapiMetric { symbol_id?: string; value_decimal?: number; value?: number }

// Bulk-fetch a derivatives metric for all Binance USDⓈ-M perps in one call,
// returning a map keyed by base asset (BTC, ETH, …). symbol_id = BINANCEFTS_PERP_{ASSET}_USDT
export async function coinapiBinancePerpMetric(
  metricId: 'DERIVATIVES_FUNDING_RATE_CURRENT' | 'DERIVATIVES_OPEN_INTEREST',
  revalidate = 120,
): Promise<Map<string, number>> {
  const rows = await coinapiGet<CoinapiMetric[]>(
    '/v1/metrics/symbol/current',
    { metric_id: metricId, exchange_id: 'BINANCEFTS' },
    revalidate,
  )
  const map = new Map<string, number>()
  for (const r of rows ?? []) {
    const sid = r.symbol_id ?? ''
    const m = sid.match(/^BINANCEFTS_PERP_([A-Z0-9]+)_USDT$/)
    if (!m) continue
    const val = r.value_decimal ?? r.value
    if (val != null) map.set(m[1].toUpperCase(), Number(val))
  }
  return map
}

// --- FRED (St. Louis Fed) macro series, e.g. WALCL / WTREGEN / RRPONTSYD / CPIAUCSL / PCE
export async function fredSeries(seriesId: string, observationStart: string, revalidate = 3600): Promise<{ date: string; value: number }[]> {
  const url = new URL('https://api.stlouisfed.org/fred/series/observations')
  url.searchParams.set('series_id', seriesId)
  url.searchParams.set('api_key', FRED_KEY)
  url.searchParams.set('file_type', 'json')
  url.searchParams.set('observation_start', observationStart)
  const res = await fetch(url.toString(), { headers: { Accept: 'application/json' }, next: { revalidate } })
  if (!res.ok) throw new Error(`FRED ${res.status} ${seriesId}`)
  const j = await res.json() as { observations?: { date: string; value: string }[] }
  return (j.observations ?? [])
    .filter(o => o.value !== '.' && o.value != null)
    .map(o => ({ date: o.date, value: Number(o.value) }))
    .filter(o => !Number.isNaN(o.value))
}

// read the first defined numeric field from a record (defensive against field renames)
export function pick(obj: Record<string, unknown>, keys: string[], fallback = 0): number {
  for (const k of keys) {
    const v = obj?.[k]
    if (v != null && v !== '' && !Number.isNaN(Number(v))) return Number(v)
  }
  return fallback
}
