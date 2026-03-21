'use client';

interface ScoreCardsProps {
  currentScore: number;
  totalImprovement: number;
  currentRound: number;
  maxRounds: number;
}

export function ScoreCards({ currentScore, totalImprovement, currentRound, maxRounds }: ScoreCardsProps) {
  return (
    <div className="grid grid-cols-3 gap-2.5 mb-4">
      <Card value={currentScore} label="当前总分" color="text-[hsl(var(--primary))]" />
      <Card value={totalImprovement > 0 ? `+${totalImprovement}` : String(totalImprovement)} label="累计提升" color="text-yellow-400" />
      <Card value={`${currentRound} / ${maxRounds}`} label="轮次" color="text-[hsl(var(--muted-foreground))]" />
    </div>
  );
}

function Card({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div className="bg-[hsl(230,30%,10%)] border border-[hsl(230,20%,15%)] rounded-lg p-3 text-center">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-[10px] text-[hsl(230,20%,30%)] mt-0.5">{label}</div>
    </div>
  );
}
