"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef } from "react";

import {
  ApiError,
  api,
  goToLogin,
  unwrap,
  type ChatDoneEvent,
  type ChatMessage,
  type ChatSourcesEvent,
  type ChatTokenEvent,
} from "@/lib/api/client";

import { readSse } from "./sse";
import { startTurn, turnReducer, type Turn, type TurnAction } from "./turn";

type State = { turn: Turn | null };
type Action = { type: "start"; turn: Turn } | { type: "clear" } | TurnAction;

function reducer(state: State, action: Action): State {
  if (action.type === "start") return { turn: action.turn };
  if (action.type === "clear") return { turn: null };
  return state.turn ? { turn: turnReducer(state.turn, action) } : state;
}

export const conversationsKey = (tenantId: string) => ["conversations", tenantId] as const;
export const messagesKey = (tenantId: string, conversationId: string) =>
  ["messages", tenantId, conversationId] as const;

async function postMessage(
  tenantId: string,
  conversationId: string,
  content: string,
  signal: AbortSignal,
): Promise<ReadableStream<Uint8Array>> {
  const response = await fetch(`/api/v1/tenants/${tenantId}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ content }),
    signal,
  });
  if (response.status === 401) {
    goToLogin();
    throw new ApiError(401, "unauthorized");
  }
  if (!response.ok || !response.body) {
    const retryAfter = Number(response.headers.get("retry-after"));
    throw new ApiError(response.status, response.statusText, Number.isFinite(retryAfter) ? retryAfter : undefined);
  }
  return response.body;
}

/**
 * Akış sürerken gösterilen tur yereldedir. Akış bitince sunucudaki kayıt yeniden okunur ve yerel tur
 * ancak kayıt geldikten sonra kaldırılır; böylece cevap ekranda bir an bile kaybolmaz.
 */
export function useChat(tenantId: string, onConversationCreated: (id: string) => void) {
  const queryClient = useQueryClient();
  const [{ turn }, dispatch] = useReducer(reducer, { turn: null });
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const reset = useCallback(() => {
    abort.current?.abort();
    dispatch({ type: "clear" });
  }, []);

  const stop = useCallback(() => {
    abort.current?.abort();
    dispatch({ type: "stop" });
  }, []);

  const send = useCallback(
    async (question: string, existingConversationId: string | null) => {
      const controller = new AbortController();
      abort.current = controller;
      const key = existingConversationId ? messagesKey(tenantId, existingConversationId) : null;
      const baseCount = key ? (queryClient.getQueryData<ChatMessage[]>(key)?.length ?? 0) : 0;
      dispatch({ type: "start", turn: startTurn(question, baseCount) });

      let conversationId = existingConversationId;
      try {
        if (!conversationId) {
          const created = unwrap(
            await api.POST("/v1/tenants/{tenantId}/conversations", {
              params: { path: { tenantId }, header: { "Idempotency-Key": crypto.randomUUID() } },
              body: {},
            }),
          );
          conversationId = created.id;
          queryClient.setQueryData(messagesKey(tenantId, created.id), []);
          onConversationCreated(created.id);
        }
        const body = await postMessage(tenantId, conversationId, question, controller.signal);
        for await (const { event, data } of readSse(body)) {
          if (event === "sources") {
            dispatch({ type: "sources", sources: (JSON.parse(data) as ChatSourcesEvent).sources });
          } else if (event === "token") {
            dispatch({ type: "token", text: (JSON.parse(data) as ChatTokenEvent).text });
          } else if (event === "done") {
            dispatch({ type: "done", done: JSON.parse(data) as ChatDoneEvent });
          }
        }
        await refresh(queryClient, tenantId, conversationId);
        dispatch({ type: "clear" });
      } catch (error) {
        if (controller.signal.aborted) {
          // API yarım mesajı bağlantı kopunca kaydeder; bu biraz sürebilir, kayıt gelene dek yerel tur kalır.
          if (conversationId) await waitForInterrupted(queryClient, tenantId, conversationId, baseCount, dispatch, abort, controller);
          return;
        }
        const status = error instanceof ApiError ? error.status : 0;
        dispatch({
          type: "fail",
          error:
            status === 429
              ? { key: "rateLimited", retryAfterSeconds: (error as ApiError).retryAfterSeconds }
              : { key: "failed" },
        });
      }
    },
    [onConversationCreated, queryClient, tenantId],
  );

  return { turn, send, stop, reset };
}

async function refresh(queryClient: ReturnType<typeof useQueryClient>, tenantId: string, conversationId: string) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: messagesKey(tenantId, conversationId) }),
    queryClient.invalidateQueries({ queryKey: conversationsKey(tenantId) }),
  ]);
}

async function waitForInterrupted(
  queryClient: ReturnType<typeof useQueryClient>,
  tenantId: string,
  conversationId: string,
  baseCount: number,
  dispatch: (action: Action) => void,
  current: { current: AbortController | null },
  controller: AbortController,
) {
  for (const delay of [500, 1500, 3000, 5000]) {
    await new Promise((resolve) => setTimeout(resolve, delay));
    if (current.current !== controller) return; // kullanıcı bu arada yeni soru sordu
    await refresh(queryClient, tenantId, conversationId);
    const messages = queryClient.getQueryData<ChatMessage[]>(messagesKey(tenantId, conversationId));
    if ((messages?.length ?? 0) >= baseCount + 2) {
      dispatch({ type: "clear" });
      return;
    }
  }
}
