package dev.meridian.api.outbox;

import java.util.Map;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

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

    OutboxWriter(JdbcClient jdbc, JsonMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    /** @return olayın kimliği; tüketiciler tekrarlanan teslimatı bununla ayıklar */
    public UUID append(String eventType, UUID aggregateId, Map<String, ?> data) {
        UUID eventId = UUID.randomUUID();
        jdbc.sql("""
                INSERT INTO outbox (event_id, tenant_id, event_type, aggregate_id, payload)
                VALUES (:eventId, current_tenant_id(), :eventType, :aggregateId, :payload::jsonb)""")
            .param("eventId", eventId)
            .param("eventType", eventType)
            .param("aggregateId", aggregateId)
            .param("payload", json.writeValueAsString(data))
            .update();
        return eventId;
    }
}
