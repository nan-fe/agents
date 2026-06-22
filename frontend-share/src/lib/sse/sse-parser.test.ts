import { describe, expect, it, vi } from 'vitest';

import {
  parseSseChunk,
  parseSSEStream,
  processSseLine,
  type SseParseState,
} from './sse-parser';

const emptyState = (): SseParseState => ({ dataLines: [] });

describe('processSseLine', () => {
  it('parses id and data lines into an event on blank line', () => {
    const state = emptyState();

    expect(processSseLine('id: evt-1', state)).toBeNull();
    expect(processSseLine('data: {"type":"log"}', state)).toBeNull();

    const event = processSseLine('', state);
    expect(event).toEqual({
      eventId: 'evt-1',
      data: '{"type":"log"}',
    });
    expect(state.dataLines).toEqual([]);
  });

  it('joins multi-line data fields', () => {
    const state = emptyState();

    processSseLine('data: line-one', state);
    processSseLine('data: line-two', state);

    const event = processSseLine('', state);
    expect(event?.data).toBe('line-one\nline-two');
  });

  it('ignores comments and event fields', () => {
    const state = emptyState();

    expect(processSseLine(': keep-alive', state)).toBeNull();
    expect(processSseLine('event: message', state)).toBeNull();
  });
});

describe('parseSseChunk', () => {
  it('normalizes CRLF and emits multiple events', () => {
    const state = emptyState();
    const events = parseSseChunk(
      'id: 1\r\ndata: first\r\n\r\nid: 2\r\ndata: second\r\n\r\n',
      state,
    );

    expect(events).toEqual([
      { eventId: '1', data: 'first' },
      { eventId: '2', data: 'second' },
    ]);
  });
});

describe('parseSSEStream', () => {
  it('streams chunked SSE payloads through onMessage', async () => {
    const encoder = new TextEncoder();
    const payload = 'id: stream-1\ndata: {"ok":true}\n\n';
    const chunks = [payload.slice(0, 10), payload.slice(10)];
    let index = 0;

    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (index >= chunks.length) {
          controller.close();
          return;
        }
        controller.enqueue(encoder.encode(chunks[index]));
        index += 1;
      },
    });

    const messages: Array<{ body: { ok: boolean }; eventId?: string }> = [];
    await parseSSEStream({
      reader: stream.getReader(),
      parseMessage: (raw) => JSON.parse(raw) as { ok: boolean },
      onMessage: (message, eventId) => {
        messages.push({ body: message, eventId });
      },
    });

    expect(messages).toEqual([{ body: { ok: true }, eventId: 'stream-1' }]);
  });
});
