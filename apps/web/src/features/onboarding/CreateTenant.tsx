"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useT } from "@/i18n/context";
import { ApiError, api, unwrap } from "@/lib/api/client";

const schema = z.object({
  name: z.string().trim().min(2).max(100),
  slug: z.string().regex(/^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/),
});
type Form = z.infer<typeof schema>;

export function CreateTenant() {
  const t = useT();
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(schema) });

  const create = useMutation({
    mutationFn: async (body: Form) => unwrap(await api.POST("/v1/tenants", { params: { header: { "Idempotency-Key": crypto.randomUUID() } }, body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  });

  return (
    <main className="center">
      <form className="card" onSubmit={handleSubmit((values) => create.mutate(values))} noValidate>
        <h1>{t("onboardingTitle")}</h1>
        <p>{t("onboardingBody")}</p>
        <label htmlFor="name">{t("tenantName")}</label>
        <input id="name" aria-invalid={!!errors.name} aria-describedby="name-error" {...register("name")} />
        <p id="name-error" className="field-error">
          {errors.name ? t("tenantNameError") : ""}
        </p>
        <label htmlFor="slug">{t("tenantSlug")}</label>
        <input id="slug" aria-invalid={!!errors.slug} aria-describedby="slug-error" {...register("slug")} />
        <p id="slug-error" className="field-error">
          {errors.slug ? t("tenantSlugError") : ""}
        </p>
        {create.isError ? (
          <p className="notice notice-warn" role="alert">
            {create.error instanceof ApiError && create.error.status === 409 ? t("tenantConflict") : t("failed")}
          </p>
        ) : null}
        <button type="submit" className="btn btn-primary" disabled={create.isPending}>
          {t("createTenant")}
        </button>
      </form>
    </main>
  );
}
