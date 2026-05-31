'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { PORTFOLIOS, ALL_SYMBOLS, StockData, HistoricalPoint, Alert, MOCK_QUOTES } from '@/lib/stocks';
import { PortfolioSection } from './PortfolioSection';
import { PerformanceChart } from './PerformanceChart';
import { AlertPanel } from './AlertPanel';

type QuoteRecord = Record<string, StockData>;
type HistoryRecord = Record<string, HistoricalPoint[]>;

function parseQuotes(data: unknown): QuoteRecord | null {
  try {
    const quotes = (data as { quoteResponse: { result: Record<string, unknown>[] } }).quoteResponse?.result ?? [];
    if (!quotes.length) return null;
    const result: QuoteRecord = {};
    for (const q of quotes) {
      const sym = q.symbol as string;
      result[sym] = {
        symbol: sym,
        name: (q.shortName as string) || sym,
        price: (q.regularMarketPrice as number) ?? 0,
        change: (q.regularMarketChange as number) ?? 0,
        changePercent: (q.regularMarketChangePercent as number) ?? 0,
        volume: (q.regularMarketVolume as number) ?? 0,
        dayHigh: (q.regularMarketDayHigh as number) ?? 0,
        dayLow: (q.regularMarketDayLow as number) ?? 0,
        fiftyTwoWeekHigh: (q.fiftyTwoWeekHigh as number) ?? 0,
        fiftyTwoWeekLow: (q.fiftyTwoWeekLow as number) ?? 0,
      };
    }
    return result;
  } catch {
    return null;
  }
}

function parseHistory(data: unknown): HistoricalPoint[] {
  try {
    const result = (data as { chart: { result: { timestamp: number[]; indicators: { quote: { close: number[] }[] } }[] } }).chart?.result?.[0];
    if (!result) return [];
    const timestamps = result.timestamp ?? [];
    const closes = result.indicators?.quote?.[0]?.close ?? [];
    return timestamps
      .map((ts, i) => ({
        date: new Date(ts * 1000).toISOString().split('T')[0],
        close: closes[i] ?? 0,
      }))
      .filter((p) => p.close > 0);
  } catch {
    return [];
  }
}

function isMarketOpen(): boolean {
  const now = new Date();
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const day = et.getDay();
  const hours = et.getHours() + et.getMinutes() / 60;
  return day >= 1 && day <= 5 && hours >= 9.5 && hours < 16;
}

const REFRESH_INTERVAL = 30_000;
const COUNTDOWN_STEP = 1_000;

