import { promises as fs } from 'fs';
import path from 'path';
import EquityChart, { EquityPoint } from './EquityChart';

export const metadata = {
  title: 'Hedge Fund — Paper Account',
  description: 'Agentic hedge fund: regime, positions, watchlist, and track record',
};

interface Position {
  shares: number;
  entry_px: number;
  entry_date: string;
  peak_px?: number;
  stop_px?: number | null;
}

interface Trade {
  symbol: string;
  entry_date: string;
  entry_px: number;
  exit_date: string;
  exit_px: number;
  shares: number;
  pnl: number;
  reason: string;
}

interface Ledger {
  created: string;
  start_equity: number;
  cash: number;
  positions: Record<string, Position>;
  trades: Trade[];
  history: { date: string; equity: number; cash: number; n_positions: number; regime: string }[];
}

interface WatchlistRow {
  symbol: string;
  score: number;
  tier: string;
  category: string;
  trend_gate: boolean;
  asymmetric: boolean;
  rsi: number;
  off_52w_high: number;
}

interface Snapshot {
  as_of: string;
  generated_utc: string;
  stale: boolean;
  regime: { state: string; score: number; multiplier: number; breadth: number };
  equity: number;
  start_equity: number;
  actions: string[];
  positions: Record<string, { shares: number; entry_px: number; last_px: number; unrealized: number }>;
  watchlist: WatchlistRow[];
  asymmetric_setups: string[];
}

async function loadState(): Promise<{ ledger: Ledger; snap: Snapshot }> {
  const base = path.join(process.cwd(), 'trading', 'hedgefund', 'state');
  const [ledgerRaw, snapRaw] = await Promise.all([
    fs.readFile(path.join(base, 'ledger.json'), 'utf-8'),
    fs.readFile(path.join(base, 'dashboard.json'), 'utf-8'),
  ]);
  return { ledger: JSON.parse(ledgerRaw), snap: JSON.parse(snapRaw) };
}

const usd = (v: number) =>
  v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

const REGIME_STYLE: Record<string, { dot: string; text: string }> = {
  RISK_ON: { dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-400' },
  MIXED: { dot: 'bg-amber-500', text: 'text-amber-700 dark:text-amber-400' },
  CAUTION: { dot: 'bg-orange-500', text: 'text-orange-700 dark:text-orange-400' },
  RISK_OFF: { dot: 'bg-red-500', text: 'text-red-700 dark:text-red-400' },
};

function Delta({ value, digits = 1 }: { value: number; digits?: number }) {
  const positive = value >= 0;
  return (
    <span className={positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
      {positive ? '+' : ''}
      {value.toFixed(digits)}%
    </span>
  );
}

function Tile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-1 text-xl font-semibold text-zinc-900 dark:text-zinc-50">{children}</div>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
      <h2 className="mb-4 text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h2>
      {children}
    </section>
  );
}

const th = 'px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400';
const td = 'px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200';

