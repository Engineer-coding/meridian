# AI servisi imajı. Bağımlılıklar kilit dosyasından kurulur; çalışma imajında derleyici ve uv yoktur.
FROM ghcr.io/astral-sh/uv:0.9.4-python3.13-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
# Önce yalnızca bağımlılıklar: kod değişince bu katman önbellekten gelir.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

FROM python:3.13-slim-bookworm AS runtime
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8090 \
    EMBEDDING_CACHE_DIR=/tmp/fastembed
USER 10001
EXPOSE 8090
CMD ["python", "-m", "meridian_ai"]

# Yalnızca CI'daki küme testi için: model, embedding ve GitHub sabit parçalarla değişir (tests/e2e_stack.py).
#   docker build --target test -t meridian-ai-test:local apps/ai-service
FROM runtime AS test
COPY --chown=10001:10001 tests/e2e_stack.py tests/e2e_stack.py
CMD ["python", "tests/e2e_stack.py"]

# Varsayılan hedef: üretim imajı.
FROM runtime
