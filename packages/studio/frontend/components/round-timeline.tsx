'use client';

import { useState } from 'react';
import type { RoundResult } from '@/types';

interface RoundTimelineProps {
  rounds: RoundResult[];
}

export function RoundTimeline({ rounds }: RoundTimelineProps) {
  const reversed = [...rounds].reverse();

  if (reversed.length === 0) {
    return (
      <div className="text-xs text-[hsl(var(--muted-foreground))] text-center py-8">
        尚无实验记录
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-[11px] text-[hsl(230,20%,30%)] uppercase tracking-wider mb-2">轮次详情</div>
      {reversed.map((round) => (
        <RoundCard key={round.round_number} round={round} />
      ))}
    </div>
  );
}

function RoundCard({ round }: { round: RoundResult }) {
  const [expanded, setExpanded] = useState(false);

  const borderColor =
    round.status === 'keep' ? 'border-l-[hsl(var(--primary))]' :
    round.status === 'discard' ? 'border-l-red-500' :
    'border-l-yellow-400';

  const statusBg =
    round.status === 'keep' ? 'bg-[hsl(160,30%,15%)] text-[hsl(var(--primary))]' :
    round.status === 'discard' ? 'bg-[hsl(350,30%,15%)] text-red-400' :
    'bg-[hsl(45,30%,15%)] text-yellow-400';

  return (
    <div
      className={`bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] ${borderColor} border-l-[3px] rounded-lg cursor-pointer transition-colors hover:border-[hsl(230,20%,20%)]`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center px-3 py-2.5 gap-2.5">
        <div className="text-xs font-bold text-[hsl(var(--muted-foreground))] min-w-[50px]">
          Round {round.round_number}
        </div>
        <div className={`text-[10px] px-2 py-0.5 rounded font-semibold ${statusBg}`}>
          {round.status === 'keep' ? 'Keep' : round.status === 'discard' ? 'Discard' : 'Error'}
        </div>
        <div className="text-[11px] text-[hsl(var(--muted-foreground))] flex-1 truncate">
          {round.target_dimension}
        </div>
        <div className={`text-sm font-bold ${round.delta > 0 ? 'text-[hsl(var(--primary))]' : round.delta < 0 ? 'text-red-400' : 'text-[hsl(var(--muted-foreground))]'}`}>
          {round.delta > 0 ? `+${round.delta}` : round.delta}
        </div>
      </div>

      {expanded && (
        <div className="px-3 pb-3 border-t border-[hsl(230,20%,15%)] mt-0 pt-2.5 text-xs text-[hsl(var(--muted-foreground))] leading-relaxed">
          <p>{round.description}</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {Object.entries(round.scores_after).map(([dim, score]) => {
              const before = round.scores_before[dim];
              const changed = score !== before;
              return (
                <span key={dim} className="bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded px-2 py-0.5 text-[10px]">
                  {dim} {changed ? (
                    <span className="text-[hsl(var(--primary))]">{before}→{score}</span>
                  ) : (
                    <span>{score}</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
