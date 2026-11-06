"use client";

import { useT } from "@/i18n/context";
import type { CitedSource } from "@/lib/api/client";

import { plainExcerpt, safeHttpUrl } from "./citations";

export function Sources({
  sources,
  cited,
  active,
  idPrefix,
}: {
  sources: CitedSource[];
  cited: number[];
  active: number | null;
  idPrefix: string;
}) {
  const t = useT();
  if (sources.length === 0) return null;
  return (
    <details className="sources" open={active !== null || undefined}>
      <summary>{t("sourcesTitle", { count: sources.length })}</summary>
      <ol>
        {sources.map((source) => {
          const url = safeHttpUrl(source.url);
          return (
            <li
              key={source.number}
              id={`${idPrefix}-${source.number}`}
              className={source.number === active ? "source source-active" : "source"}
            >
              <span className="source-number">{source.number}</span>
              <div className="source-main">
                <p className="source-title">
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer nofollow">
                      {source.title}
                    </a>
                  ) : (
                    source.title
                  )}
                  {cited.includes(source.number) ? <span className="source-cited">{t("sourceCited")}</span> : null}
                </p>
                <p className="source-path">
                  {source.documentPath}
                  {source.section ? ` · ${source.section}` : ""}
                </p>
                <p className="source-content">{plainExcerpt(source.content)}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </details>
  );
}
