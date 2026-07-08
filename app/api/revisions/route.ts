import { NextRequest, NextResponse } from 'next/server';
import { RevisionEvent, computeVelocity, DEFAULT_WINDOW_DAYS, DEFAULT_HALF_LIFE_DAYS } from '@/lib/revisions';

export const dynamic = 'force-dynamic';

const UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// --- Provider 1: Financial Modeling Prep (needs FMP_API_KEY) ---------------

async function fetchFmp(symbol: string): Promise<RevisionEvent[] | null> {
  const key = process.env.FMP_API_KEY;
  if (!key) return null;
  const url = `https://financialmodelingprep.com/stable/grades?symbol=${encodeURIComponent(symbol)}&apikey=${key}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) return null;
  const rows = (await res.json()) as {
    symbol: string;
    date: string;
    gradingCompany: string;
    previousGrade: string;
    newGrade: string;
    action: string;
  }[];
  if (!Array.isArray(rows)) return null;
  return rows.map((r) => ({
    symbol: r.symbol,
    date: r.date,
    firm: r.gradingCompany,
    action: r.action,
    fromGrade: r.previousGrade,
    toGrade: r.newGrade,
  }));
}

// --- Provider 2: Yahoo Finance upgradeDowngradeHistory (keyless) -----------

let yahooCrumb: { cookie: string; crumb: string; fetchedAt: number } | null = null;

async function getYahooCrumb(): Promise<{ cookie: string; crumb: string } | null> {
  if (yahooCrumb && Date.now() - yahooCrumb.fetchedAt < 30 * 60_000) return yahooCrumb;
  try {
    const cookieRes = await fetch('https://fc.yahoo.com', {
      headers: { 'User-Agent': UA },
      redirect: 'manual',
      cache: 'no-store',
    });
    const cookie = cookieRes.headers.get('set-cookie')?.split(';')[0] ?? '';
    if (!cookie) return null;
    const crumbRes = await fetch('https://query1.finance.yahoo.com/v1/test/getcrumb', {
      headers: { 'User-Agent': UA, Cookie: cookie },
      cache: 'no-store',
    });
    if (!crumbRes.ok) return null;
    const crumb = (await crumbRes.text()).trim();
    if (!crumb || crumb.includes('Too Many Requests')) return null;
    yahooCrumb = { cookie, crumb, fetchedAt: Date.now() };
    return yahooCrumb;
  } catch {
    return null;
  }
}

async function fetchYahoo(symbol: string): Promise<RevisionEvent[] | null> {
  const auth = await getYahooCrumb();
  const base = `https://query2.finance.yahoo.com/v10/finance/quoteSummary/${encodeURIComponent(symbol)}?modules=upgradeDowngradeHistory`;
  const url = auth ? `${base}&crumb=${encodeURIComponent(auth.crumb)}` : base;
  const res = await fetch(url, {
    headers: { 'User-Agent': UA, ...(auth ? { Cookie: auth.cookie } : {}) },
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const data = await res.json();
  const history =
    data?.quoteSummary?.result?.[0]?.upgradeDowngradeHistory?.history ?? null;
  if (!Array.isArray(history)) return null;
  return history.map((h: { epochGradeDate: number; firm: string; toGrade: string; fromGrade: string; action: string }) => ({
    symbol,
    date: new Date(h.epochGradeDate * 1000).toISOString().slice(0, 10),
    firm: h.firm,
    action: h.action, // up | down | init | main | reit
    fromGrade: h.fromGrade,
    toGrade: h.toGrade,
  }));
}

async function fetchEvents(symbol: string): Promise<{ events: RevisionEvent[]; provider: string } | null> {
  try {
    const fmp = await fetchFmp(symbol);
    if (fmp && fmp.length) return { events: fmp, provider: 'fmp' };
  } catch {
    // fall through to Yahoo
  }
  try {
    const yahoo = await fetchYahoo(symbol);
    if (yahoo && yahoo.length) return { events: yahoo, provider: 'yahoo' };
  } catch {
    // both providers down
  }
  return null;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const symbols = (searchParams.get('symbols') || '')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 24);
  const windowDays = Number(searchParams.get('days')) || DEFAULT_WINDOW_DAYS;
  const halfLifeDays = Number(searchParams.get('halfLife')) || DEFAULT_HALF_LIFE_DAYS;

  if (!symbols.length) {
    return NextResponse.json({ error: 'symbols query param required' }, { status: 400 });
  }

  const results = await Promise.all(
    symbols.map(async (symbol) => {
      const fetched = await fetchEvents(symbol);
      if (!fetched) return { symbol, error: 'no data from any provider' };
      const result = computeVelocity(symbol, fetched.events, { windowDays, halfLifeDays });
      // Cap the event list per symbol to keep payloads sane.
      return { ...result, events: result.events.slice(0, 40), provider: fetched.provider };
    }),
  );

  return NextResponse.json({
    asOf: new Date().toISOString(),
    windowDays,
    halfLifeDays,
    results,
  });
}
