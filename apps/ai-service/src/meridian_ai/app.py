import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from meridian_ai.agent import Agent
from meridian_ai.answering import Answerer
from meridian_ai.consumer import IndexingConsumer
from meridian_ai.db import create_pool
from meridian_ai.embedding import DIMENSIONS, E5Embedder, Embedder
from meridian_ai.fetchers import GitHubFetcher
from meridian_ai.guardrails import install_log_masking
from meridian_ai.handlers import Handler
from meridian_ai.indexer import Indexer
from meridian_ai.internal_api import create_router
from meridian_ai.llm import LLM, build_chain
from meridian_ai.mcp_server import ApiGate, create_mcp
from meridian_ai.reranking import MODELS, CrossEncoderReranker
from meridian_ai.retrieval import Retriever
from meridian_ai.settings import Settings

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, embedder: Embedder | None = None, llm: LLM | None = None
) -> FastAPI:
    """Uygulama fabrikası: testler kendi bileşenlerini verir, üretimde ortamdan okunur."""
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    install_log_masking()
    # Her GitHub/model indirme isteği INFO seviyesinde loglanırdı.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    embedder = embedder or E5Embedder(
        settings.embedding_model, settings.embedding_cache_dir, settings.embedding_batch_size
    )
    if embedder.dimensions != DIMENSIONS:
        raise ValueError(f"embedding boyutu {embedder.dimensions}, şema {DIMENSIONS} bekliyor")

    pool = create_pool(settings.database_conninfo)
    http = httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True)
    token = settings.github_token.get_secret_value() if settings.github_token else None
    handler: Handler = Indexer(
        pool, embedder, {"github": GitHubFetcher(http, settings.max_files_per_source, token=token)}
    )
    consumer = IndexingConsumer(settings, handler)

    # CPU'da ilk token dakikalar sürebilir: okuma süresi genel istemciden çok daha uzun.
    llm_http = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0))
    llm = llm or build_chain(settings.llm_chain, llm_http, settings.ollama_url)
    reranker = (
        CrossEncoderReranker(MODELS[settings.reranker], settings.embedding_cache_dir)
        if settings.reranker
        else None
    )
    retriever = Retriever(pool, embedder, reranker=reranker, rerank_candidates=settings.rerank_candidates)
    answerer = Answerer(
        retriever,
        llm,
        k=settings.answer_sources,
        max_tokens=settings.answer_max_tokens,
        rerank=reranker is not None,
    )

    agent_llm = (
        build_chain(settings.agent_llm_chain, llm_http, settings.ollama_url)
        if settings.agent_llm_chain
        else llm
    )
    agent = Agent(pool, retriever, agent_llm) if hasattr(agent_llm, "complete_json") else None
    mcp_http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))
    mcp, mcp_app = create_mcp(settings.api_url, mcp_http, settings.mcp_allowed_hosts)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Veritabanı açılmasa da süreç başlar; hazır olma kontrolü bunu gösterir.
        await pool.open(wait=False)
        consumer.start()
        async with mcp.session_manager.run():
            yield
        await consumer.stop()
        await mcp_http.aclose()
        await http.aclose()
        await llm_http.aclose()
        await pool.close()

    app = FastAPI(title="Meridian AI", version=version("meridian-ai"), lifespan=lifespan)
    app.include_router(
        create_router(answerer, settings.ai_internal_token.get_secret_value(), retriever, agent)
    )
    app.mount("/mcp", ApiGate(mcp_app))

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        """Süreç ayakta mı? Broker kapalıyken de UP: yeniden başlatmak sorunu çözmez."""
        return {"status": "UP"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        """Kuyruktan iş alıyor ve veritabanına yazabiliyor mu? Değilse 503."""
        if consumer.ready and await _database_ready():
            return JSONResponse({"status": "UP"})
        return JSONResponse({"status": "DOWN"}, status_code=503)

    async def _database_ready() -> bool:
        try:
            async with pool.connection(timeout=2) as connection:
                await connection.execute("SELECT 1")
            return True
        except Exception:
            log.warning("veritabanına ulaşılamıyor", exc_info=True)
            return False

    return app
