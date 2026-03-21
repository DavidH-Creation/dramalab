'use client';

import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { RoundResult } from '@/types';

interface TrendChartProps {
  rounds: RoundResult[];
  selectedRound: number | null;
  onSelectRound: (index: number) => void;
}

export function TrendChart({ rounds, selectedRound, onSelectRound }: TrendChartProps) {
  const data = rounds.map((r, i) => ({
    name: `R${r.round_number}`,
    score: r.status === 'keep' ? r.total_after : r.total_before,
    status: r.status,
    index: i,
  }));

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    if (cx == null || cy == null) return null;
    const isSelected = payload.index === selectedRound;
    const color = payload.status === 'keep' ? '#64ffda' : payload.status === 'discard' ? '#e94560' : '#ffd93d';
    return (
      <g onClick={() => onSelectRound(payload.index)} style={{ cursor: 'pointer' }}>
        {isSelected && <circle cx={cx} cy={cy} r={10} fill="none" stroke={color} strokeWidth={2} opacity={0.4} />}
        <circle cx={cx} cy={cy} r={5} fill={color} stroke="#0a0a1a" strokeWidth={2} />
      </g>
    );
  };

  if (data.length === 0) {
    return (
      <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-4 h-[180px] flex items-center justify-center">
        <span className="text-xs text-[hsl(var(--muted-foreground))]">等待数据...</span>
      </div>
    );
  }

  return (
    <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-4">
      <div className="text-xs text-[hsl(var(--muted-foreground))] mb-3">评分趋势</div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#64ffda" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#64ffda" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(230,20%,15%)" />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#8892b0' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#555' }} axisLine={false} tickLine={false} width={30} />
          <Tooltip
            contentStyle={{ background: '#111130', border: '1px solid #1e1e3a', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: '#8892b0' }}
          />
          <Area type="monotone" dataKey="score" stroke="#64ffda" strokeWidth={2} fill="url(#scoreGradient)" dot={<CustomDot />} activeDot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
