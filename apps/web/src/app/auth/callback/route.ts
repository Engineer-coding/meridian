import { cookies } from "next/headers";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/server/env";
import { exchangeCode } from "@/server/oidc";
import { LOGIN_COOKIE, SESSION_COOKIE, cookieOptions, safeReturnTo, seal, unseal, type LoginState } from "@/server/session";

const SESSION_TTL_SECONDS = 60 * 60 * 8;

export async function GET(request: NextRequest) {
  const config = env();
  const store = await cookies();
  const login = await unseal<LoginState>(store.get(LOGIN_COOKIE)?.value, config.SESSION_SECRET);
  store.delete(LOGIN_COOKIE);
  const failed = NextResponse.redirect(new URL("/signed-out?error=login", config.APP_URL));
  if (!login) return failed;

  // Vekil arkasında request.url iç adres olabilir; doğrulama yayımlanan adresle yapılır.
  const callback = new URL("/auth/callback", config.APP_URL);
  callback.search = request.nextUrl.search;
  try {
    const session = await exchangeCode(callback, login.state, login.verifier);
    const response = NextResponse.redirect(new URL(safeReturnTo(login.returnTo), config.APP_URL));
    response.cookies.set(
      SESSION_COOKIE,
      await seal(session, config.SESSION_SECRET, SESSION_TTL_SECONDS),
      cookieOptions(config.APP_URL, SESSION_TTL_SECONDS),
    );
    return response;
  } catch (error) {
    console.warn("giriş tamamlanamadı", error instanceof Error ? error.message : "bilinmeyen hata");
    return failed;
  }
}
