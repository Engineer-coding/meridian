package dev.meridian.api.knowledge;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** Kiracı filtresi yok: izolasyonu RLS sağlar, kiracı kimliği bağlamdan okunur. */
@Repository
@Transactional
class SourceRepository {

    private static final String COLUMNS =
        "id, collection_id, name, type, status, document_count, last_indexed_at, last_error, created_at";

    private static final RowMapper<Source> SOURCE = (rs, rowNum) -> new Source(
        rs.getObject("id", UUID.class), rs.getObject("collection_id", UUID.class), rs.getString("name"),
        rs.getString("type"), rs.getString("status"), rs.getInt("document_count"),
        rs.getObject("last_indexed_at", OffsetDateTime.class), rs.getString("last_error"),
        rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcClient jdbc;

    SourceRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    Source insert(UUID id, UUID collectionId, String name, String type, String configJson) {
        return jdbc.sql("""
                INSERT INTO sources (id, tenant_id, collection_id, name, type, config)
                VALUES (:id, current_tenant_id(), :collectionId, :name, :type, :config::jsonb)
                RETURNING %s""".formatted(COLUMNS))
            .param("id", id)
            .param("collectionId", collectionId)
            .param("name", name)
            .param("type", type)
            .param("config", configJson)
            .query(SOURCE)
            .single();
    }

    @Transactional(readOnly = true)
    Optional<Source> findById(UUID id) {
        return jdbc.sql("SELECT %s FROM sources WHERE id = :id".formatted(COLUMNS))
            .param("id", id)
            .query(SOURCE)
            .optional();
    }

    /** Anahtar kümesi sayfalaması, en yeniden eskiye; {@code after} önceki sayfanın son satırıdır. */
    @Transactional(readOnly = true)
    List<Source> findPage(SourceCursor after, int limit) {
        var query = after == null
            ? jdbc.sql("SELECT %s FROM sources ORDER BY created_at DESC, id DESC LIMIT :limit".formatted(COLUMNS))
            : jdbc.sql("""
                    SELECT %s FROM sources
                    WHERE (created_at, id) < (:createdAt, :id)
                    ORDER BY created_at DESC, id DESC LIMIT :limit""".formatted(COLUMNS))
                .param("createdAt", after.createdAt())
                .param("id", after.id());
        return query.param("limit", limit).query(SOURCE).list();
    }

    Source markPending(UUID id) {
        return jdbc.sql("""
                UPDATE sources SET status = 'pending', last_error = NULL WHERE id = :id
                RETURNING %s""".formatted(COLUMNS))
            .param("id", id)
            .query(SOURCE)
            .single();
    }

    @Transactional(readOnly = true)
    String findConfig(UUID id) {
        return jdbc.sql("SELECT config::text FROM sources WHERE id = :id").param("id", id).query(String.class).single();
    }

    /** @return durum değiştiyse true; kaynak zaten silinmekteyse false */
    boolean markDeleting(UUID id) {
        return jdbc.sql("UPDATE sources SET status = 'deleting' WHERE id = :id AND status <> 'deleting'")
            .param("id", id)
            .update() == 1;
    }
}
