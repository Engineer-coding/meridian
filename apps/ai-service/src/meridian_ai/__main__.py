"""``python -m meridian_ai``: servisi başlatır.

uvicorn Windows'ta ProactorEventLoop kullanır; psycopg'nin asenkron sürücüsü bunu desteklemez.
Döngüyü burada kendimiz kurduğumuz için her platformda SelectorEventLoop çalışır.
"""

import asyncio
import os
import sys

import uvicorn


def main() -> None:
    host = os.environ.get("HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("HTTP_PORT", "8090"))
    # Tek Python süreci bir çekirdekle sınırlı; yük testinde 500 eşzamanlı sohbette AI süreci işlemciyi
    # bitirdi, iki süreç p95'i belirgin düşürdü (ADR-0019). Linux'ta HTTP_WORKERS ile süreç sayısı artar.
    workers = int(os.environ.get("HTTP_WORKERS", "1"))
    if workers > 1 and sys.platform != "win32":
        uvicorn.run("meridian_ai.app:create_app", factory=True, host=host, port=port, workers=workers)
        return
    config = uvicorn.Config(
        "meridian_ai.app:create_app",
        factory=True,
        host=host,
        port=port,
    )
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(uvicorn.Server(config).serve(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
