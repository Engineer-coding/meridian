import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/server/env";
import { endSession } from "@/server/oidc";
import { isAllowedOrigin } from "@/server/proxy";
import { SESSION_COOKIE, unseal, type Session } from "@/server/session";

/** Yalnızca POST: bir bağlantı ya da <img> kullanıcıyı çıkış yaptıramasın. */
export async function POST(request: NextRequest) {
  const config = env();
  if (!isAllowedOrigin("POST", request.headers.get("origin"), config.APP_URL)) {
    return NextResponse.json({ title: "Origin not allowed", status: 403 }, { status: 403 });
  }
  const store = await cookies();
  const session = await unseal<Session>(store.get(SESSION_COOKIE)?.value, config.SESSION_SECRET);
  store.delete(SESSION_COOKIE);
  if (session) await endSession(session);
  return NextResponse.redirect(new URL("/signed-out", config.APP_URL), 303);
}
