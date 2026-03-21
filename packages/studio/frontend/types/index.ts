export interface RoundResult {
  round_number: number;
  status: 'keep' | 'discard' | 'error';
  total_before: number;
  total_after: number;
  delta: number;
  target_dimension: string;
  description: string;
  scores_before: Record<string, number>;
  scores_after: Record<string, number>;
  max_total: number;
}

export interface PluginConfig {
  model: string;
  rounds: number;
  reasoning_effort: string;
  mode: string;
  keep_threshold: number;
}

export interface PluginState {
  status: 'idle' | 'initializing' | 'running' | 'complete' | 'error';
  inputText: string;
  criteriaText: string;
  config: PluginConfig;
  rounds: RoundResult[];
  baselineScores: Record<string, number> | null;
  selectedRound: number | null;
  currentRound: number;
  maxRounds: number;
  sessionId: string | null;
  errorMessage: string | null;
}

export interface UploadResult {
  text: string;
  filename: string;
  size_kb: number;
}

export interface InitResult {
  session_id: string;
  sequences: Array<{ id: string; title?: string; char_count?: number; scene_count?: number }>;
}

export const DEFAULT_CONFIG: PluginConfig = {
  model: 'sonnet',
  rounds: 10,
  reasoning_effort: 'medium',
  mode: 'auto',
  keep_threshold: 1,
};
