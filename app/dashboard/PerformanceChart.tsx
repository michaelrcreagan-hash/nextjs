'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Portfolio, HistoricalPoint } from '@/lib/stocks';

interface PerformanceChartProps {
  portfolios: Portfolio[];
  history: Record<string, HistoricalPoint[]>;
}

function calcPerformance(
  portfolio: Portfolio,
  history: Record<string, HistoricalPoint[]>,
): Map<string, number> {
  const available = portfolio.symbols.filter((s) => (history[s]?.length ?? 0) > 1);
  if (available.length === 0) return new Map();

  const histories = available.map((s) => history[s]);
  const len = Math.min(...histories.map((h) => h.length));
  const result = new Map<string, number>();

  for (let i = 0; i < len; i++) {
    const returns = available.map((sym) => {
      const h = history[sym];
      return ((h[i].close - h[0].close) / h[0].close) * 100;
    });
    const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
    result.set(histories[0][i].date, parseFloat(avg.toFixed(2)));
  }
  return result;
}

export function PerformanceChart({ portfolios, history }: PerformanceChartProps) {
  const perfMaps = portfolios.map((p) => calcPerformance(p, history));

  const dateSet = new Set<string>();
  perfMaps.forEach((m) => m.forEach((_, d) => dateSet.add(d)));
  const dates = Array.from(dateSet).sort();

  const chartData = dates.map((date) => {
    const entry: Record<string, number | string> = { date };
    portfolios.forEach((p, i) => {
      const val = perfMaps[i].get(date);
      if (val !== undefined) entry[p.id] = val;
    });
    return entry;
  });

  const hasData = chartData.length > 0 && portfolios.some((p, i) => perfMaps[i].size > 0);

  if (!hasData) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        <h3 className="text-white font-semibold mb-4">Portfolio Performance (30 Days)</h3>
        <div className="h-64 flex items-center justify-center animate-pulse">
          <div className="text-gray-600 text-sm">Loading chart data…</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
      <h3 className="text-white font-semibold mb-4">Portfolio Performance (30 Days)</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 5, right: 24, left: 8, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <ReferenceLine y={0} stroke="#374151" strokeDasharray="4 4" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#1f2937' }}
            tickFormatter={(v) => {
              const d = new Date(v);
              return `${d.getMonth() + 1}/${d.getDate()}`;
            }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#6b7280', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`}
            width={52}
          />
          <Tooltip
            contentStyle={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(value, name) => [
              typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%` : String(value),
              portfolios.find((p) => p.id === String(name))?.name ?? String(name),
            ]}
            labelFormatter={(label) =>
              new Date(label).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            }
          />
          <Legend
            wrapperStyle={{ fontSize: '12px', paddingTop: '16px' }}
            formatter={(value) =>
              portfolios.find((p) => p.id === value)?.name ?? value
            }
          />
          {portfolios.map((portfolio) => (
            <Line
              key={portfolio.id}
              type="monotone"
              dataKey={portfolio.id}
              stroke={portfolio.hexColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: portfolio.hexColor, strokeWidth: 0 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
