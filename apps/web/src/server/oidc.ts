import * as client from "openid-client";

import { env } from "./env";
import type { Session } from "./session";

let configuration: Promise<client.Configuration> | undefined;

function discover(): Promise<client.Configuration> {
  const { OIDC_ISSUER, OIDC_CLIENT_ID } = env();
  configuration ??= client
    .discovery(new URL(OIDC_ISSUER), OIDC_CLIENT_ID, undefined, client.None(), {
      // Yerel Keycloak http konuşur; üretim issuer'ı https olmak zorundadır.
      execute: OIDC_ISSUER.startsWith("http://") ? [client.allowInsecureRequests] : [],
    })
    .catch((error: unknown) => {
      configuration = undefined; // geçici bir hata kalıcı olmasın
      throw error;
    });
  return configuration;
}

function toSession(tokens: client.TokenEndpointResponse, previousRefresh?: string): Session {
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token ?? previousRefresh,
    expiresAt: Math.floor(Date.now() / 1000) + (tokens.expires_in ?? 60),
  };
}

export async function authorizationRedirect(
  redirectUri: string,
): Promise<{ url: URL; state: string; verifier: string }> {
  const config = await discover();
  const verifier = client.randomPKCECodeVerifier();
  const state = client.randomState();
  const url = client.buildAuthorizationUrl(config, {
    redirect_uri: redirectUri,
    scope: "openid profile email",
    code_challenge: await client.calculatePKCECodeChallenge(verifier),
    code_challenge_method: "S256",
    state,
  });
  return { url, state, verifier };
}

export async function exchangeCode(callbackUrl: URL, state: string, verifier: string): Promise<Session> {
  const tokens = await client.authorizationCodeGrant(await discover(), callbackUrl, {
    pkceCodeVerifier: verifier,
    expectedState: state,
  });
  return toSession(tokens);
}

export async function refresh(session: Session): Promise<Session | null> {
  if (!session.refreshToken) return null;
  try {
    return toSession(await client.refreshTokenGrant(await discover(), session.refreshToken), session.refreshToken);
  } catch {
    return null; // süresi dolmuş ya da iptal edilmiş: yeniden giriş gerekir
  }
}

/** Keycloak oturumunu tarayıcıyı yönlendirmeden kapatır; başarısızlık çıkışı engellemez. */
export async function endSession(session: Session): Promise<void> {
  if (!session.refreshToken) return;
  const config = await discover();
  const endpoint = config.serverMetadata().end_session_endpoint;
  if (!endpoint) return;
  await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: env().OIDC_CLIENT_ID, refresh_token: session.refreshToken }),
  }).catch(() => undefined);
}
