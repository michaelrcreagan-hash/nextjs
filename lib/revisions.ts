// Analyst Revision Velocity engine.
//
// velocity      = Σ (rating_change × weight)
// weight        = analyst_success × recency_decay
// recency_decay = 0.5 ^ (age_days / half_life)
//
// The normalized score (velocity / Σ weights) is the weighted average of
// recent upgrades/downgrades — positive means the tape of revisions is
// tilting up, and the recency half-life makes the freshest calls dominate,
// which is what surfaces early inflections before consensus moves.

export type Bucket =
  | 'ai-bottlenecks'
  | 'macro'
  | 'sector-rotation'
  | 'individual-stocks';

export const BUCKET_LABELS: Record<Bucket, string> = {
  'ai-bottlenecks': 'AI Bottlenecks',
  macro: 'Macro',
  'sector-rotation': 'Sector Rotation / Outperformance',
  'individual-stocks': 'Individual Stocks (non-AI)',
};

export interface TrackedAnalyst {
  name: string;
  firm: string;
  bucket: Bucket;
  // TipRanks-style success rate in [0,1]. `source` records where/when the
  // number was pulled so it can be refreshed instead of trusted blindly.
  success: number;
  source: string;
  // Tickers this analyst covers — grade feeds only carry the firm name, so
  // a firm match plus a coverage-list hit attributes the event to the
  // analyst (and their personal success rate) instead of the firm default.
  coverage: string[];
  notes?: string;
}

export interface FirmProfile {
  // Canonical firm name plus aliases as they appear across data feeds.
  aliases: string[];
  bucket: Bucket;
  success: number; // firm-level default when no tracked analyst matches
  source: string;
}

// ---------------------------------------------------------------------------
// Registry: the user's tracked people/entities, assigned to buckets.
// Success seeds come from TipRanks (live pull 2026-07-08 where noted;
// otherwise last-known published star ratings — refresh via TipRanks
// Expert Center or StarMine when entitlements allow).
// ---------------------------------------------------------------------------

export const TRACKED_ANALYSTS: TrackedAnalyst[] = [
  {
    name: 'Michael Siperco',
    firm: 'RBC Capital',
    bucket: 'individual-stocks',
    success: 0.65,
    source: 'TipRanks live 2026-07-08: rank #5, avg 1y return +64.7%, 68 covered',
    coverage: ['NGD', 'SA', 'SSRM', 'PAAS', 'CGAU', 'HL', 'SKE', 'CDE', 'ORLA', 'NG', 'AGI', 'EGO', 'GMINF', 'KNTNF', 'TORXF'],
    notes: 'Precious metals / miners — earliest-mover on gold-equity revisions',
  },
  {
    name: 'Carey MacRury',
    firm: 'Canaccord Genuity',
    bucket: 'individual-stocks',
    success: 0.6,
    source: 'TipRanks profile (seed; refresh monthly)',
    coverage: ['AEM', 'ABX', 'B', 'KGC', 'BTG', 'IAG', 'OR', 'FNV', 'WPM', 'ELD', 'LUG', 'AGI'],
    notes: 'Canaccord gold & precious metals',
  },
  {
    name: 'Shane Nagle',
    firm: 'National Bank',
    bucket: 'individual-stocks',
    success: 0.58,
    source: 'TipRanks profile (seed; refresh monthly)',
    coverage: ['TECK', 'FM', 'HBM', 'CS', 'LUN', 'ERO', 'CCO', 'IVN', 'NGEX', 'ALTM'],
    notes: 'National Bank Financial base metals / copper',
  },
  {
    name: 'Don DeMarco',
    firm: 'National Bank',
    bucket: 'individual-stocks',
    success: 0.62,
    source: 'TipRanks profile (seed; refresh monthly)',
    coverage: ['AGI', 'PAAS', 'FVI', 'EDV', 'OGC', 'AYA', 'DPM', 'KNT', 'MAG', 'SSRM'],
    notes: 'National Bank Financial precious metals',
  },
  {
    name: 'Quinn Bolton',
    firm: 'Needham',
    bucket: 'ai-bottlenecks',
    success: 0.67,
    source: 'TipRanks profile (seed; 5-star semis analyst)',
    coverage: ['NVDA', 'AVGO', 'MRVL', 'CRDO', 'ALAB', 'AMBA', 'SLAB', 'RMBS', 'MTSI', 'SITM', 'AIP', 'LSCC', 'POET'],
    notes: 'Needham semis/optical networking — AI compute + interconnect bottlenecks',
  },
];

