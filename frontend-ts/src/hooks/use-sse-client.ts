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

        setStatus(attempt === 0 ? "connecting" : "reconnecting");
        if (attempt > 0) {
          setRetryCount(attempt);
        }

        let response: Response | null = null;
        try {
          response = await createRequest(controller.signal);
        } catch (requestError) {
          if (controller.signal.aborted) {
            abortControllerRef.current = null;
            return null;
          }
          latestError = toError(requestError);
        }

        if (controller.signal.aborted) {
          abortControllerRef.current = null;
          return null;
        }

        if (response && !response.ok) {
          latestError = new Error(
            `SSE request failed with status ${response.status}`,
          );
          response = null;
        }

        if (response && !response.body) {
          latestError = new Error("SSE response body is empty");
          response = null;
        }

        if (response?.body) {
          setStatus("streaming");
          onOpen?.();

          const reader = response.body.getReader();
          let streamFailed = false;

          try {
            await parseSSEStream({
              reader,
              parseMessage,
              onMessage,
            });
          } catch (streamError) {
            if (controller.signal.aborted) {
              abortControllerRef.current = null;
              return null;
            }
            latestError = toError(streamError);
            streamFailed = true;
          }

          if (!streamFailed) {
            onComplete?.();
            setStatus("completed");
            abortControllerRef.current = null;
            return null;
          }
        }

        if (controller.signal.aborted) {
          abortControllerRef.current = null;
          return null;
        }

        if (latestError) {
          setError(latestError);
        }

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

      abortControllerRef.current = null;

      if (fallback) {
        setStatus("degraded");
        try {
          return await fallback(latestError);
        } catch (fallbackError) {
          const finalError = toError(fallbackError);
          setError(finalError);
          setStatus("failed");
          return null;
        }
      }

      const finalError = latestError ?? new Error("SSE stream failed");
      setError(finalError);
      setStatus("failed");
      return null;
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
