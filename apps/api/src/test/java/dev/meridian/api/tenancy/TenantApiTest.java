package dev.meridian.api.tenancy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.startsWith;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
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
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import com.jayway.jsonpath.JsonPath;

import dev.meridian.api.PostgresIntegrationTest;

/** POST /v1/tenants: sözleşme, idempotency ve hata durumları. */
@AutoConfigureMockMvc
class TenantApiTest extends PostgresIntegrationTest {

    @Autowired
    MockMvc mvc;

    UUID user;
    String slug;

    @BeforeEach
    void newUser() {
        user = UUID.randomUUID();
        slug = "acme-" + UUID.randomUUID().toString().substring(0, 8);
    }

    @Test
    void createsTenantAndMakesCallerOwner() throws Exception {
        String body = mvc.perform(create("key-" + UUID.randomUUID(), slug, "Acme"))
            .andExpect(status().isCreated())
            .andExpect(header().string("Location", startsWith("/v1/tenants/")))
            .andExpect(jsonPath("$.slug").value(slug))
            .andExpect(jsonPath("$.plan").value("free"))
            .andReturn().getResponse().getContentAsString();
        String tenantId = JsonPath.read(body, "$.id");

        mvc.perform(get("/v1/me").with(token()))
            .andExpect(jsonPath("$.memberships.length()").value(1))
            .andExpect(jsonPath("$.memberships[0].tenantId").value(tenantId))
            .andExpect(jsonPath("$.memberships[0].role").value("owner"));
        mvc.perform(get("/v1/tenants/{id}", tenantId).with(token())).andExpect(status().isOk());
    }

    @Test
    void retryWithSameKeyReturnsSameTenantWithoutCreatingAnother() throws Exception {
        String key = "key-" + UUID.randomUUID();
        String first = mvc.perform(create(key, slug, "Acme")).andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        String second = mvc.perform(create(key, slug, "Acme")).andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();

        assertThat((String) JsonPath.read(second, "$.id")).isEqualTo(JsonPath.read(first, "$.id"));
        mvc.perform(get("/v1/me").with(token())).andExpect(jsonPath("$.memberships.length()").value(1));
    }

    @Test
    void sameKeyWithDifferentBodyIsRejected() throws Exception {
        String key = "key-" + UUID.randomUUID();
        mvc.perform(create(key, slug, "Acme")).andExpect(status().isCreated());
        mvc.perform(create(key, slug, "Başka bir isim"))
            .andExpect(status().isUnprocessableContent());
    }

    @Test
    void takenSlugIsConflict() throws Exception {
        mvc.perform(create("key-" + UUID.randomUUID(), slug, "Acme")).andExpect(status().isCreated());
        user = UUID.randomUUID();
        mvc.perform(create("key-" + UUID.randomUUID(), slug, "Acme"))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.status").value(409));
    }

    @Test
    void failedRequestDoesNotBurnTheKey() throws Exception {
        String taken = slug;
        mvc.perform(create("key-" + UUID.randomUUID(), taken, "Acme")).andExpect(status().isCreated());
        user = UUID.randomUUID();
        String key = "key-" + UUID.randomUUID();
        mvc.perform(create(key, taken, "Acme")).andExpect(status().isConflict());
        // Başarısız istek anahtar kaydıyla birlikte geri alındı: yeniden deneme 422 değil,
        // asıl hatayı (409) görür. Hatalar önbelleğe alınmaz.
        mvc.perform(create(key, taken, "Acme")).andExpect(status().isConflict());
    }

    @Test
    void missingIdempotencyKeyIsBadRequest() throws Exception {
        mvc.perform(post("/v1/tenants").with(token())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Acme\",\"slug\":\"" + slug + "\"}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void invalidSlugIsBadRequest() throws Exception {
        mvc.perform(create("key-" + UUID.randomUUID(), "Bad Slug!", "Acme"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void unknownFieldIsBadRequest() throws Exception {
        mvc.perform(post("/v1/tenants").with(token())
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Acme\",\"slug\":\"" + slug + "\",\"plan\":\"enterprise\"}"))
            .andExpect(status().isBadRequest());
    }

    private MockHttpServletRequestBuilder create(String key, String slug, String name) {
        return post("/v1/tenants").with(token())
            .header("Idempotency-Key", key)
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"name\":\"" + name + "\",\"slug\":\"" + slug + "\"}");
    }

    private JwtRequestPostProcessor token() {
        return jwt().jwt(j -> j.subject(user.toString()).claim("email", "owner@acme.test").claim("name", "Owner"));
    }
}
