import { useCallback, useEffect, useRef, useState } from "react";
import { parseSSEStream } from "../utils/sse-parser";

type SSEStatus =
  | "idle"
  | "connecting"
  | "streaming"
  | "reconnecting"
  | "completed"
  | "degraded"
  | "failed";

export type SSEConnectOptions<TMessage, TResult> = {
  createRequest: (signal: AbortSignal) => Promise<Response>;
  onMessage: (message: TMessage) => void;
  parseMessage?: (payload: string) => TMessage;
  onOpen?: () => void;
  onComplete?: () => void;
  maxRetries?: number;
  retryBaseDelayMs?: number;
  retryMaxDelayMs?: number;
  fallback?: (error: unknown) => Promise<TResult>;
};

const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_BASE_DELAY = 1000;
const DEFAULT_RETRY_MAX_DELAY = 8000;

const wait = (ms: number) =>
  new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });

const toError = (error: unknown): Error => {
  if (error instanceof Error) return error;
  return new Error("SSE stream failed");
};

export const useSSEClient = () => {
  const [status, setStatus] = useState<SSEStatus>("idle");
  const [retryCount, setRetryCount] = useState(0);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setStatus("idle");
  }, []);

  useEffect(() => () => disconnect(), [disconnect]);

  const connect = useCallback(
    async <TMessage, TResult = unknown>(
      options: SSEConnectOptions<TMessage, TResult>,
    ): Promise<TResult | null> => {
      const {
        createRequest,
        onMessage,
        parseMessage = JSON.parse as (payload: string) => TMessage,
        onOpen,
        onComplete,
        maxRetries = DEFAULT_MAX_RETRIES,
        retryBaseDelayMs = DEFAULT_RETRY_BASE_DELAY,
        retryMaxDelayMs = DEFAULT_RETRY_MAX_DELAY,
        fallback,
      } = options;

      let attempt = 0;
      let latestError: Error | null = null;

      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      setError(null);
      setRetryCount(0);

      while (attempt <= maxRetries) {
        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          setStatus(attempt === 0 ? "connecting" : "reconnecting");
          if (attempt > 0) {
            setRetryCount(attempt);
          }

          const response = await createRequest(controller.signal);
          if (!response.ok) {
            throw new Error(`SSE request failed with status ${response.status}`);
          }

          if (!response.body) {
            throw new Error("SSE response body is empty");
          }

          setStatus("streaming");
          onOpen?.();

          const reader = response.body.getReader();
          await parseSSEStream({
            reader,
            parseMessage,
            onMessage,
          });

          onComplete?.();
          setStatus("completed");
          abortControllerRef.current = null;
          return null;
        } catch (streamError) {
          if (controller.signal.aborted) {
            abortControllerRef.current = null;
            return null;
          }

          latestError = toError(streamError);
          setError(latestError);

          if (attempt === maxRetries) {
            break;
          }

          const delay = Math.min(
            retryMaxDelayMs,
            retryBaseDelayMs * 2 ** attempt,
          );
          await wait(delay);
          attempt += 1;
        }
      }

      abortControllerRef.current = null;

      if (fallback) {
        try {
          setStatus("degraded");
          return await fallback(latestError);
        } catch (fallbackError) {
          const finalError = toError(fallbackError);
          setError(finalError);
          setStatus("failed");
          throw finalError;
        }
      }

      const finalError = latestError ?? new Error("SSE stream failed");
      setStatus("failed");
      throw finalError;
    },
    [],
  );

  return {
    connect,
    disconnect,
    status,
    retryCount,
    error,
  };
};
