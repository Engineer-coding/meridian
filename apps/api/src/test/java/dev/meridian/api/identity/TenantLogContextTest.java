package dev.meridian.api.identity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.servlet.HandlerExceptionResolver;

import dev.meridian.api.tenancy.MembershipRepository;

/** Kiracı kimliği istek boyunca her log satırında durur ve istekten sonra sızmaz (ADR-0017). */
class TenantLogContextTest {

    @AfterEach
    void clear() {
        SecurityContextHolder.clearContext();
        MDC.clear();
    }

    @Test
    void tenantIsInTheLogContextOnlyWhileTheRequestRuns() throws Exception {
        UUID tenant = UUID.randomUUID();
        var memberships = mock(MembershipRepository.class);
        when(memberships.findRole(any())).thenReturn(Optional.of("owner"));
        var jwt = Jwt.withTokenValue("t").header("alg", "none").subject(UUID.randomUUID().toString())
            .issuedAt(Instant.now()).expiresAt(Instant.now().plusSeconds(60)).build();
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt));

        var seen = new AtomicReference<String>();
        var request = new MockHttpServletRequest("GET", "/v1/tenants/" + tenant + "/sources");
        new TenantContextFilter(memberships, mock(HandlerExceptionResolver.class))
            .doFilter(request, new MockHttpServletResponse(), (req, res) -> seen.set(MDC.get("tenant.id")));

        assertThat(seen.get()).isEqualTo(tenant.toString());
        assertThat(MDC.get("tenant.id")).isNull();
    }
}
