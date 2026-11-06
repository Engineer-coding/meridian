"use client";

import { useEffect, useState } from "react";

import { useT } from "@/i18n/context";

import { AssistantMessage, UserMessage } from "./Message";
import type { Turn } from "./turn";

function Elapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return <span className="elapsed">{seconds} sn</span>;
}

export function TurnView({ turn, onRetry }: { turn: Turn; onRetry: () => void }) {
  const t = useT();
  const running = turn.phase === "searching" || turn.phase === "waiting" || turn.phase === "streaming";
  const status = turn.phase === "searching" ? t("statusSearching") : turn.phase === "waiting" ? t("statusWaiting") : null;

  return (
    <>
      <UserMessage text={turn.question} />
      {status ? (
        // Yerel modelde ilk token bir dakika sürebilir: kullanıcı neyin beklendiğini görmeli.
        <p className="status" role="status">
          <span className="status-dot" aria-hidden="true" />
          {status} <Elapsed />
        </p>
      ) : null}
      {turn.phase === "failed" ? (
        <div className="notice notice-warn" role="alert">
          <p>
            {turn.error?.key === "rateLimited"
              ? t("rateLimited", { seconds: turn.error.retryAfterSeconds ?? 60 })
              : t("failed")}
          </p>
          <button type="button" className="btn-quiet" onClick={onRetry}>
            {t("retry")}
          </button>
        </div>
      ) : (
        <AssistantMessage
          view={{
            text: turn.answer,
            sources: turn.sources,
            cited: turn.done?.cited ?? [],
            abstained: turn.done?.abstained ?? false,
            degraded: turn.done?.degraded ?? false,
            interrupted: turn.phase === "stopped",
            streaming: running,
          }}
        />
      )}
    </>
  );
}
