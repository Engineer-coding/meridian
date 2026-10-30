package dev.meridian.api.tenancy;

import javax.sql.DataSource;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class TenancyConfiguration {

    /** Spring Boot'un varsayılan transaction manager'ının yerine geçer. */
    @Bean
    TenantAwareTransactionManager transactionManager(DataSource dataSource) {
        return new TenantAwareTransactionManager(dataSource);
    }
}