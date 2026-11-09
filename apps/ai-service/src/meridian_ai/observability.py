"""İzleme (ADR-0017): OpenTelemetry izleri, metrikleri ve JSON loglar.

Ölçülen kod (cevap hattı, ajan, arama, indeksleme) değiştirilmez: model, arama ve embedding dışarıdan sarılır.
Böylece değerlendirme raporlarının parmak izi değişmez ve izleme kalite ölçümünü etkileyemez.

Span ve iz kimlikleri her durumda üretilir ve taşınır; toplayıcıya gönderim yalnızca ``OTEL_EXPORT`` açıkken
yapılır. Kişisel veri span'a da loga da yazılmaz: soru ve belge metni yok; sayılar, süreler ve kimlikler var.
"""

import json
import logging
import time
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from opentelemetry import context, metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.trace import Span, Status, StatusCode

from meridian_ai.guardrails import mask_pii
from meridian_ai.llm import Message, usage_counter

SERVICE = "meridian-ai"
# İstek boyunca kiracı: log satırına ve span'a yazılır. Kimlik değildir, kişiye işaret etmez.
current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)

tracer = trace.get_tracer("meridian.ai")
_meter = metrics.get_meter("meridian.ai")
# Saniye cinsinden; CPU'da model çağrısı dakikalar sürebildiği için kovalar geniştir.
_SECONDS = [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300]
llm_duration = _meter.create_histogram(
    "meridian.llm.duration",
    unit="s",
    description="Model çağrısı süresi",
    explicit_bucket_boundaries_advisory=_SECONDS,
)
llm_first_token = _meter.create_histogram(
    "meridian.llm.first_token",
    unit="s",
    description="İlk token süresi",
    explicit_bucket_boundaries_advisory=_SECONDS,
)
llm_tokens = _meter.create_counter("meridian.llm.tokens", unit="{token}", description="Harcanan token")
retrieval_duration = _meter.create_histogram(
    "meridian.retrieval.duration",
    unit="s",
    description="Arama süresi",
    explicit_bucket_boundaries_advisory=_SECONDS,
)
indexing_duration = _meter.create_histogram(
    "meridian.indexing.duration",
    unit="s",
    description="Bir kaynak olayının işlenme süresi",
    explicit_bucket_boundaries_advisory=_SECONDS,
)
answers = _meter.create_counter("meridian.answers", unit="{answer}", description="Sonuca göre cevaplar")
agent_runs = _meter.create_counter(
    "meridian.agent.runs", unit="{run}", description="Duruma göre ajan çalıştırmaları"
)

_configured = False


def configure(
    *,
    export: bool = False,
    endpoint: str = "http://127.0.0.1:4318",
    sampling: float = 1.0,
    environment: str = "local",
    span_exporter: SpanExporter | None = None,
    metric_reader: MetricReader | None = None,
) -> None:
    """Süreç başına bir kez; sonraki çağrılar bir şey yapmaz (testler önce kendi dışa aktarıcısını verir)."""
    global _configured
    if _configured:
        return
    _configured = True
    resource = Resource.create(
        {"service.name": SERVICE, "service.namespace": "meridian", "deployment.environment": environment}
    )
    provider = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(sampling)))
    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    if export:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(provider)

    readers: list[MetricReader] = [metric_reader] if metric_reader is not None else []
    if export:
        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"), export_interval_millis=15_000
            )
        )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

    if export:
        logs = LoggerProvider(resource=resource)
        logs.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
        )
        handler = LoggingHandler(logger_provider=logs)
        handler.addFilter(_PiiFilter())
        logging.getLogger().addHandler(handler)

    # Model, MCP ve GitHub istekleri: span olur, iz bağlamı karşı tarafa geçer.
    HTTPXClientInstrumentor().instrument()


class _PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_pii(record.getMessage())
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    """Tek satır JSON; iz ve kiracı kimliği her satırda. Kişisel veri maskesi ayrı filtrededir."""

    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span().get_span_context()
        line: dict[str, Any] = {
            "@timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "log.level": record.levelname,
            "log.logger": record.name,
            "message": record.getMessage(),
            "service.name": SERVICE,
        }
        if span.is_valid:
            line["traceId"] = format(span.trace_id, "032x")
            line["spanId"] = format(span.span_id, "016x")
        if tenant := current_tenant.get():
            line["tenant.id"] = tenant
        if record.exc_info:
            line["error.stack_trace"] = self.formatException(record.exc_info)
        elif record.exc_text:
            line["error.stack_trace"] = record.exc_text
        return json.dumps(line, ensure_ascii=False)


def use_json_logs() -> None:
    for handler in logging.getLogger().handlers:
        if not isinstance(handler, LoggingHandler):
            handler.setFormatter(JsonFormatter())


@contextmanager
def tenant_scope(tenant_id: UUID | str) -> Iterator[None]:
    token = current_tenant.set(str(tenant_id))
    try:
        trace.get_current_span().set_attribute("tenant.id", str(tenant_id))
        yield
    finally:
        current_tenant.reset(token)


