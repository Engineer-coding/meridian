package dev.meridian.api.identity;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.server.resource.web.authentication.BearerTokenAuthenticationFilter;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.servlet.HandlerExceptionResolver;

import dev.meridian.api.tenancy.MembershipRepository;

@Configuration(proxyBeanMethods = false)
class SecurityConfiguration {

    /**
     * Durumsuz API: oturum ve çerez yok, her istek Bearer token taşır. CSRF koruması
     * çerezle kimlik doğrulamaya karşıdır; çerez olmadığı için kapatılır.
     */
    @Bean
    SecurityFilterChain apiSecurity(HttpSecurity http, MembershipRepository memberships,
            @Qualifier("handlerExceptionResolver") HandlerExceptionResolver errors) throws Exception {
        // Filtre bilerek bean değil: bean olsaydı Spring Boot onu güvenlik zincirinin dışında
        // ikinci kez, kimlik doğrulamadan önce de çalıştırırdı.
        var tenantContextFilter = new TenantContextFilter(memberships, errors);
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth -> oauth.jwt(Customizer.withDefaults()))
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf.disable())
            .addFilterAfter(tenantContextFilter, BearerTokenAuthenticationFilter.class)
            .build();
    }
}