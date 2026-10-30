package dev.meridian.api.tenancy;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/**
 * Bağlamdaki kullanıcının üyelikleri. Kiracı seçilmeden de çalışır: {@code self_read}
 * politikası kullanıcının kendi üyelik satırlarını görmesine izin verir.
 */
@Repository
@Transactional(readOnly = true)
public class MembershipRepository {

    private final JdbcClient jdbc;

    MembershipRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<String> findRole(UUID tenantId) {
        return jdbc.sql("SELECT role FROM memberships WHERE tenant_id = :tenantId AND user_id = current_user_id()")
            .param("tenantId", tenantId)
            .query(String.class)
            .optional();
    }

    public List<Membership> findForCurrentUser() {
        return jdbc.sql("""
                SELECT m.tenant_id, t.name AS tenant_name, m.role
                FROM memberships m JOIN tenants t ON t.id = m.tenant_id
                WHERE m.user_id = current_user_id()
                ORDER BY t.name""")
            .query((rs, rowNum) -> new Membership(
                rs.getObject("tenant_id", UUID.class), rs.getString("tenant_name"), rs.getString("role")))
            .list();
    }
}