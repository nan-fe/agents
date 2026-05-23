import {
  createEventIdDedupeState,
  setResumeAfterEventId,
  shouldEnqueueSseEvent,
} from "./sse-event-id";

/** 消息入队前按 event_id 过滤与去重：保留已有 Agent 日志，仅追加新事件 */
export type StreamIngestor = {
  resetSeenEventIds: () => void;
  setResumeAfterEventId: (eventId: string | null) => void;
  ingest: (eventId: string | undefined, enqueue: () => void) => boolean;
};

export const createStreamIngestor = (): StreamIngestor => {
  const state = createEventIdDedupeState();

  return {
    resetSeenEventIds() {
      state.seenEventIds.clear();
      state.resumeAfterEventId = null;
    },
    setResumeAfterEventId(eventId) {
      setResumeAfterEventId(state, eventId);
    },
    ingest(eventId, enqueue) {
      if (!shouldEnqueueSseEvent(state, eventId)) {
        return false;
      }
      enqueue();
      return true;
    },
  };
};
