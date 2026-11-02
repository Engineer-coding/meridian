package dev.meridian.api.knowledge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.ArrayList;
import java.util.List;
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
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;

/** Koleksiyon ve kaynak uçları: outbox atomikliği, idempotency, roller ve sayfalama. */
@AutoConfigureMockMvc
class SourceApiTest extends PostgresIntegrationTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    TenantRepository tenants;

    UUID owner;
    String tenantId;
    String collectionId;

    @BeforeEach
    void tenantWithCollection() throws Exception {
        owner = UUID.randomUUID();
        tenantId = createTenant(owner);
        collectionId = createCollection(owner, tenantId, "Mühendislik");
    }

    @Test
    void createdSourceAndItsEventAreWrittenTogether() throws Exception {
        String body = mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), web("https://kubernetes.io/docs/")))
            .andExpect(status().isAccepted())
            .andExpect(jsonPath("$.status").value("pending"))
            .andExpect(jsonPath("$.type").value("web"))
            .andExpect(jsonPath("$.collectionId").value(collectionId))
            .andReturn().getResponse().getContentAsString();
        String sourceId = JsonPath.read(body, "$.id");

        // Varsayılanlar (maxPages) olaya doldurulmuş hâliyle yazılır: tüketici sözleşmeyi bilmek zorunda kalmaz.
        assertThat(queryAsSuperuser("""
                SELECT concat_ws('|', event_type, tenant_id, payload->>'sourceId', payload->>'collectionId',
                                 payload->'config'->>'startUrl', payload->'config'->>'maxPages')
                FROM core.outbox WHERE aggregate_id = '%s'""".formatted(sourceId)))
            .containsExactly(String.join("|", "source.created", tenantId, sourceId, collectionId,
                "https://kubernetes.io/docs/", "100"));
        mvc.perform(get("/v1/tenants/{t}/sources/{s}", tenantId, sourceId).with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name").value("Kubernetes docs"));
    }

    @Test
    void locationPointsToTheNewSource() throws Exception {
        var result = mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), github("kubernetes/website")))
            .andExpect(status().isAccepted())
            .andReturn().getResponse();
        String sourceId = JsonPath.read(result.getContentAsString(), "$.id");
        assertThat(result.getHeader("Location")).isEqualTo("/v1/tenants/" + tenantId + "/sources/" + sourceId);
    }

    @Test
    void retryWithSameKeyReturnsSameSourceAndEmitsOneEvent() throws Exception {
        String key = "key-" + UUID.randomUUID();
        String first = mvc.perform(createSource(owner, key, github("kubernetes/website")))
            .andExpect(status().isAccepted()).andReturn().getResponse().getContentAsString();
        String second = mvc.perform(createSource(owner, key, github("kubernetes/website")))
            .andExpect(status().isAccepted()).andReturn().getResponse().getContentAsString();

        String sourceId = JsonPath.read(first, "$.id");
        assertThat((String) JsonPath.read(second, "$.id")).isEqualTo(sourceId);
        assertThat(outboxEvents(sourceId)).hasSize(1);
    }

    @Test
    void sameKeyWithDifferentConfigIsRejected() throws Exception {
        String key = "key-" + UUID.randomUUID();
        mvc.perform(createSource(owner, key, github("kubernetes/website"))).andExpect(status().isAccepted());
        mvc.perform(createSource(owner, key, github("kubernetes/kubernetes")))
            .andExpect(status().isUnprocessableContent());
    }

    @Test
    void anotherTenantsCollectionIsNotFoundAndNothingIsWritten() throws Exception {
        UUID stranger = UUID.randomUUID();
        String otherTenant = createTenant(stranger);
        String foreignCollection = createCollection(stranger, otherTenant, "Gizli");

        mvc.perform(post("/v1/tenants/{t}/sources", tenantId).with(token(owner))
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content(sourceJson(foreignCollection, github("kubernetes/website"))))
            .andExpect(status().isNotFound());

        assertThat(queryAsSuperuser("SELECT count(*) FROM core.sources WHERE collection_id = '" + foreignCollection + "'"))
            .containsExactly("0");
    }

    @Test
    void viewerCannotAddSources() throws Exception {
        UUID viewer = UUID.randomUUID();
        mvc.perform(get("/v1/me").with(token(viewer))).andExpect(status().isOk());
        TenantContext.runAs(new Identity(owner, UUID.fromString(tenantId)),
            () -> tenants.addMembership(UUID.fromString(tenantId), viewer, "viewer"));

        mvc.perform(createSource(viewer, "key-" + UUID.randomUUID(), github("kubernetes/website")))
            .andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).with(token(viewer)))
            .andExpect(status().isOk());
    }

    @Test
    void githubPathsAndDefaultsReachTheEvent() throws Exception {
        String body = mvc.perform(createSource(owner, "key-" + UUID.randomUUID(),
                "{\"type\":\"github\",\"repository\":\"kubernetes/website\",\"paths\":[\"content/en/docs/concepts\"]}"))
            .andExpect(status().isAccepted())
            .andReturn().getResponse().getContentAsString();
        String sourceId = JsonPath.read(body, "$.id");

        assertThat(queryAsSuperuser("""
                SELECT concat_ws('|', payload->'config'->>'branch', payload->'config'->'paths'->>0)
                FROM core.outbox WHERE aggregate_id = '%s'""".formatted(sourceId)))
            .containsExactly("main|content/en/docs/concepts");
    }

    @Test
    void invalidConfigIsBadRequest() throws Exception {
        mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), "{\"type\":\"github\",\"repository\":\"not a repo\"}"))
            .andExpect(status().isBadRequest());
        mvc.perform(createSource(owner, "key-" + UUID.randomUUID(),
                "{\"type\":\"github\",\"repository\":\"org/repo\",\"paths\":[\"/etc\"]}"))
            .andExpect(status().isBadRequest());
        mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), "{\"type\":\"ftp\"}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void listIsPagedNewestFirstWithOpaqueCursor() throws Exception {
        for (int i = 0; i < 5; i++) {
            mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), github("org/repo-" + i)))
                .andExpect(status().isAccepted());
        }
        String page1 = mvc.perform(get("/v1/tenants/{t}/sources?limit=2", tenantId).with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.items.length()").value(2))
            .andReturn().getResponse().getContentAsString();
        String cursor = JsonPath.read(page1, "$.nextCursor");
        String page2 = mvc.perform(get("/v1/tenants/{t}/sources?limit=2&cursor={c}", tenantId, cursor).with(token(owner)))
            .andExpect(jsonPath("$.items.length()").value(2))
            .andReturn().getResponse().getContentAsString();
        String page3 = mvc.perform(get("/v1/tenants/{t}/sources?limit=2&cursor={c}", tenantId, JsonPath.read(page2, "$.nextCursor")).with(token(owner)))
            .andExpect(jsonPath("$.items.length()").value(1))
            .andExpect(jsonPath("$.nextCursor").doesNotExist())
            .andReturn().getResponse().getContentAsString();

        List<String> ids = new ArrayList<>();
        for (String page : List.of(page1, page2, page3)) {
            ids.addAll(JsonPath.read(page, "$.items[*].id"));
        }
        assertThat(ids).hasSize(5).doesNotHaveDuplicates();

        mvc.perform(get("/v1/tenants/{t}/sources?cursor=bozuk", tenantId).with(token(owner)))
            .andExpect(status().isBadRequest());
    }

    @Test
    void deleteMarksSourceAndEmitsEventOnce() throws Exception {
        String sourceId = JsonPath.read(mvc.perform(createSource(owner, "key-" + UUID.randomUUID(), github("org/repo")))
            .andReturn().getResponse().getContentAsString(), "$.id");

        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, sourceId).with(token(owner)))
            .andExpect(status().isAccepted());
        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, sourceId).with(token(owner)))
            .andExpect(status().isAccepted());

        mvc.perform(get("/v1/tenants/{t}/sources/{s}", tenantId, sourceId).with(token(owner)))
            .andExpect(jsonPath("$.status").value("deleting"));
        assertThat(outboxEvents(sourceId)).extracting(e -> e.substring(0, e.indexOf('|')))
            .containsExactly("source.created", "source.deleted");
    }

    @Test
    void duplicateCollectionNameIsConflict() throws Exception {
        mvc.perform(post("/v1/tenants/{t}/collections", tenantId).with(token(owner))
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Mühendislik\"}"))
            .andExpect(status().isConflict());
        mvc.perform(get("/v1/tenants/{t}/collections", tenantId).with(token(owner)))
            .andExpect(jsonPath("$.length()").value(1));
    }

    private List<String> outboxEvents(String aggregateId) throws Exception {
        return queryAsSuperuser("SELECT event_type || '|' || tenant_id || '|' || payload::text FROM core.outbox "
            + "WHERE aggregate_id = '" + aggregateId + "' ORDER BY id");
    }

    private String createTenant(UUID user) throws Exception {
        String body = mvc.perform(post("/v1/tenants").with(token(user))
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Acme\",\"slug\":\"acme-" + UUID.randomUUID().toString().substring(0, 8) + "\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        return JsonPath.read(body, "$.id");
    }

    private String createCollection(UUID user, String tenant, String name) throws Exception {
        String body = mvc.perform(post("/v1/tenants/{t}/collections", tenant).with(token(user))
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"" + name + "\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        return JsonPath.read(body, "$.id");
    }

    private MockHttpServletRequestBuilder createSource(UUID user, String key, String configJson) {
        return post("/v1/tenants/{t}/sources", tenantId).with(token(user))
            .header("Idempotency-Key", key)
            .contentType(MediaType.APPLICATION_JSON)
            .content(sourceJson(collectionId, configJson));
    }

    private static String sourceJson(String collection, String configJson) {
        return "{\"name\":\"Kubernetes docs\",\"collectionId\":\"" + collection + "\",\"config\":" + configJson + "}";
    }

    private static String web(String url) {
        return "{\"type\":\"web\",\"startUrl\":\"" + url + "\"}";
    }

    private static String github(String repository) {
        return "{\"type\":\"github\",\"repository\":\"" + repository + "\"}";
    }

    private static JwtRequestPostProcessor token(UUID user) {
        return jwt().jwt(j -> j.subject(user.toString()).claim("email", user + "@acme.test"));
    }
}
