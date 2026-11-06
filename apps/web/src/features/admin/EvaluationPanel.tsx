"use client";

import { useLocale, useT } from "@/i18n/context";
import type { MessageKey } from "@/i18n/messages";

import evalData from "./evalData.json";
import { formatMetric, thresholdState } from "./evalMath";

const LABELS: Record<string, MessageKey> = {
  "recall@3": "evalRecall3",
  "recall@5": "evalRecall5",
  mrr: "evalMrr",
  correct: "evalCorrect",
  correct_when_answered: "evalCorrectAnswered",
  abstain_when_unanswerable: "evalAbstainUnanswerable",
  abstain_when_answerable: "evalAbstainAnswerable",
  gold_in_context: "evalGoldInContext",
  gold_cited: "evalGoldCited",
  invalid_citation_rate: "evalInvalidCitation",
  median_total_seconds: "evalLatency",
};

type Values = Record<string, number | undefined> | null;
type Release = (typeof evalData.releases)[number] & { retrieval: Values; answers: Values };

export function EvaluationPanel() {
  const t = useT();
  const locale = useLocale();
  const releases = evalData.releases as Release[];
  const { min, max } = evalData.thresholds as { min: Record<string, number>; max: Record<string, number> };
  const metrics = [...evalData.metrics.retrieval, ...evalData.metrics.answers];
  const value = (release: Release, metric: string) => (release.retrieval?.[metric] ?? release.answers?.[metric]) as number | undefined;

  return (
    <>
      <h1>{t("adminEvaluation")}</h1>
      <p className="form-hint">{t("evalIntro")}</p>
      <p className="notice">{t("evalNotComparable")}</p>
      <div className="table-wrap">
        <table className="data-table eval-table">
          <caption className="visually-hidden">{t("adminEvaluation")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("evalMetric")}</th>
              {releases.map((release) => (
                <th scope="col" className="num" key={release.version}>
                  {release.version}
                  <span className="th-note">
                    {t("evalGolden", { golden: release.golden, count: release.questions })}
                  </span>
                </th>
              ))}
              <th scope="col" className="num">
                {t("evalThreshold")}
              </th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric) => (
              <tr key={metric}>
                <th scope="row">{t(LABELS[metric]!)}</th>
                {releases.map((release) => {
                  const state = thresholdState(value(release, metric), min[metric], max[metric]);
                  return (
                    <td className="num" key={release.version}>
                      {formatMetric(metric, value(release, metric), locale)}
                      {/* Eşikler yalnızca güncel altın sete uygulanır. */}
                      {state === "fail" && release.golden === "v2" ? <span className="badge badge-failed"> {t("evalBelow")}</span> : null}
                    </td>
                  );
                })}
                <td className="num">
                  {min[metric] !== undefined ? `≥ ${formatMetric(metric, min[metric], locale)}` : null}
                  {max[metric] !== undefined ? `≤ ${formatMetric(metric, max[metric], locale)}` : null}
                  {min[metric] === undefined && max[metric] === undefined ? "–" : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
