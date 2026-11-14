export MSYS_NO_PATHCONV := 1

COMPOSE = docker compose -f infra/compose/compose.yaml --env-file .env 

PYTHON ?= python

.PHONY: up down ps logs psql reset smoke contract-lint eval-validate api-test ai-test ai-run web-test web-e2e e2e-full web-run eval eval-smoke eval-answers eval-redteam obs-check load images helm-test k8s-up k8s-dev k8s-down k8s-smoke tf-check demo-up demo-down demo-smoke

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
# Prometheus kuralları ve alarm testleri (ADR-0018): eşikler sentetik seriyle sınanır.
obs-check:
	docker run --rm -v "$(CURDIR)/infra/helm/meridian/files/prometheus:/p" -w /p/tests --entrypoint promtool prom/prometheus:v3.15.1 check rules ../rules/slo.yml
	docker run --rm -v "$(CURDIR)/infra/helm/meridian/files/prometheus:/p" -w /p/tests --entrypoint promtool prom/prometheus:v3.15.1 test rules slo_test.yml
	docker run --rm -v "$(CURDIR)/infra/helm/meridian/files/prometheus:/p" -w /p --entrypoint promtool prom/prometheus:v3.15.1 check config prometheus.yml

# Yük testi (packages/load): SCENARIO=chat (500 eşzamanlı sohbet) ya da indexing (50 eşzamanlı iş).
load:
	bash packages/load/run.sh

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
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation --answers --name $(NAME) $(if $(LLM),--llm $(LLM))

# Kırmızı takım seti gerçek modelle (ADR-0016). CPU'da saatler sürer; rapor depoya girer, CI kapısı denetler.
eval-redteam:
	cd apps/ai-service && PYTHONUTF8=1 uv run python -m meridian_ai.evaluation.redteam --name $(NAME) $(if $(LLM),--llm $(LLM))

# Üretim imajları (Faz 6, ADR-0009); kind kümesi bu yerel etiketleri yükler.
images:
	docker build -f apps/api/Dockerfile -t meridian-api:local .
	docker build -t meridian-ai:local apps/ai-service
	docker build --target test -t meridian-ai-test:local apps/ai-service
	docker build -t meridian-web:local apps/web

# Helm chart: lint, birim testleri (helm-unittest) ve şema doğrulaması (kubeconform; Traefik CRD'leri katalogdan).
CHART := infra/helm/meridian
KUBECONFORM := kubeconform -strict -summary -schema-location default 	-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
helm-test:
	helm lint $(CHART) -f $(CHART)/values-local.yaml
	helm unittest $(CHART)
	bash infra/k8s/test-preflight.sh
	bash infra/k8s/test-up-demo.sh
	bash infra/demo/test-demo.sh
	helm template meridian $(CHART) -f $(CHART)/values-local.yaml | $(KUBECONFORM)
	helm template meridian $(CHART) -f $(CHART)/values-local.yaml -f $(CHART)/values-ci.yaml | $(KUBECONFORM)
	helm template meridian $(CHART) -f $(CHART)/values-demo.yaml --set appUrl=https://meridian.1.2.3.4.sslip.io --set image.tag=sha-0000000 | $(KUBECONFORM)

# Yerel Kubernetes (ADR-0009): kind + Argo CD. k8s-up dalı GitHub'dan çeker (push edilmiş olmalı);
# k8s-dev aynı chart'ı çalışma ağacından kurar. Önce: make images.
K8S_REVISION ?= $(shell git rev-parse --abbrev-ref HEAD)
k8s-up:
	bash infra/k8s/up.sh local argo $(K8S_REVISION)

k8s-dev:
	bash infra/k8s/up.sh local helm

k8s-down:
	bash infra/k8s/down.sh

k8s-smoke:
	bash infra/k8s/smoke.sh http://meridian.localtest.me alice alice

# Terraform (canlı demo, ADR-0009): biçim, doğrulama ve sır taraması. Terraform kurulu olmak zorunda değil.
TERRAFORM_VERSION := $(shell grep '^TERRAFORM_VERSION=' infra/versions.env | cut -d= -f2)
TERRAFORM = docker run --rm -v "$(CURDIR)/infra/terraform:/tf" -w /tf/$(1) hashicorp/terraform:$(TERRAFORM_VERSION)
tf-check:
	$(call TERRAFORM,.) fmt -check -recursive
	for dir in persistent demo; do \
		test -f infra/terraform/$$dir/main.tf || { echo "infra/terraform/$$dir/main.tf yok"; exit 1; }; \
		$(call TERRAFORM,$$dir) init -backend=false -input=false >/dev/null && \
		$(call TERRAFORM,$$dir) validate || exit 1; \
	done
	if grep -rnE 'ANTHROPIC|SESSION_SECRET|DB_[A-Z_]*PASSWORD|KEYCLOAK_ADMIN' infra/terraform --include='*.tf' --include='*.tftpl'; then \
		echo "Terraform kodunda uygulama sırrı"; exit 1; \
	fi

# Canlı demo (ADR-0009, docs/runbooks/demo.md): Hetzner'de tek sunucu; HCLOUD_TOKEN gerekli.
demo-up:
	bash infra/demo/up.sh

demo-down:
	bash infra/demo/down.sh

demo-smoke:
	bash infra/demo/smoke.sh
