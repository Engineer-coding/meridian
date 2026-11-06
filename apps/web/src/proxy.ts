import { NextResponse, type NextRequest } from "next/server";

/**
 * Her isteğe yeni nonce'lu CSP: model çıktısı ve belge içeriği güvenilmez veridir, sanitizer bir gün
 * delinse bile enjekte edilen betik çalışmamalı. Next, başlıktaki nonce'u kendi betiklerine ekler.
 */
export function proxy(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const dev = process.env.NODE_ENV === "development";
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    `connect-src 'self'${dev ? " ws:" : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("x-pathname", request.nextUrl.pathname);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Content-Type-Options", "nosniff");
  // "no-referrer" form gönderimlerinde Origin başlığını "null" yapar ve CSRF denetimini bozar.
  response.headers.set("Referrer-Policy", "same-origin");
  return response;
}

export const config = {
  // API vekili ve statik dosyalar HTML değildir.
  matcher: ["/((?!api/|auth/|_next/static|_next/image|favicon.ico).*)"],
};
