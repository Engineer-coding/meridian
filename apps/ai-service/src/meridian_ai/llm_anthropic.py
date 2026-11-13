"""Anthropic sağlayıcısı (ADR-0008): barındırılan Claude modelleri, demo için ``claude-haiku-5-5``.

Ollama'nın aksine veri makineden çıkar: soru metni ve seçilen parçalar Anthropic'e gider. Parçalar
indekslemede PII'den arındırılır (ADR-0016); kimlik, kiracı ve kullanıcı bilgisi istekte yoktur.

Her hata ``LLMUnavailable`` olur; ilk token'dan önceyse zincir sıradaki sağlayıcıya geçer. Düşünme
kapalıdır: kısa, kaynağa dayalı cevaplarda yalnızca ilk token gecikmesini uzatır.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import anthropic
import httpx2

from meridian_ai.llm import LLMUnavailable, Message, usage_counter

# Zincir yedeğe hızlı geçsin: SDK'nın varsayılan uzun yeniden denemeleri kullanıcıyı bekletir.
_RETRIES = 1
_TIMEOUT = httpx2.Timeout(30.0, connect=5.0)
_THINKING: Any = {"type": "disabled"}


def make_client(api_key: str, http_client: httpx2.AsyncClient | None = None) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key=api_key, max_retries=_RETRIES, timeout=_TIMEOUT, http_client=http_client
    )


def _split(messages: Sequence[Message]) -> tuple[str, list[dict[str, str]]]:
    """Baştaki sistem mesajları API'nin üst düzey ``system`` alanına gider."""
    system: list[str] = []
    rest = list(messages)
    while rest and rest[0].role == "system":
        system.append(rest.pop(0).content)
    return "\n\n".join(system), [{"role": m.role, "content": m.content} for m in rest]


def _count(usage: Any) -> None:
    if (counter := usage_counter.get()) is not None:
        counter.prompt_tokens += usage.input_tokens or 0
        counter.completion_tokens += usage.output_tokens or 0
        counter.counted = True


class AnthropicLLM:
    def __init__(self, client: anthropic.AsyncAnthropic | None, model: str) -> None:
        """``client`` yoksa (anahtar tanımlı değil) her çağrı istek atmadan ``LLMUnavailable`` olur."""
        self.name = f"anthropic/{model}"
        self._client = client
        self._model = model

    def _require_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            raise LLMUnavailable(f"{self.name}: anahtar yok")
        return self._client

    def _unavailable(self, error: anthropic.APIError) -> LLMUnavailable:
        # Mesaj gövdesi bilerek alınmaz: sunucu metni log'a girer, kısa ve öngörülebilir kalsın.
        if isinstance(error, anthropic.APIStatusError):
            return LLMUnavailable(f"{self.name}: HTTP {error.status_code}")
        return LLMUnavailable(f"{self.name}: {type(error).__name__}")

    def _params(self, messages: Sequence[Message], max_tokens: int) -> dict[str, Any]:
        system, turns = _split(messages)
        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": turns,
            "thinking": _THINKING,
        }
        if system:
            params["system"] = system
        return params

    async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        client = self._require_client()
        try:
            async with client.messages.stream(
                **self._params(messages, max_tokens), output_config={"effort": "low"}
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            raise self._unavailable(e) from e
        _count(final.usage)
        if final.stop_reason == "refusal":
            raise LLMUnavailable(f"{self.name}: refusal")

    async def complete_json(
        self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int
    ) -> str:
        client = self._require_client()
        try:
            response = await client.messages.create(
                **self._params(messages, max_tokens),
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APIError as e:
            raise self._unavailable(e) from e
        _count(response.usage)
        if response.stop_reason == "refusal":
            raise LLMUnavailable(f"{self.name}: refusal")
        return next((b.text for b in response.content if b.type == "text"), "")
