export MSYS_NO_PATHCONV := 1

COMPOSE = docker compose -f infra/compose/compose.yaml --env-file .env 

PYTHON ?= python

.PHONY: up down ps logs psql reset smoke contract-lint eval-validate api-test ai-test ai-run eval eval-smoke eval-answers

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

psql:
	$(COMPOSE) exec postgres psql -U meridian -d meridian

reset:
	$(COMPOSE) down -v

smoke:
	$(COMPOSE) exec -T postgres psql -U meridian -d meridian -v ON_ERROR_STOP=1 < infra/compose/postgres/smoke.sql

contract-lint:
	docker run --rm -v "$(CURDIR)/packages/api-contract:/spec" -w /spec redocly/cli:2.62.2 lint openapi.yaml

eval-validate:
	$(PYTHON) -I packages/eval/scripts/validate_golden.py packages/eval/golden/v1.jsonl

api-test:
	cd apps/api && ./mvnw -B verify

ai-test:
	cd apps/ai-service && uv sync --locked && uv run ruff check && uv run ruff format --check && uv run pytest

ai-run:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai

# Retrieval değerlendirmesi ve ablasyon tablosu (ADR-0007). İlk çalıştırma korpusu gömer
# (CPU'da ~1,5 saat) ve iki reranker'ı indirir;
# embedding'ler ~/.cache/meridian/eval altında saklanır, sonraki çalıştırmalar dakikalar sürer.
# Kayıtlı baseline'ı güncellemek için: make eval NAME=baseline
NAME ?= latest
eval:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --rerank bge-m3,jina-v2 --name $(NAME)

# Modelsiz duman testi: korpus + altın set + indeksleme + arama hattını doğrular, kaliteyi ölçmez.
eval-smoke:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --embedder hash --name smoke

# Kaynaklı cevap değerlendirmesi (Ollama, ADR-0008). Bu donanımda soru başına ~1,5 dk;
# cevaplar ~/.cache/meridian/eval altında önbelleklenir.
eval-answers:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --answers --name $(NAME)
