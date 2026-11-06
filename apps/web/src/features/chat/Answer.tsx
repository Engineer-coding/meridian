"use client";

import { createContext, useContext, useId, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import type { CitedSource } from "@/lib/api/client";
import { useT } from "@/i18n/context";

import { plainExcerpt, remarkCitations, safeHttpUrl } from "./citations";

const TIP_WIDTH = 340;
const TIP_MARGIN = 8;
const TIP_ROOM_ABOVE = 180;

/**
 * Sabit konum: konuşma alanı kaydırılabilir olduğu için `absolute` pencere kenarda kesilirdi. Üstte yer
 * yoksa altta açılır, yatayda ekranın dışına taşmaz.
 */
export function tooltipPosition(chip: { top: number; bottom: number; left: number; width: number }, viewport: number): CSSProperties {
  const width = Math.min(TIP_WIDTH, viewport - 2 * TIP_MARGIN);
  const centered = chip.left + chip.width / 2 - width / 2;
  const left = Math.max(TIP_MARGIN, Math.min(centered, viewport - width - TIP_MARGIN));
  return chip.top >= TIP_ROOM_ABOVE
    ? { left, width, bottom: `calc(100dvh - ${chip.top - 6}px)` }
    : { left, width, top: chip.bottom + 6 };
}

function Citation({
  number,
  source,
  onOpen,
}: {
  number: string;
  source: CitedSource | undefined;
  onOpen: (number: number) => void;
}) {
  const t = useT();
  const [position, setPosition] = useState<CSSProperties | null>(null);
  const open = position !== null;
  const tooltip = useId();

  function show(element: HTMLElement) {
    setPosition(tooltipPosition(element.getBoundingClientRect(), window.innerWidth));
  }
  const hide = () => setPosition(null);
  // Model var olmayan bir kaynak numarası yazdıysa bağlantı gibi gösterilmez.
  if (!source) {
    return (
      <span className="cite cite-invalid" title={t("citationMissing")}>
        {number}
      </span>
    );
  }
  return (
    <span className="cite-wrap" onMouseEnter={(event) => show(event.currentTarget)} onMouseLeave={hide}>
      <button
        type="button"
        className="cite"
        aria-label={t("citationLabel", { number, title: source.title })}
        aria-describedby={open ? tooltip : undefined}
        onClick={() => onOpen(source.number)}
        onFocus={(event) => show(event.currentTarget)}
        onBlur={hide}
        onKeyDown={(event) => {
          if (event.key === "Escape") hide();
        }}
      >
        {number}
      </button>
      {open ? (
        <span role="tooltip" id={tooltip} className="cite-tip" style={position ?? undefined}>
          <span className="cite-tip-title">{source.section || source.title}</span>
          <span className="cite-tip-body">{plainExcerpt(source.content, 280)}</span>
        </span>
      ) : null}
    </span>
  );
}

type AnswerContextValue = { sources: CitedSource[]; onOpenSource: (number: number) => void };

const AnswerContext = createContext<AnswerContextValue>({ sources: [], onOpenSource: () => undefined });

function CitationNode({ n }: { n?: string }) {
  const { sources, onOpenSource } = useContext(AnswerContext);
  return (
    <Citation number={n ?? ""} source={sources.find((source) => String(source.number) === n)} onOpen={onOpenSource} />
  );
}

// Modül düzeyinde sabit: render içinde tanımlansaydı her token'da bileşen türü değişir, atıf düğmesi
// yeniden kurulur, klavye odağı ve açık kaynak penceresi kaybolurdu.
const COMPONENTS = {
  // Model çıktısı güvenilmez veridir: ham HTML hiç işlenmez (rehype-raw yok), bağlantı yalnızca http(s).
  a: ({ href, children }: { href?: string; children?: ReactNode }) => {
    const safe = safeHttpUrl(href);
    return safe ? (
      <a href={safe} target="_blank" rel="noopener noreferrer nofollow">
        {children}
      </a>
    ) : (
      <>{children}</>
    );
  },
  // Görsel, kullanıcının IP'sini ve soruyu dışarı sızdırmanın klasik yoludur (CSP de engeller).
  img: ({ alt }: { alt?: string }) => <>{alt}</>,
  cite: CitationNode,
} as unknown as Components;

const REMARK_PLUGINS = [remarkGfm, remarkCitations];

export function Answer({
  text,
  sources,
  onOpenSource,
}: {
  text: string;
  sources: CitedSource[];
  onOpenSource: (number: number) => void;
}) {
  const context = useMemo(() => ({ sources, onOpenSource }), [sources, onOpenSource]);
  return (
    <AnswerContext.Provider value={context}>
      <div className="answer">
        <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>
          {text}
        </ReactMarkdown>
      </div>
    </AnswerContext.Provider>
  );
}
