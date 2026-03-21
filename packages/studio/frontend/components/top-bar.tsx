'use client';

import { Clapperboard } from 'lucide-react';

interface TopBarProps {
  status: string;
  currentRound: number;
  maxRounds: number;
}

const plugins = [
  { name: '剧本优化', active: true },
  { name: '分镜修改', active: false },
  { name: '场景提示词', active: false },
];

export function TopBar({ status, currentRound, maxRounds }: TopBarProps) {
  return (
    <div className="h-12 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] flex items-center px-5 gap-4">
      <div className="flex items-center gap-2 text-[hsl(var(--primary))] font-bold text-sm">
        <Clapperboard className="w-4 h-4" />
        DramaLab
      </div>
      <div className="flex gap-1 ml-6">
        {plugins.map((p) => (
          <button
            key={p.name}
            className={`px-3 py-1.5 rounded-md text-xs ${
              p.active
                ? 'bg-[hsl(230,20%,15%)] text-[hsl(var(--primary))]'
                : 'text-[hsl(var(--muted-foreground))] opacity-40 cursor-not-allowed'
            }`}
            disabled={!p.active}
          >
            {p.name}
          </button>
        ))}
      </div>
      <div className="flex-1" />
      {status === 'running' && (
        <div className="flex items-center gap-2 text-xs text-yellow-400">
          <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
          Running · Round {currentRound}/{maxRounds}
        </div>
      )}
      {status === 'complete' && (
        <div className="flex items-center gap-2 text-xs text-[hsl(var(--primary))]">
          <div className="w-2 h-2 bg-[hsl(var(--primary))] rounded-full" />
          Complete
        </div>
      )}
    </div>
  );
}
