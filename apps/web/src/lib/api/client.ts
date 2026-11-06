import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Conversation = components["schemas"]["Conversation"];
export type ChatMessage = components["schemas"]["ChatMessage"];
export type CitedSource = components["schemas"]["CitedSource"];
export type ChatSourcesEvent = components["schemas"]["ChatSourcesEvent"];
export type ChatTokenEvent = components["schemas"]["ChatTokenEvent"];
export type ChatDoneEvent = components["schemas"]["ChatDoneEvent"];
export type Me = components["schemas"]["Me"];
export type Membership = components["schemas"]["Membership"];
export type Problem = components["schemas"]["Problem"];

export function goToLogin(): void {
  // Giriş bir rota işleyicisidir ve dış siteye yönlendirir: istemci içi geçiş olamaz.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign("/auth/login");
}

const redirectOnUnauthorized: Middleware = {
  onResponse({ response }) {
    if (response.status === 401) goToLogin();
    return response;
  },
};

/** Tarayıcıdan yalnızca aynı kökendeki vekil çağrılır; token bu kodun eline hiç geçmez. */
export const api = createClient<paths>({ baseUrl: "/api" });
api.use(redirectOnUnauthorized);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly retryAfterSeconds?: number,
  ) {
    super(message);
  }
}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const problem = result.error as Partial<Problem> | undefined;
  throw new ApiError(result.response.status, problem?.detail ?? problem?.title ?? "error");
}
