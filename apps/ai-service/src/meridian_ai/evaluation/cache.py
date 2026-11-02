"""Diskte kalıcı embedding önbelleği: korpus bir kez gömülür, sonraki çalıştırmalar saniyeler sürer."""

import hashlib
import json
import sqlite3
import time
from array import array
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

from meridian_ai.embedding import Embedder
from meridian_ai.llm import LLM, Message


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


class CachingLLM:
    """LLM cevaplarını (ve ölçülen süreleri) diskte saklar: CPU'da saatler süren cevap
    değerlendirmesi bir kez çalışır; istem, model ya da ayar değişirse anahtar da değişir."""

    def __init__(self, inner: LLM, path: Path) -> None:
        self.name = inner.name
        self._inner = inner
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS completions (key TEXT PRIMARY KEY, model TEXT, text TEXT,"
            " first_token REAL, total REAL)"
        )
        self.last_used: str | None = None
        self.last_timing: tuple[float | None, float] | None = None
        self.hits = 0
        self.misses = 0

    def _key(self, messages: Sequence[Message], max_tokens: int) -> str:
        payload = json.dumps(
            [self.name, max_tokens, [(m.role, m.content) for m in messages]], ensure_ascii=False
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        key = self._key(messages, max_tokens)
        row = self._db.execute(
            "SELECT model, text, first_token, total FROM completions WHERE key = ?", (key,)
        ).fetchone()
        if row:
            self.hits += 1
            self.last_used, self.last_timing = row[0], (row[2], row[3])
            yield row[1]
            return

        self.misses += 1
        started = time.monotonic()
        first: float | None = None
        parts: list[str] = []
        async for token in self._inner.stream(messages, max_tokens=max_tokens):
            first = first or time.monotonic() - started
            parts.append(token)
            yield token
        total = time.monotonic() - started
        self.last_used = getattr(self._inner, "last_used", None) or self._inner.name
        self.last_timing = (first, total)
        self._db.execute(
            "INSERT OR REPLACE INTO completions VALUES (?, ?, ?, ?, ?)",
            (key, self.last_used, "".join(parts), first, total),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()
