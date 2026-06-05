// ============================================================================
// Turbulence model — realized-volatility forecasting via optimal-lag OLS.
// Ported from the Colab/statsmodels prototype. Pure functions (no I/O):
//   turbulence = annualized rolling stdev of log returns (%)
//   target     = forward mean turbulence over `horizon` days
//   per predictor: pick the lag (0..maxLag) maximizing |corr| with the target
//   fit OLS (normal equations + tiny ridge) → R², forecast, regime signal
// ============================================================================

export const NaNv = Number.NaN

export function logReturns(p: number[]): number[] {
  const out = [NaNv]
  for (let i = 1; i < p.length; i++) out.push(p[i] > 0 && p[i - 1] > 0 ? Math.log(p[i] / p[i - 1]) : NaNv)
  return out
}

// Annualized realized volatility in percent (rolling stdev of log returns).
export function realizedVol(p: number[], window = 20): number[] {
  const r = logReturns(p)
  const out = new Array(p.length).fill(NaNv)
  for (let i = window; i < p.length; i++) {
    const slice = r.slice(i - window + 1, i + 1).filter(v => !Number.isNaN(v))
    if (slice.length < window) continue
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / (slice.length - 1)
    out[i] = Math.sqrt(variance) * Math.sqrt(252) * 100
  }
  return out
}

export function pctChange(p: number[]): number[] {
  const out = [NaNv]
  for (let i = 1; i < p.length; i++) out.push(p[i - 1] ? (p[i] - p[i - 1]) / p[i - 1] : NaNv)
  return out
}

// shifted[i] = arr[i - lag]  (pandas .shift(lag); uses past values)
export function shift(arr: number[], lag: number): number[] {
  const out = new Array(arr.length).fill(NaNv)
  for (let i = lag; i < arr.length; i++) out[i] = arr[i - lag]
  return out
}

// Forward mean over horizon: mean(target[i+1 .. i+horizon]) of the turbulence series.
export function forwardMean(series: number[], horizon: number): number[] {
  const out = new Array(series.length).fill(NaNv)
  for (let i = 0; i < series.length; i++) {
    const slice = series.slice(i + 1, i + 1 + horizon).filter(v => !Number.isNaN(v))
    if (slice.length === horizon) out[i] = slice.reduce((a, b) => a + b, 0) / horizon
  }
  return out
}

// Rolling z-score (used for the VIX "PC" / principal-component proxy).
export function rollingZ(p: number[], window = 252): number[] {
  const out = new Array(p.length).fill(NaNv)
  for (let i = window - 1; i < p.length; i++) {
    const slice = p.slice(i - window + 1, i + 1).filter(v => !Number.isNaN(v))
    if (slice.length < window) continue
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length
    const sd = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / (slice.length - 1))
    out[i] = sd ? (p[i] - mean) / sd : NaNv
  }
  return out
}

export function pearson(a: number[], b: number[]): number {
  const xs: number[] = [], ys: number[] = []
  for (let i = 0; i < a.length; i++) if (!Number.isNaN(a[i]) && !Number.isNaN(b[i])) { xs.push(a[i]); ys.push(b[i]) }
  const n = xs.length
  if (n < 10) return NaNv
  const mx = xs.reduce((s, v) => s + v, 0) / n, my = ys.reduce((s, v) => s + v, 0) / n
  let num = 0, dx = 0, dy = 0
  for (let i = 0; i < n; i++) { const a2 = xs[i] - mx, b2 = ys[i] - my; num += a2 * b2; dx += a2 * a2; dy += b2 * b2 }
  return dx && dy ? num / Math.sqrt(dx * dy) : NaNv
}

export function optimizeLag(pred: number[], target: number[], maxLag = 63): { lag: number; corr: number } {
  let best = { lag: 0, corr: 0 }
  for (let lag = 0; lag <= maxLag; lag++) {
    const c = pearson(shift(pred, lag), target)
    if (!Number.isNaN(c) && Math.abs(c) > Math.abs(best.corr)) best = { lag, corr: +c.toFixed(4) }
  }
  return best
}

// --- OLS via normal equations with a tiny ridge for numerical stability ---
function invert(M: number[][]): number[][] | null {
  const n = M.length
  const A = M.map((row, i) => [...row, ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))])
  for (let col = 0; col < n; col++) {
    let piv = col
    for (let r = col + 1; r < n; r++) if (Math.abs(A[r][col]) > Math.abs(A[piv][col])) piv = r
    if (Math.abs(A[piv][col]) < 1e-12) return null
    ;[A[col], A[piv]] = [A[piv], A[col]]
    const d = A[col][col]
    for (let j = 0; j < 2 * n; j++) A[col][j] /= d
    for (let r = 0; r < n; r++) {
      if (r === col) continue
      const f = A[r][col]
      for (let j = 0; j < 2 * n; j++) A[r][j] -= f * A[col][j]
    }
  }
  return A.map(row => row.slice(n))
}

export interface OlsResult { beta: number[]; r2: number; predict: (row: number[]) => number }

// X: rows of feature vectors (no intercept). Intercept added internally.
export function olsFit(X: number[][], y: number[], ridge = 1e-6): OlsResult | null {
  const n = X.length
  if (n < 20) return null
  const k = X[0].length + 1
  const Xd = X.map(r => [1, ...r])
  const XtX: number[][] = Array.from({ length: k }, () => new Array(k).fill(0))
  const Xty: number[] = new Array(k).fill(0)
  for (let i = 0; i < n; i++) {
    for (let a = 0; a < k; a++) {
      Xty[a] += Xd[i][a] * y[i]
      for (let b = 0; b < k; b++) XtX[a][b] += Xd[i][a] * Xd[i][b]
    }
  }
  for (let a = 0; a < k; a++) XtX[a][a] += ridge
  const inv = invert(XtX)
  if (!inv) return null
  const beta = new Array(k).fill(0)
  for (let a = 0; a < k; a++) for (let b = 0; b < k; b++) beta[a] += inv[a][b] * Xty[b]
  const my = y.reduce((s, v) => s + v, 0) / n
  let ssr = 0, sst = 0
  for (let i = 0; i < n; i++) {
    let yhat = 0
    for (let a = 0; a < k; a++) yhat += beta[a] * Xd[i][a]
    ssr += (y[i] - yhat) ** 2
    sst += (y[i] - my) ** 2
  }
  const predict = (row: number[]) => beta[0] + row.reduce((s, v, j) => s + v * beta[j + 1], 0)
  return { beta, r2: sst ? 1 - ssr / sst : 0, predict }
}
