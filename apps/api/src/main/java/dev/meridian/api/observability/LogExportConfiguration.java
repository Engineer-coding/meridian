package dev.meridian.api.observability;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.instrumentation.logback.appender.v1_0.OpenTelemetryAppender;

/**
 * logback-spring.xml'deki ekleyici, uygulama bağlamı kurulana dek SDK'yı bilmez; burada bağlanır. Gönderim
 * kapalıyken SDK'nın log dışa aktarıcısı yoktur ve satırlar yalnızca konsola yazılır.
 */
@Configuration(proxyBeanMethods = false)
class LogExportConfiguration {

    @Bean
    InitializingBean openTelemetryLogAppender(OpenTelemetry openTelemetry) {
        return () -> OpenTelemetryAppender.install(openTelemetry);
    }
}
