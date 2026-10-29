export MSYS_NO_PATHCONV := 1

COMPOSE = docker compose -f infra/compose/compose.yaml --env-file .env

.PHONY: up down ps logs psql reset smoke contract-lint

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
