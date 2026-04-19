'use client';

import { StockData, Alert } from '@/lib/stocks';
import { Sparkline } from './Sparkline';

interface StockCardProps {
  stock: StockData;
  sparklineData: { value: number }[];
  portfolioColor: string;
  alerts: Alert[];
  onAddAlert: (symbol: string) => void;
}

function fmt(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return String(n);
}

export function StockCard({ stock, sparklineData, portfolioColor, alerts, onAddAlert }: StockCardProps) {
  const pos = stock.changePercent >= 0;
  const hasAlert = alerts.some((a) => a.symbol === stock.symbol && !a.triggered);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 transition-all duration-200">
      <div className="flex items-start justify-between mb-1">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-white text-sm">{stock.symbol}</span>
            <button
              onClick={() => onAddAlert(stock.symbol)}
              title={hasAlert ? 'Alert active — click to manage' : 'Set price alert'}
              className={`text-xs transition-colors leading-none ${hasAlert ? 'text-yellow-400' : 'text-gray-600 hover:text-gray-400'}`}
            >
              {hasAlert ? '🔔' : '🔕'}
            </button>
          </div>
          <span className="text-gray-500 text-xs truncate block">{stock.name}</span>
        </div>
        <div className="text-right ml-2 shrink-0">
          <div className="text-white font-semibold text-sm">${stock.price.toFixed(2)}</div>
          <div className={`text-xs font-medium ${pos ? 'text-green-400' : 'text-red-400'}`}>
            {pos ? '+' : ''}{stock.change.toFixed(2)} ({pos ? '+' : ''}{stock.changePercent.toFixed(2)}%)
          </div>
        </div>
      </div>

      <div className="my-2">
        <Sparkline data={sparklineData} symbol={stock.symbol} color={portfolioColor} />
      </div>

      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <div className="text-gray-500">
          Day <span className="text-gray-300">${stock.dayLow.toFixed(2)}–${stock.dayHigh.toFixed(2)}</span>
        </div>
        <div className="text-gray-500">
          52W <span className="text-gray-300">${stock.fiftyTwoWeekLow.toFixed(2)}–${stock.fiftyTwoWeekHigh.toFixed(2)}</span>
        </div>
        <div className="text-gray-500">
          Vol <span className="text-gray-300">{fmt(stock.volume)}</span>
        </div>
      </div>
    </div>
  );
}
