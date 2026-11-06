"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useLocale, useT } from "@/i18n/context";
import type { MessageKey } from "@/i18n/messages";
import { ApiError, api, unwrap, type Source } from "@/lib/api/client";

import { QueryError, formatDateTime, useTenant } from "./AdminShell";
import { refetchWhileActive } from "./sourceStatus";

const STATUS: Record<Source["status"], MessageKey> = {
  pending: "sourcePending",
  indexing: "sourceIndexing",
  ready: "sourceReady",
  failed: "sourceFailed",
  deleting: "sourceDeleting",
};

const schema = z.object({
  name: z.string().trim().min(1).max(200),
  collectionId: z.string().min(1),
  repository: z.string().trim().regex(/^[\w.-]+\/[\w.-]+$/),
  branch: z.string().trim().max(200),
  paths: z.string().trim().max(1000),
});
type Form = z.infer<typeof schema>;

export function SourcesPanel() {
  const t = useT();
  const locale = useLocale();
  const { tenantId, isAdmin, canContribute } = useTenant();
  const queryClient = useQueryClient();
  const key = ["sources", tenantId];

  const sources = useInfiniteQuery({
    queryKey: key,
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/v1/tenants/{tenantId}/sources", {
          params: { path: { tenantId }, query: { cursor: pageParam, limit: 20 } },
        }),
      ),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    refetchInterval: (query) => refetchWhileActive(query.state.data?.pages.flatMap((page) => page.items) ?? []),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: key });
  const retry = useMutation({
    mutationFn: async (sourceId: string) =>
      unwrap(await api.POST("/v1/tenants/{tenantId}/sources/{sourceId}/retry", { params: { path: { tenantId, sourceId } } })),
    onSettled: refresh,
  });
  const remove = useMutation({
    mutationFn: async (sourceId: string) => {
      const result = await api.DELETE("/v1/tenants/{tenantId}/sources/{sourceId}", { params: { path: { tenantId, sourceId } } });
      if (!result.response.ok) throw new ApiError(result.response.status, "error");
    },
    onSettled: refresh,
  });

  const items = sources.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <>
      <h1>{t("adminSources")}</h1>
      {canContribute ? <AddSource onAdded={refresh} /> : null}
      {sources.isError ? <QueryError error={sources.error} onRetry={() => void sources.refetch()} /> : null}
      {sources.isPending ? <p role="status">{t("loading")}</p> : null}
      {sources.isSuccess && items.length === 0 ? <p className="admin-empty">{t("sourcesEmpty")}</p> : null}
      {retry.isError || remove.isError ? (
        <p className="notice notice-warn" role="alert">
          {t("failed")}
        </p>
      ) : null}
      {items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">{t("adminSources")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("sourceName")}</th>
                <th scope="col">{t("sourceStatus")}</th>
                <th scope="col" className="num">
                  {t("sourceDocuments")}
                </th>
                <th scope="col">{t("sourceLastIndexed")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((source) => (
                <tr key={source.id}>
                  <td>
                    {source.name}
                    {source.lastError ? <span className="row-error">{source.lastError}</span> : null}
                  </td>
                  <td>
                    <span className={`badge badge-${source.status}`}>{t(STATUS[source.status])}</span>
                  </td>
                  <td className="num">{source.documentCount ?? 0}</td>
                  <td>{formatDateTime(source.lastIndexedAt, locale)}</td>
                  <td className="row-actions">
                    {source.status === "failed" && canContribute ? (
                      <button
                        type="button"
                        className="btn-quiet"
                        disabled={retry.isPending}
                        aria-label={`${t("sourceRetry")}: ${source.name}`}
                        onClick={() => retry.mutate(source.id)}
                      >
                        {t("sourceRetry")}
                      </button>
                    ) : null}
                    {isAdmin && source.status !== "deleting" ? (
                      <button
                        type="button"
                        className="btn-quiet btn-danger"
                        disabled={remove.isPending}
                        aria-label={`${t("delete")}: ${source.name}`}
                        onClick={() => {
                          if (window.confirm(t("sourceDeleteConfirm", { name: source.name }))) remove.mutate(source.id);
                        }}
                      >
                        {t("delete")}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {sources.hasNextPage ? (
        <button type="button" className="btn" disabled={sources.isFetchingNextPage} onClick={() => void sources.fetchNextPage()}>
          {t("loadMore")}
        </button>
      ) : null}
    </>
  );
}

function AddSource({ onAdded }: { onAdded: () => void }) {
  const t = useT();
  const { tenantId, isAdmin } = useTenant();
  const queryClient = useQueryClient();
  const collectionsKey = ["collections", tenantId];

  const collections = useQuery({
    queryKey: collectionsKey,
    queryFn: async () => unwrap(await api.GET("/v1/tenants/{tenantId}/collections", { params: { path: { tenantId } } })),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { branch: "main", paths: "" } });

  const add = useMutation({
    mutationFn: async ({ name, collectionId, repository, branch, paths }: Form) =>
      unwrap(
        await api.POST("/v1/tenants/{tenantId}/sources", {
          params: { path: { tenantId }, header: { "Idempotency-Key": crypto.randomUUID() } },
          body: {
            name,
            collectionId,
            config: {
              type: "github",
              repository,
              branch: branch || "main",
              paths: paths.split(",").map((path) => path.trim()).filter(Boolean),
            },
          },
        }),
      ),
    onSuccess: () => {
      reset();
      onAdded();
    },
  });

  const createCollection = useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/v1/tenants/{tenantId}/collections", {
          params: { path: { tenantId }, header: { "Idempotency-Key": crypto.randomUUID() } },
          body: { name: t("collectionDefaultName") },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: collectionsKey }),
  });

  if (collections.isPending) return null;
  if (collections.isSuccess && collections.data.length === 0) {
    return (
      <div className="notice">
        <p>{isAdmin ? t("collectionNeeded") : t("collectionNeededMember")}</p>
        {isAdmin ? (
          <button type="button" className="btn" disabled={createCollection.isPending} onClick={() => createCollection.mutate()}>
            {t("collectionCreate")}
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <details className="admin-form">
      <summary>{t("sourceAdd")}</summary>
      <form onSubmit={handleSubmit((values) => add.mutate(values))} noValidate>
        <p className="form-hint">{t("sourceGithubOnly")}</p>
        <div className="form-grid">
          <div>
            <label htmlFor="source-name">{t("sourceName")}</label>
            <input id="source-name" aria-invalid={!!errors.name} aria-describedby="source-name-error" {...register("name")} />
            <p id="source-name-error" className="field-error">
              {errors.name ? t("sourceNameError") : ""}
            </p>
          </div>
          <div>
            <label htmlFor="source-collection">{t("sourceCollection")}</label>
            <select id="source-collection" {...register("collectionId")}>
              {collections.data?.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="source-repository">{t("sourceRepository")}</label>
            <input
              id="source-repository"
              placeholder="kubernetes/website"
              aria-invalid={!!errors.repository}
              aria-describedby="source-repository-error"
              {...register("repository")}
            />
            <p id="source-repository-error" className="field-error">
              {errors.repository ? t("sourceRepositoryError") : ""}
            </p>
          </div>
          <div>
            <label htmlFor="source-branch">{t("sourceBranch")}</label>
            <input id="source-branch" {...register("branch")} />
          </div>
          <div className="form-wide">
            <label htmlFor="source-paths">{t("sourcePaths")}</label>
            <input id="source-paths" placeholder="docs, content/en" {...register("paths")} />
          </div>
        </div>
        {add.isError ? (
          <p className="notice notice-warn" role="alert">
            {t("failed")}
          </p>
        ) : null}
        <button type="submit" className="btn btn-primary" disabled={add.isPending}>
          {t("sourceAdd")}
        </button>
      </form>
    </details>
  );
}
