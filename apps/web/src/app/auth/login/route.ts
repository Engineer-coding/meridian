import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/server/env";
import { authorizationRedirect } from "@/server/oidc";
import { LOGIN_COOKIE, cookieOptions, safeReturnTo, seal } from "@/server/session";

const LOGIN_TTL_SECONDS = 600;

export async function GET(request: NextRequest) {
  const config = env();
  const { url, state, verifier } = await authorizationRedirect(new URL("/auth/callback", config.APP_URL).href);
  const response = NextResponse.redirect(url);
  response.cookies.set(
    LOGIN_COOKIE,
    await seal(
      { state, verifier, returnTo: safeReturnTo(request.nextUrl.searchParams.get("returnTo")) },
      config.SESSION_SECRET,
      LOGIN_TTL_SECONDS,
    ),
    cookieOptions(config.APP_URL, LOGIN_TTL_SECONDS),
  );
  return response;
}
