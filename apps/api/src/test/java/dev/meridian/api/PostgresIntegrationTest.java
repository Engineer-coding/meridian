package dev.meridian.api;

import java.sql.DriverManager;
import java.util.ArrayList;
import java.util.List;

import org.springframework.boot.micrometer.tracing.test.autoconfigure.AutoConfigureTracing;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.postgresql.PostgreSQLContainer;
import org.testcontainers.rabbitmq.RabbitMQContainer;
import org.testcontainers.utility.DockerImageName;
import org.testcontainers.utility.MountableFile;

/**
 * Tüm entegrasyon testleri için tek PostgreSQL ve tek RabbitMQ container'ı (singleton
 * container deseni): Compose ile aynı başlangıç scriptlerini kullanır ve test sınıfları
 * arasında paylaşılır. Bağlantı havuzu bilerek 1 bağlantıyla sınırlıdır: ardışık işlemler
 * aynı fiziksel bağlantıyı kullanır, böylece bağlamın bağlantı üzerinden sızması testlerde
 * yakalanır. Outbox aktarıcısının zamanlayıcısı kapalıdır; testler onu elle çalıştırır.
 */
// Testler üretimdeki gibi iz bağlamı taşır; OTLP gönderimi yapılandırmada kapalıdır.
@AutoConfigureTracing
@SpringBootTest
public abstract class PostgresIntegrationTest {

    private static final String INIT = "../../infra/compose/postgres/init/";

    protected static final String APP_PASSWORD = "app_test";
    protected static final String RELAY_PASSWORD = "relay_test";
    protected static final String AI_PASSWORD = "ai_test";

    protected static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer(
            DockerImageName.parse("pgvector/pgvector:pg17").asCompatibleSubstituteFor("postgres"))
        .withEnv("DB_OWNER_PASSWORD", "owner_test")
        .withEnv("DB_APP_PASSWORD", APP_PASSWORD)
        .withEnv("DB_RELAY_PASSWORD", RELAY_PASSWORD)
        .withEnv("DB_AI_PASSWORD", AI_PASSWORD)
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "01-extensions.sql"),
            "/docker-entrypoint-initdb.d/01-extensions.sql")
        .withCopyFileToContainer(MountableFile.forHostPath(INIT + "02-roles.sh", 0755),
            "/docker-entrypoint-initdb.d/02-roles.sh");

    protected static final RabbitMQContainer RABBIT = new RabbitMQContainer(DockerImageName.parse("rabbitmq:4.1-management"));

    protected static final GenericContainer<?> REDIS = new GenericContainer<>(DockerImageName.parse("redis:7.4-alpine"))
        .withExposedPorts(6379);

    static {
        POSTGRES.start();
        RABBIT.start();
        REDIS.start();
    }

    @DynamicPropertySource
    static void datasource(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.datasource.username", () -> "meridian_app");
        registry.add("spring.datasource.password", () -> APP_PASSWORD);
        registry.add("spring.datasource.hikari.maximum-pool-size", () -> 1);
        registry.add("spring.flyway.user", () -> "meridian_owner");
        registry.add("spring.flyway.password", () -> "owner_test");
        registry.add("meridian.outbox.relay.password", () -> RELAY_PASSWORD);
        registry.add("meridian.outbox.relay.enabled", () -> false);
        registry.add("spring.data.redis.host", REDIS::getHost);
        registry.add("spring.data.redis.port", () -> REDIS.getMappedPort(6379));
        registry.add("meridian.ai.internal-token", () -> "test-internal-token");
        registry.add("spring.rabbitmq.host", RABBIT::getHost);
        registry.add("spring.rabbitmq.port", RABBIT::getAmqpPort);
        registry.add("spring.rabbitmq.username", RABBIT::getAdminUsername);
        registry.add("spring.rabbitmq.password", RABBIT::getAdminPassword);
    }

    /** Katalog sorguları için: RLS dışındaki sistem bilgisini süper kullanıcıyla okur. */
    protected static List<String> queryAsSuperuser(String sql) throws Exception {
        return queryAs(POSTGRES.getUsername(), POSTGRES.getPassword(), sql);
    }

    /** Sorguyu verilen rolle, uygulama katmanını ve kimlik bağlamını atlayarak çalıştırır. */
    protected static List<String> queryAs(String role, String password, String sql) throws Exception {
        try (var conn = DriverManager.getConnection(POSTGRES.getJdbcUrl(), role, password);
             var rs = conn.createStatement().executeQuery(sql)) {
            var rows = new ArrayList<String>();
            while (rs.next()) {
                rows.add(rs.getString(1));
            }
            return rows;
        }
    }

    /** İfadeleri verilen rolle tek bağlantıda sırayla çalıştırır (ör. önce set_config, sonra yazma). */
    protected static void executeAs(String role, String password, String... statements) throws Exception {
        try (var conn = DriverManager.getConnection(POSTGRES.getJdbcUrl(), role, password);
             var statement = conn.createStatement()) {
            for (String sql : statements) {
                statement.execute(sql);
            }
        }
    }
}
