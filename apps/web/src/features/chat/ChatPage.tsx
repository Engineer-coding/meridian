"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSelectedTenant } from "@/features/shell/tenant";
import { useT } from "@/i18n/context";
import { api, unwrap, type ChatMessage, type Me, type Membership } from "@/lib/api/client";

import { Composer } from "./Composer";
import { AssistantMessage, UserMessage, type AssistantView } from "./Message";
import { TurnView } from "./TurnView";
import { conversationsKey, messagesKey, useChat } from "./useChat";

function toView(message: ChatMessage): AssistantView {
  return {
    text: message.content,
    sources: message.sources ?? [],
    cited: message.cited ?? [],
    abstained: message.abstained ?? false,
    degraded: message.degraded ?? false,
    interrupted: message.status === "interrupted",
    streaming: false,
  };
}

/** Seçili çalışma alanı; değişince sohbet durumu `key` ile sıfırlanır, kiracılar birbirine karışmaz. */
export function ChatPage({ me }: { me: Me }) {
  const { membership, select } = useSelectedTenant(me);
  return <TenantChat key={membership.tenantId} me={me} membership={membership} onSelectTenant={select} />;
}

function TenantChat({
  me,
  membership,
  onSelectTenant,
}: {
  me: Me;
  membership: Membership;
  onSelectTenant: (tenantId: string) => void;
}) {
  const t = useT();
  const tenantId = membership.tenantId;
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [navOpen, setNavOpen] = useState(false);
  const { turn, send, stop, reset } = useChat(tenantId, setConversationId);
  const end = useRef<HTMLDivElement>(null);

  const conversations = useQuery({
    queryKey: conversationsKey(tenantId),
    queryFn: async () =>
      unwrap(await api.GET("/v1/tenants/{tenantId}/conversations", { params: { path: { tenantId } } })),
  });

  const messages = useQuery({
    queryKey: messagesKey(tenantId, conversationId ?? "none"),
    enabled: conversationId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/v1/tenants/{tenantId}/conversations/{conversationId}/messages", {
          params: { path: { tenantId, conversationId: conversationId! } },
        }),
      ),
  });

  const visible = useMemo(() => {
    const all = messages.data ?? [];
    return turn ? all.slice(0, turn.baseCount) : all;
  }, [messages.data, turn]);

  const busy = turn !== null && ["searching", "waiting", "streaming", "finishing"].includes(turn.phase);
  const lastQuestion = [...visible].reverse().find((message) => message.role === "user")?.content;

  const ask = useCallback((question: string) => void send(question, conversationId), [conversationId, send]);

  const answerLength = turn?.answer.length ?? 0;
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [visible.length, answerLength, turn?.phase]);

  function open(id: string | null) {
    reset();
    setConversationId(id);
    setNavOpen(false);
  }

  return (
    <div className="app">
      <a href="#question" className="skip-link">
        {t("skipToQuestion")}
      </a>
      <header className="topbar">
        <button
          type="button"
          className="btn-quiet nav-toggle"
          aria-expanded={navOpen}
          aria-controls="conversations"
          onClick={() => setNavOpen((value) => !value)}
        >
          {t("conversations")}
        </button>
        <span className="brand">Meridian</span>
        {me.memberships.length > 1 ? (
          <label className="tenant">
            <span className="visually-hidden">{t("workspace")}</span>
            <select value={tenantId} onChange={(event) => onSelectTenant(event.target.value)}>
              {me.memberships.map((item) => (
                <option key={item.tenantId} value={item.tenantId}>
                  {item.tenantName}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="tenant">{membership.tenantName}</span>
        )}
        <Link href="/admin" className="admin-back">
          {t("adminTitle")}
        </Link>
      </header>

      <nav id="conversations" className={navOpen ? "nav nav-open" : "nav"} aria-label={t("conversations")}>
        <button type="button" className="btn btn-new" onClick={() => open(null)}>
          {t("newConversation")}
        </button>
        {conversations.isError ? <p className="nav-empty">{t("failed")}</p> : null}
        {conversations.data?.length === 0 ? <p className="nav-empty">{t("noConversations")}</p> : null}
        <ul>
          {conversations.data?.map((conversation) => (
            <li key={conversation.id}>
              <button
                type="button"
                className="nav-item"
                aria-current={conversation.id === conversationId ? "page" : undefined}
                onClick={() => open(conversation.id)}
              >
                {conversation.title || t("untitled")}
              </button>
            </li>
          ))}
        </ul>
        <div className="nav-footer">
          <span className="nav-user">{me.displayName ?? me.email}</span>
          <form action="/auth/logout" method="post">
            <button type="submit" className="btn-quiet">
              {t("signOut")}
            </button>
          </form>
        </div>
      </nav>

      <main className="main">
        <div className="thread" aria-busy={busy}>
          {conversationId === null && !turn ? (
            <div className="empty">
              <h1>{t("emptyTitle")}</h1>
              <p>{t("emptyBody")}</p>
            </div>
          ) : null}
          {messages.isError ? <p className="notice notice-warn">{t("failed")}</p> : null}
          {visible.map((message, index) =>
            message.role === "user" ? (
              <UserMessage key={message.id} text={message.content} />
            ) : (
              <AssistantMessage
                key={message.id}
                view={toView(message)}
                onRegenerate={
                  index === visible.length - 1 && !busy && lastQuestion ? () => ask(lastQuestion) : undefined
                }
              />
            ),
          )}
          {turn ? <TurnView turn={turn} onRetry={() => ask(turn.question)} /> : null}
          <div ref={end} />
        </div>
        <div className="composer-dock">
          <Composer busy={busy} onSend={ask} onStop={stop} />
          <p className="disclaimer">{t("disclaimer")}</p>
        </div>
      </main>
    </div>
  );
}
