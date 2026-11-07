package dev.meridian.api.agents;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.JwtRequestPostProcessor;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;

import com.jayway.jsonpath.JsonPath;

import dev.meridian.api.PostgresIntegrationTest;
import dev.meridian.api.chat.AiServiceStub;

/** Ajan çalıştırması: kayıt, insan onayı, çift karar, gizlilik, kota ve anahtar sınırları. */
@AutoConfigureMockMvc
class AgentApiTest extends PostgresIntegrationTest {

    static final AiServiceStub AI = new AiServiceStub();

    private static final String STEP = "{\"event\":\"step\",\"data\":{\"thought\":\"ara\",\"action\":\"search_knowledge\","
        + "\"input\":{\"query\":\"q\"},\"observation\":\"bulundu\",\"rows\":true,\"gelecekteAlan\":1}}";
    private static final String APPROVAL = "{\"event\":\"approval_required\",\"data\":{\"thought\":\"aç\","
        + "\"title\":\"Disk dolu\",\"description\":\"Ayrıntı\",\"usage\":{\"promptTokens\":100,\"completionTokens\":10}}}";
    private static final String DONE = "{\"event\":\"done\",\"data\":{\"status\":\"completed\",\"answer\":\"Bitti [1]\","
        + "\"cited\":[1],\"invalidCitations\":[],\"sources\":[{\"number\":1,\"documentPath\":\"a.md\",\"title\":\"A\","
        + "\"url\":null,\"section\":\"S\",\"content\":\"metin\"}],\"stopReason\":null,\"model\":\"m\","
        + "\"usage\":{\"promptTokens\":50,\"completionTokens\":5}}}";

    @DynamicPropertySource
    static void ai(DynamicPropertyRegistry registry) {
        registry.add("meridian.ai.url", AI::url);
        registry.add("meridian.search.rate.capacity", () -> 3);
    }

    @Autowired
    MockMvc mvc;

    UUID owner;
    String tenantId;

