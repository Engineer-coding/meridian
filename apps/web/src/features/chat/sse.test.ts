// @vitest-environment node
import { describe, expect, it } from "vitest";

import { createSseParser, readSse } from "./sse";

describe("SSE ayrıştırıcı", () => {
  it("parçalara bölünmüş olayları birleştirir", () => {
    const parse = createSseParser();
    expect(parse('event: tok')).toEqual([]);
    expect(parse('en\ndata: {"text":"a"}\n')).toEqual([]);
    expect(parse('\nevent: done\ndata: {}\n\n')).toEqual([
      { event: "token", data: '{"text":"a"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("CRLF, yorum satırı ve çok satırlı veriyi işler", () => {
    const parse = createSseParser();
    expect(parse(": ping\r\n\r\nevent: x\r\ndata: a\r\ndata: b\r\n\r\n")).toEqual([{ event: "x", data: "a\nb" }]);
  });

  it("baytların ortasından bölünen Türkçe harfi bozmaz", async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text":"kişi"}\n\n');
    const cut = bytes.indexOf(0xc5) + 1; // "ş" iki bayt: tam ortasından böl
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, cut));
        controller.enqueue(bytes.slice(cut));
        controller.close();
      },
    });

    const events = [];
    for await (const event of readSse(body)) events.push(event);

    expect(events).toEqual([{ event: "token", data: '{"text":"kişi"}' }]);
  });
});
