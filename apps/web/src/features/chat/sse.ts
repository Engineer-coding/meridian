/** `fetch` gövdesini SSE olaylarına çevirir: EventSource POST ve özel başlık desteklemez. */

export type SseEvent = { event: string; data: string };

export function createSseParser() {
  let buffer = "";
  return (chunk: string): SseEvent[] => {
    buffer += chunk.replace(/\r\n?/g, "\n");
    const events: SseEvent[] = [];
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const parsed = parseBlock(buffer.slice(0, end));
      if (parsed) events.push(parsed);
      buffer = buffer.slice(end + 2);
      end = buffer.indexOf("\n\n");
    }
    return events;
  };
}

function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const parse = createSseParser();
  // TextDecoderStream, parçalar arasında bölünmüş çok baytlı harfleri ("ş") doğru birleştirir.
  const reader = body.pipeThrough(new TextDecoderStream() as unknown as ReadableWritablePair<string, Uint8Array>).getReader();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return;
      yield* parse(value);
    }
  } finally {
    reader.releaseLock();
  }
}
