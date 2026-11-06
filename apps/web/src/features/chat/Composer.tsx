"use client";

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { useT } from "@/i18n/context";

const MAX_LENGTH = 4000;

export function Composer({
  busy,
  onSend,
  onStop,
}: {
  busy: boolean;
  onSend: (question: string) => void;
  onStop: () => void;
}) {
  const t = useT();
  const [value, setValue] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  const question = value.trim();

  function submit(event?: FormEvent) {
    event?.preventDefault();
    if (busy || !question) return;
    onSend(question);
    setValue("");
    area.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) submit(event);
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        {t("questionLabel")}
      </label>
      <textarea
        id="question"
        ref={area}
        rows={2}
        maxLength={MAX_LENGTH}
        value={value}
        placeholder={t("questionPlaceholder")}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
      />
      {busy ? (
        <button type="button" className="btn btn-stop" onClick={onStop}>
          {t("stop")}
        </button>
      ) : (
        <button type="submit" className="btn btn-primary" disabled={!question}>
          {t("send")}
        </button>
      )}
    </form>
  );
}
