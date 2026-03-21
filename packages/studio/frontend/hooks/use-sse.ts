'use client';

import { useEffect, useRef, useCallback } from 'react';
import type { RoundResult } from '@/types';

interface UseSSEOptions {
  onRound: (result: RoundResult) => void;
  onComplete: (data: { total_rounds: number; final_score: number; total_improvement: number }) => void;
  onError: (message: string) => void;
}

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000];

export function useSSE(defaultUrl: string | null, { onRound, onComplete, onError }: UseSSEOptions) {
  const sourceRef = useRef<{ close: () => void } | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  const connect = useCallback((overrideUrl?: string, config?: Record<string, unknown>) => {
    const targetUrl = overrideUrl || defaultUrl;
    if (!targetUrl) return;
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const controller = new AbortController();
    let retryCount = 0;

    function attemptConnect(): void {
      fetch(targetUrl!, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: config || {} }),
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error(`SSE connection failed: ${response.statusText}`);
          const reader = response.body?.getReader();
          if (!reader) throw new Error('No response body');

          // Store reader ref for cleanup
          readerRef.current = reader;
          // Reset retry count on successful connection
          retryCount = 0;

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
                  // Accumulate multiline data per SSE spec
                  eventData += (eventData ? '\n' : '') + line.slice(6);
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
          if (err.name === 'AbortError') return;

          if (retryCount < MAX_RETRIES) {
            const delay = RETRY_DELAYS[retryCount] ?? RETRY_DELAYS[RETRY_DELAYS.length - 1];
            retryCount++;
            setTimeout(attemptConnect, delay);
          } else {
            onError(err.message);
          }
        });
    }

    attemptConnect();

    sourceRef.current = {
      close: () => {
        // Cancel reader explicitly before aborting
        readerRef.current?.cancel().catch(() => {});
        readerRef.current = null;
        controller.abort();
      },
    };
  }, [defaultUrl, onRound, onComplete, onError]);

  useEffect(() => {
    return () => {
      readerRef.current?.cancel().catch(() => {});
      readerRef.current = null;
      sourceRef.current?.close();
    };
  }, []);

  return { connect, disconnect: () => sourceRef.current?.close() };
}
