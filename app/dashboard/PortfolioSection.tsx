'use client';

import { Portfolio, StockData, HistoricalPoint, Alert } from '@/lib/stocks';
import { StockCard } from './StockCard';

interface PortfolioSectionProps {
  portfolio: Portfolio;
  quotes: Record<string, StockData>;
  history: Record<string, HistoricalPoint[]>;
  alerts: Alert[];
  onAddAlert: (symbol: string) => void;
}

export function PortfolioSection({ portfolio, quotes, history, alerts, onAddAlert }: PortfolioSectionProps) {
  const loaded = portfolio.symbols.map((s) => quotes[s]).filter(Boolean);
  const avgChange =
    loaded.length > 0
      ? loaded.reduce((acc, s) => acc + s.changePercent, 0) / loaded.length
      : null;

  return (
    <section>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: portfolio.hexColor }}
            />
            {portfolio.name}
          </h2>
          <p className="text-gray-500 text-xs mt-0.5 pl-4">{portfolio.description}</p>
        </div>
        {avgChange !== null && (
          <div
            className={`text-xs font-semibold px-3 py-1 rounded-full shrink-0 ${
              avgChange >= 0 ? 'text-green-400 bg-green-400/10' : 'text-red-400 bg-red-400/10'
            }`}
          >
            {avgChange >= 0 ? '+' : ''}{avgChange.toFixed(2)}% avg today
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {portfolio.symbols.map((symbol) => {
          const stock = quotes[symbol];
          const sparkline = (history[symbol] ?? []).map((p) => ({ value: p.close }));

          if (!stock) {
            return (
              <div key={symbol} className="bg-gray-900 border border-gray-800 rounded-xl p-4 animate-pulse">
                <div className="h-3 bg-gray-700 rounded w-1/2 mb-1.5" />
                <div className="h-2.5 bg-gray-800 rounded w-3/4 mb-3" />
                <div className="h-12 bg-gray-800 rounded mb-3" />
                <div className="h-2 bg-gray-800 rounded w-full mb-1" />
                <div className="h-2 bg-gray-800 rounded w-2/3" />
              </div>
            );
          }

          return (
            <StockCard
              key={symbol}
              stock={stock}
              sparklineData={sparkline}
              portfolioColor={portfolio.hexColor}
              alerts={alerts}
              onAddAlert={onAddAlert}
            />
          );
        })}
      </div>
    </section>
  );
}
