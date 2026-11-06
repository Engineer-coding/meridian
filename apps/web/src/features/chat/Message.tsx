"use client";

import dynamic from "next/dynamic";
import { useId, useState } from "react";

import { useT } from "@/i18n/context";
import type { CitedSource } from "@/lib/api/client";

import { Sources } from "./Sources";

// Markdown ayrıştırıcı ilk JS bütçesini aşırır; ilk cevaba kadar gerekmez.
const Answer = dynamic(() => import("./Answer").then((module) => module.Answer), { ssr: false });

export type AssistantView = {
  text: string;
  sources: CitedSource[];
  cited: number[];
  abstained: boolean;
  degraded: boolean;
  interrupted: boolean;
  streaming: boolean;
};

export function UserMessage({ text }: { text: string }) {
  return <p className="msg-user">{text}</p>;
}

export function AssistantMessage({ view, onRegenerate }: { view: AssistantView; onRegenerate?: () => void }) {
  const t = useT();
  const prefix = useId();
  const [active, setActive] = useState<number | null>(null);

  function openSource(number: number) {
    setActive(number);
    // <details> açıldıktan sonraki karede öğe görünür olur.
    requestAnimationFrame(() => {
      const element = document.getElementById(`${prefix}-${number}`);
      element?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }

  return (
    <article className="msg-assistant" aria-label={t("answerLabel")}>
      {view.abstained ? (
        <p className="notice notice-abstain">{t("abstained")}</p>
      ) : view.degraded ? (
        <p className="notice notice-warn">{t("degraded")}</p>
      ) : (
        <Answer text={view.text} sources={view.sources} onOpenSource={openSource} />
      )}
      {view.interrupted ? <p className="msg-meta">{t("interrupted")}</p> : null}
      <Sources sources={view.sources} cited={view.cited} active={active} idPrefix={prefix} />
      {onRegenerate && !view.streaming ? (
        <button type="button" className="btn-quiet" onClick={onRegenerate}>
          {t("regenerate")}
        </button>
      ) : null}
    </article>
  );
}
