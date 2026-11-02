package dev.meridian.api.outbox;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.AmqpException;
import org.springframework.amqp.core.AmqpAdmin;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.connection.CachingConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.transaction.support.TransactionTemplate;

import com.zaxxer.hikari.HikariDataSource;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.tenancy.Tenant;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** Outbox → RabbitMQ: atomiklik, yayın onayı, hata durumunda kayıpsızlık ve rol sınırları. */
class OutboxRelayTest extends PostgresIntegrationTest {

    @Autowired
    OutboxWriter writer;

    @Autowired
    OutboxRelay relay;

    @Autowired
    TenantRepository tenants;

    @Autowired
    TransactionTemplate tx;

    @Autowired
    RabbitTemplate rabbit;

    @Autowired
    AmqpAdmin admin;

    @Autowired
    JsonMapper json;

    Identity alice;
    Tenant acme;

    @BeforeEach
    void emptyOutboxAndQueue() {
        alice = new Identity(UUID.randomUUID(), UUID.randomUUID());
        acme = TenantContext.callAs(alice,
            () -> tenants.createWithOwner("alice@acme.test", "acme-" + UUID.randomUUID().toString().substring(0, 8), "Acme"));
        relay.drain();
        admin.purgeQueue(Messaging.INDEXING_QUEUE, false);
    }

    @Test
    void publishedEventCarriesIdentityAndLeavesTheOutbox() throws Exception {
        UUID sourceId = UUID.randomUUID();
        UUID eventId = append("source.created", sourceId, Map.of("sourceId", sourceId));

        assertThat(relay.drain()).isEqualTo(1);

        Message message = rabbit.receive(Messaging.INDEXING_QUEUE, 5_000);
        assertThat(message).isNotNull();
        assertThat(message.getMessageProperties().getMessageId()).isEqualTo(eventId.toString());
        assertThat(message.getMessageProperties().getType()).isEqualTo("source.created");
        assertThat((String) message.getMessageProperties().getHeader(Messaging.TENANT_HEADER)).isEqualTo(acme.id().toString());

        JsonNode envelope = json.readTree(message.getBody());
        assertThat(envelope.get("eventId").asString()).isEqualTo(eventId.toString());
        assertThat(envelope.get("tenantId").asString()).isEqualTo(acme.id().toString());
        assertThat(envelope.get("data").get("sourceId").asString()).isEqualTo(sourceId.toString());

        assertThat(queryAsSuperuser("SELECT count(*) FROM core.outbox WHERE event_id = '" + eventId + "'")).containsExactly("0");
    }

    @Test
    void eventsArePublishedInOrderAcrossBatches() {
        int count = OutboxRelay.BATCH_SIZE + 5;
        List<UUID> expected = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            expected.add(append("source.created", UUID.randomUUID(), Map.of("n", i)));
        }

        assertThat(relay.drain()).isEqualTo(count);

        List<String> received = new ArrayList<>();
        Message message;
        while ((message = rabbit.receive(Messaging.INDEXING_QUEUE, 2_000)) != null) {
            received.add(message.getMessageProperties().getMessageId());
        }
        assertThat(received).containsExactlyElementsOf(expected.stream().map(UUID::toString).toList());
    }

    @Test
    void rolledBackBusinessTransactionLeavesNoEvent() throws Exception {
        UUID aggregate = UUID.randomUUID();
        assertThatThrownBy(() -> TenantContext.runAs(alice, () -> tx.executeWithoutResult(status -> {
            writer.append("source.created", aggregate, Map.of());
            throw new IllegalStateException("iş kaydı başarısız");
        }))).isInstanceOf(IllegalStateException.class);

        assertThat(queryAsSuperuser("SELECT count(*) FROM core.outbox WHERE aggregate_id = '" + aggregate + "'")).containsExactly("0");
    }

    @Test
    void unreachableBrokerKeepsEventsForTheNextAttempt() throws Exception {
        UUID eventId = append("source.created", UUID.randomUUID(), Map.of());

        var deadBroker = new CachingConnectionFactory("127.0.0.1", 1);
        deadBroker.setPublisherConfirmType(CachingConnectionFactory.ConfirmType.SIMPLE);
        try (HikariDataSource relayDataSource = DataSourceBuilder.create().type(HikariDataSource.class)
                 .url(POSTGRES.getJdbcUrl()).username("meridian_relay").password(RELAY_PASSWORD).build();
             var brokenRelay = new OutboxRelay(relayDataSource, new RabbitTemplate(deadBroker), json)) {
            assertThatThrownBy(brokenRelay::relayBatch).isInstanceOf(AmqpException.class);
        } finally {
            deadBroker.destroy();
        }

        assertThat(queryAsSuperuser("SELECT count(*) FROM core.outbox WHERE event_id = '" + eventId + "'")).containsExactly("1");
        assertThat(relay.drain()).isEqualTo(1);
    }

    @Test
    void appRoleCanAppendButNotReadOrDeleteEvents() {
        assertThatThrownBy(() -> queryAs("meridian_app", APP_PASSWORD, "SELECT count(*) FROM core.outbox"))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).as("insufficient_privilege").isEqualTo("42501"));
        assertThatThrownBy(() -> executeAs("meridian_app", APP_PASSWORD, "DELETE FROM core.outbox"))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).isEqualTo("42501"));
    }

    @Test
    void appCannotWriteAnEventForAnotherTenant() {
        UUID otherTenant = UUID.randomUUID();
        assertThatThrownBy(() -> executeAs("meridian_app", APP_PASSWORD,
                "SELECT set_config('app.tenant_id', '" + acme.id() + "', false)",
                "INSERT INTO core.outbox (event_id, tenant_id, event_type, aggregate_id, payload) VALUES ('"
                    + UUID.randomUUID() + "', '" + otherTenant + "', 'source.created', '" + UUID.randomUUID() + "', '{}')"))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).as("RLS ihlali").isEqualTo("42501"));
    }

    @Test
    void relayRoleSeesOnlyTheOutbox() {
        for (String table : List.of("sources", "collections", "tenants", "users", "memberships", "idempotency_keys",
                "documents", "chunks", "processed_events")) {
            assertThatThrownBy(() -> queryAs("meridian_relay", RELAY_PASSWORD, "SELECT count(*) FROM core." + table))
                .as(table)
                .isInstanceOf(SQLException.class)
                .satisfies(e -> assertThat(((SQLException) e).getSQLState()).isEqualTo("42501"));
        }
        assertThatThrownBy(() -> executeAs("meridian_relay", RELAY_PASSWORD,
                "INSERT INTO core.outbox (event_id, tenant_id, event_type, aggregate_id, payload) VALUES ('"
                    + UUID.randomUUID() + "', '" + acme.id() + "', 'source.created', '" + UUID.randomUUID() + "', '{}')"))
            .as("aktarıcı olay uyduramaz")
            .isInstanceOf(SQLException.class);
    }

    private UUID append(String type, UUID aggregate, Map<String, ?> data) {
        return TenantContext.callAs(alice, () -> tx.execute(status -> writer.append(type, aggregate, data)));
    }
}
