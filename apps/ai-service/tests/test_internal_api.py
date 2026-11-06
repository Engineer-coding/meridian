"""Çekirdek API'nin çağırdığı iç uç: gizli anahtar, olay akışı, kiracı izolasyonu, zarif bozulma."""

import json
import re
from collections.abc import AsyncIterator, Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from meridian_ai.answering import EVIDENCE_PROMPTS
from meridian_ai.app import create_app
from meridian_ai.embedding import HashEmbedder
from meridian_ai.evaluation import runner
from meridian_ai.evaluation.corpus import Corpus
from meridian_ai.evaluation.database import Database
from meridian_ai.evaluation.golden import Question, SourceRef
from meridian_ai.fetchers import RawDocument
from meridian_ai.llm import LLMUnavailable
from meridian_ai.settings import Settings

TOKEN = "gizli-anahtar"  # noqa: S105
HEADERS = {"X-Internal-Token": TOKEN}
DOC = RawDocument(
    "kvkk/6698.md",
    "u",
    "v",
    "# KVKK\n\n### Madde 13 – Başvuru\n\nVeri sorumlusu başvuruyu en geç otuz gün içinde sonuçlandırır.",
)


class Model:
    name = "test/model"

    def __init__(self) -> None:
        self.down = False

    async def stream(self, messages, *, max_tokens) -> AsyncIterator[str]:
        if self.down:
            raise LLMUnavailable("kapalı")
        if messages[-1].content in EVIDENCE_PROMPTS.values():
            yield re.search(r"\[1\] [^\n]*\n([^.\n]+)", messages[1].content).group(1)
        else:
            yield "Otuz gün "
            yield "içinde [1]."


@pytest.fixture(scope="module")
async def tenant(database: Database) -> UUID:
    """Gerçek indeksleme hattından geçmiş tek belgeli bir kiracı."""
    question = Question(
        "q", "Başvuru kaç gün?", "tr", "single_hop", "kvkk", (SourceRef(DOC.path, "Madde 13"),)
    )
    await runner.run(database, [Corpus("kvkk", "upload", "v", [DOC])], [question], HashEmbedder())
    [(tenant_id,)] = runner._query(
        database, "SELECT tenant_id FROM core.sources WHERE name = 'kvkk' ORDER BY created_at DESC LIMIT 1"
    )
    return tenant_id


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture
def client(settings: Settings, model: Model) -> Iterator[TestClient]:
    configured = settings.model_copy(update={"ai_internal_token": SecretStr(TOKEN)})
    with TestClient(create_app(configured, embedder=HashEmbedder(), llm=model)) as client:
        yield client


def events(response) -> list[tuple[str, dict]]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [(row["event"], row["data"]) for row in map(json.loads, response.text.splitlines())]


def ask(client: TestClient, tenant_id: UUID, **extra) -> object:
    body = {"tenantId": str(tenant_id), "question": "Başvuru kaç gün içinde sonuçlandırılır?", **extra}
    return client.post("/internal/v1/answer", headers=HEADERS, json=body)


@pytest.mark.parametrize("headers", [{}, {"X-Internal-Token": "wrong"}, {"X-Internal-Token": ""}])
def test_wrong_or_missing_secret_is_refused(client: TestClient, headers: dict) -> None:
    body = {"tenantId": str(uuid4()), "question": "soru"}
    assert client.post("/internal/v1/answer", headers=headers, json=body).status_code == 401


def test_endpoint_is_closed_when_no_secret_is_configured(settings: Settings, model: Model) -> None:
    configured = settings.model_copy(update={"ai_internal_token": SecretStr("")})
    with TestClient(create_app(configured, embedder=HashEmbedder(), llm=model)) as client:
        body = {"tenantId": str(uuid4()), "question": "soru"}
        assert (
            client.post("/internal/v1/answer", headers={"X-Internal-Token": ""}, json=body).status_code == 401
        )


def test_answer_is_streamed_as_ordered_events(client: TestClient, tenant: UUID) -> None:
    rows = events(ask(client, tenant))

    assert [name for name, _ in rows] == ["sources", "token", "token", "done"]
    source = rows[0][1]["sources"][0]
    assert source["number"] == 1
    assert source["documentPath"] == DOC.path
    assert "otuz gün" in source["content"]
    done = rows[-1][1]
    assert done["answer"] == "Otuz gün içinde [1]."
    assert done["cited"] == [1]
    assert done["abstained"] is False and done["degraded"] is False
    assert done["evidenceSource"] == 1
    assert done["model"] == "test/model"
    assert done["usage"] is None  # bu sağlayıcı sayaç vermiyor; API metinden tahmin eder


def test_another_tenant_finds_nothing_and_the_model_is_not_called(client: TestClient, model: Model) -> None:
    model.down = True  # çağrılsaydı "degraded" dönerdi
    rows = events(ask(client, uuid4()))

    assert rows[0] == ("sources", {"sources": []})
    assert rows[-1][1]["abstained"] is True and rows[-1][1]["degraded"] is False


def test_unavailable_model_still_returns_sources(client: TestClient, tenant: UUID, model: Model) -> None:
    model.down = True
    rows = events(ask(client, tenant))

    assert [name for name, _ in rows] == ["sources", "done"]
    assert rows[0][1]["sources"]
    assert rows[-1][1]["degraded"] is True


def test_collection_filter_is_applied(client: TestClient, tenant: UUID) -> None:
    rows = events(ask(client, tenant, collectionIds=[str(uuid4())]))
    assert rows[0][1]["sources"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"question": "tenant yok"},
        {"tenantId": "bozuk", "question": "soru"},
        {"tenantId": str(uuid4()), "question": ""},
        {"tenantId": str(uuid4()), "question": "soru", "fazladan": 1},
    ],
)
def test_malformed_requests_are_rejected(client: TestClient, body: dict) -> None:
    assert client.post("/internal/v1/answer", headers=HEADERS, json=body).status_code == 422
