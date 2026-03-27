export function calculateSMA(values: number[], period: number): number[] {
  return values.map((_, i) => {
    if (i < period - 1) return NaN
    const slice = values.slice(i - period + 1, i + 1).filter(v => !isNaN(v))
    return slice.length === period ? slice.reduce((a, b) => a + b, 0) / period : NaN
  })
}

export function calculateEMA(values: number[], period: number): number[] {
  const k = 2 / (period + 1)
  const result: number[] = []
  let ema = NaN
  for (let i = 0; i < values.length; i++) {
    if (isNaN(values[i])) { result.push(NaN); continue }
    if (isNaN(ema)) { ema = values[i] } else { ema = values[i] * k + ema * (1 - k) }
    result.push(ema)
  }
  return result
}

export function calculateRSI(closes: number[], period = 14): number[] {
  if (closes.length < period + 1) return closes.map(() => 50)
  const result: number[] = new Array(period).fill(NaN)
  let gains = 0, losses = 0
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1]
    if (d > 0) gains += d; else losses -= d
  }
  let ag = gains / period, al = losses / period
  result.push(al === 0 ? 100 : 100 - 100 / (1 + ag / al))
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1]
    ag = (ag * (period - 1) + Math.max(d, 0)) / period
    al = (al * (period - 1) + Math.max(-d, 0)) / period
    result.push(al === 0 ? 100 : 100 - 100 / (1 + ag / al))
  }
  return result
}

export function calculateStochRSI(closes: number[], rsiP = 14, stochP = 14, smoothK = 3, smoothD = 3) {
  const rsi = calculateRSI(closes, rsiP).filter(v => !isNaN(v))
  const rawK: number[] = []
  for (let i = stochP - 1; i < rsi.length; i++) {
    const slice = rsi.slice(i - stochP + 1, i + 1)
    const mn = Math.min(...slice), mx = Math.max(...slice)
    rawK.push(mx === mn ? 50 : ((rsi[i] - mn) / (mx - mn)) * 100)
  }
  const k = calculateSMA(rawK, smoothK).filter(v => !isNaN(v))
  const d = calculateSMA(k, smoothD).filter(v => !isNaN(v))
  return { k, d }
}

export function calculateADX(highs: number[], lows: number[], closes: number[], period = 14): number[] {
  if (closes.length < period + 2) return closes.map(() => 20)
  const tr: number[] = [], pdm: number[] = [], mdm: number[] = []
  for (let i = 1; i < closes.length; i++) {
    const up = highs[i] - highs[i - 1], dn = lows[i - 1] - lows[i]
    pdm.push(up > dn && up > 0 ? up : 0)
    mdm.push(dn > up && dn > 0 ? dn : 0)
    tr.push(Math.max(highs[i] - lows[i], Math.abs(highs[i] - closes[i - 1]), Math.abs(lows[i] - closes[i - 1])))
  }
  let sTR = tr.slice(0, period).reduce((a, b) => a + b, 0)
  let sPDM = pdm.slice(0, period).reduce((a, b) => a + b, 0)
  let sMDM = mdm.slice(0, period).reduce((a, b) => a + b, 0)
  const adx: number[] = new Array(period + 1).fill(NaN)
  let prevADX = NaN
  for (let i = period; i < tr.length; i++) {
    sTR = sTR - sTR / period + tr[i]
    sPDM = sPDM - sPDM / period + pdm[i]
    sMDM = sMDM - sMDM / period + mdm[i]
    const pDI = (sPDM / sTR) * 100, mDI = (sMDM / sTR) * 100
    const dx = (pDI + mDI) === 0 ? 0 : (Math.abs(pDI - mDI) / (pDI + mDI)) * 100
    prevADX = isNaN(prevADX) ? dx : (prevADX * (period - 1) + dx) / period
    adx.push(prevADX)
  }
  return adx
}

export function last<T>(arr: T[]): T { return arr[arr.length - 1] }
export function lastN<T>(arr: T[], n: number): T[] { return arr.slice(-n) }

export interface Kline {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export function parseBinanceKlines(raw: number[][]): Kline[] {
  return raw.map(k => ({
    time: Math.floor(k[0] / 1000),
    open: parseFloat(String(k[1])),
    high: parseFloat(String(k[2])),
    low: parseFloat(String(k[3])),
    close: parseFloat(String(k[4])),
    volume: parseFloat(String(k[5])),
  }))
}
