"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, type ReactNode } from "react";

import { useSelectedTenant } from "@/features/shell/tenant";
import { useT } from "@/i18n/context";
import type { MessageKey } from "@/i18n/messages";
import { ApiError, api, unwrap, type Membership } from "@/lib/api/client";

type Tenant = { tenantId: string; role: Membership["role"]; isAdmin: boolean; canContribute: boolean };

const TenantContext = createContext<Tenant | null>(null);

export function useTenant(): Tenant {
  const tenant = useContext(TenantContext);
  if (!tenant) throw new Error("useTenant yalnızca AdminShell içinde kullanılır");
  return tenant;
}

const SECTIONS: { href: string; label: MessageKey; adminOnly: boolean }[] = [
  { href: "/admin/sources", label: "adminSources", adminOnly: false },
  { href: "/admin/usage", label: "adminUsage", adminOnly: true },
  { href: "/admin/evaluation", label: "adminEvaluation", adminOnly: false },
  { href: "/admin/api-keys", label: "adminApiKeys", adminOnly: true },
  { href: "/admin/audit", label: "adminAudit", adminOnly: true },
];

export function AdminShell({ children }: { children: ReactNode }) {
  const t = useT();
  const me = useQuery({ queryKey: ["me"], queryFn: async () => unwrap(await api.GET("/v1/me")) });

  if (me.isPending) {
    return (
      <main className="center">
        <p role="status">{t("loading")}</p>
      </main>
    );
  }
  if (me.isError || me.data.memberships.length === 0) {
    return (
      <main className="center">
        <div className="notice notice-warn" role="alert">
          <p>{me.isError ? t("apiDown") : t("adminNoWorkspace")}</p>
          <Link href="/">{t("adminBackToChat")}</Link>
        </div>
      </main>
    );
  }
  return <Loaded me={me.data}>{children}</Loaded>;
}

function Loaded({ me, children }: { me: Parameters<typeof useSelectedTenant>[0]; children: ReactNode }) {
  const t = useT();
  const pathname = usePathname();
  const { membership, select } = useSelectedTenant(me);
  const isAdmin = membership.role === "owner" || membership.role === "admin";
  const tenant: Tenant = {
    tenantId: membership.tenantId,
    role: membership.role,
    isAdmin,
    canContribute: membership.role !== "viewer",
  };

  return (
    <div className="admin">
      <header className="admin-top">
        <span className="brand">Meridian</span>
        {me.memberships.length > 1 ? (
          <label className="tenant">
            <span className="visually-hidden">{t("workspace")}</span>
            <select value={membership.tenantId} onChange={(event) => select(event.target.value)}>
              {me.memberships.map((item) => (
                <option key={item.tenantId} value={item.tenantId}>
                  {item.tenantName}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="tenant">{membership.tenantName}</span>
        )}
        <Link href="/" className="admin-back">
          {t("adminBackToChat")}
        </Link>
      </header>
      <nav className="admin-nav" aria-label={t("adminTitle")}>
        <ul>
          {SECTIONS.filter((section) => isAdmin || !section.adminOnly).map((section) => (
            <li key={section.href}>
              <Link href={section.href} aria-current={pathname === section.href ? "page" : undefined}>
                {t(section.label)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {/* Çalışma alanı değişince paneller sıfırlanır: kiracıların verisi birbirine karışmaz. */}
      <main className="admin-main" key={membership.tenantId}>
        <TenantContext.Provider value={tenant}>{children}</TenantContext.Provider>
      </main>
    </div>
  );
}

/** Sorgu hatası: yetki yoksa bunu söyler, değilse yeniden deneme sunar. */
export function QueryError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  const t = useT();
  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="notice notice-warn" role="alert">
        {t("adminForbidden")}
      </p>
    );
  }
  return (
    <div className="notice notice-warn" role="alert">
      <p>{t("failed")}</p>
      <button type="button" className="btn-quiet" onClick={onRetry}>
        {t("retry")}
      </button>
    </div>
  );
}

export function formatDateTime(value: string | null | undefined, locale: string): string {
  if (!value) return "–";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
