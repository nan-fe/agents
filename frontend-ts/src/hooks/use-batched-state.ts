import { useCallback, useEffect, useRef, useState } from "react";

export const BATCH_RENDER_DELAY_MS = 50;

type StateUpdater<T> = (prev: T) => T;

export const useBatchedState = <T,>(initialValue: T) => {
  const [state, setState] = useState<T>(initialValue);
  const pendingUpdatersRef = useRef<StateUpdater<T>[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rafRef = useRef<number | null>(null);

  const applyPendingInAnimationFrame = useCallback(() => {
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      const updaters = pendingUpdatersRef.current;
      pendingUpdatersRef.current = [];

      if (updaters.length === 0) {
        return;
      }

      setState((prev) => updaters.reduce((next, updater) => updater(next), prev));

      if (pendingUpdatersRef.current.length > 0) {
        timeoutRef.current = setTimeout(() => {
          timeoutRef.current = null;
          applyPendingInAnimationFrame();
        }, BATCH_RENDER_DELAY_MS);
      }
    });
  }, []);

  const scheduleFlush = useCallback(() => {
    if (timeoutRef.current !== null || rafRef.current !== null) {
      return;
    }

    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      applyPendingInAnimationFrame();
    }, BATCH_RENDER_DELAY_MS);
  }, [applyPendingInAnimationFrame]);

  const batchUpdate = useCallback(
    (updater: StateUpdater<T>) => {
      pendingUpdatersRef.current.push(updater);
      scheduleFlush();
    },
    [scheduleFlush],
  );

  const cancelScheduledFlush = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const flushNow = useCallback(() => {
    cancelScheduledFlush();

    const updaters = pendingUpdatersRef.current;
    pendingUpdatersRef.current = [];

    if (updaters.length === 0) {
      return;
    }

    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = null;
      setState((prev) => updaters.reduce((next, updater) => updater(next), prev));
    });
  }, [cancelScheduledFlush]);

  const resetState = useCallback(
    (nextValue: T) => {
      cancelScheduledFlush();
      pendingUpdatersRef.current = [];
      setState(nextValue);
    },
    [cancelScheduledFlush],
  );

  useEffect(() => () => cancelScheduledFlush(), [cancelScheduledFlush]);

  return {
    state,
    batchUpdate,
    flushNow,
    resetState,
    setState,
  };
};