    @BeforeEach
    void tenant() throws Exception {
        AI.reset();
        owner = UUID.randomUUID();
        tenantId = JsonPath.read(mvc.perform(post("/v1/tenants").with(token(owner))
                .header("Idempotency-Key", "key-" + UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"slug\":\"a-" + UUID.randomUUID().toString().substring(0, 8) + "\",\"name\":\"Acme\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString(), "$.id");
    }

    @Test
    void stepsAreStoredAndStreamedAndTokensRecorded() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, STEP, DONE));

        String stream = start(owner, "görev").andExpect(status().isOk()).andReturn().getResponse()
            .getContentAsString(StandardCharsets.UTF_8);
        assertThat(stream).contains("event: run", "event: step", "event: end").doesNotContain("promptTokens");
        String run = runId(stream);

        mvc.perform(get("/v1/tenants/{t}/agent-runs/{r}", tenantId, run).with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status").value("completed"))
            .andExpect(jsonPath("$.answer").value("Bitti [1]"))
            .andExpect(jsonPath("$.steps[0].action").value("search_knowledge"))
            .andExpect(jsonPath("$.steps[0].rows").doesNotExist())
            .andExpect(jsonPath("$.sources[0].documentPath").value("a.md"))
            .andExpect(jsonPath("$.tokens").value(55));
        // Yanıtta olmayan alanlar geçmişte kalır: onaydan sonra AI servisine aynen döner.
        assertThat(queryAsSuperuser("SELECT steps->0->>'rows' FROM core.agent_runs WHERE id = '%s'".formatted(run)))
            .containsExactly("true");
        mvc.perform(get("/v1/tenants/{t}/agent-runs", tenantId).with(token(owner))).andExpect(status().isOk());
        assertThat(queryAsSuperuser("SELECT prompt_tokens || '|' || estimated FROM core.usage_events WHERE tenant_id = '%s'"
            .formatted(tenantId))).containsExactly("50|false");
    }

    @Test
    void approvedTicketIsWrittenByTheCoreOnceAndTheAgentResumes() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, STEP, APPROVAL));
        String run = runId(start(owner, "ticket aç").andExpect(status().isOk()).andReturn().getResponse()
            .getContentAsString(StandardCharsets.UTF_8));

        mvc.perform(get("/v1/tenants/{t}/agent-runs/{r}", tenantId, run).with(token(owner)))
            .andExpect(jsonPath("$.status").value("waiting_approval"))
            .andExpect(jsonPath("$.pending.title").value("Disk dolu"));
        assertThat(tickets()).isEmpty();

        AI.reset();
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, DONE));
        decide(owner, run, true).andExpect(status().isOk());

        assertThat(tickets()).containsExactly("Disk dolu|Ayrıntı|" + owner);
        String resumed = AI.calls.getLast().body();
        assertThat(resumed).contains("Ticket oluşturuldu").contains("\"tokensUsed\":110");
        mvc.perform(get("/v1/tenants/{t}/agent-runs/{r}", tenantId, run).with(token(owner)))
            .andExpect(jsonPath("$.status").value("completed"))
            .andExpect(jsonPath("$.pending").doesNotExist())
            .andExpect(jsonPath("$.steps[1].action").value("create_ticket"))
            .andExpect(jsonPath("$.steps[1].approved").value(true));

        // Çift karar ikinci ticket üretmez.
        decide(owner, run, true).andExpect(status().isConflict());
        assertThat(tickets()).hasSize(1);
        assertThat(queryAsSuperuser("SELECT action FROM core.audit_log WHERE tenant_id = '%s' AND action LIKE 'ticket%%'"
            .formatted(tenantId))).containsExactly("ticket.create");
    }

    @Test
    void rejectedTicketIsNeverWritten() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, APPROVAL));
        String run = runId(start(owner, "ticket aç").andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8));

        AI.behave(exchange -> AiServiceStub.ndjson(exchange, DONE));
        decide(owner, run, false).andExpect(status().isOk());

        assertThat(tickets()).isEmpty();
        assertThat(AI.calls.getLast().body()).contains("Kullanıcı reddetti");
        assertThat(queryAsSuperuser("SELECT action FROM core.audit_log WHERE tenant_id = '%s' AND action = 'agent.reject'"
            .formatted(tenantId))).hasSize(1);
    }

    @Test
    void clientCannotSmuggleTicketContentInTheApproval() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, APPROVAL));
        String run = runId(start(owner, "ticket aç").andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8));

        mvc.perform(post("/v1/tenants/{t}/agent-runs/{r}/approval", tenantId, run).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"approved\":true,\"title\":\"sahte\"}"))
            .andExpect(status().isBadRequest());
        assertThat(tickets()).isEmpty();
    }

    @Test
    void runsArePrivateAndViewerCannotApprove() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, APPROVAL));
        String run = runId(start(owner, "özel").andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8));

        UUID member = addMember("member");
        mvc.perform(get("/v1/tenants/{t}/agent-runs/{r}", tenantId, run).with(token(member))).andExpect(status().isNotFound());
        decide(member, run, true).andExpect(status().isNotFound());
        assertThat(tickets()).isEmpty();

        UUID viewer = addMember("viewer");
        String own = runId(start(viewer, "kendi").andExpect(status().isOk()).andReturn().getResponse()
            .getContentAsString(StandardCharsets.UTF_8));
        decide(viewer, own, true).andExpect(status().isForbidden());
        assertThat(tickets()).isEmpty();
    }

    @Test
    void oneRunAtATimeAndStaleRunsDoNotBlockForever() throws Exception {
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "INSERT INTO core.agent_runs (id, tenant_id, user_id, goal) VALUES ('%s', '%s', '%s', 'süren')"
                .formatted(UUID.randomUUID(), tenantId, owner));
        start(owner, "ikinci").andExpect(status().isConflict());

        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "UPDATE core.agent_runs SET updated_at = now() - interval '11 minutes' WHERE tenant_id = '%s'".formatted(tenantId));
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, DONE));
        start(owner, "ikinci").andExpect(status().isOk());
    }

    @Test
    void usedUpQuotaStopsTheRunBeforeTheModel() throws Exception {
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "INSERT INTO core.usage_events (id, tenant_id, user_id, prompt_tokens, completion_tokens) VALUES ('%s', '%s', '%s', 200000, 0)"
                .formatted(UUID.randomUUID(), tenantId, owner));
        start(owner, "görev").andExpect(status().isTooManyRequests());
        assertThat(AI.calls).isEmpty();
    }

    @Test
    void unreachableAiMarksTheRunFailedWithoutError() throws Exception {
        AI.behave(exchange -> {
            throw new java.io.IOException("kapalı");
        });
        String stream = start(owner, "görev").andExpect(status().isOk()).andReturn().getResponse()
            .getContentAsString(StandardCharsets.UTF_8);
        assertThat(stream).contains("\"status\":\"failed\"", "ai_unavailable");
    }

    @Test
    void apiKeysCannotStartAgentsButReadScopeCanSearch() throws Exception {
        String secret = JsonPath.read(mvc.perform(post("/v1/tenants/{t}/api-keys", tenantId).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"mcp\",\"scopes\":[\"sources:read\",\"sources:write\",\"chat\"]}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString(), "$.secret");

        mvc.perform(post("/v1/tenants/{t}/agent-runs", tenantId).header("X-API-Key", secret)
                .contentType(MediaType.APPLICATION_JSON).content("{\"goal\":\"x\"}"))
            .andExpect(status().isForbidden());
        mvc.perform(post("/v1/tenants/{t}/search", tenantId).header("X-API-Key", secret)
                .contentType(MediaType.APPLICATION_JSON).content("{\"query\":\"q\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.hits[0].documentPath").value("a.md"));
        assertThat(AI.calls.getLast().body()).contains(tenantId);
    }

    @Test
    void searchIsRateLimitedAndDocumentsAreScopedToTheTenant() throws Exception {
        for (int i = 0; i < 3; i++) {
            mvc.perform(post("/v1/tenants/{t}/search", tenantId).with(token(owner))
                    .contentType(MediaType.APPLICATION_JSON).content("{\"query\":\"q\"}"))
                .andExpect(status().isOk());
        }
        mvc.perform(post("/v1/tenants/{t}/search", tenantId).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON).content("{\"query\":\"q\"}"))
            .andExpect(status().isTooManyRequests());
        mvc.perform(get("/v1/tenants/{t}/documents", tenantId).param("path", "yok.md").with(token(owner)))
            .andExpect(status().isNotFound());
    }

    @Test
    void appRoleCannotReadTheAgentViewsAndAiRoleCannotTouchTickets() {
        assertThatThrownBy(() -> queryAs("meridian_app", APP_PASSWORD, "SELECT * FROM core.agent_sources"))
            .hasMessageContaining("permission denied");
        assertThatThrownBy(() -> queryAs("meridian_ai", AI_PASSWORD, "SELECT * FROM core.tickets"))
            .hasMessageContaining("permission denied");
        assertThatThrownBy(() -> queryAs("meridian_ai", AI_PASSWORD, "SELECT * FROM core.agent_runs"))
            .hasMessageContaining("permission denied");
    }

    private ResultActions start(UUID user, String goal) throws Exception {
        return mvc.perform(post("/v1/tenants/{t}/agent-runs", tenantId).with(token(user))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"goal\":\"" + goal + "\"}"));
    }

    private ResultActions decide(UUID user, String run, boolean approved) throws Exception {
        return mvc.perform(post("/v1/tenants/{t}/agent-runs/{r}/approval", tenantId, run).with(token(user))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"approved\":" + approved + "}"));
    }

    private static String runId(String stream) {
        String line = stream.substring(stream.indexOf("event: run"));
        String data = line.substring(line.indexOf("data: ") + 6, line.indexOf("\n\n"));
        return JsonPath.read(data, "$.id");
    }

    private java.util.List<String> tickets() throws Exception {
        return queryAsSuperuser("SELECT concat_ws('|', title, description, created_by) FROM core.tickets WHERE tenant_id = '%s'"
            .formatted(tenantId));
    }

    private UUID addMember(String role) throws Exception {
        UUID user = UUID.randomUUID();
        executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(),
            "INSERT INTO core.users (id, email) VALUES ('%s', '%s@acme.test')".formatted(user, user),
            "INSERT INTO core.memberships (tenant_id, user_id, role) VALUES ('%s', '%s', '%s')".formatted(tenantId, user, role));
        return user;
    }

    private static JwtRequestPostProcessor token(UUID user) {
        return jwt().jwt(j -> j.subject(user.toString()).claim("email", user + "@acme.test"));
    }
}