export default async function FundPage() {
  const { ledger, snap } = await loadState();

  const equityHistory: EquityPoint[] = ledger.history.map((h) => ({
    date: h.date,
    equity: h.equity,
    regime: h.regime,
  }));
  const totalReturn = ((snap.equity - snap.start_equity) / snap.start_equity) * 100;
  const cashPct = (ledger.cash / snap.equity) * 100;
  const regimeStyle = REGIME_STYLE[snap.regime.state] ?? REGIME_STYLE.MIXED;
  const closedTrades = [...ledger.trades].reverse().slice(0, 12);
  const wins = ledger.trades.filter((t) => t.pnl > 0).length;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 text-zinc-900 dark:text-zinc-100">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Hedge Fund — Paper Account</h1>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            As of {snap.as_of} · updated nightly after US close
            {snap.stale && ' · ⚠️ data stale'}
          </p>
        </div>
        <div className={`flex items-center gap-2 rounded-full border border-zinc-200 px-3 py-1.5 text-sm font-medium dark:border-zinc-700 ${regimeStyle.text}`}>
          <span className={`h-2 w-2 rounded-full ${regimeStyle.dot}`} />
          {snap.regime.state.replace('_', '-')} · {Math.round(snap.regime.multiplier * 100)}% gross
        </div>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Equity">{usd(snap.equity)}</Tile>
        <Tile label="Total return"><Delta value={totalReturn} digits={2} /></Tile>
        <Tile label="Positions">
          {Object.keys(snap.positions).length}
          <span className="ml-2 text-sm font-normal text-zinc-500 dark:text-zinc-400">{cashPct.toFixed(0)}% cash</span>
        </Tile>
        <Tile label="Breadth">{Math.round(snap.regime.breadth * 100)}%</Tile>
      </div>

      <div className="mb-6">
        <SectionCard title="Equity curve">
          <EquityChart data={equityHistory} startEquity={snap.start_equity} />
        </SectionCard>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <SectionCard title="Open positions">
          {Object.keys(snap.positions).length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">Flat — no open positions.</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800">
                  <th className={th}>Symbol</th>
                  <th className={th}>Entry</th>
                  <th className={th}>Last</th>
                  <th className={th}>Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(snap.positions).map(([sym, p]) => (
                  <tr key={sym} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800/60">
                    <td className={`${td} font-medium`}>{sym}</td>
                    <td className={td}>{p.entry_px.toFixed(2)}</td>
                    <td className={td}>{p.last_px.toFixed(2)}</td>
                    <td className={td}><Delta value={p.unrealized} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {snap.actions.length > 0 && (
            <div className="mt-4 rounded-lg bg-zinc-50 p-3 text-xs text-zinc-600 dark:bg-zinc-800/60 dark:text-zinc-300">
              <div className="mb-1 font-medium">Latest actions</div>
              <ul className="list-inside list-disc space-y-0.5">
                {snap.actions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>

        <SectionCard title={`Closed trades (${ledger.trades.length} total${ledger.trades.length ? `, ${Math.round((wins / ledger.trades.length) * 100)}% wins` : ''})`}>
          {closedTrades.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">No closed trades yet — the track record starts here.</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800">
                  <th className={th}>Symbol</th>
                  <th className={th}>Exit</th>
                  <th className={th}>Reason</th>
                  <th className={th}>P&L</th>
                </tr>
              </thead>
              <tbody>
                {closedTrades.map((t, i) => (
                  <tr key={`${t.symbol}-${t.exit_date}-${i}`} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800/60">
                    <td className={`${td} font-medium`}>{t.symbol}</td>
                    <td className={td}>{t.exit_date}</td>
                    <td className={`${td} text-xs`}>{t.reason.replace(/_/g, ' ')}</td>
                    <td className={`${td} ${t.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
                      {t.pnl >= 0 ? '+' : ''}
                      {usd(t.pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>
      </div>

      <SectionCard title="Conviction watchlist">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800">
                <th className={th}>Symbol</th>
                <th className={th}>Score</th>
                <th className={th}>Tier</th>
                <th className={th}>Category</th>
                <th className={th}>RSI</th>
                <th className={th}>Off 52w high</th>
                <th className={th}>Setup</th>
              </tr>
            </thead>
            <tbody>
              {snap.watchlist.map((w) => (
                <tr key={w.symbol} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800/60">
                  <td className={`${td} font-medium`}>{w.symbol}</td>
                  <td className={td}>
                    <div className="flex items-center gap-2">
                      <span className="w-10 tabular-nums">{w.score.toFixed(1)}</span>
                      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                        <span
                          className="block h-full rounded-full bg-blue-600 dark:bg-blue-400"
                          style={{ width: `${Math.min(w.score, 100)}%` }}
                        />
                      </span>
                    </div>
                  </td>
                  <td className={td}>{w.tier}</td>
                  <td className={`${td} text-xs`}>{w.category.replace(/_/g, ' ')}</td>
                  <td className={`${td} tabular-nums`}>{w.rsi.toFixed(0)}</td>
                  <td className={`${td} tabular-nums`}>{w.off_52w_high.toFixed(1)}%</td>
                  <td className={`${td} text-xs`}>
                    {w.asymmetric ? '⚡ asymmetric' : w.trend_gate ? 'trend intact' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {snap.asymmetric_setups.length > 0 && (
          <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
            ⚡ Asymmetric setups (volatility squeeze + intact trend near highs): {snap.asymmetric_setups.join(', ')}
          </p>
        )}
      </SectionCard>

      <footer className="mt-6 text-xs text-zinc-400 dark:text-zinc-500">
        Paper trading only — validated rules from trading/hedgefund/REPORT.md. Morning reports live in
        trading/hedgefund/reports/.
      </footer>
    </main>
  );
}
