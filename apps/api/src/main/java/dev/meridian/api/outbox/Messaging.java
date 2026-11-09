package dev.meridian.api.outbox;

/**
 * RabbitMQ topolojisinin adları (ADR-0004). Çekirdek API olayları {@link #EVENTS} konu
 * exchange'ine olay türüyle (ör. {@code source.created}) yayımlar; AI servisi
 * {@link #INDEXING_QUEUE} kuyruğundan tüketir. Reddedilen veya teslim sınırını aşan mesajlar
 * {@link #DEAD_LETTERS} üzerinden {@link #INDEXING_DLQ} kuyruğuna düşer.
 */
public final class Messaging {

    public static final String EVENTS = "meridian.events";
    public static final String DEAD_LETTERS = "meridian.dlx";
    public static final String INDEXING_QUEUE = "ai.indexing";
    public static final String INDEXING_DLQ = "ai.indexing.dlq";

    /** Mesaj başlığı: olayın ait olduğu kiracı. */
    public static final String TENANT_HEADER = "tenant_id";
    /** W3C iz bağlamı; tüketici indekslemeyi olayı doğuran isteğin izine bağlar (ADR-0017). */
    public static final String TRACEPARENT_HEADER = "traceparent";

    private Messaging() {
    }
}
