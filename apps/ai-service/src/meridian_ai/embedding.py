"""Metinden vektöre (ADR-0012)."""

import asyncio
import hashlib
import math
import re
import threading
from pathlib import Path
from typing import Protocol

# Şema ile aynı olmalı: chunks.embedding vector(1024).
DIMENSIONS = 1024
DEFAULT_MODEL = "intfloat/multilingual-e5-large"

_WORD = re.compile(r"\w+", re.UNICODE)


class Embedder(Protocol):
    dimensions: int

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class E5Embedder:
    """intfloat/multilingual-e5-large, ONNX ile yerelde (fastembed); GPU ya da API anahtarı gerekmez.

    E5 ailesi metnin rolünü ön ekten öğrenir: belgeler ``passage:``, sorular ``query:`` ile
    gömülür. Ön eksiz kullanım retrieval kalitesini belirgin düşürür.
    """

    dimensions = DIMENSIONS

    def __init__(self, model: str, cache_dir: Path, batch_size: int) -> None:
        self._model_name = model
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(self._model_name, cache_dir=str(self._cache_dir))
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().embed(texts, batch_size=self._batch_size)
        return [vector.tolist() for vector in vectors]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        # Model CPU'yu meşgul eder; olay döngüsü (kuyruk kalp atışları, sağlık uçları) donmasın.
        return await asyncio.to_thread(self._embed, [f"passage: {t}" for t in texts])

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await asyncio.to_thread(self._embed, [f"query: {text}"])
        return vector


class HashEmbedder:
    """Testler ve çevrimdışı geliştirme için: kelime torbasının hash'lenmiş, normalize vektörü.

    Anlamı değil kelime örtüşmesini yakalar; aynı kelimeleri paylaşan metinler yakın düşer, bu
    da retrieval testlerinin modelsiz ve deterministik çalışmasına yeter.
    """

    dimensions = DIMENSIONS

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in _WORD.findall(text.lower()):
            digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)
