export MSYS_NO_PATHCONV := 1

COMPOSE = docker compose -f infra/compose/compose.yaml --env-file .env 

PYTHON ?= python

.PHONY: up down ps logs psql reset smoke contract-lint eval-validate api-test ai-test ai-run eval eval-smoke

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
	$(PYTHON) -I packages/eval/scripts/validate_golden.py packages/eval/golden/v0.jsonl

api-test:
	cd apps/api && ./mvnw -B verify

ai-test:
	cd apps/ai-service && uv sync --locked && uv run ruff check && uv run ruff format --check && uv run pytest

ai-run:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai

# Retrieval değerlendirmesi (Faz 3 kapısı). İlk çalıştırma korpusu gömer (CPU'da ~1,5 saat);
# embedding'ler ~/.cache/meridian/eval altında saklanır, sonraki çalıştırmalar dakikalar sürer.
# Kayıtlı baseline'ı güncellemek için: make eval NAME=baseline
NAME ?= latest
eval:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --name $(NAME)

# Modelsiz duman testi: korpus + altın set + indeksleme + arama hattını doğrular, kaliteyi ölçmez.
eval-smoke:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --embedder hash --name smoke