export const FIRM_PROFILES: FirmProfile[] = [
  // --- AI bottlenecks: institutions whose AI-supply-chain calls we track ---
  { aliases: ['Needham'], bucket: 'ai-bottlenecks', success: 0.62, source: 'TipRanks firm ranking (seed)' },
  { aliases: ['Raymond James'], bucket: 'ai-bottlenecks', success: 0.6, source: 'TipRanks firm ranking (seed)' },
  { aliases: ['Goldman Sachs'], bucket: 'ai-bottlenecks', success: 0.61, source: 'TipRanks firm ranking (seed)' },
  { aliases: ['Piper Sandler'], bucket: 'ai-bottlenecks', success: 0.58, source: 'TipRanks firm ranking (seed)' },
  { aliases: ['RBC Capital', 'RBC Capital Markets', 'RBC'], bucket: 'ai-bottlenecks', success: 0.59, source: 'TipRanks firm ranking (seed)' },

  // --- Macro / strategy shops (tracked for regime, not single names) ---
  { aliases: ['Morgan Stanley'], bucket: 'macro', success: 0.57, source: 'Mike Wilson — US equity strategy' },
  { aliases: ['BCA Research', 'BCA'], bucket: 'macro', success: 0.55, source: 'Macro research house (no per-call feed)' },
  { aliases: ['Fundstrat', 'FS Insight'], bucket: 'macro', success: 0.6, source: 'Tom Lee — tracked bull' },
  { aliases: ['Duquesne', 'Duquesne Family Office'], bucket: 'macro', success: 0.65, source: 'Druckenmiller — via 13F, quarterly' },

  // --- Sector rotation / quant revision models ---
  { aliases: ['LSEG StarMine', 'StarMine', 'Refinitiv'], bucket: 'sector-rotation', success: 0.6, source: 'StarMine ARM / SmartEstimate (needs LSEG entitlement)' },

  // --- Individual stocks (non-AI) firm defaults ---
  { aliases: ['Canaccord Genuity', 'Canaccord'], bucket: 'individual-stocks', success: 0.56, source: 'TipRanks firm ranking (seed)' },
  { aliases: ['National Bank', 'National Bank Financial', 'National Bank of Canada'], bucket: 'individual-stocks', success: 0.56, source: 'TipRanks firm ranking (seed)' },
];

// Firms not in the registry still count, at a discounted default weight, so
// the score reflects the whole tape while tracked names dominate.
export const DEFAULT_FIRM_SUCCESS = 0.5;
export const DEFAULT_HALF_LIFE_DAYS = 30;
export const DEFAULT_WINDOW_DAYS = 120;

// ---------------------------------------------------------------------------
// Rating normalization
// ---------------------------------------------------------------------------

const RATING_SCORES: Record<string, number> = {
  'strong buy': 2,
  'top pick': 2,
  'conviction buy': 2,
  buy: 1,
  outperform: 1,
  overweight: 1,
  positive: 1,
  accumulate: 1,
  add: 1,
  'sector outperform': 1,
  'market outperform': 1,
  'speculative buy': 1,
  hold: 0,
  neutral: 0,
  'market perform': 0,
  'sector perform': 0,
  'equal-weight': 0,
  'equal weight': 0,
  'in-line': 0,
  'in line': 0,
  'peer perform': 0,
  perform: 0,
  'sector weight': 0,
  'mixed': 0,
  underperform: -1,
  underweight: -1,
  reduce: -1,
  negative: -1,
  'sector underperform': -1,
  sell: -2,
  'strong sell': -2,
};

