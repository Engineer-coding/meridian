"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { AssistantMessage } from "@/features/chat/Message";
import { readSse } from "@/features/chat/sse";
import { useSelectedTenant } from "@/features/shell/tenant";
import { useT } from "@/i18n/context";
import type { MessageKey } from "@/i18n/messages";
import { ApiError, api, goToLogin, unwrap, type AgentRun, type AgentStep, type Me, type Membership } from "@/lib/api/client";

const ACTIONS: Record<string, MessageKey> = {
  search_knowledge: "agentActionSearch",
  fetch_document: "agentActionFetch",
  query_sql: "agentActionSql",
  create_ticket: "agentActionTicket",
  invalid: "agentActionInvalid",
};

const STOP_REASONS: Record<string, MessageKey> = {
  step_budget: "agentStopSteps",
  token_budget: "agentStopTokens",
  time_budget: "agentStopTime",
  invalid_output: "agentStopInvalid",
  llm_unavailable: "agentStopModel",
  ai_unavailable: "agentStopModel",
};

type Failure = { key: MessageKey };

async function openStream(url: string, body: unknown, signal: AbortSignal): Promise<ReadableStream<Uint8Array>> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (response.status === 401) {
    goToLogin();
    throw new ApiError(401, "unauthorized");
  }
  if (!response.ok || !response.body) throw new ApiError(response.status, response.statusText);
  return response.body;
}

function failureFor(error: unknown): Failure {
  if (error instanceof ApiError && error.status === 409) return { key: "agentBusy" };
  if (error instanceof ApiError && error.status === 429) return { key: "quotaExceeded" };
  if (error instanceof ApiError && error.status === 403) return { key: "agentForbidden" };
  return { key: "failed" };
}

export function AgentPage() {
  const t = useT();
  const me = useQuery({ queryKey: ["me"], queryFn: async () => unwrap(await api.GET("/v1/me")) });
  if (me.isPending) {
    return (
      <main className="center">
        <p role="status">{t("loading")}</p>
      </main>
    );
  }
  if (me.isError || me.data.memberships.length === 0) {
    return (
      <main className="center">
        <div className="notice notice-warn" role="alert">
          <p>{me.isError ? t("apiDown") : t("adminNoWorkspace")}</p>
          <Link href="/">{t("adminBackToChat")}</Link>
        </div>
      </main>
    );
  }
  return <Loaded me={me.data} />;
}

function Loaded({ me }: { me: Me }) {
  const { membership, select } = useSelectedTenant(me);
  return <TenantAgent key={membership.tenantId} me={me} membership={membership} onSelect={select} />;
}

