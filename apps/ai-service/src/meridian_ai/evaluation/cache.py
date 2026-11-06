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
from meridian_ai.reranking import Reranker


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
        self._timings: list[tuple[float | None, float]] = []
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
            self.last_used = row[0]
            self._timings.append((row[2], row[3]))
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
        self._timings.append((first, total))
        self._db.execute(
            "INSERT OR REPLACE INTO completions VALUES (?, ?, ?, ?, ?)",
            (key, self.last_used, "".join(parts), first, total),
        )
        self._db.commit()

    def take_timing(self) -> tuple[float | None, float]:
        """Son okumadan beri yapılan tüm çağrıların süresi: bir soru kanıt ve cevap olmak üzere iki
        çağrı yapar. İlk token, önceki çağrıların toplamı + son çağrının ilk token süresidir."""
        timings, self._timings = self._timings, []
        earlier = sum(total for _, total in timings[:-1])
        first = timings[-1][0] if timings else None
        return (None if first is None else earlier + first, sum(total for _, total in timings))

    def close(self) -> None:
        self._db.close()


class CachingReranker:
    """Soru-parça skorlarını ve ölçülen süreyi saklar; ablasyon yeniden çalıştırılınca model
    yalnızca yeni çiftler için çağrılır. ``last_seconds``: son sorgunun (ölçülmüş) yeniden
    sıralama süresi, önbellekten gelse bile."""

    def __init__(self, inner: Reranker, path: Path) -> None:
        self.name = inner.name
        self._inner = inner
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS rerank (key TEXT PRIMARY KEY, score REAL, seconds REAL)")
        self.last_seconds = 0.0

    def _key(self, query: str, text: str) -> str:
        return hashlib.sha256(f"{self.name}\0{query}\0{text}".encode()).hexdigest()

    async def scores(self, query: str, texts: Sequence[str]) -> list[float]:
        keys = [self._key(query, t) for t in texts]
        rows = [
            self._db.execute("SELECT score, seconds FROM rerank WHERE key = ?", (k,)).fetchone() for k in keys
        ]
        missing = [i for i, row in enumerate(rows) if row is None]
        if missing:
            started = time.monotonic()
            computed = await self._inner.scores(query, [texts[i] for i in missing])
            per_pair = (time.monotonic() - started) / len(missing)
            for i, score in zip(missing, computed, strict=True):
                rows[i] = (score, per_pair)
                self._db.execute("INSERT OR REPLACE INTO rerank VALUES (?, ?, ?)", (keys[i], score, per_pair))
            self._db.commit()
        self.last_seconds = sum(row[1] for row in rows)
        return [row[0] for row in rows]

    def close(self) -> None:
        self._db.close()
