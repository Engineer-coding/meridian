import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AgentPage } from "@/features/agent/AgentPage";
import { env } from "@/server/env";
import { SESSION_COOKIE, unseal, type Session } from "@/server/session";

export default async function Page() {
  const store = await cookies();
  const session = await unseal<Session>(store.get(SESSION_COOKIE)?.value, env().SESSION_SECRET);
  if (!session) redirect("/auth/login?returnTo=%2Fagent");
  return <AgentPage />;
}
