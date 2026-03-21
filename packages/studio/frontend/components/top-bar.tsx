'use client';

import { Clapperboard } from 'lucide-react';

interface TopBarProps {
  status: string;
  currentRound: number;
  maxRounds: number;
}

const plugins = [
  { name: 'ScriptSmith', active: true },
  { name: 'Storyboard', active: false },
  { name: 'Prompt Lab', active: false },
];

export function TopBar({ status, currentRound, maxRounds }: TopBarProps) {
  return (
    <div className="h-12 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] flex items-center px-5 gap-4">
      <div className="flex items-center gap-2 text-[hsl(var(--primary))] font-bold text-sm">
        <Clapperboard className="w-4 h-4" />
        DramaLab
      </div>
      <div className="flex gap-1 ml-6">
        {plugins.map((plugin) => (
          <button
            key={plugin.name}
            className={`px-3 py-1.5 rounded-md text-xs ${
              plugin.active
                ? 'bg-[hsl(230,20%,15%)] text-[hsl(var(--primary))]'
                : 'text-[hsl(var(--muted-foreground))] opacity-40 cursor-not-allowed'
            }`}
            disabled={!plugin.active}
          >
            {plugin.name}
          </button>
        ))}
      </div>
      <div className="flex-1" />
      {status === 'running' && (
        <div className="flex items-center gap-2 text-xs text-yellow-400">
          <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
          Running | Round {currentRound}/{maxRounds}
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
