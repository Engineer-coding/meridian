"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";

import { ChatPage } from "@/features/chat/ChatPage";
import { useT } from "@/i18n/context";
import { api, unwrap } from "@/lib/api/client";

// Form doğrulama kütüphaneleri yalnızca ilk kurulumda gerekir.
const CreateTenant = dynamic(
  () => import("@/features/onboarding/CreateTenant").then((module) => module.CreateTenant),
  { ssr: false },
);

export function Home() {
  const t = useT();
  const me = useQuery({ queryKey: ["me"], queryFn: async () => unwrap(await api.GET("/v1/me")) });

  if (me.isPending) {
    return (
      <main className="center">
        <p role="status">{t("loading")}</p>
      </main>
    );
  }
  if (me.isError) {
    return (
      <main className="center">
        <div className="notice notice-warn" role="alert">
          <p>{t("apiDown")}</p>
          <button type="button" className="btn-quiet" onClick={() => void me.refetch()}>
            {t("retry")}
          </button>
        </div>
      </main>
    );
  }
  return me.data.memberships.length === 0 ? <CreateTenant /> : <ChatPage me={me.data} />;
}
