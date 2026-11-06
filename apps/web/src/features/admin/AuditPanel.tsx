"use client";

import { useInfiniteQuery } from "@tanstack/react-query";

import { useLocale, useT } from "@/i18n/context";
import { api, unwrap } from "@/lib/api/client";

import { QueryError, formatDateTime, useTenant } from "./AdminShell";

const shortId = (id: string) => id.slice(0, 8);

export function AuditPanel() {
  const t = useT();
  const locale = useLocale();
  const { tenantId } = useTenant();
  const audit = useInfiniteQuery({
    queryKey: ["audit", tenantId],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/v1/tenants/{tenantId}/audit-log", {
          params: { path: { tenantId }, query: { cursor: pageParam, limit: 50 } },
        }),
      ),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
  });
  const items = audit.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <h1>{t("adminAudit")}</h1>
      <p className="form-hint">{t("auditIntro")}</p>
      {audit.isError ? <QueryError error={audit.error} onRetry={() => void audit.refetch()} /> : null}
      {audit.isPending ? <p role="status">{t("loading")}</p> : null}
      {audit.isSuccess && items.length === 0 ? <p className="admin-empty">{t("auditEmpty")}</p> : null}
      {items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">{t("adminAudit")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("auditTime")}</th>
                <th scope="col">{t("auditActor")}</th>
                <th scope="col">{t("auditAction")}</th>
                <th scope="col">{t("auditOutcome")}</th>
                <th scope="col">{t("auditTarget")}</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => (
                <tr key={entry.id}>
                  <td>{formatDateTime(entry.createdAt, locale)}</td>
                  <td>
                    {entry.actorEmail ?? (entry.actorUserId ? shortId(entry.actorUserId) : "–")}
                    {entry.apiKeyId ? <span className="row-code">{t("auditViaKey", { id: shortId(entry.apiKeyId) })}</span> : null}
                  </td>
                  <td>
                    <code>{entry.action}</code>
                  </td>
                  <td>
                    <span className={entry.outcome === "denied" ? "badge badge-failed" : "badge badge-ready"}>
                      {t(entry.outcome === "denied" ? "auditDenied" : "auditAllowed")}
                    </span>
                  </td>
                  <td>{entry.targetId ? <code title={entry.targetId}>{shortId(entry.targetId)}</code> : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {audit.hasNextPage ? (
        <button type="button" className="btn" disabled={audit.isFetchingNextPage} onClick={() => void audit.fetchNextPage()}>
          {t("loadMore")}
        </button>
      ) : null}
    </>
  );
}
