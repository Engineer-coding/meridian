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

from meridian_ai.answering import Answerer, Done, SourcesFound, Token
from meridian_ai.llm import UsageCounter, usage_counter

log = logging.getLogger(__name__)


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tenant_id: UUID = Field(alias="tenantId")
    question: str = Field(min_length=1, max_length=4000)
    collection_ids: list[UUID] | None = Field(default=None, alias="collectionIds", max_length=20)


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


async def _stream(answerer: Answerer, request: AnswerRequest) -> AsyncIterator[bytes]:
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
                    yield _line("done", _done(done, usage))
    except Exception:
        # Akış başladı, durum kodu artık değiştirilemez; arama ya da embedding hatası da
        # kullanıcıya yarım bağlantı olarak değil, "cevap üretilemedi" olarak ulaşır.
        log.exception("cevap akışı başarısız tenant=%s", request.tenant_id)
        yield _line("done", _done(Done("", degraded=True), usage))


def create_router(answerer: Answerer, token: str) -> APIRouter:
    router = APIRouter(prefix="/internal/v1")

    @router.post("/answer")
    async def answer(
        request: AnswerRequest,
        x_internal_token: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        given = (x_internal_token or "").encode()
        if not token or not hmac.compare_digest(given, token.encode()):
            raise HTTPException(status_code=401)
        return StreamingResponse(_stream(answerer, request), media_type="application/x-ndjson")

    return router
