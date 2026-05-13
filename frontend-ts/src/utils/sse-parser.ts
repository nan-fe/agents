export type ParseSSEStreamOptions<TMessage> = {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  parseMessage: (payload: string) => TMessage;
  onMessage: (message: TMessage) => void;
  onParseError?: (error: unknown, payload: string) => void;
};

export const parseSSEStream = async <TMessage>({
  reader,
  parseMessage,
  onMessage,
  onParseError,
}: ParseSSEStreamOptions<TMessage>): Promise<void> => {
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const processBufferLines = (flushRemainder = false) => {
    const lines = buffer.split("\n");
    buffer = flushRemainder ? "" : lines.pop() || "";
    const linesToProcess = flushRemainder ? lines : lines;

    for (const rawLine of linesToProcess) {
      const line = rawLine.trim();
      if (!line.startsWith("data:")) continue;

      const dataStr = line.slice(5).trim();
      if (!dataStr) continue;

      try {
        const parsedMessage = parseMessage(dataStr);
        onMessage(parsedMessage);
      } catch (error) {
        onParseError?.(error, dataStr);
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    processBufferLines();
  }

  buffer += decoder.decode();
  processBufferLines(true);
};
