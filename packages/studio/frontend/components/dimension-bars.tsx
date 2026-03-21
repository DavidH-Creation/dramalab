'use client';

import type { RoundResult } from '@/types';

interface DimensionBarsProps {
  round: RoundResult | null;
  baseline: Record<string, number> | null;
}

export function DimensionBars({ round, baseline }: DimensionBarsProps) {
  if (!round) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-[hsl(var(--muted-foreground))]">
        点击图表数据点查看维度分数
      </div>
    );
  }

  const scores = round.status === 'keep' ? round.scores_after : round.scores_before;
  const dimensions = Object.keys(scores);

  // Per-dimension max: assumes equal split of max_total across dimensions.
  // This is correct for script-forge where all dimensions share the same max score.
  // If a future plugin uses unequal max scores, RoundResult should carry per-dimension max.
  const perDimMax = Math.ceil(round.max_total / Math.max(dimensions.length, 1));

  return (
    <div className="space-y-2">
      <div className="text-[10px] text-[hsl(var(--muted-foreground))]">
        Round {round.round_number} 维度分数
      </div>
      {dimensions.map((dim) => {
        const score = scores[dim];
        const baselineScore = baseline?.[dim] ?? score;
        const pct = (score / perDimMax) * 100;
        const basePct = (baselineScore / perDimMax) * 100;
        const isWeakest = dim === round.target_dimension;
        const improved = score > baselineScore;

        return (
          <div key={dim} className="flex items-center gap-2">
            <div className="text-[10px] text-[hsl(var(--muted-foreground))] w-12 text-right truncate">{dim}</div>
            <div className="flex-1 h-3.5 bg-[hsl(230,30%,12%)] rounded relative overflow-hidden">
              <div
                className="absolute top-0 h-full border-r-2 border-dashed border-white/20"
                style={{ left: `${Math.min(basePct, 100)}%` }}
              />
              <div
                className={`h-full rounded transition-all ${
                  isWeakest ? 'bg-yellow-400' : improved ? 'bg-[hsl(var(--primary))]' : 'bg-[hsl(var(--primary))]'
                }`}
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-[hsl(var(--foreground))] w-10 text-right">
              {score}/{perDimMax}
            </div>
          </div>
        );
      })}
      <div className="text-[8px] text-[hsl(230,20%,25%)]">虚线 = 初始分</div>
    </div>
  );
}
