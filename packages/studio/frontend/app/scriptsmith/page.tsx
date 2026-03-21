'use client';

import { TopBar } from '@/components/top-bar';
import { InputPanel } from '@/components/input-panel';
import { ConfigPanel } from '@/components/config-panel';
import { ResultsPanel } from '@/components/results-panel';
import { usePlugin } from '@/hooks/use-plugin';

export default function ScriptSmithPage() {
  const { state, dispatch, handleUpload, handleStart, handleStop, handleExport } = usePlugin('scriptsmith');

  return (
    <div className="h-screen flex flex-col">
      <TopBar status={state.status} currentRound={state.currentRound} maxRounds={state.maxRounds} />
      <div className="flex flex-1 min-h-0">
        <div className="w-[30%]">
          <InputPanel
            text={state.inputText}
            onTextChange={(text) => dispatch({ type: 'SET_INPUT', text })}
            onUpload={(file) => handleUpload(file, 'input')}
          />
        </div>
        <div className="w-[22%]">
          <ConfigPanel
            criteriaText={state.criteriaText}
            onCriteriaChange={(text) => dispatch({ type: 'SET_CRITERIA', text })}
            onCriteriaUpload={(file) => handleUpload(file, 'criteria')}
            config={state.config}
            onConfigChange={(config) => dispatch({ type: 'SET_CONFIG', config })}
            isRunning={state.status === 'running'}
            onStart={handleStart}
            onStop={handleStop}
          />
        </div>
        <div className="w-[48%]">
          <ResultsPanel
            rounds={state.rounds}
            baselineScores={state.baselineScores}
            selectedRound={state.selectedRound}
            onSelectRound={(i) => dispatch({ type: 'SELECT_ROUND', index: i })}
            maxRounds={state.maxRounds}
            onExport={handleExport}
            status={state.status}
          />
        </div>
      </div>
      {state.errorMessage && (
        <div className="bg-red-900/50 border-t border-red-800 px-4 py-2 text-xs text-red-300">
          {state.errorMessage}
        </div>
      )}
    </div>
  );
}
