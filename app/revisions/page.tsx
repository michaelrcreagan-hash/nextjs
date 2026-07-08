'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BUCKET_LABELS,
  Bucket,
  REVISION_WATCHLIST,
  TRACKED_ANALYSTS,
  FIRM_PROFILES,
  ScoredEvent,
  VelocityResult,
} from '@/lib/revisions';

interface ApiSymbolResult extends Partial<VelocityResult> {
  symbol: string;
  provider?: string;
  error?: string;
}

interface ApiResponse {
  asOf: string;
  windowDays: number;
  halfLifeDays: number;
  results: ApiSymbolResult[];
}

const REFRESH_INTERVAL = 5 * 60_000; // ratings tape moves slower than quotes

const SIGNAL_STYLE: Record<string, { label: string; className: string }> = {
  'strong-up': { label: 'STRONG UP', className: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' },
  up: { label: 'UP', className: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  flat: { label: 'FLAT', className: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20' },
  down: { label: 'DOWN', className: 'bg-red-500/10 text-red-400 border-red-500/20' },
  'strong-down': { label: 'STRONG DOWN', className: 'bg-red-500/20 text-red-300 border-red-500/40' },
};

const BUCKET_COLORS: Record<string, string> = {
  'ai-bottlenecks': '#a855f7',
  macro: '#3b82f6',
  'sector-rotation': '#f59e0b',
  'individual-stocks': '#10b981',
  other: '#71717a',
};

function fmt(n: number | undefined, digits = 2): string {
  if (n === undefined || !Number.isFinite(n)) return '—';
  return (n >= 0 ? '+' : '') + n.toFixed(digits);
}

export default function RevisionsPage() {
  const defaultSymbols = useMemo(() => REVISION_WATCHLIST.map((w) => w.symbol).join(','), []);
  const [symbolsInput, setSymbolsInput] = useState(defaultSymbols);
  const [activeSymbols, setActiveSymbols] = useState(defaultSymbols);
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async (symbols: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/revisions?symbols=${encodeURIComponent(symbols)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = (await res.json()) as ApiResponse;
      setData(json);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(activeSymbols);
    const id = setInterval(() => load(activeSymbols), REFRESH_INTERVAL);
    return () => clearInterval(id);
  }, [activeSymbols, load]);

  const ranked = useMemo(() => {
    const rows = (data?.results ?? []).filter((r) => !r.error) as (VelocityResult & { provider?: string })[];
    return [...rows].sort((a, b) => (b.weightedAvg ?? 0) - (a.weightedAvg ?? 0));
  }, [data]);

  const failed = useMemo(() => (data?.results ?? []).filter((r) => r.error), [data]);

  const selectedResult = ranked.find((r) => r.symbol === selected) ?? ranked[0];

  const bucketRollup = useMemo(() => {
    const map = new Map<string, { velocity: number; weightSum: number; events: number }>();
    for (const r of ranked) {
      for (const b of r.buckets ?? []) {
        const cur = map.get(b.bucket) ?? { velocity: 0, weightSum: 0, events: 0 };
        cur.velocity += b.velocity;
        cur.weightSum += b.weightSum;
        cur.events += b.events;
        map.set(b.bucket, cur);
      }
    }
    return [...map.entries()]
      .map(([bucket, v]) => ({ bucket, ...v, wavg: v.weightSum > 0 ? v.velocity / v.weightSum : 0 }))
      .sort((a, b) => b.weightSum - a.weightSum);
  }, [ranked]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Analyst Revision Velocity</h1>
            <p className="text-sm text-zinc-400 mt-1">
              velocity = Σ (rating change × weight) · weight = success% × 0.5^(age/{data?.halfLifeDays ?? 30}d) ·
              window {data?.windowDays ?? 120}d · live via {ranked[0]?.provider === 'fmp' ? 'FMP' : 'Yahoo Finance'}
            </p>
          </div>
          <div className="text-right text-xs text-zinc-500">
            {data && <div>as of {new Date(data.asOf).toLocaleTimeString()}</div>}
            <div>auto-refresh 5m</div>
          </div>
        </header>

        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setActiveSymbols(symbolsInput.toUpperCase());
          }}
        >
          <input
            value={symbolsInput}
            onChange={(e) => setSymbolsInput(e.target.value)}
            placeholder="Comma-separated tickers"
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-zinc-600"
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg bg-zinc-100 text-zinc-900 text-sm font-semibold hover:bg-white"
          >
            Scan
          </button>
        </form>

        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 px-4 py-3 text-sm">
            {error}
          </div>
        )}
        {failed.length > 0 && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 px-4 py-2 text-xs">
            No provider data for: {failed.map((f) => f.symbol).join(', ')}
          </div>
        )}

        {/* Bucket rollup */}
        <section className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {bucketRollup.map((b) => (
            <div key={b.bucket} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-4">
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <span className="w-2 h-2 rounded-full" style={{ background: BUCKET_COLORS[b.bucket] ?? '#71717a' }} />
                {BUCKET_LABELS[b.bucket as Bucket] ?? 'Other Firms'}
              </div>
              <div className={`text-xl font-bold mt-1 ${b.wavg > 0.05 ? 'text-emerald-400' : b.wavg < -0.05 ? 'text-red-400' : 'text-zinc-300'}`}>
                {fmt(b.wavg)}
              </div>
              <div className="text-[11px] text-zinc-500">{b.events} events · Σw {b.weightSum.toFixed(1)}</div>
            </div>
          ))}
        </section>

        <div className="grid lg:grid-cols-5 gap-6">
          {/* Ranking table */}
          <section className="lg:col-span-3 rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800 text-sm font-semibold">
              Velocity ranking {loading && <span className="text-zinc-500 font-normal">· refreshing…</span>}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase text-zinc-500">
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-4 py-2">Symbol</th>
                    <th className="text-right px-2 py-2">Wtd avg</th>
                    <th className="text-right px-2 py-2">Raw Σ</th>
                    <th className="text-right px-2 py-2">Up / Down</th>
                    <th className="text-right px-2 py-2">Events</th>
                    <th className="text-right px-4 py-2">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((r) => {
                    const sig = SIGNAL_STYLE[r.signal ?? 'flat'];
                    return (
                      <tr
                        key={r.symbol}
                        onClick={() => setSelected(r.symbol)}
                        className={`border-b border-zinc-800/50 cursor-pointer hover:bg-zinc-800/40 ${selectedResult?.symbol === r.symbol ? 'bg-zinc-800/60' : ''}`}
                      >
                        <td className="px-4 py-2 font-mono font-semibold">{r.symbol}</td>
                        <td className={`px-2 py-2 text-right font-mono ${(r.weightedAvg ?? 0) > 0 ? 'text-emerald-400' : (r.weightedAvg ?? 0) < 0 ? 'text-red-400' : 'text-zinc-400'}`}>
                          {fmt(r.weightedAvg)}
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-zinc-400">{fmt(r.velocity)}</td>
                        <td className="px-2 py-2 text-right font-mono">
                          <span className="text-emerald-400">{r.upgrades}</span>
                          <span className="text-zinc-600"> / </span>
                          <span className="text-red-400">{r.downgrades}</span>
                        </td>
                        <td className="px-2 py-2 text-right text-zinc-400">{r.eventCount}</td>
                        <td className="px-4 py-2 text-right">
                          <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded border ${sig.className}`}>
                            {sig.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {!ranked.length && !loading && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
                        No data. Providers may be rate-limiting — set FMP_API_KEY for the primary feed.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {/* Event tape for selected symbol */}
          <section className="lg:col-span-2 rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800 text-sm font-semibold">
              {selectedResult ? `${selectedResult.symbol} revision tape` : 'Revision tape'}
            </div>
            <div className="max-h-[480px] overflow-y-auto divide-y divide-zinc-800/50">
              {(selectedResult?.events ?? []).map((ev: ScoredEvent, i: number) => (
                <div key={i} className="px-4 py-2.5 text-xs">
                  <div className="flex justify-between gap-2">
                    <span className={`font-semibold ${ev.tracked ? 'text-amber-300' : 'text-zinc-200'}`}>
                      {ev.tracked ? `★ ${ev.analyst} · ` : ''}{ev.firm}
                    </span>
                    <span className="text-zinc-500 shrink-0">{ev.date}</span>
                  </div>
                  <div className="flex justify-between gap-2 mt-0.5">
                    <span className="text-zinc-400">
                      {ev.action}
                      {ev.fromGrade && ev.toGrade && ev.fromGrade !== ev.toGrade
                        ? `: ${ev.fromGrade} → ${ev.toGrade}`
                        : ev.toGrade
                          ? `: ${ev.toGrade}`
                          : ''}
                    </span>
                    <span className={`font-mono shrink-0 ${ev.contribution > 0 ? 'text-emerald-400' : ev.contribution < 0 ? 'text-red-400' : 'text-zinc-500'}`}>
                      {fmt(ev.contribution, 3)}
                    </span>
                  </div>
                </div>
              ))}
              {!selectedResult?.events?.length && (
                <div className="px-4 py-8 text-center text-zinc-500 text-sm">Select a symbol</div>
              )}
            </div>
          </section>
        </div>

        {/* Tracked roster */}
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 overflow-hidden">
          <div className="px-4 py-3 border-b border-zinc-800 text-sm font-semibold">Tracked analysts & institutions</div>
          <div className="grid md:grid-cols-2 divide-y md:divide-y-0 divide-zinc-800/50">
            <div className="p-4 space-y-2">
              {TRACKED_ANALYSTS.map((a) => (
                <div key={a.name} className="flex items-start justify-between gap-3 text-xs">
                  <div>
                    <span className="font-semibold text-amber-300">★ {a.name}</span>
                    <span className="text-zinc-500"> · {a.firm}</span>
                    {a.notes && <div className="text-zinc-500">{a.notes}</div>}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="font-mono">{(a.success * 100).toFixed(0)}%</div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-zinc-700" style={{ color: BUCKET_COLORS[a.bucket] }}>
                      {BUCKET_LABELS[a.bucket]}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 space-y-1.5">
              {FIRM_PROFILES.map((f) => (
                <div key={f.aliases[0]} className="flex items-center justify-between gap-3 text-xs">
                  <span className="text-zinc-300">{f.aliases[0]}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="font-mono text-zinc-400">{(f.success * 100).toFixed(0)}%</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-zinc-700" style={{ color: BUCKET_COLORS[f.bucket] }}>
                      {BUCKET_LABELS[f.bucket]}
                    </span>
                  </div>
                </div>
              ))}
              <p className="text-[11px] text-zinc-600 pt-2">
                Success seeds from TipRanks (Siperco verified live 2026-07-08). StarMine ARM / SmartEstimate need an
                LSEG entitlement — slots reserved in the registry. Untracked firms count at 50% weight.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
