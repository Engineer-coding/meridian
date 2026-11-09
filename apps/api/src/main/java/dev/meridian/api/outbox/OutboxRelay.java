package dev.meridian.api.outbox;

import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;

import javax.sql.DataSource;

import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.MessageProperties;
import org.springframework.amqp.rabbit.core.RabbitOperations;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * Outbox'taki olayları RabbitMQ'ya aktarır. Kendi veritabanı rolüyle ({@code meridian_relay})
 * çalışır: bu rol tüm kiracıların olaylarını görür ama başka hiçbir tabloya erişemez.
 *
 * <p>Bir parti şöyle işlenir: olaylar okunur, yayımlanır, broker her birini diske yazdığını
 * onaylar (publisher confirm) ve ancak ondan sonra satırlar silinir. Onay gelmezse işlem geri
 * alınır, satırlar yerinde kalır ve sonraki turda yeniden denenir. Bu yüzden teslimat en az
 * bir kezdir; tüketiciler {@code messageId} (= event_id) ile tekrarı ayıklar.
 *
 * <p>Birden fazla API örneği çalışırken aynı anda yalnızca biri aktarır (işleme yerel
 * advisory lock). Böylece aynı olay iki örnek tarafından eşzamanlı yayımlanmaz ve sıra korunur.
 */
public class OutboxRelay implements AutoCloseable {

    static final int BATCH_SIZE = 100;
    private static final long CONFIRM_TIMEOUT_MS = 5_000;
    private static final long LEADER_LOCK = 0x6d6572_6f7574L; // "mer" "out"

    private record Pending(long id, UUID eventId, UUID tenantId, String eventType, UUID aggregateId,
            String payload, OffsetDateTime createdAt, String traceparent) {
    }

    private final DataSource dataSource;
    private final JdbcClient jdbc;
    private final TransactionTemplate tx;
    private final RabbitOperations rabbit;
    private final JsonMapper json;

    OutboxRelay(DataSource relayDataSource, RabbitOperations rabbit, JsonMapper json) {
        this.dataSource = relayDataSource;
        this.jdbc = JdbcClient.create(relayDataSource);
        this.tx = new TransactionTemplate(new JdbcTransactionManager(relayDataSource));
        this.rabbit = rabbit;
        this.json = json;
    }

    /** Bekleyen olaylardan bir partiyi aktarır. @return yayımlanan olay sayısı */
    public int relayBatch() {
        Integer published = tx.execute(status -> {
            boolean leader = jdbc.sql("SELECT pg_try_advisory_xact_lock(:lock)")
                .param("lock", LEADER_LOCK)
                .query(Boolean.class)
                .single();
            if (!leader) {
                return 0;
            }
            List<Pending> batch = jdbc.sql("""
                    SELECT id, event_id, tenant_id, event_type, aggregate_id, payload::text AS payload, created_at,
                           traceparent
                    FROM outbox ORDER BY id LIMIT :limit""")
                .param("limit", BATCH_SIZE)
                .query((rs, rowNum) -> new Pending(rs.getLong("id"), rs.getObject("event_id", UUID.class),
                    rs.getObject("tenant_id", UUID.class), rs.getString("event_type"),
                    rs.getObject("aggregate_id", UUID.class), rs.getString("payload"),
                    rs.getObject("created_at", OffsetDateTime.class), rs.getString("traceparent")))
                .list();
            if (batch.isEmpty()) {
                return 0;
            }
            rabbit.invoke(channel -> {
                batch.forEach(event -> channel.send(Messaging.EVENTS, event.eventType(), toMessage(event)));
                channel.waitForConfirmsOrDie(CONFIRM_TIMEOUT_MS);
                return null;
            });
            // Aralık değil kimlik listesiyle silinir: okuma anında henüz commit edilmemiş, daha
            // küçük kimlikli bir olay aralığa düşse bile yayımlanmadan silinmez.
            jdbc.sql("DELETE FROM outbox WHERE id IN (:ids)")
                .param("ids", batch.stream().map(Pending::id).toList())
                .update();
            return batch.size();
        });
        return published == null ? 0 : published;
    }

    /** Biriken tüm olayları aktarır. @return yayımlanan olay sayısı */
    public int drain() {
        int total = 0;
        int published;
        do {
            published = relayBatch();
            total += published;
        } while (published == BATCH_SIZE);
        return total;
    }

    private Message toMessage(Pending event) {
        var envelope = new LinkedHashMap<String, Object>();
        envelope.put("eventId", event.eventId());
        envelope.put("type", event.eventType());
        envelope.put("tenantId", event.tenantId());
        envelope.put("aggregateId", event.aggregateId());
        envelope.put("occurredAt", event.createdAt().toString());
        envelope.put("data", json.readValue(event.payload(), JsonNode.class));

        var properties = new MessageProperties();
        properties.setMessageId(event.eventId().toString());
        properties.setType(event.eventType());
        properties.setContentType(MessageProperties.CONTENT_TYPE_JSON);
        properties.setContentEncoding("utf-8");
        properties.setDeliveryMode(MessageDeliveryMode.PERSISTENT);
        properties.setHeader(Messaging.TENANT_HEADER, event.tenantId().toString());
        if (event.traceparent() != null) {
            properties.setHeader(Messaging.TRACEPARENT_HEADER, event.traceparent());
        }
        return new Message(json.writeValueAsBytes(envelope), properties);
    }

    @Override
    public void close() throws Exception {
        if (dataSource instanceof AutoCloseable closeable) {
            closeable.close();
        }
    }
}
