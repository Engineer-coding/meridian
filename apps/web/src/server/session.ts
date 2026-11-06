import { EncryptJWT, jwtDecrypt } from "jose";

/**
 * Oturum, HttpOnly bir çerezde şifreli (JWE) durur. Token'lar tarayıcı koduna hiç ulaşmaz: XSS
 * oturumu çalamaz, API'yi yalnızca sayfa açıkken çağırabilir (ADR-0013).
 */
export type Session = {
  accessToken: string;
  refreshToken?: string;
  /** Erişim token'ının bitişi, epoch saniye. */
  expiresAt: number;
};

export type LoginState = { state: string; verifier: string };

export const SESSION_COOKIE = "meridian_session";
export const LOGIN_COOKIE = "meridian_login";
// Tarayıcılar 4096 baytın üstündeki çerezi sessizce atar; bu da sonsuz giriş döngüsü demektir.
export const MAX_COOKIE_BYTES = 4000;

async function key(secret: string): Promise<Uint8Array> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret));
  return new Uint8Array(digest);
}

export async function seal(
  payload: Session | LoginState,
  secret: string,
  ttlSeconds: number,
): Promise<string> {
  const token = await new EncryptJWT({ ...payload })
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(`${ttlSeconds}s`)
    .encrypt(await key(secret));
  if (token.length > MAX_COOKIE_BYTES) {
    throw new Error(`oturum çerezi çok büyük: ${token.length} bayt`);
  }
  return token;
}

/** Geçersiz, süresi dolmuş ya da başka anahtarla şifrelenmiş çerez için null döner. */
export async function unseal<T extends Session | LoginState>(
  token: string | undefined,
  secret: string,
): Promise<T | null> {
  if (!token) return null;
  try {
    const { payload } = await jwtDecrypt(token, await key(secret));
    return payload as unknown as T;
  } catch {
    return null;
  }
}

export function cookieOptions(appUrl: string, maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: appUrl.startsWith("https://"),
    path: "/",
    maxAge,
  };
}
