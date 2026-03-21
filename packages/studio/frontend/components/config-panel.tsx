'use client';

import type { PluginConfig } from '@/types';
import { FileUpload } from './file-upload';

interface ConfigPanelProps {
  criteriaText: string;
  onCriteriaChange: (text: string) => void;
  onCriteriaUpload: (file: File) => Promise<{ filename: string; size_kb: number }>;
  config: PluginConfig;
  onConfigChange: (config: Partial<PluginConfig>) => void;
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function ConfigPanel({
  criteriaText, onCriteriaChange, onCriteriaUpload,
  config, onConfigChange, isRunning, onStart, onStop,
}: ConfigPanelProps) {
  return (
    <div className="flex flex-col h-full border-r border-[hsl(230,20%,15%)]">
      <div className="px-4 py-3 bg-[hsl(230,40%,8%)] border-b border-[hsl(230,20%,15%)] text-xs font-semibold text-[hsl(var(--muted-foreground))] uppercase tracking-wider">
        ⚙️ 配置
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium">评分标准</label>
          <FileUpload accept=".docx,.md" label="上传 .docx / .md" onUpload={onCriteriaUpload} compact />
          <textarea
            className="w-full h-24 bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md p-2 text-[11px] text-[hsl(var(--foreground))] resize-none focus:outline-none focus:border-[hsl(var(--primary))] font-mono"
            value={criteriaText}
            onChange={(e) => onCriteriaChange(e.target.value)}
            placeholder="评分标准..."
          />
        </div>

        <hr className="border-[hsl(230,20%,15%)]" />

        <div className="space-y-3">
          <ConfigSelect label="模型" value={config.model} options={['sonnet', 'opus', 'haiku']} onChange={(v) => onConfigChange({ model: v })} />
          <ConfigNumber label="轮数" value={config.rounds} min={1} max={100} onChange={(v) => onConfigChange({ rounds: v })} />
          <ConfigSelect label="Reasoning Effort" value={config.reasoning_effort} options={['low', 'medium', 'high']} onChange={(v) => onConfigChange({ reasoning_effort: v })} />
          <ConfigSelect label="模式" value={config.mode} options={['auto', 'macro', 'micro']} onChange={(v) => onConfigChange({ mode: v })} />
          <ConfigNumber label="Keep Threshold" value={config.keep_threshold} min={1} max={10} onChange={(v) => onConfigChange({ keep_threshold: v })} />
        </div>

        <button
          className={`w-full py-3 rounded-lg font-bold text-sm transition-all ${
            isRunning
              ? 'bg-red-500 hover:bg-red-600 text-white'
              : 'bg-[hsl(var(--primary))] hover:brightness-110 text-[hsl(var(--background))]'
          }`}
          onClick={isRunning ? onStop : onStart}
        >
          {isRunning ? '⏹ STOP' : '▶ START'}
        </button>
      </div>
    </div>
  );
}

function ConfigSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium block mb-1">{label}</label>
      <select
        className="w-full bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md px-2 py-2 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:border-[hsl(var(--primary))]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>)}
      </select>
    </div>
  );
}

function ConfigNumber({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="text-[11px] text-[hsl(var(--muted-foreground))] font-medium block mb-1">{label}</label>
      <input
        type="number"
        className="w-full bg-[hsl(230,40%,6%)] border border-[hsl(230,20%,15%)] rounded-md px-2 py-2 text-sm text-[hsl(var(--foreground))] focus:outline-none focus:border-[hsl(var(--primary))]"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}
