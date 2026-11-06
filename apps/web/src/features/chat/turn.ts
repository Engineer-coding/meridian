import type { ChatDoneEvent, CitedSource } from "@/lib/api/client";

/** Sürmekte olan tek bir soru-cevap. Saf reducer: akış sırası UI olmadan test edilir. */
export type Turn = {
  question: string;
  phase: "searching" | "waiting" | "streaming" | "finishing" | "stopped" | "failed";
  answer: string;
  sources: CitedSource[];
  done?: ChatDoneEvent;
  /** Sunucudaki mesaj sayısı: bu turdan önceki mesajlar ile bu turunkiler buradan ayrılır. */
  baseCount: number;
  error?: { key: "rateLimited" | "failed"; retryAfterSeconds?: number; detail?: string };
};

export type TurnAction =
  | { type: "sources"; sources: CitedSource[] }
  | { type: "token"; text: string }
  | { type: "done"; done: ChatDoneEvent }
  | { type: "stop" }
  | { type: "fail"; error: NonNullable<Turn["error"]> };

export function startTurn(question: string, baseCount: number): Turn {
  return { question, phase: "searching", answer: "", sources: [], baseCount };
}

export function turnReducer(turn: Turn, action: TurnAction): Turn {
  switch (action.type) {
    case "sources":
      return { ...turn, sources: action.sources, phase: "waiting" };
    case "token":
      return { ...turn, answer: turn.answer + action.text, phase: "streaming" };
    case "done":
      return { ...turn, answer: action.done.answer, done: action.done, phase: "finishing" };
    case "stop":
      return turn.phase === "finishing" ? turn : { ...turn, phase: "stopped" };
    case "fail":
      return { ...turn, phase: "failed", error: action.error };
  }
}
