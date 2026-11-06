import { describe, expect, it } from "vitest";

import type { ChatDoneEvent } from "@/lib/api/client";

import { startTurn, turnReducer } from "./turn";

const done: ChatDoneEvent = { messageId: "m", answer: "Tam cevap [1].", cited: [1], abstained: false, degraded: false };

describe("sohbet turu", () => {
  it("kaynak → token → son olay sırasını izler", () => {
    let turn = startTurn("soru", 2);
    expect(turn.phase).toBe("searching");

    turn = turnReducer(turn, { type: "sources", sources: [] });
    expect(turn.phase).toBe("waiting");

    turn = turnReducer(turnReducer(turn, { type: "token", text: "Ta" }), { type: "token", text: "m" });
    expect(turn).toMatchObject({ answer: "Tam", phase: "streaming" });

    turn = turnReducer(turn, { type: "done", done });
    expect(turn).toMatchObject({ answer: "Tam cevap [1].", phase: "finishing", baseCount: 2 });
  });

  it("durdurma yarım cevabı korur", () => {
    const turn = turnReducer(turnReducer(startTurn("soru", 0), { type: "token", text: "yarım" }), { type: "stop" });
    expect(turn).toMatchObject({ answer: "yarım", phase: "stopped" });
  });

  it("biten cevap durdurulmuş sayılmaz", () => {
    const finished = turnReducer(startTurn("soru", 0), { type: "done", done });
    expect(turnReducer(finished, { type: "stop" }).phase).toBe("finishing");
  });
});
