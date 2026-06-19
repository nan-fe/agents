export type ParseSSEStreamOptions<TMessage> = {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  parseMessage: (payload: string) => TMessage;
  onMessage: (message: TMessage, eventId?: string) => void;
  onParseError?: (error: unknown, payload: string) => void;
};

const parseSseIdLine = (line: string): string | null => {
  const match = /^id:\s*(.*)$/.exec(line);
  if (!match) {
    return null;
  }
  const value = match[1]?.trim();
  return value ? value : null;
};

export type SseParseState = {
  currentEventId?: string;
  dataLines: string[];
};

export const processSseLine = (
  rawLine: string,
  state: SseParseState,
): { eventId?: string; data: string } | null => {
  const line = rawLine.replace(/\r$/, "");
  if (!line) {
    if (state.dataLines.length === 0) {
      return null;
    }
    const payload = {
      eventId: state.currentEventId,
      data: state.dataLines.join("\n"),
    };
    state.dataLines = [];
    return payload;
  }

  if (line.startsWith(":")) {
    return null;
  }

  const eventId = parseSseIdLine(line);
  if (eventId !== null) {
    state.currentEventId = eventId;
    return null;
  }

  if (line.startsWith("event:")) {
    return null;
  }

  if (line.startsWith("data:")) {
    state.dataLines.push(line.slice(5).trimStart());
  }

  return null;
};

export const parseSseChunk = (
  chunk: string,
  state: SseParseState,
): Array<{ eventId?: string; data: string }> => {
  const events: Array<{ eventId?: string; data: string }> = [];
  const normalized = chunk.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

  for (const line of normalized.split("\n")) {
    const event = processSseLine(line, state);
    if (event) {
      events.push(event);
    }
  }

  return events;
};

export const parseSSEStream = async <TMessage>({
  reader,
  parseMessage,
  onMessage,
  onParseError,
}: ParseSSEStreamOptions<TMessage>): Promise<void> => {
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  const state: SseParseState = { dataLines: [] };

  const emit = (event: { eventId?: string; data: string }) => {
    if (!event.data) {
      return;
    }
    try {
      onMessage(parseMessage(event.data), event.eventId);
    } catch (error) {
      onParseError?.(error, event.data);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex !== -1) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);
      const event = processSseLine(line, state);
      if (event) {
        emit(event);
      }
      newlineIndex = buffer.indexOf("\n");
    }
  }

  buffer += decoder.decode();
  buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (buffer.length > 0) {
    const event = processSseLine(buffer, state);
    if (event) {
      emit(event);
    }
  }

  if (state.dataLines.length > 0) {
    emit({ eventId: state.currentEventId, data: state.dataLines.join("\n") });
    state.dataLines = [];
  }
};
