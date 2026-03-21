'use client';

import { useReducer, useCallback, useRef } from 'react';

import type { PluginState, PluginConfig, RoundResult } from '@/types';
import { DEFAULT_CONFIG } from '@/types';
import { initPlugin, stopPlugin, uploadFile, exportDocx, getStreamUrl } from '@/lib/api';

import { useSSE } from './use-sse';

type Action =
  | { type: 'SET_INPUT'; text: string }
  | { type: 'SET_CRITERIA'; text: string }
  | { type: 'SET_CONFIG'; config: Partial<PluginConfig> }
  | { type: 'SET_STATUS'; status: PluginState['status'] }
  | { type: 'SET_SESSION'; sessionId: string }
  | { type: 'ADD_ROUND'; result: RoundResult }
  | { type: 'SET_BASELINE'; scores: Record<string, number> }
  | { type: 'SELECT_ROUND'; index: number | null }
  | { type: 'COMPLETE'; data: { total_rounds: number; final_score: number } }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' };

const initialState: PluginState = {
  status: 'idle',
  inputText: '',
  criteriaText: '',
  config: DEFAULT_CONFIG,
  rounds: [],
  baselineScores: null,
  selectedRound: null,
  currentRound: 0,
  maxRounds: 10,
  sessionId: null,
  errorMessage: null,
};

function reducer(state: PluginState, action: Action): PluginState {
  switch (action.type) {
    case 'SET_INPUT':
      return { ...state, inputText: action.text };
    case 'SET_CRITERIA':
      return { ...state, criteriaText: action.text };
    case 'SET_CONFIG':
      return {
        ...state,
        config: { ...state.config, ...action.config },
        maxRounds: action.config.rounds ?? state.maxRounds,
      };
    case 'SET_STATUS':
      return { ...state, status: action.status, errorMessage: null };
    case 'SET_SESSION':
      return { ...state, sessionId: action.sessionId };
    case 'ADD_ROUND': {
      const rounds = [...state.rounds, action.result];
      const baseline = state.baselineScores ?? action.result.scores_before;
      return {
        ...state,
        rounds,
        currentRound: rounds.length,
        baselineScores: baseline,
        selectedRound: rounds.length - 1,
      };
    }
    case 'SELECT_ROUND':
      return { ...state, selectedRound: action.index };
    case 'COMPLETE':
      return { ...state, status: 'complete' };
    case 'ERROR':
      return { ...state, status: 'error', errorMessage: action.message };
    case 'RESET':
      return initialState;
    default:
      return state;
  }
}

export function usePlugin(pluginName: string = 'scriptsmith') {
  const [state, dispatch] = useReducer(reducer, initialState);
  const streamUrlRef = useRef<string | null>(null);

  const { connect, disconnect } = useSSE(streamUrlRef.current, {
    onRound: (result) => dispatch({ type: 'ADD_ROUND', result }),
    onComplete: (data) => dispatch({ type: 'COMPLETE', data }),
    onError: (message) => dispatch({ type: 'ERROR', message }),
  });

  const handleUpload = useCallback(async (file: File, target: 'input' | 'criteria') => {
    const result = await uploadFile(file);
    dispatch({ type: target === 'input' ? 'SET_INPUT' : 'SET_CRITERIA', text: result.text });
    return result;
  }, []);

  const handleStart = useCallback(async () => {
    if (!state.inputText || !state.criteriaText) return;

    dispatch({ type: 'SET_STATUS', status: 'initializing' });

    try {
      const result = await initPlugin(
        pluginName,
        state.inputText,
        state.criteriaText,
        state.config as unknown as Record<string, unknown>,
      );
      dispatch({ type: 'SET_SESSION', sessionId: result.session_id });
      dispatch({ type: 'SET_STATUS', status: 'running' });

      streamUrlRef.current = getStreamUrl(pluginName, result.session_id);
      setTimeout(() => connect(), 0);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      dispatch({ type: 'ERROR', message });
    }
  }, [state.inputText, state.criteriaText, state.config, pluginName, connect]);

  const handleStop = useCallback(async () => {
    if (state.sessionId) {
      await stopPlugin(pluginName, state.sessionId);
      disconnect();
    }
  }, [state.sessionId, pluginName, disconnect]);

  const handleExport = useCallback(async () => {
    if (state.sessionId) {
      await exportDocx(pluginName, state.sessionId);
    }
  }, [state.sessionId, pluginName]);

  return {
    state,
    dispatch,
    handleUpload,
    handleStart,
    handleStop,
    handleExport,
  };
}
