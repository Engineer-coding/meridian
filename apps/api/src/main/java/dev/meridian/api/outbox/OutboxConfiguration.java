package dev.meridian.api.outbox;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Declarables;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBooleanProperty;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.jdbc.DataSourceBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;

import com.zaxxer.hikari.HikariDataSource;

import tools.jackson.databind.json.JsonMapper;

@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(OutboxConfiguration.RelayProperties.class)
class OutboxConfiguration {

    /** Aktarıcının kendi veritabanı bağlantısı ({@code meridian_relay} rolü). */
    @ConfigurationProperties("meridian.outbox.relay")
    record RelayProperties(String url, String username, String password) {
    }

    /**
     * Aktarıcının bağlantı havuzu bilerek bean değil: bean olsaydı uygulamanın ana
     * DataSource'u ile yarışır, başka bir sınıf da onu enjekte edip RLS'siz rolle sorgu
     * çalıştırabilirdi.
     */
    @Bean
    OutboxRelay outboxRelay(RelayProperties properties, RabbitTemplate rabbit, JsonMapper json) {
        HikariDataSource dataSource = DataSourceBuilder.create()
            .type(HikariDataSource.class)
            .url(properties.url())
            .username(properties.username())
            .password(properties.password())
            .build();
        dataSource.setPoolName("outbox-relay");
        dataSource.setMaximumPoolSize(2);
        return new OutboxRelay(dataSource, rabbit, json);
    }

    /**
     * Topoloji burada, yayımlayan tarafta tanımlanır: kuyruk ilk olaydan önce var olmalıdır,
     * yoksa tüketici henüz bağlanmamışken yayımlanan olaylar kaybolur. Kuyruklar quorum
     * tipindedir (çoğaltılmış, diske yazılır); teslim sınırını aşan mesaj DLQ'ya düşer.
     */
    @Bean
    Declarables messagingTopology() {
        TopicExchange events = new TopicExchange(Messaging.EVENTS, true, false);
        DirectExchange deadLetters = new DirectExchange(Messaging.DEAD_LETTERS, true, false);
        Queue indexing = QueueBuilder.durable(Messaging.INDEXING_QUEUE)
            .quorum()
            .deadLetterExchange(Messaging.DEAD_LETTERS)
            .deadLetterRoutingKey(Messaging.INDEXING_QUEUE)
            .deliveryLimit(5)
            .build();
        Queue indexingDlq = QueueBuilder.durable(Messaging.INDEXING_DLQ).quorum().build();
        Binding sourceEvents = BindingBuilder.bind(indexing).to(events).with("source.*");
        Binding deadLettered = BindingBuilder.bind(indexingDlq).to(deadLetters).with(Messaging.INDEXING_QUEUE);
        return new Declarables(events, deadLetters, indexing, indexingDlq, sourceEvents, deadLettered);
    }

    /** Testler aktarıcıyı elle çalıştırmak için kapatır ({@code meridian.outbox.relay.enabled=false}). */
    @Configuration(proxyBeanMethods = false)
    @EnableScheduling
    @ConditionalOnBooleanProperty(name = "meridian.outbox.relay.enabled", matchIfMissing = true)
    static class RelaySchedule {

        private static final Logger log = LoggerFactory.getLogger(RelaySchedule.class);

        private final OutboxRelay relay;

        RelaySchedule(OutboxRelay relay) {
            this.relay = relay;
        }

        /** Broker'a ulaşılamazsa olaylar outbox'ta bekler; bir sonraki tur yeniden dener. */
        @Scheduled(fixedDelayString = "${meridian.outbox.relay.poll-interval:500ms}")
        void relay() {
            try {
                int published = relay.drain();
                if (published > 0) {
                    log.debug("Outbox: {} olay yayımlandı", published);
                }
            } catch (RuntimeException e) {
                log.warn("Outbox aktarımı başarısız, sonraki turda yeniden denenecek: {}", e.toString());
            }
        }
    }
}
