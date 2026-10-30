package dev.meridian.api.tenancy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.tenancy.TenantContext.Identity;

/** "A kiracısı B'nin verisini göremez ve değiştiremez" — uygulama kodu üzerinden, gerçek RLS ile. */
class TenantIsolationTest extends PostgresIntegrationTest {

    @Autowired
    TenantRepository tenants;

    Identity alice;
    Identity bob;
    Tenant acme;
    Tenant beta;

    @BeforeEach
    void createTwoTenants() {
        alice = new Identity(UUID.randomUUID(), UUID.randomUUID());
        bob = new Identity(UUID.randomUUID(), UUID.randomUUID());
        acme = TenantContext.callAs(alice, () -> tenants.createWithOwner("alice@acme.test", slug("acme"), "Acme"));
        beta = TenantContext.callAs(bob, () -> tenants.createWithOwner("bob@beta.test", slug("beta"), "Beta"));
    }

    @Test
    void tenantSeesOnlyItself() {
        assertThat(TenantContext.callAs(alice, tenants::findVisible)).containsExactly(acme);
    }

    @Test
    void cannotReadAnotherTenantById() {
        assertThat(TenantContext.callAs(alice, () -> tenants.findById(beta.id()))).isEmpty();
    }

    @Test
    void cannotUpdateAnotherTenant() {
        assertThat(TenantContext.callAs(alice, () -> tenants.rename(beta.id(), "hacked"))).isZero();
        assertThat(TenantContext.callAs(bob, () -> tenants.findById(beta.id())))
            .hasValueSatisfying(t -> assertThat(t.name()).isEqualTo("Beta"));
    }

    @Test
    void cannotInsertIntoAnotherTenant() {
        assertThatThrownBy(() -> TenantContext.runAs(alice,
                () -> tenants.addMembership(beta.id(), alice.userId(), "admin")))
            .isInstanceOf(DataAccessException.class);
    }

    @Test
    void noContextSeesNothing() {
        assertThat(tenants.findVisible()).isEmpty();
    }

    @Test
    void contextDoesNotLeakThroughPooledConnection() {
        assertThat(TenantContext.callAs(alice, tenants::findVisible)).isNotEmpty();
        // Havuzda tek bağlantı var: bu çağrı Alice'in az önce kullandığı bağlantıyı alır.
        assertThat(tenants.findVisible()).isEmpty();
    }

    @Test
    void userWithoutTenantSeesOnlyOwnMemberships() {
        var aliceWithoutTenant = new Identity(alice.userId(), null);
        assertThat(TenantContext.callAs(aliceWithoutTenant, tenants::findVisible)).containsExactly(acme);
    }

    private static String slug(String prefix) {
        return prefix + "-" + UUID.randomUUID().toString().substring(0, 8);
    }
}