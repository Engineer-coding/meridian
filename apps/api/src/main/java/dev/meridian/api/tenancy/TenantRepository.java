package dev.meridian.api.tenancy;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/**
 * Sorgular kiracı filtresi içermez: izolasyonu RLS sağlar. Kimlikler de parametre olarak
 * değil, veritabanındaki bağlamdan ({@code current_tenant_id()}, {@code current_user_id()})
 * okunur; böylece çağıran kod başka bir kiracının kimliğini araya sokamaz.
 */
@Repository
@Transactional
public class TenantRepository {

    private static final RowMapper<Tenant> TENANT = (rs, rowNum) -> new Tenant(
        rs.getObject("id", UUID.class), rs.getString("slug"), rs.getString("name"), rs.getString("plan"));

    private final JdbcClient jdbc;

    TenantRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** Bağlamdaki kullanıcıyı kaydeder ve bağlamdaki kiracıyı onun sahipliğinde oluşturur. */
    public Tenant createWithOwner(String ownerEmail, String slug, String name) {
        jdbc.sql("""
                INSERT INTO users (id, email) VALUES (current_user_id(), :email)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email""")
            .param("email", ownerEmail)
            .update();
        Tenant tenant = jdbc.sql("""
                INSERT INTO tenants (id, slug, name) VALUES (current_tenant_id(), :slug, :name)
                RETURNING id, slug, name, plan""")
            .param("slug", slug)
            .param("name", name)
            .query(TENANT)
            .single();
        jdbc.sql("INSERT INTO memberships (tenant_id, user_id, role) VALUES (current_tenant_id(), current_user_id(), 'owner')")
            .update();
        return tenant;
    }

    public void addMembership(UUID tenantId, UUID userId, String role) {
        jdbc.sql("INSERT INTO memberships (tenant_id, user_id, role) VALUES (:tenantId, :userId, :role)")
            .param("tenantId", tenantId)
            .param("userId", userId)
            .param("role", role)
            .update();
    }

    @Transactional(readOnly = true)
    public List<Tenant> findVisible() {
        return jdbc.sql("SELECT id, slug, name, plan FROM tenants ORDER BY slug").query(TENANT).list();
    }

    @Transactional(readOnly = true)
    public Optional<Tenant> findById(UUID id) {
        return jdbc.sql("SELECT id, slug, name, plan FROM tenants WHERE id = :id")
            .param("id", id)
            .query(TENANT)
            .optional();
    }

    public int rename(UUID id, String name) {
        return jdbc.sql("UPDATE tenants SET name = :name WHERE id = :id")
            .param("id", id)
            .param("name", name)
            .update();
    }
}