'use client'

import { useEffect, useRef } from 'react'
import type { Kline } from '@/app/lib/indicators'

interface Props {
  data: Kline[]
  newCandle?: Kline | null
  height?: number
}

export default function TradingChart({ data, newCandle, height = 380 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<ReturnType<typeof import('lightweight-charts')['createChart']> | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<any>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    let cleanup: (() => void) | undefined

    const init = async () => {
      const { createChart, CandlestickSeries } = await import('lightweight-charts')

      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null }

      const chart = createChart(containerRef.current!, {
        layout: { background: { color: '#0f172a' }, textColor: '#94a3b8' },
        grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
        width: containerRef.current!.clientWidth,
        height,
        crosshair: {
          vertLine: { color: '#475569', width: 1, style: 1 },
          horzLine: { color: '#475569', width: 1, style: 1 },
        },
        timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#334155' },
      })

      const series = chart.addSeries(CandlestickSeries, {
        upColor: '#10b981',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      })

      series.setData(
        data.map(k => ({ time: k.time as unknown as import('lightweight-charts').Time, open: k.open, high: k.high, low: k.low, close: k.close }))
      )
      chart.timeScale().fitContent()

      chartRef.current = chart
      seriesRef.current = series

      const onResize = () => {
        if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
      }
      window.addEventListener('resize', onResize)
      cleanup = () => { window.removeEventListener('resize', onResize); chart.remove() }
    }

    init()
    return () => { cleanup?.() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, height])

  useEffect(() => {
    if (newCandle && seriesRef.current) {
      seriesRef.current.update({
        time: newCandle.time as unknown as import('lightweight-charts').Time,
        open: newCandle.open, high: newCandle.high, low: newCandle.low, close: newCandle.close,
      })
    }
  }, [newCandle])

  return <div ref={containerRef} className="w-full" style={{ height }} />
}
