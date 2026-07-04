'use client';

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface EquityPoint {
  date: string;
  equity: number;
  regime: string;
}

const fmtUsd = (v: number) =>
  v.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });

function EquityTooltip({
  active,
  payload,
  label,
  startEquity,
}: {
  active?: boolean;
  payload?: { value: number; payload: EquityPoint }[];
  label?: string;
  startEquity: number;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  const ret = ((p.value - startEquity) / startEquity) * 100;
  return (
    <div className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-md dark:border-zinc-700 dark:bg-zinc-900">
      <div className="font-medium text-zinc-900 dark:text-zinc-100">{label}</div>
      <div className="mt-1 text-zinc-600 dark:text-zinc-300">{fmtUsd(p.value)}</div>
      <div className="text-zinc-500 dark:text-zinc-400">
        {ret >= 0 ? '+' : ''}
        {ret.toFixed(2)}% since start · {p.payload.regime}
      </div>
    </div>
  );
}

export default function EquityChart({
  data,
  startEquity,
}: {
  data: EquityPoint[];
  startEquity: number;
}) {
  const values = data.map((d) => d.equity);
  const min = Math.min(...values, startEquity);
  const max = Math.max(...values, startEquity);
  const pad = Math.max((max - min) * 0.15, max * 0.002);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563eb" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#2563eb" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.08} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.55 }}
            tickLine={false}
            axisLine={false}
            minTickGap={48}
          />
          <YAxis
            domain={[min - pad, max + pad]}
            tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.55 }}
            tickLine={false}
            axisLine={false}
            width={72}
            tickFormatter={(v: number) => fmtUsd(v)}
          />
          <Tooltip
            content={<EquityTooltip startEquity={startEquity} />}
            cursor={{ stroke: 'currentColor', strokeOpacity: 0.25, strokeDasharray: '4 4' }}
          />
          <ReferenceLine
            y={startEquity}
            stroke="currentColor"
            strokeOpacity={0.3}
            strokeDasharray="4 4"
          />
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#2563eb"
            strokeWidth={2}
            fill="url(#equityFill)"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--background, #fff)' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
