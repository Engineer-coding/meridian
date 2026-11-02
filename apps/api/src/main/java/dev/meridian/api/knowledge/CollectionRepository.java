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
class CollectionRepository {

    private static final RowMapper<Collection> COLLECTION = (rs, rowNum) -> new Collection(
        rs.getObject("id", UUID.class), rs.getString("name"), rs.getObject("created_at", OffsetDateTime.class));

    private final JdbcClient jdbc;

    CollectionRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    Collection insert(UUID id, String name) {
        return jdbc.sql("""
                INSERT INTO collections (id, tenant_id, name) VALUES (:id, current_tenant_id(), :name)
                RETURNING id, name, created_at""")
            .param("id", id)
            .param("name", name)
            .query(COLLECTION)
            .single();
    }

    @Transactional(readOnly = true)
    Optional<Collection> findById(UUID id) {
        return jdbc.sql("SELECT id, name, created_at FROM collections WHERE id = :id")
            .param("id", id)
            .query(COLLECTION)
            .optional();
    }

    @Transactional(readOnly = true)
    List<Collection> findAll() {
        return jdbc.sql("SELECT id, name, created_at FROM collections ORDER BY name").query(COLLECTION).list();
    }
}
