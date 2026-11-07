export MSYS_NO_PATHCONV := 1

COMPOSE = docker compose -f infra/compose/compose.yaml --env-file .env 

PYTHON ?= python

.PHONY: up down ps logs psql reset smoke contract-lint eval-validate api-test ai-test ai-run web-test web-e2e e2e-full web-run eval eval-smoke eval-answers eval-redteam

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
	$(PYTHON) -I packages/eval/scripts/validate_golden.py packages/eval/golden/v2.jsonl

api-test:
	cd apps/api && ./mvnw -B verify

ai-test:
	cd apps/ai-service && uv sync --locked && uv run ruff check && uv run ruff format --check && uv run pytest

web-test:
	cd apps/web && npm ci && npm run check:api && npm run check:eval && npm run lint && npm run typecheck && npm test

web-e2e:
	cd apps/web && npm run test:e2e

# Tam sistem: gerçek Keycloak, API, AI servisi, RabbitMQ, PostgreSQL ve tarayıcı. Atılabilir altyapı, ayrı portlar.
E2E_COMPOSE = docker compose -f infra/compose/compose.e2e.yaml --env-file .env.example
e2e-full:
	$(E2E_COMPOSE) down -v
	$(E2E_COMPOSE) up -d --wait
	cd apps/api && ./mvnw -B -q -DskipTests package
	cd apps/web && npx playwright test --config playwright.full.config.ts; status=$$?; cd ../..; 	$(E2E_COMPOSE) down -v; exit $$status

web-run:
	cd apps/web && npm run dev

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

# Kırmızı takım seti gerçek modelle (ADR-0016). CPU'da saatler sürer; rapor depoya girer, CI kapısı denetler.
eval-redteam:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation.redteam --name $(NAME)
