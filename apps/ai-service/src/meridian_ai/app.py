import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from meridian_ai.consumer import IndexingConsumer
from meridian_ai.handlers import Handler, handle_event
from meridian_ai.settings import Settings


def create_app(settings: Settings | None = None, handler: Handler = handle_event) -> FastAPI:
    """Uygulama fabrikası: testler kendi ayarlarını ve işleyicisini verir, üretimde ortamdan okunur."""
    settings = settings or Settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    consumer = IndexingConsumer(settings, handler)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        consumer.start()
        yield
        await consumer.stop()

    app = FastAPI(title="Meridian AI", version=version("meridian-ai"), lifespan=lifespan)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        """Süreç ayakta mı? Broker kapalıyken de UP: yeniden başlatmak sorunu çözmez."""
        return {"status": "UP"}

    @app.get("/health/ready")
    async def ready() -> JSONResponse:
        """Kuyruktan iş alıyor mu? Değilse 503; orkestratör trafiği ve alarmı buna göre yönetir."""
        if consumer.ready:
            return JSONResponse({"status": "UP"})
        return JSONResponse({"status": "DOWN"}, status_code=503)

    return app
