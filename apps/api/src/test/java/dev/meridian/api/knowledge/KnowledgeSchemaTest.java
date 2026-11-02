package dev.meridian.api.knowledge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.tenancy.Tenant;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;

/**
 * Uygulama katmanını atlayan saldırgan modeli: uygulama rolüyle doğrudan SQL. Yabancı anahtar
 * denetimi RLS'e tabi değildir; bileşik FK olmasaydı başka kiracının koleksiyon kimliğini bilen
 * biri ona kaynak bağlayabilirdi.
 */
class KnowledgeSchemaTest extends PostgresIntegrationTest {

    @Autowired
    TenantRepository tenants;

    Tenant acme;
    UUID betaCollection;

    @BeforeEach
    void twoTenants() throws Exception {
        acme = TenantContext.callAs(new Identity(UUID.randomUUID(), UUID.randomUUID()),
            () -> tenants.createWithOwner("alice@acme.test", "acme-" + UUID.randomUUID().toString().substring(0, 8), "Acme"));
        Tenant beta = TenantContext.callAs(new Identity(UUID.randomUUID(), UUID.randomUUID()),
            () -> tenants.createWithOwner("bob@beta.test", "beta-" + UUID.randomUUID().toString().substring(0, 8), "Beta"));
        betaCollection = UUID.randomUUID();
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "INSERT INTO core.collections (id, tenant_id, name) VALUES ('" + betaCollection + "', '" + beta.id() + "', 'Gizli')");
    }

    @Test
    void anotherTenantsCollectionIsInvisible() throws Exception {
        assertThat(queryAs("meridian_app", APP_PASSWORD, """
                SELECT count(*) FROM (SELECT set_config('app.tenant_id', '%s', false)) ctx, core.collections
                WHERE id = '%s'""".formatted(acme.id(), betaCollection)))
            .containsExactly("0");
    }

    @Test
    void sourceCannotReferenceAnotherTenantsCollectionEvenWithItsId() {
        assertThatThrownBy(() -> executeAs("meridian_app", APP_PASSWORD,
                "SELECT set_config('app.tenant_id', '" + acme.id() + "', false)",
                "INSERT INTO core.sources (id, tenant_id, collection_id, name, type, config) VALUES ('"
                    + UUID.randomUUID() + "', '" + acme.id() + "', '" + betaCollection + "', 'x', 'upload', '{}')"))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).as("foreign_key_violation").isEqualTo("23503"));
    }
}
