package dev.meridian.api.chat;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
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
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.tenancy.TenantContext.Identity;
import dev.meridian.api.tenancy.TenantRepository;

/** Sohbet uçları: olay sırası, kayıt, zarif bozulma, gizlilik ve oran sınırı. */
@AutoConfigureMockMvc
class ChatApiTest extends PostgresIntegrationTest {

    private static final int RATE_CAPACITY = 4;
    static final AiServiceStub AI = new AiServiceStub();

    @DynamicPropertySource
    static void ai(DynamicPropertyRegistry registry) {
        registry.add("meridian.ai.url", AI::url);
        registry.add("meridian.chat.rate.capacity", () -> RATE_CAPACITY);
    }

    @Autowired
    MockMvc mvc;

    @Autowired
    TenantRepository tenants;

    UUID owner;
    String tenantId;
    String conversationId;

    @BeforeEach
    void conversation() throws Exception {
        AI.reset();
        owner = UUID.randomUUID();
        String body = mvc.perform(post("/v1/tenants").with(token(owner))
                .header("Idempotency-Key", AiServiceStub.randomKey())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"Acme\",\"slug\":\"acme-" + UUID.randomUUID().toString().substring(0, 8) + "\"}"))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        tenantId = JsonPath.read(body, "$.id");
        conversationId = createConversation(owner, "{}");
    }

    @Test
    void answerStreamsInOrderAndIsStored() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, AiServiceStub.sources(),
            AiServiceStub.token("Otuz "), AiServiceStub.token("gün [1]."),
            AiServiceStub.done("Otuz gün [1].", false, false)));

        var result = send(owner, "Kaç gün?").andExpect(status().isOk());
        String stream = result.andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        assertThat(result.andReturn().getResponse().getContentType()).startsWith(MediaType.TEXT_EVENT_STREAM_VALUE);
        assertThat(events(stream)).containsExactly("sources", "token", "token", "done");
        String done = stream.substring(stream.indexOf("event: done"));
        String messageId = JsonPath.read(done.substring(done.indexOf("data: ") + 6).trim(), "$.messageId");

        mvc.perform(get("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(owner)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.length()").value(2))
            .andExpect(jsonPath("$[0].role").value("user"))
            .andExpect(jsonPath("$[0].content").value("Kaç gün?"))
            .andExpect(jsonPath("$[1].id").value(messageId))
            .andExpect(jsonPath("$[1].role").value("assistant"))
            .andExpect(jsonPath("$[1].content").value("Otuz gün [1]."))
            .andExpect(jsonPath("$[1].status").value("complete"))
            .andExpect(jsonPath("$[1].cited[0]").value(1))
            .andExpect(jsonPath("$[1].sources[0].documentPath").value("kvkk/6698.md"))
            .andExpect(jsonPath("$[1].model").value("ollama/test"));
    }

    @Test
    void verifiedTenantAndSecretReachTheAiService() throws Exception {
        UUID collection = UUID.randomUUID();
        mvc.perform(post("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"content\":\"soru\",\"collectionIds\":[\"" + collection + "\"]}"))
            .andExpect(status().isOk());

        assertThat(AI.calls).hasSize(1);
        var call = AI.calls.getFirst();
        assertThat(call.token()).isEqualTo("test-internal-token");
        assertThat(call.upgrade()).as("uvicorn h2c yükseltmesinde gövdeyi okumaz").isNull();
        assertThat((String) JsonPath.read(call.body(), "$.tenantId")).isEqualTo(tenantId);
        assertThat((String) JsonPath.read(call.body(), "$.question")).isEqualTo("soru");
        assertThat((String) JsonPath.read(call.body(), "$.collectionIds[0]")).isEqualTo(collection.toString());
    }

    @Test
    void firstQuestionBecomesTheTitleOnlyWhenNoneWasGiven() throws Exception {
        send(owner, "İlk soru").andExpect(status().isOk());
        send(owner, "İkinci soru").andExpect(status().isOk());
        String titled = createConversation(owner, "{\"title\":\"Benim başlığım\"}");

        mvc.perform(get("/v1/tenants/{t}/conversations", tenantId).with(token(owner)))
            .andExpect(jsonPath("$[?(@.id=='" + conversationId + "')].title").value("İlk soru"))
            .andExpect(jsonPath("$[?(@.id=='" + titled + "')].title").value("Benim başlığım"));
    }

    @Test
    void unreachableAiServiceDegradesInsteadOfFailing() throws Exception {
        AI.behave(exchange -> exchange.sendResponseHeaders(500, -1));

        String stream = send(owner, "soru").andExpect(status().isOk())
            .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        assertThat(events(stream)).containsExactly("done");
        assertThat(stream).contains("\"degraded\":true");
        mvc.perform(get("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(owner)))
            .andExpect(jsonPath("$[1].degraded").value(true))
            .andExpect(jsonPath("$[1].content").value(""));
    }

    @Test
    void streamCutMidAnswerKeepsWhatArrivedAndMarksDegraded() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, AiServiceStub.sources(), AiServiceStub.token("Yarım ")));

        String stream = send(owner, "soru").andExpect(status().isOk())
            .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);

        assertThat(events(stream)).containsExactly("sources", "token", "done");
        mvc.perform(get("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(owner)))
            .andExpect(jsonPath("$[1].content").value("Yarım "))
            .andExpect(jsonPath("$[1].degraded").value(true))
            .andExpect(jsonPath("$[1].sources[0].number").value(1));
    }

    @Test
    void abstentionIsRecorded() throws Exception {
        AI.behave(exchange -> AiServiceStub.ndjson(exchange, AiServiceStub.sources(),
            AiServiceStub.done("BİLMİYORUM", true, false)));

        send(owner, "Kaç saat?").andExpect(status().isOk());

        mvc.perform(get("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(owner)))
            .andExpect(jsonPath("$[1].abstained").value(true));
    }

    @Test
    void conversationsArePrivateEvenWithinATenant() throws Exception {
        UUID colleague = member("admin");
        send(owner, "gizli soru").andExpect(status().isOk());
        int calls = AI.calls.size();

        mvc.perform(get("/v1/tenants/{t}/conversations", tenantId).with(token(colleague)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.length()").value(0));
        mvc.perform(get("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(colleague)))
            .andExpect(status().isNotFound());
        send(colleague, "araya gireyim").andExpect(status().isNotFound());
        assertThat(AI.calls).as("başkasının konuşmasında model çağrılmaz").hasSize(calls);
    }

    @Test
    void viewerCanChatInTheirOwnConversation() throws Exception {
        UUID viewer = member("viewer");
        conversationId = createConversation(viewer, "{}");
        send(viewer, "soru").andExpect(status().isOk());
    }

    @Test
    void databaseEnforcesPrivacyWithoutTheApplication() throws Exception {
        send(owner, "gizli").andExpect(status().isOk());
        UUID stranger = UUID.randomUUID();

        try (var conn = DriverManager.getConnection(POSTGRES.getJdbcUrl(), "meridian_app", APP_PASSWORD);
             var statement = conn.createStatement()) {
            statement.execute("SELECT set_config('app.tenant_id', '" + tenantId + "', false)");
            statement.execute("SELECT set_config('app.user_id', '" + stranger + "', false)");
            try (var rows = statement.executeQuery("SELECT count(*) FROM core.messages")) {
                rows.next();
                assertThat(rows.getLong(1)).as("aynı kiracının başka kullanıcısı").isZero();
            }
        }
        // FK denetimi RLS'i atlar: bileşik anahtar, başkasının konuşmasına mesaj bağlanmasını engeller.
        assertThatThrownBy(() -> executeAs(POSTGRES.getUsername(), POSTGRES.getPassword(), """
                INSERT INTO core.messages (id, tenant_id, user_id, conversation_id, role, content)
                VALUES ('%s', '%s', '%s', '%s', 'user', 'sızma')"""
                .formatted(UUID.randomUUID(), tenantId, stranger, conversationId)))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).isEqualTo("23503"));
    }

    @Test
    void messagesCannotBeRewritten() {
        assertThatThrownBy(() -> executeAs("meridian_app", APP_PASSWORD,
                "UPDATE core.messages SET content = 'x'"))
            .isInstanceOf(SQLException.class)
            .satisfies(e -> assertThat(((SQLException) e).getSQLState()).isEqualTo("42501"));
    }

    @Test
    void tooManyMessagesAreRejectedBeforeTheModelRuns() throws Exception {
        for (int i = 0; i < RATE_CAPACITY; i++) {
            send(owner, "soru " + i).andExpect(status().isOk());
        }
        int calls = AI.calls.size();

        send(owner, "bir tane daha")
            .andExpect(status().isTooManyRequests())
            .andExpect(header().exists("Retry-After"));
        assertThat(AI.calls).hasSize(calls);
    }

    @Test
    void invalidMessagesAreRejected() throws Exception {
        send(owner, "").andExpect(status().isBadRequest());
        mvc.perform(post("/v1/tenants/{t}/conversations/{c}/messages", tenantId, UUID.randomUUID()).with(token(owner))
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"content\":\"soru\"}"))
            .andExpect(status().isNotFound());
        assertThat(AI.calls).isEmpty();
    }

    @Test
    void creatingAConversationIsIdempotent() throws Exception {
        String key = AiServiceStub.randomKey();
        String first = JsonPath.read(createWithKey(key, "{}"), "$.id");
        String second = JsonPath.read(createWithKey(key, "{}"), "$.id");
        assertThat(second).isEqualTo(first);
    }

    private String createWithKey(String key, String body) throws Exception {
        return mvc.perform(post("/v1/tenants/{t}/conversations", tenantId).with(token(owner))
                .header("Idempotency-Key", key)
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
    }

    private String createConversation(UUID user, String body) throws Exception {
        String created = mvc.perform(post("/v1/tenants/{t}/conversations", tenantId).with(token(user))
                .header("Idempotency-Key", AiServiceStub.randomKey())
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        return JsonPath.read(created, "$.id");
    }

    private ResultActions send(UUID user, String content) throws Exception {
        return mvc.perform(post("/v1/tenants/{t}/conversations/{c}/messages", tenantId, conversationId).with(token(user))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"content\":\"" + content + "\"}"));
    }

    private UUID member(String role) throws Exception {
        UUID user = UUID.randomUUID();
        mvc.perform(get("/v1/me").with(token(user))).andExpect(status().isOk());
        TenantContext.runAs(new Identity(owner, UUID.fromString(tenantId)),
            () -> tenants.addMembership(UUID.fromString(tenantId), user, role));
        return user;
    }

    private static List<String> events(String stream) {
        var names = new ArrayList<String>();
        stream.lines().filter(l -> l.startsWith("event: ")).forEach(l -> names.add(l.substring(7)));
        return names;
    }

    private static JwtRequestPostProcessor token(UUID user) {
        return jwt().jwt(j -> j.subject(user.toString()).claim("email", user + "@acme.test"));
    }
}