export default function DashboardPage() {
  const [quotes, setQuotes] = useState<QuoteRecord>({});
  const [history, setHistory] = useState<HistoryRecord>({});
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFetching, setIsFetching] = useState(false);
  const [useMock, setUseMock] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL / 1000);
  const [triggeredMsgs, setTriggeredMsgs] = useState<string[]>([]);
  const [alertSymbol, setAlertSymbol] = useState<string | undefined>();
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const checkAlerts = useCallback((newQuotes: QuoteRecord, currentAlerts: Alert[]) => {
    const msgs: string[] = [];
    const updated = currentAlerts.map((alert) => {
      if (alert.triggered) return alert;
      const price = newQuotes[alert.symbol]?.price;
      if (!price) return alert;
      const hit =
        (alert.type === 'above' && price >= alert.targetPrice) ||
        (alert.type === 'below' && price <= alert.targetPrice);
      if (hit) {
        msgs.push(
          `${alert.symbol} ${alert.type === 'above' ? '↑ above' : '↓ below'} $${alert.targetPrice.toFixed(2)} — current $${price.toFixed(2)}`,
        );
        return { ...alert, triggered: true };
      }
      return alert;
    });
    if (msgs.length > 0) {
      setAlerts(updated);
      localStorage.setItem('stock-alerts', JSON.stringify(updated));
      setTriggeredMsgs((prev) => [...new Set([...prev, ...msgs])]);
    }
  }, []);

  const fetchQuotes = useCallback(async () => {
    setIsFetching(true);
    try {
      const res = await fetch(`/api/stocks?symbols=${ALL_SYMBOLS.join(',')}`);
      const data = await res.json();
      const parsed = data.error ? null : parseQuotes(data);
      if (parsed && Object.keys(parsed).length > 0) {
        setQuotes(parsed);
        setUseMock(false);
        setLastUpdated(new Date());
        setAlerts((prev) => {
          checkAlerts(parsed, prev);
          return prev;
        });
      } else {
        setQuotes(MOCK_QUOTES);
        setUseMock(true);
        setLastUpdated(new Date());
      }
    } catch {
      setQuotes(MOCK_QUOTES);
      setUseMock(true);
    } finally {
      setIsFetching(false);
      setIsLoading(false);
    }
  }, [checkAlerts]);

  const fetchHistory = useCallback(async () => {
    const results: HistoryRecord = {};
    await Promise.all(
      ALL_SYMBOLS.map(async (symbol) => {
        try {
          const res = await fetch(`/api/stocks/history?symbol=${symbol}&range=1mo&interval=1d`);
          const data = await res.json();
          if (!data.error) {
            const points = parseHistory(data);
            if (points.length > 0) results[symbol] = points;
          }
        } catch {
          // silent — sparkline just won't render
        }
      }),
    );
    if (Object.keys(results).length > 0) setHistory(results);
  }, []);

  const startCountdown = useCallback(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    setCountdown(REFRESH_INTERVAL / 1000);
    countdownRef.current = setInterval(() => {
      setCountdown((c) => (c <= 1 ? REFRESH_INTERVAL / 1000 : c - 1));
    }, COUNTDOWN_STEP);
  }, []);

  const refresh = useCallback(async () => {
    await fetchQuotes();
    startCountdown();
  }, [fetchQuotes, startCountdown]);

  useEffect(() => {
    try {
      const saved = localStorage.getItem('stock-alerts');
      if (saved) setAlerts(JSON.parse(saved));
    } catch {}

    fetchQuotes().then(startCountdown);
    fetchHistory();

    timerRef.current = setInterval(fetchQuotes, REFRESH_INTERVAL);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAddAlert = useCallback((alert: Omit<Alert, 'id' | 'triggered' | 'createdAt'>) => {
    const newAlert: Alert = {
      ...alert,
      id: crypto.randomUUID(),
      triggered: false,
      createdAt: new Date().toISOString(),
    };
    setAlerts((prev) => {
      const updated = [...prev, newAlert];
      localStorage.setItem('stock-alerts', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const handleRemoveAlert = useCallback((id: string) => {
    setAlerts((prev) => {
      const updated = prev.filter((a) => a.id !== id);
      localStorage.setItem('stock-alerts', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const handleSetAlertForSymbol = useCallback((symbol: string) => {
    setAlertSymbol(symbol);
    setTimeout(() => {
      document.getElementById('alert-panel')?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  }, []);

  const marketOpen = isMarketOpen();

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6 space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Stock Dashboard</h1>
            <div className="flex items-center gap-3 mt-1">
              <div className="flex items-center gap-1.5">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${marketOpen ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
                <span className="text-xs text-gray-500">{marketOpen ? 'Market open' : 'Market closed'}</span>
              </div>
              {lastUpdated && (
                <span className="text-xs text-gray-600">
                  Updated {lastUpdated.toLocaleTimeString()} · next in {countdown}s
                </span>
              )}
              {useMock && (
                <span className="text-xs text-yellow-500/80 bg-yellow-500/10 px-2 py-0.5 rounded-full">
                  Demo data
                </span>
              )}
            </div>
          </div>
          <button
            onClick={refresh}
            disabled={isFetching}
            className="flex items-center gap-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:opacity-40 shrink-0"
          >
            <span className={isFetching ? 'animate-spin inline-block' : ''}>↻</span> Refresh
          </button>
        </div>

        {/* Triggered alert banner */}
        {triggeredMsgs.length > 0 && (
          <div className="bg-yellow-400/10 border border-yellow-400/30 rounded-xl px-5 py-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="text-yellow-400 font-semibold text-sm mb-1">⚡ Price Alerts Triggered</h3>
                <ul className="text-yellow-300/70 text-xs space-y-0.5">
                  {triggeredMsgs.map((msg, i) => (
                    <li key={i}>{msg}</li>
                  ))}
                </ul>
              </div>
              <button
                onClick={() => setTriggeredMsgs([])}
                className="text-yellow-400/50 hover:text-yellow-400 text-xs shrink-0 mt-0.5"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Portfolio sections */}
        {PORTFOLIOS.map((portfolio) => (
          <PortfolioSection
            key={portfolio.id}
            portfolio={portfolio}
            quotes={quotes}
            history={history}
            alerts={alerts}
            onAddAlert={handleSetAlertForSymbol}
          />
        ))}

        {/* Performance chart */}
        {!isLoading && <PerformanceChart portfolios={PORTFOLIOS} history={history} />}

        {/* Alert panel */}
        {!isLoading && (
          <AlertPanel
            alerts={alerts}
            quotes={quotes}
            onAddAlert={handleAddAlert}
            onRemoveAlert={handleRemoveAlert}
            defaultSymbol={alertSymbol}
          />
        )}
      </div>
    </div>
  );
}
