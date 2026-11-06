package dev.meridian.api.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.JwtRequestPostProcessor;
import org.springframework.test.web.servlet.MockMvc;

import com.jayway.jsonpath.JsonPath;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.usage.UsageMeter;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;

/** Yönetim uçları: yeniden deneme, denetim kaydı, kullanım ve kota, API anahtarları. */
@AutoConfigureMockMvc
class AdminApiTest extends PostgresIntegrationTest {

    @Autowired
    MockMvc mvc;

    @Autowired
    UsageMeter usage;

    UUID owner;
    String tenantId;
    String collectionId;

    @BeforeEach
    void tenant() throws Exception {
        owner = UUID.randomUUID();
        tenantId = JsonPath.read(mvc.perform(post("/v1/tenants").with(token(owner))
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"slug\":\"t-" + UUID.randomUUID().toString().substring(0, 8) + "\",\"name\":\"Acme\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString(), "$.id");
        collectionId = JsonPath.read(mvc.perform(post("/v1/tenants/{t}/collections", tenantId).with(token(owner))
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Belgeler\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString(), "$.id");
    }

    // --- yeniden deneme ---

    @Test
    void failedSourceGoesBackToTheQueueWithANewEvent() throws Exception {
        String source = createSource(owner);
        fail(source);

        mvc.perform(post("/v1/tenants/{t}/sources/{s}/retry", tenantId, source).with(token(owner)))
            .andExpect(status().isAccepted())
            .andExpect(jsonPath("$.status").value("pending"))
            .andExpect(jsonPath("$.lastError").doesNotExist());

        var events = queryAsSuperuser("""
            SELECT concat_ws('|', event_id, payload->'config'->>'startUrl') FROM core.outbox
            WHERE aggregate_id = '%s' AND event_type = 'source.created'""".formatted(source));
        assertThat(events).hasSize(2);
        assertThat(events).allMatch(event -> event.endsWith("|https://example.com/"));
        assertThat(events.get(0).split("\\|")[0]).isNotEqualTo(events.get(1).split("\\|")[0]);
    }

    @Test
    void retryDoesNothingWhileQueuedAndConflictsWhenDone() throws Exception {
        String source = createSource(owner);
        mvc.perform(post("/v1/tenants/{t}/sources/{s}/retry", tenantId, source).with(token(owner)))
            .andExpect(status().isAccepted());
        assertThat(queryAsSuperuser("SELECT 1 FROM core.outbox WHERE aggregate_id = '%s'".formatted(source))).hasSize(1);

        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "UPDATE core.sources SET status = 'ready' WHERE id = '%s'".formatted(source));
        mvc.perform(post("/v1/tenants/{t}/sources/{s}/retry", tenantId, source).with(token(owner)))
            .andExpect(status().isConflict());
    }

    // --- denetim ---

    @Test
    void changesAndRefusalsAreRecordedInOrder() throws Exception {
        String source = createSource(owner);
        UUID viewer = addMember("viewer");
        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, source).with(token(viewer)))
            .andExpect(status().isForbidden());
        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, source).with(token(owner)))
            .andExpect(status().isAccepted());

        mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).param("limit", "3").with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.items[0].action").value("source.delete"))
            .andExpect(jsonPath("$.items[0].outcome").value("allowed"))
            .andExpect(jsonPath("$.items[0].targetId").value(source))
            .andExpect(jsonPath("$.items[0].actorUserId").value(owner.toString()))
            .andExpect(jsonPath("$.items[1].action").value("source.delete"))
            .andExpect(jsonPath("$.items[1].outcome").value("denied"))
            .andExpect(jsonPath("$.items[1].actorUserId").value(viewer.toString()))
            .andExpect(jsonPath("$.items[2].action").value("source.create"));
    }

    @Test
    void auditLogPagesWithACursor() throws Exception {
        createSource(owner);
        createSource(owner);
        String first = mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).param("limit", "2").with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.items.length()").value(2))
            .andReturn().getResponse().getContentAsString();
        // source x2 + collection = 3 kayıt
        mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).param("cursor", (String) JsonPath.read(first, "$.nextCursor"))
                .with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.items.length()").value(1))
            .andExpect(jsonPath("$.items[0].action").value("collection.create"))
            .andExpect(jsonPath("$.nextCursor").doesNotExist());
    }

    @Test
    void membersCannotReadAdminData() throws Exception {
        UUID member = addMember("member");
        mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).with(token(member))).andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/usage", tenantId).with(token(member))).andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/api-keys", tenantId).with(token(member))).andExpect(status().isForbidden());
    }

    @Test
    void auditAndUsageRowsCannotBeRewrittenByTheApplication() {
        for (String statement : List.of("UPDATE core.audit_log SET action = 'x'", "DELETE FROM core.audit_log",
                "UPDATE core.usage_events SET prompt_tokens = 0", "DELETE FROM core.usage_events",
                "DELETE FROM core.api_keys")) {
            assertThatThrownBy(() -> executeAs("meridian_app", APP_PASSWORD, statement))
                .as(statement)
                .hasMessageContaining("permission denied");
        }
    }

    // --- kullanım ve kota ---

    @Test
    void usageSeriesHasEveryDayAndTodaysTotal() throws Exception {
        record(1000, 500, false);
        record(100, 50, true);

        mvc.perform(get("/v1/tenants/{t}/usage", tenantId).param("days", "7").with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.plan").value("free"))
            .andExpect(jsonPath("$.dailyTokenLimit").value(200000))
            .andExpect(jsonPath("$.tokensToday").value(1650))
            .andExpect(jsonPath("$.estimatedTokens").value(150))
            .andExpect(jsonPath("$.costUsd").value(0.0))
            .andExpect(jsonPath("$.days.length()").value(7))
            .andExpect(jsonPath("$.days[0].tokens").value(0))
            .andExpect(jsonPath("$.days[6].tokens").value(1650))
            .andExpect(jsonPath("$.days[6].answers").value(2));
    }

    @Test
    void usedUpQuotaStopsTheQuestionBeforeTheModelRuns() throws Exception {
        String conversation = JsonPath.read(mvc.perform(post("/v1/tenants/{t}/conversations", tenantId).with(token(owner))
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString(), "$.id");
        record(200000, 0, false);

        mvc.perform(post("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversation).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"content\":\"Soru?\"}"))
            .andExpect(status().isTooManyRequests())
            .andExpect(header().exists("Retry-After"))
            .andExpect(jsonPath("$.type").value("https://meridian.dev/problems/quota-exceeded"));
        assertThat(queryAsSuperuser("SELECT 1 FROM core.messages WHERE conversation_id = '%s'".formatted(conversation)))
            .isEmpty();
    }

    // --- API anahtarları ---

    @Test
    void secretIsShownOnceAndOnlyItsHashIsStored() throws Exception {
        String body = createKey("[\"sources:read\"]");
        String secret = JsonPath.read(body, "$.secret");
        String id = JsonPath.read(body, "$.key.id");
        assertThat(secret).startsWith("mrd_");
        assertThat(secret).startsWith((String) JsonPath.read(body, "$.key.prefix"));

        assertThat(queryAsSuperuser("SELECT key_hash FROM core.api_keys WHERE id = '%s'".formatted(id)).getFirst())
            .hasSize(64)
            .doesNotContain(secret);
        String listed = mvc.perform(get("/v1/tenants/{t}/api-keys", tenantId).with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].id").value(id))
            .andReturn().getResponse().getContentAsString();
        assertThat(listed).doesNotContain(secret).doesNotContain("Hash");
    }

    @Test
    void keyReachesOnlyWhatItsScopeAllows() throws Exception {
        String source = createSource(owner);
        String secret = JsonPath.read(createKey("[\"sources:read\"]"), "$.secret");

        mvc.perform(get("/v1/tenants/{t}/sources/{s}", tenantId, source).header("X-API-Key", secret))
            .andExpect(status().isOk());
        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, source).header("X-API-Key", secret))
            .andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/conversations", tenantId).header("X-API-Key", secret))
            .andExpect(status().isForbidden());
    }

    @Test
    void keyCanNeverManageKeysOrReadAdminData() throws Exception {
        String secret = JsonPath.read(createKey("[\"sources:read\",\"sources:write\",\"chat\"]"), "$.secret");

        mvc.perform(get("/v1/tenants/{t}/api-keys", tenantId).header("X-API-Key", secret)).andExpect(status().isForbidden());
        mvc.perform(post("/v1/tenants/{t}/api-keys", tenantId).header("X-API-Key", secret)
                .contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"x\",\"scopes\":[\"chat\"]}"))
            .andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).header("X-API-Key", secret)).andExpect(status().isForbidden());
        mvc.perform(get("/v1/tenants/{t}/usage", tenantId).header("X-API-Key", secret)).andExpect(status().isForbidden());
        mvc.perform(get("/v1/me").header("X-API-Key", secret)).andExpect(status().isUnauthorized());
    }

    @Test
    void keyOfOneTenantDoesNotOpenAnother() throws Exception {
        String secret = JsonPath.read(createKey("[\"sources:read\"]"), "$.secret");
        UUID other = UUID.randomUUID();
        String otherTenant = JsonPath.read(mvc.perform(post("/v1/tenants").with(token(other))
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"slug\":\"o-" + UUID.randomUUID().toString().substring(0, 8) + "\",\"name\":\"Other\"}"))
            .andReturn().getResponse().getContentAsString(), "$.id");

        mvc.perform(get("/v1/tenants/{t}/sources", otherTenant).header("X-API-Key", secret))
            .andExpect(status().isUnauthorized());
    }

    @Test
    void revokedExpiredAndUnknownKeysAreRejected() throws Exception {
        String body = createKey("[\"sources:read\"]");
        String secret = JsonPath.read(body, "$.secret");
        String id = JsonPath.read(body, "$.key.id");
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", "mrd_yok"))
            .andExpect(status().isUnauthorized());
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", secret))
            .andExpect(status().isOk());

        mvc.perform(delete("/v1/tenants/{t}/api-keys/{k}", tenantId, id).with(token(owner)))
            .andExpect(status().isNoContent());
        mvc.perform(delete("/v1/tenants/{t}/api-keys/{k}", tenantId, id).with(token(owner)))
            .andExpect(status().isNoContent());
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", secret))
            .andExpect(status().isUnauthorized());

        String expiring = createKey("[\"sources:read\"]");
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(), "UPDATE core.api_keys SET expires_at = now() - interval '1 second' WHERE id = '%s'"
            .formatted((String) JsonPath.read(expiring, "$.key.id")));
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", (String) JsonPath.read(expiring, "$.secret")))
            .andExpect(status().isUnauthorized());
    }

    @Test
    void keyCannotExceedItsCreatorsRoleAndDiesWithTheMembership() throws Exception {
        UUID admin = addMember("admin");
        String source = createSource(owner);
        String secret = JsonPath.read(createKey(admin, "[\"sources:read\",\"sources:write\"]"), "$.secret");

        // Rol düşürülünce anahtar da düşer: kapsam izin verse bile silme yöneticiye özgüdür.
        setRole(admin, "member");
        mvc.perform(delete("/v1/tenants/{t}/sources/{s}", tenantId, source).header("X-API-Key", secret))
            .andExpect(status().isForbidden());

        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "DELETE FROM core.memberships WHERE user_id = '%s' AND tenant_id = '%s'".formatted(admin, tenantId));
        mvc.perform(get("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", secret))
            .andExpect(status().isNotFound());
    }

    @Test
    void writesWithAKeyAreAttributedToTheKey() throws Exception {
        String body = createKey("[\"sources:write\"]");
        String secret = JsonPath.read(body, "$.secret");
        mvc.perform(post("/v1/tenants/{t}/sources", tenantId).header("X-API-Key", secret)
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content(sourceJson()))
            .andExpect(status().isAccepted());

        mvc.perform(get("/v1/tenants/{t}/audit-log", tenantId).param("limit", "1").with(token(owner)))
            .andExpect(jsonPath("$.items[0].action").value("source.create"))
            .andExpect(jsonPath("$.items[0].apiKeyId").value((String) JsonPath.read(body, "$.key.id")))
            .andExpect(jsonPath("$.items[0].actorUserId").value(owner.toString()));
    }

    @Test
    void invalidKeyRequestsAreRejected() throws Exception {
        for (String request : List.of("{\"name\":\"x\",\"scopes\":[]}", "{\"name\":\"\",\"scopes\":[\"chat\"]}",
                "{\"name\":\"x\",\"scopes\":[\"her-sey\"]}", "{\"name\":\"x\",\"scopes\":[\"chat\"],\"expiresInDays\":9999}")) {
            mvc.perform(post("/v1/tenants/{t}/api-keys", tenantId).with(token(owner))
                    .contentType(MediaType.APPLICATION_JSON).content(request))
                .andExpect(status().isBadRequest());
        }
    }

    // --- yardımcılar ---

    private void record(int prompt, int completion, boolean estimated) {
        TenantContext.runAs(new Identity(owner, UUID.fromString(tenantId)),
            () -> usage.record("ollama/test", prompt, completion, estimated));
    }

    private String createSource(UUID user) throws Exception {
        return JsonPath.read(mvc.perform(post("/v1/tenants/{t}/sources", tenantId).with(token(user))
                .header("Idempotency-Key", key())
                .contentType(MediaType.APPLICATION_JSON)
                .content(sourceJson()))
            .andExpect(status().isAccepted())
            .andReturn().getResponse().getContentAsString(), "$.id");
    }

    private String sourceJson() {
        return """
            {"name":"Site","collectionId":"%s","config":{"type":"web","startUrl":"https://example.com/"}}"""
            .formatted(collectionId);
    }

    private void fail(String source) throws Exception {
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "UPDATE core.sources SET status = 'failed', last_error = 'bozuk' WHERE id = '%s'".formatted(source));
    }

    private String createKey(String scopes) throws Exception {
        return createKey(owner, scopes);
    }

    private String createKey(UUID user, String scopes) throws Exception {
        return mvc.perform(post("/v1/tenants/{t}/api-keys", tenantId).with(token(user))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"CI\",\"scopes\":" + scopes + "}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
    }

    private UUID addMember(String role) throws Exception {
        UUID user = UUID.randomUUID();
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "INSERT INTO core.users (id, email) VALUES ('%s', '%s@acme.test')".formatted(user, user),
            "INSERT INTO core.memberships (tenant_id, user_id, role) VALUES ('%s', '%s', '%s')".formatted(tenantId, user, role));
        return user;
    }

    private void setRole(UUID user, String role) throws Exception {
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "UPDATE core.memberships SET role = '%s' WHERE user_id = '%s' AND tenant_id = '%s'".formatted(role, user, tenantId));
    }

    private static String key() {
        return "key-" + UUID.randomUUID();
    }

    private static JwtRequestPostProcessor token(UUID user) {
        return jwt().jwt(j -> j.subject(user.toString()).claim("email", user + "@acme.test"));
    }
}