@contextmanager
def consumed(headers: Mapping[str, Any], name: str) -> Iterator[Span]:
    """Kuyruk mesajı: span, mesajı doğuran isteğin izinin devamıdır (outbox ``traceparent`` başlığı)."""
    carrier = {key: str(value) for key, value in headers.items() if isinstance(value, str | bytes)}
    parent = propagate.extract(carrier)
    token = context.attach(parent)
    try:
        with tracer.start_as_current_span(name, kind=trace.SpanKind.CONSUMER) as span:
            yield span
    finally:
        context.detach(token)


def _record_error(span: Span, error: BaseException) -> None:
    span.record_exception(error)
    span.set_status(Status(StatusCode.ERROR, type(error).__name__))


class TracedLLM:
    """Her model çağrısı bir span: süre, ilk token, token sayısı. İstem ve cevap metni yazılmaz."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.name = inner.name

    def __getattr__(self, item: str) -> Any:
        # last_used gibi sağlayıcıya özgü alanlar aynen görünür.
        return getattr(self._inner, item)

    def _attributes(self, operation: str) -> dict[str, str]:
        model = getattr(self._inner, "last_used", None) or self.name
        return {"gen_ai.operation.name": operation, "gen_ai.request.model": model}

    @staticmethod
    def _tokens() -> tuple[int, int]:
        counter = usage_counter.get()
        return (counter.prompt_tokens, counter.completion_tokens) if counter else (0, 0)

    def _finish(self, span: Span, operation: str, started: float, before: tuple[int, int]) -> None:
        prompt, completion = (now - then for now, then in zip(self._tokens(), before, strict=True))
        attributes = self._attributes(operation)
        span.set_attributes(
            {**attributes, "gen_ai.usage.input_tokens": prompt, "gen_ai.usage.output_tokens": completion}
        )
        llm_duration.record(time.monotonic() - started, attributes)
        llm_tokens.add(prompt, {**attributes, "gen_ai.token.type": "input"})
        llm_tokens.add(completion, {**attributes, "gen_ai.token.type": "output"})

    async def stream(self, messages: Sequence[Message], *, max_tokens: int) -> AsyncIterator[str]:
        with tracer.start_as_current_span("llm chat", kind=trace.SpanKind.CLIENT) as span:
            started, before, first = time.monotonic(), self._tokens(), True
            try:
                async for token in self._inner.stream(messages, max_tokens=max_tokens):
                    if first:
                        first = False
                        elapsed = time.monotonic() - started
                        span.set_attribute("meridian.first_token_s", round(elapsed, 3))
                        llm_first_token.record(elapsed, self._attributes("chat"))
                    yield token
            except BaseException as e:
                _record_error(span, e)
                raise
            finally:
                self._finish(span, "chat", started, before)

    async def complete_json(
        self, messages: Sequence[Message], schema: dict[str, Any], *, max_tokens: int
    ) -> str:
        with tracer.start_as_current_span("llm decide", kind=trace.SpanKind.CLIENT) as span:
            started, before = time.monotonic(), self._tokens()
            try:
                return await self._inner.complete_json(messages, schema, max_tokens=max_tokens)
            except BaseException as e:
                _record_error(span, e)
                raise
            finally:
                self._finish(span, "decide", started, before)


class TracedRetriever:
    """Arama span'ı: mod, istenen ve bulunan sayı. Sorgu metni yazılmaz."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    async def search(self, tenant_id: UUID, query: str, *, k: int, mode: Any = None, **kwargs: Any) -> Any:
        with tracer.start_as_current_span("retrieval.search") as span:
            started = time.monotonic()
            arguments = {"k": k, **kwargs} if mode is None else {"k": k, "mode": mode, **kwargs}
            try:
                hits = await self._inner.search(tenant_id, query, **arguments)
            except BaseException as e:
                _record_error(span, e)
                raise
            attributes = {
                "retrieval.mode": str(mode or "vector"),
                "retrieval.rerank": bool(kwargs.get("rerank")),
            }
            span.set_attributes({**attributes, "retrieval.k": k, "retrieval.hits": len(hits)})
            retrieval_duration.record(time.monotonic() - started, attributes)
            return hits


class TracedEmbedder:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.dimensions = inner.dimensions

    def __getattr__(self, item: str) -> Any:
        return getattr(self._inner, item)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        with tracer.start_as_current_span("embedding.passages") as span:
            span.set_attribute("embedding.count", len(texts))
            return await self._inner.embed_passages(texts)

    async def embed_query(self, text: str) -> list[float]:
        with tracer.start_as_current_span("embedding.query"):
            return await self._inner.embed_query(text)


class TracedHandler:
    """Kuyruk işleyicisi: süre ve sonuç metriği; başarısızlık span'da hata olarak işaretlenir."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    async def handle(self, event: Any) -> None:
        span = trace.get_current_span()
        span.set_attributes({"messaging.event_type": event.type, "tenant.id": str(event.tenant_id)})
        started, outcome = time.monotonic(), "ok"
        token = current_tenant.set(str(event.tenant_id))
        try:
            await self._inner.handle(event)
        except BaseException as e:
            outcome = "error"
            _record_error(span, e)
            raise
        finally:
            current_tenant.reset(token)
            indexing_duration.record(
                time.monotonic() - started, {"event.type": event.type, "outcome": outcome}
            )

    async def failed(self, event: Any, error: Exception) -> None:
        await self._inner.failed(event, error)
