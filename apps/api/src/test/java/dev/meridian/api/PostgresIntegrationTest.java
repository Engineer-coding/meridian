package dev.meridian.api;

import java.sql.DriverManager;
import java.util.ArrayList;
import java.util.List;

import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

/**
 * Tüm entegrasyon testleri için tek PostgreSQL container'ı (singleton container deseni):
 * Compose ile aynı başlangıç scriptlerini kullanır ve test sınıfları arasında paylaşılır.
 * Bağlantı havuzu bilerek 1 bağlantıyla sınırlıdır: ardışık işlemler aynı fiziksel
 * bağlantıyı kullanır, böylece bağlamın bağlantı üzerinden sızması testlerde yakalanır.
 */
@SpringBootTest
public abstract class PostgresIntegrationTest {

    private static final String INIT = "../../infra/compose/postgres/init/";

    protected static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(
            DockerImageName.parse("pgvector/pgvector:pg17").asCompatibleSubstituteFor("postgres"))
        .withEnv("DB_OWNER_PASSWORD", "owner_test")
        .withEnv("DB_APP_PASSWORD", "app_test")
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "01-extensions.sql"),
            "/docker-entrypoint-initdb.d/01-extensions.sql")
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "02-roles.sh", 0755),
            "/docker-entrypoint-initdb.d/02-roles.sh");

    static {
        POSTGRES.start();
    }

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", () -> "meridian_app");
        registry.add("spring.datasource.password", () -> "app_test");
        registry.add("spring.datasource.hikari.maximum-pool-size", () -> 1);
        registry.add("spring.flyway.user", () -> "meridian_owner");
        registry.add("spring.flyway.password", () -> "owner_test");
    }

    /** Katalog sorguları için: RLS dışındaki sistem bilgisini süper kullanıcıyla okur. */
    protected static List<String> queryAsSuperuser(String sql) throws Exception {
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