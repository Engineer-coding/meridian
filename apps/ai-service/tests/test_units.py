import json
import random
from datetime import timedelta
from uuid import uuid4

import pytest

from meridian_ai.events import InvalidMessage, parse_event
from meridian_ai.retry import backoff
from meridian_ai.settings import Settings


def envelope(**overrides: object) -> dict[str, object]:
    return {
        "eventId": str(uuid4()),
        "type": "source.created",
        "tenantId": str(uuid4()),
        "aggregateId": str(uuid4()),
        "occurredAt": "2026-11-02T10:00:00Z",
        "data": {"sourceId": str(uuid4())},
    } | overrides


def test_backoff_grows_exponentially_within_jitter_bounds() -> None:
    rng = random.Random(42)
    for attempt, ceiling in [(1, 1_000), (2, 4_000), (3, 16_000), (4, 64_000)]:
        for _ in range(200):
            delay = backoff(attempt, base_ms=1_000, factor=4, rng=rng)
            assert timedelta(milliseconds=ceiling / 2) <= delay <= timedelta(milliseconds=ceiling)


def test_backoff_spreads_simultaneous_failures() -> None:
    delays = {backoff(3, base_ms=1_000, factor=4) for _ in range(50)}
    assert len(delays) > 40


def test_backoff_rejects_zeroth_attempt() -> None:
    with pytest.raises(ValueError):
        backoff(0, base_ms=1_000, factor=4)


def test_valid_envelope_is_parsed() -> None:
    raw = envelope()
    event = parse_event(json.dumps(raw).encode(), raw["eventId"], {"tenant_id": raw["tenantId"]})
    assert str(event.tenant_id) == raw["tenantId"]
    assert event.type == "source.created"


@pytest.mark.parametrize(
    ("body", "message_id", "tenant"),
    [
        (b"not json", None, None),
        (json.dumps(envelope(tenantId="kiraci-degil")).encode(), None, None),
        (json.dumps({"eventId": str(uuid4())}).encode(), None, None),
    ],
)
def test_unreadable_envelope_is_invalid(body: bytes, message_id: str | None, tenant: str | None) -> None:
    with pytest.raises(InvalidMessage):
        parse_event(body, message_id, {"tenant_id": tenant})


def test_header_and_body_must_agree() -> None:
    raw = envelope()
    body = json.dumps(raw).encode()
    with pytest.raises(InvalidMessage, match="message_id"):
        parse_event(body, str(uuid4()), {"tenant_id": raw["tenantId"]})
    with pytest.raises(InvalidMessage, match="tenant_id"):
        parse_event(body, raw["eventId"], {"tenant_id": str(uuid4())})


def test_password_with_special_characters_is_escaped_in_url() -> None:
    settings = Settings(rabbitmq_user="meridian", rabbitmq_password="p@ss/w:rd", _env_file=None)
    assert settings.amqp_url == "amqp://meridian:p%40ss%2Fw%3Ard@127.0.0.1:5672/"
