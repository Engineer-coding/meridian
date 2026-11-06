import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AdminShell } from "@/features/admin/AdminShell";
import { env } from "@/server/env";
import { SESSION_COOKIE, unseal, type Session } from "@/server/session";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const store = await cookies();
  const session = await unseal<Session>(store.get(SESSION_COOKIE)?.value, env().SESSION_SECRET);
  if (!session) {
    // Sayfa yolunu proxy yazar; kullanıcı girişten sonra açmak istediği sayfaya döner.
    const path = (await headers()).get("x-pathname") ?? "/admin";
    redirect(`/auth/login?returnTo=${encodeURIComponent(path)}`);
  }
  return <AdminShell>{children}</AdminShell>;
}
