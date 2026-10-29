package dev.meridian.api;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.DriverManager;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.transaction.support.TransactionTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

/** ADR-0002 güvencelerini gerçek PostgreSQL üzerinde doğrular. */
@SpringBootTest
@Testcontainers
class RlsSchemaTest {

    private static final String INIT = "../../infra/compose/postgres/init/";

    @Container
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(
            DockerImageName.parse("pgvector/pgvector:pg17").asCompatibleSubstituteFor("postgres"))
        .withEnv("DB_OWNER_PASSWORD", "owner_test")
        .withEnv("DB_APP_PASSWORD", "app_test")
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "01-extensions.sql"),
            "/docker-entrypoint-initdb.d/01-extensions.sql")
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "02-roles.sh", 0755),
            "/docker-entrypoint-initdb.d/02-roles.sh");

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", () -> "meridian_app");
        registry.add("spring.datasource.password", () -> "app_test");
        registry.add("spring.flyway.user", () -> "meridian_owner");
        registry.add("spring.flyway.password", () -> "owner_test");
    }

    @Autowired
    JdbcTemplate jdbc;

    @Autowired
    TransactionTemplate tx;

    @Test
    void everyCoreTableHasForcedRowLevelSecurity() throws Exception {
        List<String> unprotected = queryAsSuperuser("""
            SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'core' AND c.relkind = 'r' AND c.relname <> 'flyway_schema_history'
              AND NOT (c.relrowsecurity AND c.relforcerowsecurity)""");
        assertThat(unprotected).as("RLS veya FORCE eksik tablolar").isEmpty();
    }

    @Test
    void appRoleCannotBypassRowLevelSecurity() throws Exception {
        assertThat(queryAsSuperuser(
            "SELECT (rolsuper OR rolbypassrls)::text FROM pg_roles WHERE rolname = 'meridian_app'"))
            .containsExactly("false");
    }

    @Test
    void appRoleSeesNoRowsWithoutTenantContext() {
        String tenantId = UUID.randomUUID().toString();
        tx.executeWithoutResult(status -> {
            jdbc.queryForObject("SELECT set_config('app.tenant_id', ?, true)", String.class, tenantId);
            jdbc.update("INSERT INTO tenants (id, slug, name) VALUES (?::uuid, ?, 'Test')",
                tenantId, "t-" + tenantId.substring(0, 8));
        });

        Integer visible = jdbc.queryForObject("SELECT count(*) FROM tenants", Integer.class);
        assertThat(visible).as("bağlam yokken görünen kiracı sayısı").isZero();
    }

    private static List<String> queryAsSuperuser(String sql) throws Exception {
        try (var conn = DriverManager.getConnection(
                 POSTGRES.getJdbcUrl(), POSTGRES.getUsername(), POSTGRES.getPassword());
             var rs = conn.createStatement().executeQuery(sql)) {
            var rows = new ArrayList<String>();
            while (rs.next()) {
                rows.add(rs.getString(1));
            }
            return rows;
        }
    }
}