import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from meridian_ai.consumer import IndexingConsumer
from meridian_ai.db import create_pool
from meridian_ai.embedding import DIMENSIONS, E5Embedder, Embedder
from meridian_ai.fetchers import GitHubFetcher
from meridian_ai.handlers import Handler
from meridian_ai.indexer import Indexer
from meridian_ai.settings import Settings

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, embedder: Embedder | None = None) -> FastAPI:
    """Uygulama fabrikası: testler kendi ayarlarını ve embedder'ını verir, üretimde ortamdan okunur."""
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Veritabanı açılmasa da süreç başlar; hazır olma kontrolü bunu gösterir.
        await pool.open(wait=False)
        consumer.start()
        yield
        await consumer.stop()
        await http.aclose()
        await pool.close()

    app = FastAPI(title="Meridian AI", version=version("meridian-ai"), lifespan=lifespan)

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
