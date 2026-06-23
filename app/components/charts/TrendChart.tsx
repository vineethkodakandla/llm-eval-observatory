"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TrendProps {
  x: string[];
  series: Record<string, (number | null)[]>;
  labels: Record<string, string>;
  colors: Record<string, string>;
  domain?: [number, number];
  asPct?: boolean;
  height?: number;
}

export default function TrendChart({
  x,
  series,
  labels,
  colors,
  domain = [0, 1],
  asPct = true,
  height = 240,
}: TrendProps) {
  const ids = Object.keys(series);
  const data = x.map((date, i) => {
    const row: Record<string, string | number | null> = { date };
    ids.forEach((id) => (row[id] = series[id][i]));
    return row;
  });

  const fmt = (v: number) => (asPct ? `${Math.round(v * 100)}%` : v.toFixed(2));

  if (x.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-dashed border-ink-700 text-xs text-slate-500"
        style={{ height }}
      >
        One run so far — the trend line appears after the second nightly run.
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
          <CartesianGrid stroke="#243047" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#243047" }}
          />
          <YAxis
            domain={domain}
            tickFormatter={fmt}
            tick={{ fill: "#64748b", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          <Tooltip
            contentStyle={{
              background: "#0f1420",
              border: "1px solid #243047",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e2e8f0" }}
            formatter={(value: number, id: string) => [fmt(value), labels[id] ?? id]}
          />
          {ids.map((id) => (
            <Line
              key={id}
              type="monotone"
              dataKey={id}
              name={labels[id] ?? id}
              stroke={colors[id] ?? "#22d3ee"}
              strokeWidth={2}
              dot={{ r: 2.5 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
