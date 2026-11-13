"""Anthropic sağlayıcısı: gerçek SDK, sahte HTTP katmanı (httpx2 MockTransport) ile sınanır."""

import json
from collections.abc import AsyncIterator, Callable

import httpx2
import pytest

from meridian_ai.llm import LLMUnavailable, Message, UsageCounter, usage_counter
from meridian_ai.llm_anthropic import AnthropicLLM, make_client

MODEL = "claude-haiku-5-5"
KEY = "sk-ant-test-secret-value"


def sse(*events: dict) -> httpx2.Response:
    body = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())


def stream_events(*texts: str, stop: str = "end_turn", input_tokens: int = 10, output_tokens: int = 5):
    events: list[dict] = [
        {
            "type": "message_start",
            "message": {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": MODEL,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": input_tokens, "output_tokens": 0},
            },
        },
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    ]
    events += [
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t}} for t in texts
    ]
    events += [
        {"type": "content_block_stop", "index": 0},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop, "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        },
        {"type": "message_stop"},
    ]
    return events


def message_json(text: str | None, stop: str = "end_turn") -> httpx2.Response:
    content = [] if text is None else [{"type": "text", "text": text}]
    return httpx2.Response(
        200,
        json={
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "model": MODEL,
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 7},
        },
    )


def llm(handler: Callable[[httpx2.Request], httpx2.Response]) -> AnthropicLLM:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return AnthropicLLM(make_client(KEY, http), MODEL)


def recording(response: httpx2.Response, seen: list[dict]):
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return response

    return handler


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [t async for t in stream]


USER = [Message("user", "Soru?")]


async def test_streams_text_deltas_in_order() -> None:
    provider = llm(lambda _: sse(*stream_events("Mer", "haba")))
    assert provider.name == f"anthropic/{MODEL}"
    assert await collect(provider.stream(USER, max_tokens=300)) == ["Mer", "haba"]


async def test_request_has_no_sampling_params_and_disables_thinking() -> None:
    seen: list[dict] = []
    await collect(llm(recording(sse(*stream_events("x")), seen)).stream(USER, max_tokens=300))
    body = seen[0]
    assert not {"temperature", "top_p", "top_k"} & body.keys()
    assert body["thinking"] == {"type": "disabled"}
    assert body["output_config"]["effort"] == "low"
    assert body["model"] == MODEL
    assert body["max_tokens"] == 300


async def test_leading_system_messages_become_top_level_system() -> None:
    seen: list[dict] = []
    messages = [Message("system", "A"), Message("system", "B"), Message("user", "q")]
    await collect(llm(recording(sse(*stream_events("x")), seen)).stream(messages, max_tokens=50))
    assert seen[0]["system"] == "A\n\nB"
    assert seen[0]["messages"] == [{"role": "user", "content": "q"}]


async def test_usage_is_added_to_the_request_counter() -> None:
    counter = UsageCounter()
    token = usage_counter.set(counter)
    try:
        events = stream_events("x", input_tokens=1200, output_tokens=80)
        await collect(llm(lambda _: sse(*events)).stream(USER, max_tokens=300))
    finally:
        usage_counter.reset(token)
    assert (counter.prompt_tokens, counter.completion_tokens, counter.counted) == (1200, 80, True)


async def test_usage_is_counted_when_cut_by_max_tokens() -> None:
    counter = UsageCounter()
    token = usage_counter.set(counter)
    try:
        events = stream_events("yarım", stop="max_tokens", input_tokens=40, output_tokens=16)
        assert await collect(llm(lambda _: sse(*events)).stream(USER, max_tokens=16)) == ["yarım"]
    finally:
        usage_counter.reset(token)
    assert (counter.prompt_tokens, counter.completion_tokens, counter.counted) == (40, 16, True)


@pytest.mark.parametrize("status", [401, 429, 500, 529])
async def test_http_errors_before_first_token_become_unavailable(status: int) -> None:
    error = {"type": "error", "error": {"type": "api_error", "message": "boom"}}
    provider = llm(lambda _: httpx2.Response(status, json=error))
    with pytest.raises(LLMUnavailable) as raised:
        await collect(provider.stream(USER, max_tokens=10))
    assert str(status) in str(raised.value)
    assert KEY not in str(raised.value)


async def test_connection_error_becomes_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    with pytest.raises(LLMUnavailable):
        await collect(llm(handler).stream(USER, max_tokens=10))


async def test_refusal_before_any_text_becomes_unavailable() -> None:
    provider = llm(lambda _: sse(*stream_events(stop="refusal")))
    with pytest.raises(LLMUnavailable, match="refusal"):
        await collect(provider.stream(USER, max_tokens=10))


async def test_refusal_after_text_raises_mid_stream() -> None:
    provider = llm(lambda _: sse(*stream_events("Kısmi", stop="refusal")))
    received: list[str] = []
    with pytest.raises(LLMUnavailable, match="refusal"):
        async for token in provider.stream(USER, max_tokens=10):
            received.append(token)
    assert received == ["Kısmi"]


async def test_complete_json_sends_json_schema_format_and_returns_text() -> None:
    seen: list[dict] = []
    schema = {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}
    counter = UsageCounter()
    token = usage_counter.set(counter)
    try:
        provider = llm(recording(message_json('{"action":"finish"}'), seen))
        text = await provider.complete_json(USER, schema, max_tokens=200)
    finally:
        usage_counter.reset(token)
    assert text == '{"action":"finish"}'
    assert seen[0]["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert "stream" not in seen[0] or seen[0]["stream"] is False
    assert (counter.prompt_tokens, counter.completion_tokens, counter.counted) == (50, 7, True)


async def test_complete_json_refusal_becomes_unavailable() -> None:
    provider = llm(lambda _: message_json(None, stop="refusal"))
    with pytest.raises(LLMUnavailable, match="refusal"):
        await provider.complete_json(USER, {"type": "object"}, max_tokens=50)
