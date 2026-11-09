package dev.meridian.api.outbox;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import io.micrometer.tracing.Span;
import io.micrometer.tracing.Tracer;
import io.micrometer.tracing.propagation.Propagator;
import tools.jackson.databind.json.JsonMapper;

/**
 * Olayı çağıranın işlemine yazar: iş kaydı commit olursa olay da kalır, rollback olursa
 * ikisi birden kaybolur. "Kayıt var ama olay yok" ya da "olay gitti ama kayıt yok" durumu
 * oluşamaz. Kiracı, parametreden değil veritabanı bağlamından ({@code current_tenant_id()})
 * okunur; RLS başka bir kiracı adına olay yazılmasına izin vermez.
 */
@Component
@Transactional(propagation = Propagation.MANDATORY)
public class OutboxWriter {

    private final JdbcClient jdbc;
    private final JsonMapper json;

    private final Tracer tracer;
    private final Propagator propagator;

    OutboxWriter(JdbcClient jdbc, JsonMapper json, Tracer tracer, Propagator propagator) {
        this.jdbc = jdbc;
        this.json = json;
        this.tracer = tracer;
        this.propagator = propagator;
    }

    /** Olay işlenirken oluşan span'lar (indeksleme) onu doğuran isteğin izine bağlanır. */
    private String traceparent() {
        Span span = tracer.currentSpan();
        if (span == null) {
            return null;
        }
        Map<String, String> headers = new HashMap<>();
        propagator.inject(span.context(), headers, Map::put);
        return headers.get(Messaging.TRACEPARENT_HEADER);
    }

    /** @return olayın kimliği; tüketiciler tekrarlanan teslimatı bununla ayıklar */
    public UUID append(String eventType, UUID aggregateId, Map<String, ?> data) {
        UUID eventId = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO outbox (event_id, tenant_id, event_type, aggregate_id, payload, traceparent)
                VALUES (:eventId, current_tenant_id(), :eventType, :aggregateId, :payload::jsonb, :traceparent)""")
            .param("eventId", eventId)
            .param("eventType", eventType)
            .param("aggregateId", aggregateId)
            .param("payload", json.writeValueAsString(data))
            .param("traceparent", traceparent())
            .update();
        return eventId;
    }
}
