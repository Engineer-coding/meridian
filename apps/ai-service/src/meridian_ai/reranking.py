"""İkinci aşama sıralama (ADR-0007): ilk aşamanın adaylarını soru-parça çiftine bakan bir
çapraz kodlayıcıyla yeniden sıralar.

Embedding modeli soruyu ve parçayı ayrı ayrı vektöre çevirir; çapraz kodlayıcı ikisini birlikte
okur ve "bu parça bu soruyu cevaplıyor mu?" sorusuna daha isabetli bir skor verir. Bedeli,
her aday için ayrı bir model çağrısıdır; bu yüzden yalnızca ilk aşamanın ilk N adayına uygulanır.
"""

import asyncio
import threading
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from meridian_ai.retrieval import Hit

# Değerlendirilen modeller (ADR-0007); kısa adlar raporlarda kullanılır.
MODELS = {
    "bge-m3": "BAAI/bge-reranker-v2-m3-int8",
    "jina-v2": "jinaai/jina-reranker-v2-base-multilingual",
}


def rerank_text(hit: Hit) -> str:
    """Embedding ile aynı bağlam: başlık yolu + parça."""
    return f"{hit.section}\n{hit.content}"


class Reranker(Protocol):
    name: str

    async def scores(self, query: str, texts: Sequence[str]) -> list[float]: ...


class CrossEncoderReranker:
    """ONNX çapraz kodlayıcı (fastembed), yerelde; model ilk kullanımda indirilir."""

    def __init__(self, model: str, cache_dir: Path, batch_size: int = 8) -> None:
        self.name = model
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                self._model = TextCrossEncoder(self.name, cache_dir=str(self._cache_dir))
        return self._model

    def _score(self, query: str, texts: Sequence[str]) -> list[float]:
        return [float(s) for s in self._load().rerank(query, list(texts), batch_size=self._batch_size)]

    async def scores(self, query: str, texts: Sequence[str]) -> list[float]:
        # CPU yoğun: olay döngüsü (kuyruk, sağlık uçları, akan cevaplar) donmasın.
        return await asyncio.to_thread(self._score, query, texts)


async def rerank(reranker: Reranker, query: str, hits: Sequence[Hit], k: int) -> list[Hit]:
    if not hits:
        return []
    scores = await reranker.scores(query, [rerank_text(h) for h in hits])
    ranked = sorted(zip(hits, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [replace(hit, score=score) for hit, score in ranked[:k]]
