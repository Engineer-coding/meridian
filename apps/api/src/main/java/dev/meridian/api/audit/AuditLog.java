package dev.meridian.api.audit;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import dev.meridian.api.tenancy.TenantContext;

/**
 * Denetim kaydı. {@link #allowed} çağıranın işlemine katılır: iş geri alınırsa kayıt da kalmaz.
 * Kiracı filtresi yok: izolasyonu RLS sağlar; güncelleme ve silme yetkisi veritabanında kapalıdır.
 */
@Repository
@Transactional
public class AuditLog {

    record Entry(UUID id, String action, String outcome, UUID actorUserId, String actorEmail, UUID apiKeyId,
            String targetId, OffsetDateTime createdAt) {
    }

    private final JdbcClient jdbc;

    AuditLog(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public void allowed(String action, Object target) {
        insert(action, "allowed", target == null ? null : target.toString());
    }

    void denied(String action) {
        insert(action, "denied", null);
    }

    private void insert(String action, String outcome, String target) {
        var identity = TenantContext.current().orElseThrow();
        jdbc.sql("""
                INSERT INTO audit_log (id, tenant_id, actor_user_id, api_key_id, action, outcome, target_id)
                VALUES (:id, current_tenant_id(), :user, :apiKey, :action, :outcome, :target)""")
            .param("id", UUID.randomUUID())
            .param("user", identity.userId())
            .param("apiKey", identity.apiKeyId())
            .param("action", action)
            .param("outcome", outcome)
            .param("target", target)
            .update();
    }

    /** Anahtar kümesi sayfalaması, en yeniden eskiye. E-posta yalnızca güncel üyeler için görünür (RLS). */
    @Transactional(readOnly = true)
    List<Entry> findPage(AuditCursor after, int limit) {
        String where = after == null ? "" : "WHERE (a.created_at, a.id) < (:createdAt, :id)";
        var query = jdbc.sql("""
                SELECT a.id, a.action, a.outcome, a.actor_user_id, u.email, a.api_key_id, a.target_id, a.created_at
                FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id
                %s
                ORDER BY a.created_at DESC, a.id DESC LIMIT :limit""".formatted(where));
        if (after != null) {
            query = query.param("createdAt", after.createdAt()).param("id", after.id());
        }
        return query.param("limit", limit)
            .query((rs, rowNum) -> new Entry(rs.getObject("id", UUID.class), rs.getString("action"),
                rs.getString("outcome"), rs.getObject("actor_user_id", UUID.class), rs.getString("email"),
                rs.getObject("api_key_id", UUID.class), rs.getString("target_id"),
                rs.getObject("created_at", OffsetDateTime.class)))
            .list();
    }
}
