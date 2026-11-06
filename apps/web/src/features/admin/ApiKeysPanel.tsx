"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useLocale, useT } from "@/i18n/context";
import type { MessageKey } from "@/i18n/messages";
import { ApiError, api, unwrap, type ApiKeyScope } from "@/lib/api/client";

import { QueryError, formatDateTime, useTenant } from "./AdminShell";

const SCOPES: { value: ApiKeyScope; label: MessageKey }[] = [
  { value: "sources:read", label: "scopeSourcesRead" },
  { value: "sources:write", label: "scopeSourcesWrite" },
  { value: "chat", label: "scopeChat" },
];

const schema = z.object({
  name: z.string().trim().min(1).max(100),
  scopes: z.array(z.enum(["sources:read", "sources:write", "chat"])).min(1),
  expiresInDays: z.coerce.number<string>().int().min(1).max(365),
});
type Input = z.input<typeof schema>;
type Output = z.output<typeof schema>;

export function ApiKeysPanel() {
  const t = useT();
  const locale = useLocale();
  const { tenantId } = useTenant();
  const queryClient = useQueryClient();
  const key = ["api-keys", tenantId];
  // Gizli değer yalnızca bellekte ve yalnızca bu cevaptan sonra: yeniden okunamaz.
  const [secret, setSecret] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [now] = useState(() => Date.now());

  const keys = useQuery({
    queryKey: key,
    queryFn: async () => unwrap(await api.GET("/v1/tenants/{tenantId}/api-keys", { params: { path: { tenantId } } })),
  });
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Input, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", scopes: [], expiresInDays: "90" },
  });

  const create = useMutation({
    mutationFn: async (body: Output) =>
      unwrap(await api.POST("/v1/tenants/{tenantId}/api-keys", { params: { path: { tenantId } }, body })),
    onSuccess: (created) => {
      setSecret(created.secret);
      setCopied(false);
      reset();
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const revoke = useMutation({
    mutationFn: async (apiKeyId: string) => {
      const result = await api.DELETE("/v1/tenants/{tenantId}/api-keys/{apiKeyId}", { params: { path: { tenantId, apiKeyId } } });
      if (!result.response.ok) throw new ApiError(result.response.status, "error");
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  async function copy() {
    try {
      await navigator.clipboard.writeText(secret!);
      setCopied(true);
    } catch {
      setCopied(false); // pano engelliyse metin ekranda seçilebilir durumda kalır
    }
  }

  return (
    <>
      <h1>{t("adminApiKeys")}</h1>
      <p className="form-hint">{t("apiKeysIntro")}</p>

      {keys.isError ? (
        <QueryError error={keys.error} onRetry={() => void keys.refetch()} />
      ) : (
        <>
          {secret ? (
            <div className="secret-box" role="status">
              <p>
                <strong>{t("apiKeySecretOnce")}</strong>
              </p>
              <code>{secret}</code>
              <div className="secret-actions">
                <button type="button" className="btn" onClick={() => void copy()}>
                  {copied ? t("copied") : t("copy")}
                </button>
                <button type="button" className="btn-quiet" onClick={() => setSecret(null)}>
                  {t("apiKeySecretDone")}
                </button>
              </div>
            </div>
          ) : null}

          <details className="admin-form">
            <summary>{t("apiKeyCreate")}</summary>
            <form onSubmit={handleSubmit((values) => create.mutate(values))} noValidate>
              <div className="form-grid">
                <div>
                  <label htmlFor="key-name">{t("apiKeyName")}</label>
                  <input id="key-name" aria-invalid={!!errors.name} aria-describedby="key-name-error" {...register("name")} />
                  <p id="key-name-error" className="field-error">
                    {errors.name ? t("apiKeyNameError") : ""}
                  </p>
                </div>
                <div>
                  <label htmlFor="key-days">{t("apiKeyDays")}</label>
                  <input id="key-days" type="number" min={1} max={365} aria-invalid={!!errors.expiresInDays} aria-describedby="key-days-error" {...register("expiresInDays")} />
                  <p id="key-days-error" className="field-error">
                    {errors.expiresInDays ? t("apiKeyDaysError") : ""}
                  </p>
                </div>
              </div>
              <fieldset aria-describedby="key-scopes-error">
                <legend>{t("apiKeyScopes")}</legend>
                {SCOPES.map((scope) => (
                  <label key={scope.value} className="check">
                    <input type="checkbox" value={scope.value} {...register("scopes")} />
                    {t(scope.label)}
                  </label>
                ))}
                <p id="key-scopes-error" className="field-error">
                  {errors.scopes ? t("apiKeyScopesError") : ""}
                </p>
              </fieldset>
              {create.isError ? (
                <p className="notice notice-warn" role="alert">
                  {t("failed")}
                </p>
              ) : null}
              <button type="submit" className="btn btn-primary" disabled={create.isPending}>
                {t("apiKeyCreate")}
              </button>
            </form>
          </details>

          {revoke.isError ? (
            <p className="notice notice-warn" role="alert">
              {t("failed")}
            </p>
          ) : null}
          {keys.isPending ? <p role="status">{t("loading")}</p> : null}
          {keys.data?.length === 0 ? <p className="admin-empty">{t("apiKeysEmpty")}</p> : null}
          {keys.data?.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <caption className="visually-hidden">{t("adminApiKeys")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("apiKeyName")}</th>
                    <th scope="col">{t("apiKeyScopes")}</th>
                    <th scope="col">{t("apiKeyLastUsed")}</th>
                    <th scope="col">{t("apiKeyExpires")}</th>
                    <th scope="col">
                      <span className="visually-hidden">{t("actions")}</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {keys.data.map((item) => {
                    const expired = new Date(item.expiresAt).getTime() <= now;
                    return (
                      <tr key={item.id}>
                        <td>
                          {item.name}
                          <code className="row-code">{item.prefix}…</code>
                        </td>
                        <td>{item.scopes.join(", ")}</td>
                        <td>{formatDateTime(item.lastUsedAt, locale)}</td>
                        <td>{formatDateTime(item.expiresAt, locale)}</td>
                        <td className="row-actions">
                          {item.revokedAt ? (
                            <span className="badge badge-deleting">{t("apiKeyRevoked")}</span>
                          ) : expired ? (
                            <span className="badge badge-deleting">{t("apiKeyExpired")}</span>
                          ) : (
                            <button
                              type="button"
                              className="btn-quiet btn-danger"
                              disabled={revoke.isPending}
                              aria-label={`${t("apiKeyRevoke")}: ${item.name}`}
                              onClick={() => {
                                if (window.confirm(t("apiKeyRevokeConfirm", { name: item.name }))) revoke.mutate(item.id);
                              }}
                            >
                              {t("apiKeyRevoke")}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
