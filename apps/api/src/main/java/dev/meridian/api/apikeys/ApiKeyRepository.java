package dev.meridian.api.apikeys;

import java.sql.Array;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/** Kiracı filtresi yok: izolasyonu RLS sağlar. Gizli değerin özeti bu sınıfın dışına çıkmaz. */
@Repository
@Transactional
class ApiKeyRepository {

    record StoredKey(UUID id, UUID createdBy, String name, String prefix, List<String> scopes,
            OffsetDateTime createdAt, OffsetDateTime expiresAt, OffsetDateTime lastUsedAt,
            OffsetDateTime revokedAt) {
    }

    private static final String COLUMNS =
        "id, created_by, name, prefix, scopes, created_at, expires_at, last_used_at, revoked_at";

    private final JdbcClient jdbc;

    ApiKeyRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    StoredKey insert(UUID id, UUID createdBy, String name, String prefix, String hash, List<String> scopes,
            OffsetDateTime expiresAt) {
        return jdbc.sql("""
                INSERT INTO api_keys (id, tenant_id, created_by, name, prefix, key_hash, scopes, expires_at)
                VALUES (:id, current_tenant_id(), :createdBy, :name, :prefix, :hash,
                        string_to_array(:scopes, ','), :expiresAt)
                RETURNING %s""".formatted(COLUMNS))
            .param("id", id)
            .param("createdBy", createdBy)
            .param("name", name)
            .param("prefix", prefix)
            .param("hash", hash)
            .param("scopes", String.join(",", scopes))
            .param("expiresAt", expiresAt)
            .query(ApiKeyRepository::row)
            .single();
    }

    @Transactional(readOnly = true)
    List<StoredKey> findAll() {
        return jdbc.sql("SELECT %s FROM api_keys ORDER BY created_at DESC, id DESC".formatted(COLUMNS))
            .query(ApiKeyRepository::row)
            .list();
    }

    /** Geçerli anahtarı bulur ve son kullanımı işler (yazma yükü için en çok dakikada bir). */
    Optional<StoredKey> useActive(String hash) {
        var key = jdbc.sql("""
                SELECT %s FROM api_keys
                WHERE key_hash = :hash AND revoked_at IS NULL AND expires_at > now()""".formatted(COLUMNS))
            .param("hash", hash)
            .query(ApiKeyRepository::row)
            .optional();
        key.ifPresent(found -> jdbc.sql("""
                UPDATE api_keys SET last_used_at = now()
                WHERE id = :id AND (last_used_at IS NULL OR last_used_at < now() - interval '1 minute')""")
            .param("id", found.id())
            .update());
        return key;
    }

    boolean exists(UUID id) {
        return jdbc.sql("SELECT 1 FROM api_keys WHERE id = :id").param("id", id).query(Integer.class).optional()
            .isPresent();
    }

    void revoke(UUID id) {
        jdbc.sql("UPDATE api_keys SET revoked_at = now() WHERE id = :id AND revoked_at IS NULL")
            .param("id", id)
            .update();
    }

    private static StoredKey row(ResultSet rs, int rowNum) throws SQLException {
        Array scopes = rs.getArray("scopes");
        return new StoredKey(rs.getObject("id", UUID.class), rs.getObject("created_by", UUID.class),
            rs.getString("name"), rs.getString("prefix"), List.of((String[]) scopes.getArray()),
            rs.getObject("created_at", OffsetDateTime.class), rs.getObject("expires_at", OffsetDateTime.class),
            rs.getObject("last_used_at", OffsetDateTime.class), rs.getObject("revoked_at", OffsetDateTime.class));
    }
}
