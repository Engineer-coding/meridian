"""``python -m meridian_ai``: servisi başlatır.

uvicorn Windows'ta ProactorEventLoop kullanır; psycopg'nin asenkron sürücüsü bunu desteklemez.
Döngüyü burada kendimiz kurduğumuz için her platformda SelectorEventLoop çalışır.
"""

import asyncio
import os
import sys

import uvicorn


def main() -> None:
    config = uvicorn.Config(
        "meridian_ai.app:create_app",
        factory=True,
        host=os.environ.get("HTTP_HOST", "127.0.0.1"),
        port=int(os.environ.get("HTTP_PORT", "8090")),
    )
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(uvicorn.Server(config).serve(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
