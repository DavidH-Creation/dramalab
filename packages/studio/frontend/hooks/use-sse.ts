'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { RoundResult } from '@/types';

interface UseSSEOptions {
  onRound: (result: RoundResult) => void;
  onComplete: (data: { total_rounds: number; final_score: number; total_improvement: number }) => void;
  onError: (message: string) => void;
}

export function useSSE(url: string | null, { onRound, onComplete, onError }: UseSSEOptions) {
  const sourceRef = useRef<{ close: () => void } | null>(null);

  const connect = useCallback(() => {
    if (!url) return;
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const controller = new AbortController();

    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`SSE connection failed: ${response.statusText}`);
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';

        function pump(): Promise<void> {
          return reader!.read().then(({ done, value }) => {
            if (done) return;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let eventType = '';
            let eventData = '';

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                eventData = line.slice(6);
              } else if (line === '' && eventType && eventData) {
                try {
                  const parsed = JSON.parse(eventData);
                  if (eventType === 'round') onRound(parsed);
                  else if (eventType === 'complete') onComplete(parsed);
                  else if (eventType === 'error') onError(parsed.message);
                } catch {
                  // ignore parse errors
                }
                eventType = '';
                eventData = '';
              }
            }

            return pump();
          });
        }

        return pump();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError(err.message);
        }
      });

    sourceRef.current = { close: () => controller.abort() };
  }, [url, onRound, onComplete, onError]);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  return { connect, disconnect: () => sourceRef.current?.close() };
}
