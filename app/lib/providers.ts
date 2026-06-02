// ============================================================================
// External data providers, gated behind env-var API keys.
// Set keys in Vercel project env (or .env.local) — see .env.example.
// When a key is absent or a call fails, callers fall back to keyless sources
// (Yahoo / Binance / CoinGecko), so the dashboard always renders.
// ============================================================================

export const FMP_KEY = process.env.FMP_API_KEY ?? ''
export const COINGLASS_KEY = process.env.COINGLASS_API_KEY ?? ''

export const hasFmp = () => FMP_KEY.length > 0
export const hasCoinglass = () => COINGLASS_KEY.length > 0

const FMP_BASE = 'https://financialmodelingprep.com'
const CG_BASE = 'https://open-api-v4.coinglass.com'

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

// --- CoinGlass v4 (crypto derivatives: funding, OI, liquidations, L/S ratio)
// v4 wraps payloads as { code, msg, data }. Returns the unwrapped `data`.
export async function cgGet<T = unknown>(
  path: string,
  params: Record<string, string | number> = {},
  revalidate = 30,
): Promise<T> {
  const url = new URL(`${CG_BASE}${path}`)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v))
  const res = await fetch(url.toString(), {
    headers: { 'CG-API-KEY': COINGLASS_KEY, Accept: 'application/json' },
    next: { revalidate },
  })
  if (!res.ok) throw new Error(`CoinGlass ${res.status} ${path}`)
  const json = (await res.json()) as { code?: string | number; msg?: string; data?: T }
  if (json.code != null && String(json.code) !== '0' && String(json.code) !== '200') {
    throw new Error(`CoinGlass error ${json.code}: ${json.msg ?? 'unknown'}`)
  }
  return (json.data ?? (json as unknown as T))
}

// read the first defined numeric field from a record (defensive against v4 field renames)
export function pick(obj: Record<string, unknown>, keys: string[], fallback = 0): number {
  for (const k of keys) {
    const v = obj?.[k]
    if (v != null && v !== '' && !Number.isNaN(Number(v))) return Number(v)
  }
  return fallback
}
