import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/server/env";
import { refresh } from "@/server/oidc";
import { isAllowedOrigin, requestHeaders, responseHeaders, upstreamUrl } from "@/server/proxy";
import { SESSION_COOKIE, cookieOptions, seal, unseal, type Session } from "@/server/session";

const SESSION_TTL_SECONDS = 60 * 60 * 8;
const REFRESH_MARGIN_SECONDS = 30;

function problem(status: number, title: string): NextResponse {
  return NextResponse.json({ title, status }, { status, headers: { "Content-Type": "application/problem+json" } });
}

async function validSession(): Promise<Session | null> {
  const config = env();
  const store = await cookies();
  const session = await unseal<Session>(store.get(SESSION_COOKIE)?.value, config.SESSION_SECRET);
  if (!session) return null;
  if (session.expiresAt - REFRESH_MARGIN_SECONDS > Date.now() / 1000) return session;

  const renewed = await refresh(session);
  if (!renewed) {
    store.delete(SESSION_COOKIE);
    return null;
  }
  store.set(
    SESSION_COOKIE,
    await seal(renewed, config.SESSION_SECRET, SESSION_TTL_SECONDS),
    cookieOptions(config.APP_URL, SESSION_TTL_SECONDS),
  );
  return renewed;
}

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const config = env();
  if (!isAllowedOrigin(request.method, request.headers.get("origin"), config.APP_URL)) {
    return problem(403, "Origin not allowed");
  }
  const { path } = await context.params;
  const target = upstreamUrl(config.API_URL, path, request.nextUrl.search);
  if (!target) return problem(400, "Invalid path");

  const session = await validSession();
  if (!session) return problem(401, "Not signed in");

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: requestHeaders(request.headers, session.accessToken),
      body: hasBody ? request.body : undefined,
      // İstemci "durdur" dediğinde bağlantı API'ye kadar kapanır; API mesajı interrupted kaydeder.
      signal: request.signal,
      redirect: "manual",
      cache: "no-store",
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch {
    return problem(502, "API unavailable");
  }
  return new NextResponse(upstream.body, { status: upstream.status, headers: responseHeaders(upstream.headers) });
}

export const dynamic = "force-dynamic";
export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE };
