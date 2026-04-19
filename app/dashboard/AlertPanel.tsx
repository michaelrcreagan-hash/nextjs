'use client';

import { useState } from 'react';
import { Alert, StockData, ALL_SYMBOLS } from '@/lib/stocks';

interface AlertPanelProps {
  alerts: Alert[];
  quotes: Record<string, StockData>;
  onAddAlert: (alert: Omit<Alert, 'id' | 'triggered' | 'createdAt'>) => void;
  onRemoveAlert: (id: string) => void;
  defaultSymbol?: string;
}

export function AlertPanel({ alerts, quotes, onAddAlert, onRemoveAlert, defaultSymbol }: AlertPanelProps) {
  const [symbol, setSymbol] = useState(defaultSymbol ?? ALL_SYMBOLS[0]);
  const [type, setType] = useState<'above' | 'below'>('above');
  const [price, setPrice] = useState('');

  const currentPrice = quotes[symbol]?.price;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const targetPrice = parseFloat(price);
    if (!isNaN(targetPrice) && targetPrice > 0) {
      onAddAlert({ symbol, type, targetPrice });
      setPrice('');
    }
  };

  const inputClass =
    'bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30';

  return (
    <div id="alert-panel" className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 className="text-white font-semibold mb-4">Price Alerts</h3>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3 mb-5">
        <div className="flex flex-col gap-1">
          <label className="text-gray-500 text-xs">Symbol</label>
          <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className={inputClass}>
            {ALL_SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-gray-500 text-xs">Condition</label>
          <select value={type} onChange={(e) => setType(e.target.value as 'above' | 'below')} className={inputClass}>
            <option value="above">Price above</option>
            <option value="below">Price below</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-gray-500 text-xs">
            Target Price{currentPrice ? ` (now $${currentPrice.toFixed(2)})` : ''}
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">$</span>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              step="0.01"
              min="0"
              className={`${inputClass} pl-6 w-32`}
            />
          </div>
        </div>

        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
        >
          Add Alert
        </button>
      </form>

      {alerts.length === 0 ? (
        <p className="text-gray-600 text-sm">No alerts configured.</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`flex items-center justify-between px-4 py-2.5 rounded-lg text-sm ${
                alert.triggered
                  ? 'bg-yellow-400/10 border border-yellow-400/30'
                  : 'bg-gray-800 border border-gray-700/50'
              }`}
            >
              <div className="flex items-center gap-3">
                {alert.triggered && <span>⚡</span>}
                <span className="font-semibold text-white">{alert.symbol}</span>
                <span className="text-gray-400">
                  {alert.type === 'above' ? '↑ above' : '↓ below'} ${alert.targetPrice.toFixed(2)}
                </span>
                {alert.triggered && (
                  <span className="text-yellow-400 text-xs font-semibold tracking-wide">TRIGGERED</span>
                )}
              </div>
              <button
                onClick={() => onRemoveAlert(alert.id)}
                className="text-gray-600 hover:text-red-400 transition-colors text-xs ml-4 shrink-0"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
