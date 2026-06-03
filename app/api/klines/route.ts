import { NextResponse } from 'next/server'
import { getKlines } from '@/app/lib/klines'

export const revalidate = 0

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const symbol = searchParams.get('symbol') ?? 'BTCUSDT'
  const interval = searchParams.get('interval') ?? '1d'
  const limit = Math.min(1000, Math.max(10, Number(searchParams.get('limit') ?? 300)))
  const { klines, source } = await getKlines(symbol, interval, limit)
  return NextResponse.json({ klines, source, timestamp: Date.now() })
}
