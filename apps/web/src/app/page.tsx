import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Home } from "@/features/shell/Home";
import { env } from "@/server/env";
import { SESSION_COOKIE, unseal, type Session } from "@/server/session";

export default async function Page() {
  const store = await cookies();
  const session = await unseal<Session>(store.get(SESSION_COOKIE)?.value, env().SESSION_SECRET);
  if (!session) redirect("/auth/login");
  return <Home />;
}