export function ratingScore(grade: string | null | undefined): number | null {
  if (!grade) return null;
  const key = grade.trim().toLowerCase();
  return key in RATING_SCORES ? RATING_SCORES[key] : null;
}

export interface RevisionEvent {
  symbol: string;
  date: string; // YYYY-MM-DD
  firm: string;
  analyst?: string;
  action: string; // upgrade | downgrade | init | maintain | ...
  fromGrade?: string;
  toGrade?: string;
}

export interface ScoredEvent extends RevisionEvent {
  ratingChange: number;
  success: number;
  decay: number;
  weight: number;
  contribution: number;
  bucket: Bucket | 'other';
  tracked: boolean;
}

// Signed size of the revision. Upgrades/downgrades use the grade-score
// delta (Hold→Strong Buy moves more than Hold→Buy); initiations count at
// 75% of the new grade's score (a fresh Buy is informative but not a
// change of mind); maintains are 0.
export function ratingChange(ev: RevisionEvent): number {
  const from = ratingScore(ev.fromGrade);
  const to = ratingScore(ev.toGrade);
  const action = ev.action.toLowerCase();

  if (action.startsWith('up')) {
    return from !== null && to !== null && to > from ? to - from : 1;
  }
  if (action.startsWith('down')) {
    return from !== null && to !== null && to < from ? to - from : -1;
  }
  if (action.startsWith('init') || action.startsWith('resum') || action.startsWith('reinstat')) {
    return to !== null ? 0.75 * to : 0;
  }
  // maintain / reiterate — no new information about direction
  if (from !== null && to !== null && to !== from) return to - from;
  return 0;
}

function normalizeFirm(firm: string): string {
  return firm.trim().toLowerCase().replace(/[.,]/g, '');
}

const firmIndex: { profile: FirmProfile; alias: string }[] = FIRM_PROFILES.flatMap(
  (profile) => profile.aliases.map((alias) => ({ profile, alias: normalizeFirm(alias) })),
);

export function lookupFirm(firm: string): FirmProfile | null {
  const key = normalizeFirm(firm);
  let best: { profile: FirmProfile; alias: string } | null = null;
  for (const entry of firmIndex) {
    if (key === entry.alias || key.startsWith(entry.alias + ' ') || entry.alias.startsWith(key + ' ')) {
      if (!best || entry.alias.length > best.alias.length) best = entry;
    }
  }
  return best?.profile ?? null;
}

