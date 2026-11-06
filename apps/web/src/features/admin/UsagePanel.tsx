"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { useLocale, useT } from "@/i18n/context";
import { api, unwrap, type UsageDay } from "@/lib/api/client";

import { QueryError, formatDateTime, useTenant } from "./AdminShell";
import { niceMax, quotaState } from "./usageMath";

export function UsagePanel() {
  const t = useT();
  const locale = useLocale();
  const { tenantId } = useTenant();
  const usage = useQuery({
    queryKey: ["usage", tenantId],
    queryFn: async () =>
      unwrap(await api.GET("/v1/tenants/{tenantId}/usage", { params: { path: { tenantId }, query: { days: 30 } } })),
  });

  const number = new Intl.NumberFormat(locale);

  if (usage.isPending) {
    return (
      <>
        <h1>{t("adminUsage")}</h1>
        <p role="status">{t("loading")}</p>
      </>
    );
  }
  if (usage.isError) {
    return (
      <>
        <h1>{t("adminUsage")}</h1>
        <QueryError error={usage.error} onRetry={() => void usage.refetch()} />
      </>
    );
  }

  const { plan, dailyTokenLimit, tokensToday, resetsAt, estimatedTokens, costUsd, days } = usage.data;
  const quota = quotaState(tokensToday, dailyTokenLimit);
  const periodTokens = days.reduce((sum, day) => sum + day.tokens, 0);
  const periodAnswers = days.reduce((sum, day) => sum + day.answers, 0);

  return (
    <>
      <h1>{t("adminUsage")}</h1>
      <section className="stat-row">
        <div className="stat stat-wide">
          <h2 id="quota-title">{t("usageQuotaToday")}</h2>
          <p className="stat-value">
            {number.format(tokensToday)} <span className="stat-unit">/ {number.format(dailyTokenLimit)}</span>
          </p>
          <div
            className={`meter meter-${quota.level}`}
            role="meter"
            aria-labelledby="quota-title"
            aria-valuemin={0}
            aria-valuemax={dailyTokenLimit}
            aria-valuenow={Math.min(tokensToday, dailyTokenLimit)}
            aria-valuetext={`%${quota.percent}`}
          >
            <span style={{ width: `${quota.percent}%` }} />
          </div>
          <p className="stat-note">
            {quota.level === "full" ? <strong>{t("usageQuotaFull")} </strong> : null}
            {t("usageResets", { plan, time: formatDateTime(resetsAt, locale) })}
          </p>
        </div>
        <div className="stat">
          <h2>{t("usagePeriodTokens")}</h2>
          <p className="stat-value">{number.format(periodTokens)}</p>
          <p className="stat-note">{t("usagePeriodAnswers", { count: number.format(periodAnswers) })}</p>
        </div>
        <div className="stat">
          <h2>{t("usageCost")}</h2>
          <p className="stat-value">{new Intl.NumberFormat(locale, { style: "currency", currency: "USD" }).format(costUsd)}</p>
          <p className="stat-note">{costUsd === 0 ? t("usageCostLocal") : t("usageCostPeriod")}</p>
        </div>
      </section>
      {estimatedTokens > 0 ? (
        <p className="form-hint">{t("usageEstimated", { count: number.format(estimatedTokens) })}</p>
      ) : null}

      <section>
        <h2>{t("usageChartTitle")}</h2>
        {periodTokens === 0 ? <p className="admin-empty">{t("usageEmpty")}</p> : <UsageChart days={days} />}
        <details className="chart-table">
          <summary>{t("usageShowTable")}</summary>
          <div className="table-wrap">
            <table className="data-table">
              <caption className="visually-hidden">{t("usageChartTitle")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("usageDate")}</th>
                  <th scope="col" className="num">
                    {t("usageTokens")}
                  </th>
                  <th scope="col" className="num">
                    {t("usageAnswers")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {days.map((day) => (
                  <tr key={day.date}>
                    <td>{shortDate(day.date, locale)}</td>
                    <td className="num">{number.format(day.tokens)}</td>
                    <td className="num">{number.format(day.answers)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    </>
  );
}

function shortDate(date: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`));
}

const HEIGHT = 220;
const MARGIN = { top: 12, right: 8, bottom: 24, left: 48 };

/** Tek seri: başlık adını söyler, gösterge gerekmez. Değerlerin tamamı grafiğin altındaki tabloda. */
function UsageChart({ days }: { days: UsageDay[] }) {
  const t = useT();
  const locale = useLocale();
  const [hovered, setHovered] = useState<number | null>(null);
  // Gerçek genişlikte çizilir: viewBox ile küçültmek telefonda yazıları okunmaz hâle getirir.
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry && entry.contentRect.width > 0) setWidth(entry.contentRect.width);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const number = new Intl.NumberFormat(locale, { notation: "compact" });
  const exact = new Intl.NumberFormat(locale);

  const max = niceMax(Math.max(...days.map((day) => day.tokens)));
  const plotWidth = width - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const step = plotWidth / days.length;
  const barWidth = Math.max(2, step - 2);
  const y = (value: number) => MARGIN.top + plotHeight * (1 - value / max);
  const active = hovered === null ? null : days[hovered];

  return (
    <div className="chart" ref={container}>
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={t("usageChartLabel", { from: shortDate(days[0]!.date, locale), to: shortDate(days.at(-1)!.date, locale) })}
        onMouseLeave={() => setHovered(null)}
      >
        {[0, 0.5, 1].map((ratio) => (
          <g key={ratio}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(max * ratio)} y2={y(max * ratio)} className={ratio === 0 ? "chart-axis" : "chart-grid"} />
            <text x={MARGIN.left - 8} y={y(max * ratio) + 4} textAnchor="end" className="chart-label">
              {number.format(max * ratio)}
            </text>
          </g>
        ))}
        {days.map((day, index) => {
          const x = MARGIN.left + index * step + (step - barWidth) / 2;
          const top = y(day.tokens);
          const height = HEIGHT - MARGIN.bottom - top;
          const radius = Math.min(4, barWidth / 2, height);
          return (
            <g key={day.date}>
              {day.tokens > 0 ? (
                <path
                  className={hovered === index ? "chart-bar chart-bar-active" : "chart-bar"}
                  d={`M${x},${top + height}V${top + radius}Q${x},${top} ${x + radius},${top}H${x + barWidth - radius}Q${x + barWidth},${top} ${x + barWidth},${top + radius}V${top + height}Z`}
                />
              ) : null}
              {/* Vurgu alanı çubuktan büyük: kısa çubukların da üzerine gelinebilir. */}
              <rect x={MARGIN.left + index * step} y={MARGIN.top} width={step} height={plotHeight} fill="transparent" onMouseEnter={() => setHovered(index)} />
            </g>
          );
        })}
        {[0, days.length - 1].map((index) => (
          <text key={index} x={index === 0 ? MARGIN.left : width - MARGIN.right} y={HEIGHT - 6} textAnchor={index === 0 ? "start" : "end"} className="chart-label">
            {shortDate(days[index]!.date, locale)}
          </text>
        ))}
      </svg>
      {active && hovered !== null ? (
        <div
          className="chart-tip"
          style={{
            left: `${((MARGIN.left + (hovered + 0.5) * step) / width) * 100}%`,
            transform: hovered > days.length / 2 ? "translateX(-100%)" : undefined,
          }}
        >
          <strong>{shortDate(active.date, locale)}</strong>
          <span>
            {exact.format(active.tokens)} {t("usageTokens").toLowerCase()}
          </span>
          <span>
            {exact.format(active.answers)} {t("usageAnswers").toLowerCase()}
          </span>
        </div>
      ) : null}
    </div>
  );
}