function TenantAgent({ me, membership, onSelect }: { me: Me; membership: Membership; onSelect: (tenantId: string) => void }) {
  const t = useT();
  const tenantId = membership.tenantId;
  const queryClient = useQueryClient();
  const runsKey = ["agent-runs", tenantId];
  const [goal, setGoal] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const abort = useRef<AbortController | null>(null);

  const runs = useQuery({
    queryKey: runsKey,
    queryFn: async () => unwrap(await api.GET("/v1/tenants/{tenantId}/agent-runs", { params: { path: { tenantId } } })),
  });

  useEffect(() => () => abort.current?.abort(), []);

  const follow = useCallback(
    async (open: (signal: AbortSignal) => Promise<ReadableStream<Uint8Array>>) => {
      const controller = new AbortController();
      abort.current = controller;
      setBusy(true);
      setFailure(null);
      try {
        for await (const { event, data } of readSse(await open(controller.signal))) {
          if (event === "step") {
            const step = JSON.parse(data) as AgentStep;
            setRun((current) => (current ? { ...current, steps: [...(current.steps ?? []), step] } : current));
          } else if (event === "end") {
            setRun(JSON.parse(data) as AgentRun);
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) setFailure(failureFor(error));
      } finally {
        setBusy(false);
        void queryClient.invalidateQueries({ queryKey: runsKey });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runsKey kiracıdan türer
    [queryClient, tenantId],
  );

  function start(event: FormEvent) {
    event.preventDefault();
    const text = goal.trim();
    if (!text || busy) return;
    setRun({ id: "", goal: text, status: "running", steps: [], tokens: 0, createdAt: new Date().toISOString() });
    setGoal("");
    void follow((signal) => openStream(`/api/v1/tenants/${tenantId}/agent-runs`, { goal: text }, signal));
  }

  function decide(approved: boolean) {
    if (!run || busy) return;
    const id = run.id;
    setRun({ ...run, status: "running", pending: null });
    void follow((signal) => openStream(`/api/v1/tenants/${tenantId}/agent-runs/${id}/approval`, { approved }, signal));
  }

  async function open(id: string) {
    if (busy) return;
    setFailure(null);
    try {
      setRun(unwrap(await api.GET("/v1/tenants/{tenantId}/agent-runs/{runId}", { params: { path: { tenantId, runId: id } } })));
    } catch (error) {
      setFailure(failureFor(error));
    }
  }

  return (
    <div className="admin">
      <header className="admin-top">
        <span className="brand">Meridian</span>
        {me.memberships.length > 1 ? (
          <label className="tenant">
            <span className="visually-hidden">{t("workspace")}</span>
            <select value={tenantId} onChange={(event) => onSelect(event.target.value)}>
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
        <Link href="/" className="admin-back">
          {t("adminBackToChat")}
        </Link>
      </header>
      <nav className="admin-nav" aria-label={t("agentRuns")}>
        <p className="agent-nav-title">{t("agentRuns")}</p>
        {runs.data?.length === 0 ? <p className="admin-empty">{t("agentNoRuns")}</p> : null}
        <ul>
          {runs.data?.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className="nav-item"
                aria-current={item.id === run?.id ? "page" : undefined}
                onClick={() => void open(item.id)}
              >
                {item.goal}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <main className="admin-main">
        <h1>{t("agentTitle")}</h1>
        <p className="form-hint">{t("agentIntro")}</p>
        <form className="agent-form" onSubmit={start}>
          <label htmlFor="agent-goal">{t("agentGoal")}</label>
          <textarea id="agent-goal" rows={2} maxLength={2000} value={goal} onChange={(event) => setGoal(event.target.value)} />
          <div className="agent-form-actions">
            {busy ? (
              <button type="button" className="btn btn-stop" onClick={() => abort.current?.abort()}>
                {t("stop")}
              </button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={!goal.trim()}>
                {t("agentStart")}
              </button>
            )}
          </div>
        </form>
        {failure ? (
          <p className="notice notice-warn" role="alert">
            {t(failure.key)}
          </p>
        ) : null}
        {run ? <RunView run={run} busy={busy} onDecide={decide} /> : null}
      </main>
    </div>
  );
}

function RunView({ run, busy, onDecide }: { run: AgentRun; busy: boolean; onDecide: (approved: boolean) => void }) {
  const t = useT();
  const pending = run.pending;
  return (
    <section aria-busy={busy} aria-label={t("agentRunLabel")}>
      <p className="msg-user">{run.goal}</p>
      <ol className="agent-steps">
        {(run.steps ?? []).map((step, index) => (
          <StepView key={index} step={step} />
        ))}
      </ol>
      {busy ? (
        <p className="status" role="status">
          <span className="status-dot" aria-hidden="true" />
          {t("agentThinking")}
        </p>
      ) : null}
      {pending && run.status === "waiting_approval" ? (
        <div className="approval" role="group" aria-labelledby="approval-title">
          <h2 id="approval-title">{t("agentApprovalTitle")}</h2>
          <p className="form-hint">{t("agentApprovalHint")}</p>
          {/* Metin modelden, dolayısıyla belgelerden etkilenmiş olabilir: düz metin, olduğu gibi. */}
          <dl>
            <dt>{t("agentTicketTitle")}</dt>
            <dd>{pending.title}</dd>
            <dt>{t("agentTicketDescription")}</dt>
            <dd className="approval-text">{pending.description}</dd>
          </dl>
          <div className="secret-actions">
            <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onDecide(true)}>
              {t("agentApprove")}
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => onDecide(false)}>
              {t("agentReject")}
            </button>
          </div>
        </div>
      ) : null}
      {run.status === "completed" && run.answer ? (
        <AssistantMessage
          view={{
            text: run.answer,
            sources: run.sources ?? [],
            cited: run.cited ?? [],
            abstained: run.answer === "BİLMİYORUM",
            degraded: false,
            interrupted: false,
            streaming: false,
          }}
        />
      ) : null}
      {run.status === "failed" || run.status === "budget_exceeded" ? (
        <p className="notice notice-warn" role="alert">
          {t(STOP_REASONS[run.stopReason ?? ""] ?? "failed")}
        </p>
      ) : null}
      {run.status === "interrupted" ? <p className="notice">{t("agentInterrupted")}</p> : null}
      {!busy && run.tokens > 0 ? <p className="form-hint">{t("agentTokens", { count: run.tokens })}</p> : null}
    </section>
  );
}

function StepView({ step }: { step: AgentStep }) {
  const t = useT();
  const label = ACTIONS[step.action];
  const input = Object.values(step.input ?? {}).join(" · ");
  return (
    <li className="agent-step">
      <details>
        <summary>
          <strong>{label ? t(label) : step.action}</strong>
          {step.approved === true ? <span className="badge badge-ready">{t("agentApproved")}</span> : null}
          {step.approved === false ? <span className="badge badge-failed">{t("agentRejected")}</span> : null}
          {input ? <code className="agent-step-input">{input}</code> : null}
        </summary>
        {step.thought ? <p className="agent-thought">{step.thought}</p> : null}
        <pre className="agent-observation">{step.observation}</pre>
      </details>
    </li>
  );
}
