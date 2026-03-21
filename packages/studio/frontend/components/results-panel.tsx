'use client';

import { Download } from 'lucide-react';

import type { RoundResult } from '@/types';

import { ScoreCards } from './score-cards';
import { TrendChart } from './trend-chart';
import { DimensionBars } from './dimension-bars';
import { RoundTimeline } from './round-timeline';

interface ResultsPanelProps {
  rounds: RoundResult[];
  baselineScores: Record<string, number> | null;
  selectedRound: number | null;
  onSelectRound: (index: number) => void;
  maxRounds: number;
  onExport: () => void;
  status: string;
}

export function ResultsPanel({
  rounds,
  baselineScores,
  selectedRound,
  onSelectRound,
  maxRounds,
  onExport,
  status,
}: ResultsPanelProps) {
  const lastKeep = [...rounds].reverse().find((round) => round.status === 'keep');
  const currentScore = lastKeep?.total_after != null ? lastKeep.total_after : (rounds[0]?.total_before ?? 0);
  const firstScore = rounds[0]?.total_before ?? 0;
  const improvement = currentScore - firstScore;
  const selectedResult = selectedRound !== null ? rounds[selectedRound] : null;

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider flex items-center">
        Results
        <div className="flex-1" />
        {status === 'complete' && (
          <button onClick={onExport} className="flex items-center gap-1 text-[hsl(var(--primary))] hover:brightness-110">
            <Download className="w-3 h-3" /> Export
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <ScoreCards
          currentScore={currentScore}
          totalImprovement={improvement}
          currentRound={rounds.length}
          maxRounds={maxRounds}
        />

        <div className="flex gap-3">
          <div className="flex-[2]">
            <TrendChart rounds={rounds} selectedRound={selectedRound} onSelectRound={onSelectRound} />
          </div>
          <div className="flex-1 bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-3">
            <DimensionBars round={selectedResult} baseline={baselineScores} />
          </div>
        </div>

        <RoundTimeline rounds={rounds} />
      </div>
    </div>
  );
}
