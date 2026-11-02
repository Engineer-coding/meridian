"""Diskte kalıcı embedding önbelleği: korpus bir kez gömülür, sonraki çalıştırmalar saniyeler sürer."""

import hashlib
import sqlite3
from array import array
from pathlib import Path

from meridian_ai.embedding import Embedder


class CachingEmbedder:
    """Anahtar = model adı + metin; model ya da parçalama değişirse anahtar da değişir.

    Her parti hesaplanır hesaplanmaz yazılır: uzun bir çalıştırma yarıda kesilirse kaldığı
    yerden devam eder.
    """

    def __init__(self, inner: Embedder, model: str, path: Path) -> None:
        self.dimensions = inner.dimensions
        self._inner = inner
        self._model = model
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")
        self.hits = 0
        self.misses = 0

    def _key(self, role: str, text: str) -> str:
        return hashlib.sha256(f"{self._model}\0{role}\0{text}".encode()).hexdigest()

    def _get(self, key: str) -> list[float] | None:
        row = self._db.execute("SELECT vector FROM embeddings WHERE key = ?", (key,)).fetchone()
        return array("f", row[0]).tolist() if row else None

    def _put(self, key: str, vector: list[float]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?)", (key, array("f", vector).tobytes())
        )

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        keys = [self._key("passage", t) for t in texts]
        found = [self._get(k) for k in keys]
        missing = [i for i, v in enumerate(found) if v is None]
        self.hits += len(texts) - len(missing)
        self.misses += len(missing)
        if missing:
            computed = await self._inner.embed_passages([texts[i] for i in missing])
            for i, vector in zip(missing, computed, strict=True):
                found[i] = vector
                self._put(keys[i], vector)
            self._db.commit()
        return found  # type: ignore[return-value]

    async def embed_query(self, text: str) -> list[float]:
        key = self._key("query", text)
        if (vector := self._get(key)) is not None:
            return vector
        vector = await self._inner.embed_query(text)
        self._put(key, vector)
        self._db.commit()
        return vector

    def close(self) -> None:
        self._db.close()
