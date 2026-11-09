"""Çekirdek API'nin çağırdığı iç uç: kaynaklı cevabı satır satır JSON (NDJSON) olarak akıtır.

Yetki kararı burada verilmez (ADR-0001): çekirdek API üyeliği doğrular ve kiracıyı bildirir.
Bu ucun tek sınırı paylaşılan gizli anahtardır; anahtar yapılandırılmamışsa her istek reddedilir.
Veritabanı erişimi yine kiracı bağlamlı işlemlerle yapılır, yani RLS geçerlidir.
"""

import hmac
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from meridian_ai.agent import Agent, ApprovalRequired, RunFinished, StepDone
from meridian_ai.answering import Answerer, Done, SourcesFound, Token
from meridian_ai.llm import UsageCounter, usage_counter
from meridian_ai.observability import agent_runs, answers, tenant_scope
from meridian_ai.retrieval import Mode, Retriever

log = logging.getLogger(__name__)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    question: str = Field(min_length=1, max_length=4000)
    collection_ids: list[UUID] | None = Field(default=None, alias="collectionIds", max_length=20)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    query: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)
    collection_ids: list[UUID] | None = Field(default=None, alias="collectionIds", max_length=20)


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    goal: str = Field(min_length=1, max_length=2000)
    steps: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    tokens_used: int = Field(default=0, ge=0, alias="tokensUsed")


def _line(event: str, data: dict[str, Any]) -> bytes:
    return (json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n").encode()


def _done(done: Done, usage: UsageCounter) -> dict[str, Any]:
    return {
        "usage": (
            {"promptTokens": usage.prompt_tokens, "completionTokens": usage.completion_tokens}
            if usage.counted
            else None
        ),
        "answer": done.answer,
        "cited": done.cited,
        "invalidCitations": done.invalid_citations,
        "abstained": done.abstained,
        "degraded": done.degraded,
        "evidence": done.evidence,
        "evidenceSource": done.evidence_source,
        "model": done.model,
    }


def _outcome(done: Done) -> str:
    return "degraded" if done.degraded else "abstained" if done.abstained else "answered"


async def _stream(answerer: Answerer, request: AnswerRequest) -> AsyncIterator[bytes]:
    with tenant_scope(request.tenant_id):
        async for line in _answer_lines(answerer, request):
            yield line


async def _answer_lines(answerer: Answerer, request: AnswerRequest) -> AsyncIterator[bytes]:
    usage = UsageCounter()
    usage_counter.set(usage)
    try:
        async for event in answerer.answer(request.tenant_id, request.question, request.collection_ids):
            match event:
                case SourcesFound(sources=sources):
                    payload = [
                        {
                            "number": s.number,
                            "documentPath": s.hit.document_path,
                            "title": s.hit.title,
                            "url": s.hit.url,
                            "section": s.hit.section,
                            "content": s.hit.content,
                        }
                        for s in sources
                    ]
                    yield _line("sources", {"sources": payload})
                case Token(text=text):
                    yield _line("token", {"text": text})
                case Done() as done:
                    answers.add(1, {"outcome": _outcome(done)})
                    yield _line("done", _done(done, usage))
    except Exception:
        # Akış başladı, durum kodu artık değiştirilemez; arama ya da embedding hatası da
        # kullanıcıya yarım bağlantı olarak değil, "cevap üretilemedi" olarak ulaşır.
        log.exception("cevap akışı başarısız tenant=%s", request.tenant_id)
        answers.add(1, {"outcome": "error"})
        yield _line("done", _done(Done("", degraded=True), usage))


async def _agent_stream(agent: Agent, request: AgentRequest) -> AsyncIterator[bytes]:
    with tenant_scope(request.tenant_id):
        async for line in _agent_lines(agent, request):
            yield line


async def _agent_lines(agent: Agent, request: AgentRequest) -> AsyncIterator[bytes]:
    usage = UsageCounter()
    usage_counter.set(usage)

    def counts() -> dict[str, int] | None:
        if not usage.counted:
            return None
        return {"promptTokens": usage.prompt_tokens, "completionTokens": usage.completion_tokens}

    try:
        async for event in agent.run(request.tenant_id, request.goal, request.steps, request.tokens_used):
            match event:
                case StepDone(data=step):
                    yield _line("step", step)
                case ApprovalRequired(thought=thought, title=title, description=description):
                    agent_runs.add(1, {"status": "waiting_approval"})
                    yield _line(
                        "approval_required",
                        {"thought": thought, "title": title, "description": description, "usage": counts()},
                    )
                case RunFinished() as finished:
                    agent_runs.add(
                        1, {"status": finished.status, "stop_reason": str(finished.stop_reason or "")}
                    )
                    yield _line(
                        "done",
                        {
                            "status": finished.status,
                            "answer": finished.answer,
                            "cited": finished.cited,
                            "invalidCitations": finished.invalid_citations,
                            "sources": finished.sources,
                            "stopReason": finished.stop_reason,
                            "model": finished.model,
                            "usage": counts(),
                        },
                    )
    except Exception:
        log.exception("ajan akışı başarısız tenant=%s", request.tenant_id)
        agent_runs.add(1, {"status": "failed", "stop_reason": "internal"})
        yield _line(
            "done",
            {
                "status": "failed",
                "answer": "",
                "cited": [],
                "invalidCitations": [],
                "sources": [],
                "stopReason": "internal",
                "model": None,
                "usage": counts(),
            },
        )


def create_router(
    answerer: Answerer, token: str, retriever: Retriever | None = None, agent: Agent | None = None
) -> APIRouter:
    router = APIRouter(prefix="/internal/v1")

    def require_token(given: str | None) -> None:
        if not token or not hmac.compare_digest((given or "").encode(), token.encode()):
            raise HTTPException(status_code=401)

    @router.post("/search")
    async def search(
        request: SearchRequest,
        x_internal_token: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        require_token(x_internal_token)
        if retriever is None:
            raise HTTPException(status_code=503)
        with tenant_scope(request.tenant_id):
            hits = await retriever.search(
                request.tenant_id,
                request.query,
                k=request.k,
                mode=Mode.VECTOR,
                collection_ids=request.collection_ids,
            )
        return {
            "hits": [
                {
                    "documentPath": hit.document_path,
                    "title": hit.title,
                    "url": hit.url,
                    "section": hit.section,
                    "content": hit.content,
                    "score": hit.score,
                }
                for hit in hits
            ]
        }

    @router.post("/agent/run")
    async def agent_run(
        request: AgentRequest,
        x_internal_token: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        require_token(x_internal_token)
        if agent is None:
            raise HTTPException(status_code=503)
        return StreamingResponse(_agent_stream(agent, request), media_type="application/x-ndjson")

    @router.post("/answer")
    async def answer(
        request: AnswerRequest,
        x_internal_token: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        require_token(x_internal_token)
        return StreamingResponse(_stream(answerer, request), media_type="application/x-ndjson")

    return router