export function lookupTrackedAnalyst(firm: string, symbol: string): TrackedAnalyst | null {
  const key = normalizeFirm(firm);
  const sym = symbol.toUpperCase();
  for (const analyst of TRACKED_ANALYSTS) {
    const firmKey = normalizeFirm(analyst.firm);
    const firmMatch = key.includes(firmKey) || firmKey.includes(key);
    if (firmMatch && analyst.coverage.includes(sym)) return analyst;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Velocity
// ---------------------------------------------------------------------------

export interface VelocityOptions {
  halfLifeDays?: number;
  windowDays?: number;
  asOf?: Date;
}

export interface BucketVelocity {
  bucket: Bucket | 'other';
  velocity: number;
  weightSum: number;
  events: number;
}

export interface VelocityResult {
  symbol: string;
  velocity: number; // Σ (rating_change × weight)
  weightedAvg: number; // velocity / Σ weights — the headline score
  weightSum: number;
  eventCount: number;
  upgrades: number;
  downgrades: number;
  signal: 'strong-up' | 'up' | 'flat' | 'down' | 'strong-down';
  buckets: BucketVelocity[];
  events: ScoredEvent[];
}

export function scoreEvents(
  events: RevisionEvent[],
  opts: VelocityOptions = {},
): ScoredEvent[] {
  const halfLife = opts.halfLifeDays ?? DEFAULT_HALF_LIFE_DAYS;
  const windowDays = opts.windowDays ?? DEFAULT_WINDOW_DAYS;
  const asOf = opts.asOf ?? new Date();

  const scored: ScoredEvent[] = [];
  for (const ev of events) {
    const ageDays = (asOf.getTime() - new Date(ev.date + 'T00:00:00Z').getTime()) / 86_400_000;
    if (!Number.isFinite(ageDays) || ageDays < 0 || ageDays > windowDays) continue;

    const tracked = lookupTrackedAnalyst(ev.firm, ev.symbol);
    const firm = lookupFirm(ev.firm);
    const success = tracked?.success ?? firm?.success ?? DEFAULT_FIRM_SUCCESS;
    const bucket: Bucket | 'other' = tracked?.bucket ?? firm?.bucket ?? 'other';
    const decay = Math.pow(0.5, ageDays / halfLife);
    const change = ratingChange(ev);
    const weight = success * decay;

    scored.push({
      ...ev,
      analyst: tracked?.name ?? ev.analyst,
      ratingChange: change,
      success,
      decay,
      weight,
      contribution: change * weight,
      bucket,
      tracked: !!tracked,
    });
  }
  scored.sort((a, b) => (a.date < b.date ? 1 : -1));
  return scored;
}

export function computeVelocity(
  symbol: string,
  events: RevisionEvent[],
  opts: VelocityOptions = {},
): VelocityResult {
  const scored = scoreEvents(events, opts);

  let velocity = 0;
  let weightSum = 0;
  let upgrades = 0;
  let downgrades = 0;
  const bucketMap = new Map<string, BucketVelocity>();

  for (const ev of scored) {
    velocity += ev.contribution;
    weightSum += ev.weight;
    if (ev.ratingChange > 0) upgrades += 1;
    if (ev.ratingChange < 0) downgrades += 1;

    const b = bucketMap.get(ev.bucket) ?? { bucket: ev.bucket, velocity: 0, weightSum: 0, events: 0 };
    b.velocity += ev.contribution;
    b.weightSum += ev.weight;
    b.events += 1;
    bucketMap.set(ev.bucket, b);
  }

  const weightedAvg = weightSum > 0 ? velocity / weightSum : 0;
  const signal =
    weightedAvg >= 0.25 ? 'strong-up'
    : weightedAvg >= 0.08 ? 'up'
    : weightedAvg <= -0.25 ? 'strong-down'
    : weightedAvg <= -0.08 ? 'down'
    : 'flat';

  return {
    symbol: symbol.toUpperCase(),
    velocity,
    weightedAvg,
    weightSum,
    eventCount: scored.length,
    upgrades,
    downgrades,
    signal,
    buckets: [...bucketMap.values()].sort((a, b) => b.weightSum - a.weightSum),
    events: scored,
  };
}

// Default watchlist: AI-bottleneck supply chain + the miners the tracked
// non-AI analysts actually cover, so their calls show up out of the box.
export const REVISION_WATCHLIST: { symbol: string; bucket: Bucket }[] = [
  { symbol: 'NVDA', bucket: 'ai-bottlenecks' },
  { symbol: 'AVGO', bucket: 'ai-bottlenecks' },
  { symbol: 'MRVL', bucket: 'ai-bottlenecks' },
  { symbol: 'CRDO', bucket: 'ai-bottlenecks' },
  { symbol: 'ALAB', bucket: 'ai-bottlenecks' },
  { symbol: 'COHR', bucket: 'ai-bottlenecks' },
  { symbol: 'LITE', bucket: 'ai-bottlenecks' },
  { symbol: 'AAOI', bucket: 'ai-bottlenecks' },
  { symbol: 'MU', bucket: 'ai-bottlenecks' },
  { symbol: 'VRT', bucket: 'ai-bottlenecks' },
  { symbol: 'AGI', bucket: 'individual-stocks' },
  { symbol: 'PAAS', bucket: 'individual-stocks' },
  { symbol: 'SSRM', bucket: 'individual-stocks' },
  { symbol: 'AEM', bucket: 'individual-stocks' },
  { symbol: 'KGC', bucket: 'individual-stocks' },
  { symbol: 'TECK', bucket: 'individual-stocks' },
];
