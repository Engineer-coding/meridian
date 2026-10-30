package dev.meridian.api.identity;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.JwtRequestPostProcessor;
import org.springframework.test.web.servlet.MockMvc;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.tenancy.Tenant;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;

/** Kimlik doğrulama, kiracı bağlamı ve uç nokta seviyesinde kiracı izolasyonu. */
@AutoConfigureMockMvc
class ApiSecurityTest extends PostgresIntegrationTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    TenantRepository tenants;

    UUID alice;
    UUID bob;
    Tenant acme;
    Tenant beta;

    @BeforeEach
    void createTwoTenants() {
        alice = UUID.randomUUID();
        bob = UUID.randomUUID();
        acme = TenantContext.callAs(new Identity(alice, UUID.randomUUID()),
            () -> tenants.createWithOwner("alice@acme.test", slug("acme"), "Acme"));
        beta = TenantContext.callAs(new Identity(bob, UUID.randomUUID()),
            () -> tenants.createWithOwner("bob@beta.test", slug("beta"), "Beta"));
    }

    @Test
    void healthIsPublic() throws Exception {
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    @Test
    void apiRequiresToken() throws Exception {
        mvc.perform(get("/v1/me")).andExpect(status().isUnauthorized());
    }

    @Test
    void meReturnsOnlyOwnMemberships() throws Exception {
        mvc.perform(get("/v1/me").with(token(alice, "alice@acme.test")))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value(alice.toString()))
            .andExpect(jsonPath("$.memberships.length()").value(1))
            .andExpect(jsonPath("$.memberships[0].tenantName").value("Acme"))
            .andExpect(jsonPath("$.memberships[0].role").value("owner"));
    }

    @Test
    void memberCanReadOwnTenant() throws Exception {
        mvc.perform(get("/v1/tenants/{id}", acme.id()).with(token(alice, "alice@acme.test")))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.slug").value(acme.slug()));
    }

    @Test
    void otherTenantLooksExactlyLikeMissingTenant() throws Exception {
        var otherTenant = mvc.perform(get("/v1/tenants/{id}", beta.id()).with(token(alice, "alice@acme.test")))
            .andExpect(status().isNotFound())
            .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_PROBLEM_JSON))
            .andExpect(jsonPath("$.title").value("Not Found"))
            .andReturn().getResponse();
        var missingTenant = mvc.perform(get("/v1/tenants/{id}", UUID.randomUUID()).with(token(alice, "alice@acme.test")))
            .andExpect(status().isNotFound())
            .andReturn().getResponse();

        // Gövdelerdeki tek fark 'instance' (istek adresi) olmalı.
        assertThat(withoutInstance(otherTenant.getContentAsString()))
            .isEqualTo(withoutInstance(missingTenant.getContentAsString()));
    }

    @Test
    void nonUuidSubjectIsRejected() throws Exception {
        mvc.perform(get("/v1/me").with(jwt().jwt(j -> j.subject("not-a-uuid").claim("email", "x@x.test"))))
            .andExpect(status().isUnauthorized());
    }

    private static JwtRequestPostProcessor token(UUID userId, String email) {
        return jwt().jwt(j -> j.subject(userId.toString()).claim("email", email).claim("name", "Test User"));
    }

    private static String withoutInstance(String problemJson) {
        return problemJson.replaceAll("\"instance\":\"[^\"]*\",?", "");
    }

    private static String slug(String prefix) {
        return prefix + "-" + UUID.randomUUID().toString().substring(0, 8);
    }
}