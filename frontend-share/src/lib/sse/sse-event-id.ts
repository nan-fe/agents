export type EventIdDedupeState = {
  seenEventIds: Set<string>;
  /** 续传 checkpoint：仅渲染 event_id 严格大于该值的事件 */
  resumeAfterEventId: string | null;
};

export const createEventIdDedupeState = (): EventIdDedupeState => ({
  seenEventIds: new Set<string>(),
  resumeAfterEventId: null,
});

const compareEventId = (left: string, right: string): number =>
  Number(left) - Number(right);

/** 续传时跳过 event_id <= resumeAfterEventId，并结合 seenEventIds 去重 */
export const shouldEnqueueSseEvent = (
  state: EventIdDedupeState,
  eventId?: string,
): boolean => {
  if (!eventId) {
    return true;
  }
  if (
    state.resumeAfterEventId !== null &&
    compareEventId(eventId, state.resumeAfterEventId) <= 0
  ) {
    return false;
  }
  if (state.seenEventIds.has(eventId)) {
    return false;
  }
  state.seenEventIds.add(eventId);
  return true;
};

export const setResumeAfterEventId = (
  state: EventIdDedupeState,
  eventId: string | null,
): void => {
  state.resumeAfterEventId = eventId;
};
