"""LLM sağlayıcı soyutlaması ve yedek zinciri (ADR-0008).

Cevap üretimi yalnızca ``LLM`` arayüzünü bilir; sağlayıcı (Ollama, ileride Claude/OpenAI)
yapılandırmayla seçilir. Zincirdeki sağlayıcı ilk token'dan önce düşerse sıradakine geçilir;
hepsi düşerse çağıran "yalnızca kaynaklar" moduna iner.
"""

import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class UsageCounter:
    """Bir cevabın tüm LLM çağrılarında harcanan token'lar; sağlayıcı sayaç vermezse sıfır kalır."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    counted: bool = False


# Her isteğe kendi sayacı: sağlayıcı nesnesi istekler arasında paylaşılır, üzerinde durum tutulamaz.
usage_counter: ContextVar[UsageCounter | None] = ContextVar("usage_counter", default=None)


class LLMUnavailable(Exception):
    """Sağlayıcı cevap veremiyor (bağlantı, zaman aşımı, sunucu hatası, model yok)."""


class LLM(Protocol):
    name: str

    def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        """Cevabı parça parça üretir. Başarısızlıkta ``LLMUnavailable`` fırlatır."""
        ...


class StructuredLLM(Protocol):
    """Şemaya uyan tek JSON üretir; ajan buna dayanır. Çıktıyı yine de çağıran doğrular."""

    name: str

    async def complete_json(
        self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int
    ) -> str: ...


class OllamaLLM:
    """Ollama ``/api/chat``; yerelde, veri dışarı çıkmadan çalışır."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        model: str,
        *,
        context_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> None:
        self.name = f"ollama/{model}"
        self._client = client
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model = model
        self._options = {"num_ctx": context_tokens, "temperature": temperature}

    async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        body = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": self._options | {"num_predict": max_tokens},
        }
        try:
            async with self._client.stream("POST", self._url, json=body) as response:
                if response.status_code != 200:
                    detail = (await response.aread()).decode(errors="replace")[:200]
                    raise LLMUnavailable(f"{self.name}: HTTP {response.status_code} {detail}")
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LLMUnavailable(f"{self.name}: {chunk['error']}")
                    if text := chunk.get("message", {}).get("content"):
                        yield text
                    if chunk.get("done"):
                        if (counter := usage_counter.get()) is not None:
                            counter.prompt_tokens += chunk.get("prompt_eval_count", 0)
                            counter.completion_tokens += chunk.get("eval_count", 0)
                            counter.counted = True
                        return
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"{self.name}: {type(e).__name__}") from e
        except json.JSONDecodeError as e:
            raise LLMUnavailable(f"{self.name}: bozuk akış") from e

    async def complete_json(
        self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int
    ) -> str:
        body = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "format": schema,
            "options": self._options | {"num_predict": max_tokens},
        }
        try:
            response = await self._client.post(self._url, json=body)
            if response.status_code != 200:
                raise LLMUnavailable(f"{self.name}: HTTP {response.status_code} {response.text[:200]}")
            data = response.json()
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"{self.name}: {type(e).__name__}") from e
        except json.JSONDecodeError as e:
            raise LLMUnavailable(f"{self.name}: bozuk cevap") from e
        if "error" in data:
            raise LLMUnavailable(f"{self.name}: {data['error']}")
        if (counter := usage_counter.get()) is not None:
            counter.prompt_tokens += data.get("prompt_eval_count", 0)
            counter.completion_tokens += data.get("eval_count", 0)
            counter.counted = True
        return data.get("message", {}).get("content", "")


class FallbackLLM:
    """Sağlayıcıları sırayla dener.

    Geçiş yalnızca ilk token'dan önce yapılır: kullanıcı yarım bir cevabın ardından başka bir
    modelin cevabını görmemelidir. Akış ortasındaki hata çağırana iletilir.
    """

    def __init__(self, providers: Sequence[LLM]) -> None:
        if not providers:
            raise ValueError("en az bir sağlayıcı gerekli")
        self._providers = list(providers)
        self.name = " → ".join(p.name for p in providers)
        self.last_used: str | None = None

    async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        failures = []
        for provider in self._providers:
            tokens = provider.stream(messages, max_tokens=max_tokens)
            try:
                first = await anext(tokens)
            except StopAsyncIteration:
                first = ""
            except LLMUnavailable as e:
                log.warning("LLM sağlayıcısı kullanılamıyor, sıradakine geçiliyor: %s", e)
                failures.append(str(e))
                continue
            self.last_used = provider.name
            if first:
                yield first
            async for token in tokens:
                yield token
            return
        raise LLMUnavailable("tüm sağlayıcılar kullanılamıyor: " + "; ".join(failures))

    async def complete_json(
        self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int
    ) -> str:
        failures = []
        for provider in self._providers:
            if not hasattr(provider, "complete_json"):
                failures.append(f"{provider.name}: yapılandırılmış çıktı yok")
                continue
            try:
                text = await provider.complete_json(messages, schema, max_tokens=max_tokens)
            except LLMUnavailable as e:
                log.warning("LLM sağlayıcısı kullanılamıyor, sıradakine geçiliyor: %s", e)
                failures.append(str(e))
                continue
            self.last_used = provider.name
            return text
        raise LLMUnavailable("tüm sağlayıcılar kullanılamıyor: " + "; ".join(failures))


def build_chain(spec: str, client: httpx.AsyncClient, ollama_url: str) -> FallbackLLM:
    """``"ollama/llama3.2:3b, ollama/llama3.2:1b"`` → sırayla denenecek sağlayıcılar."""
    providers: list[LLM] = []
    for item in filter(None, (part.strip() for part in spec.split(","))):
        kind, _, model = item.partition("/")
        match kind:
            case "ollama" if model:
                providers.append(OllamaLLM(client, ollama_url, model))
            case _:
                raise ValueError(f"desteklenmeyen LLM sağlayıcısı: {item!r}")
    return FallbackLLM(providers)
