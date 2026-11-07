package dev.meridian.api.chat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.ai.AiClient;
import dev.meridian.api.audit.AuditLog;
import dev.meridian.api.contract.api.ChatApi;
import dev.meridian.api.contract.model.ChatMessage;
import dev.meridian.api.contract.model.CitedSource;
import dev.meridian.api.contract.model.Conversation;
import dev.meridian.api.contract.model.CreateConversationRequest;
import dev.meridian.api.contract.model.SendMessageRequest;
import dev.meridian.api.idempotency.IdempotencyStore;
import dev.meridian.api.tenancy.TenantContext;
import dev.meridian.api.usage.RateLimiter;
import dev.meridian.api.usage.UsageMeter;
import jakarta.servlet.http.HttpServletResponse;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

/** OpenAPI sözleşmesinden üretilen {@link ChatApi} arayüzünü uygular. */
@RestController
class ChatController implements ChatApi {

    private static final Logger log = LoggerFactory.getLogger(ChatController.class);
    private static final int TITLE_CHARS = 80;
    private static final int LIST_LIMIT = 100;
    /** Sayaç gelmediğinde kaba tahmin: karakter başına token. */
    private static final int CHARS_PER_TOKEN = 4;

    private final ConversationRepository conversations;
    private final IdempotencyStore idempotency;
    private final AiClient ai;
    private final RateLimiter limiter;
    private final int rateCapacity;
    private final int rateRefillPerMinute;
    private final UsageMeter usage;
    private final AuditLog audit;
    private final JsonMapper json;
    private final HttpServletResponse response;

    ChatController(ConversationRepository conversations, IdempotencyStore idempotency, AiClient ai,
            RateLimiter limiter, UsageMeter usage, AuditLog audit, JsonMapper json, HttpServletResponse response,
            @Value("${meridian.chat.rate.capacity}") int rateCapacity,
            @Value("${meridian.chat.rate.refill-per-minute}") int rateRefillPerMinute) {
        this.conversations = conversations;
        this.idempotency = idempotency;
        this.ai = ai;
        this.limiter = limiter;
        this.rateCapacity = rateCapacity;
        this.rateRefillPerMinute = rateRefillPerMinute;
        this.usage = usage;
        this.audit = audit;
        this.json = json;
        this.response = response;
    }

    @Override
    @Transactional
    public ResponseEntity<Conversation> createConversation(String idempotencyKey, UUID tenantId,
            CreateConversationRequest request) {
        String title = request.getTitle();
        var replay = idempotency.claim(idempotencyKey,
            String.join("\u001F", "POST /v1/tenants/{tenantId}/conversations", tenantId.toString(), String.valueOf(title)));
        if (replay.isPresent()) {
            var existing = conversations.findById(replay.get().resourceId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
            return ResponseEntity.status(HttpStatus.CREATED).body(toApi(existing));
        }
        var conversation = conversations.insert(UUID.randomUUID(), title);
        idempotency.complete(idempotencyKey, conversation.id());
        return ResponseEntity.status(HttpStatus.CREATED).body(toApi(conversation));
    }

    @Override
    public ResponseEntity<List<Conversation>> listConversations(UUID tenantId) {
        return ResponseEntity.ok(conversations.findLatest(LIST_LIMIT).stream().map(ChatController::toApi).toList());
    }

    @Override
    public ResponseEntity<List<ChatMessage>> listMessages(UUID tenantId, UUID conversationId) {
        requireConversation(conversationId);
        return ResponseEntity.ok(conversations.findMessages(conversationId).stream().map(this::toApi).toList());
    }

    /**
     * Cevabı bu thread'den doğrudan akıtır ve {@code null} döner: Spring gövdeye dokunmaz. Sanal
     * thread dakikalarca bloklanabilir; veritabanı bağlantısı akış sırasında tutulmaz.
     */
    @Override
    public ResponseEntity<String> sendMessage(UUID tenantId, UUID conversationId, SendMessageRequest request) {
        var identity = TenantContext.current().orElseThrow();
        // Hatalar akış başlamadan, normal HTTP durumlarıyla döner.
        limiter.acquire("chat", tenantId, identity.userId(), rateCapacity, rateRefillPerMinute);
        requireConversation(conversationId);
        usage.requireQuota();
        // Soru metni yazılmaz: konuşma kişiye özeldir, denetim kaydını yöneticiler okur.
        audit.allowed("chat.ask", conversationId);
        String question = request.getContent();
        conversations.insertMessage(UUID.randomUUID(), conversationId, "user", question, "complete", "[]", "[]",
            false, false, null);
        conversations.titleIfMissing(conversationId, question.substring(0, Math.min(TITLE_CHARS, question.length())));

        var turn = new Turn();
        boolean saved = false;
        response.setStatus(HttpStatus.OK.value());
        response.setContentType(MediaType.TEXT_EVENT_STREAM_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader(HttpHeaders.CACHE_CONTROL, "no-cache");
        // Ters vekil (nginx) akışı biriktirmesin.
        response.setHeader("X-Accel-Buffering", "no");
        try {
            try {
                ai.answer(tenantId, question, request.getCollectionIds(), (event, data) -> relay(turn, event, data));
            } catch (AiClient.Unavailable e) {
                log.warn("cevap üretilemedi, yalnızca kaynaklar dönülüyor: {}", e.getMessage());
                turn.degrade();
            }
            UUID messageId = save(conversationId, question, turn, "complete");
            saved = true;
            send("done", turn.done().put("messageId", messageId.toString()));
        } catch (UncheckedIOException e) {
            // İstemci ayrıldı: akış kapanınca AI servisi de üretimi bırakır; ulaşan kısım kaydedilir.
            log.info("istemci akış bitmeden ayrıldı conversation={}", conversationId);
            if (!saved) {
                save(conversationId, question, turn, "interrupted");
            }
        }
        return null;
    }

    private void relay(Turn turn, String event, JsonNode data) {
        switch (event) {
            case "sources" -> {
                turn.sources = data.get("sources");
                send(event, data);
            }
            case "token" -> {
                turn.answer.append(data.get("text").asString());
                send(event, data);
            }
            // Mesaj kimliği kayıttan sonra belli olur; "done" iletilmeden önce kaydedilir.
            case "done" -> turn.done = (ObjectNode) data;
            default -> log.debug("bilinmeyen olay atlandı: {}", event);
        }
    }

    private void send(String event, JsonNode data) {
        try {
            var out = response.getOutputStream();
            out.write(("event: " + event + "\ndata: " + json.writeValueAsString(data) + "\n\n")
                .getBytes(StandardCharsets.UTF_8));
            out.flush();
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private UUID save(UUID conversationId, String question, Turn turn, String status) {
        UUID id = UUID.randomUUID();
        ObjectNode done = turn.done();
        recordUsage(question, turn, done);
        conversations.insertMessage(id, conversationId, "assistant", done.get("answer").asString(), status,
            json.writeValueAsString(turn.sources()), json.writeValueAsString(done.get("cited")),
            done.get("abstained").asBoolean(), done.get("degraded").asBoolean(),
            done.hasNonNull("model") ? done.get("model").asString() : null);
        return id;
    }

    /** Sayaç istemciye gitmez. Yoksa (akış kesildi) elde olan metinden tahmin edilir; hiç metin yoksa model çalışmamıştır. */
    private void recordUsage(String question, Turn turn, ObjectNode done) {
        JsonNode counts = done.remove("usage");
        String model = done.hasNonNull("model") ? done.get("model").asString() : null;
        if (counts != null && counts.hasNonNull("promptTokens")) {
            usage.record(model, counts.get("promptTokens").asInt(), counts.get("completionTokens").asInt(), false);
        } else if (!turn.answer.isEmpty()) {
            int prompt = (question.length() + json.writeValueAsString(turn.sources()).length()) / CHARS_PER_TOKEN;
            usage.record(model, prompt, turn.answer.length() / CHARS_PER_TOKEN, true);
        }
    }

    private void requireConversation(UUID id) {
        if (conversations.findById(id).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
    }

    private static Conversation toApi(ConversationRepository.Conversation conversation) {
        return new Conversation(conversation.id(), conversation.createdAt()).title(conversation.title());
    }

    private ChatMessage toApi(ConversationRepository.StoredMessage message) {
        return new ChatMessage(message.id(), ChatMessage.RoleEnum.fromValue(message.role()), message.content(),
                ChatMessage.StatusEnum.fromValue(message.status()), message.createdAt())
            .sources(json.readValue(message.sources(), new TypeReference<ArrayList<CitedSource>>() { }))
            .cited(json.readValue(message.cited(), new TypeReference<ArrayList<Integer>>() { }))
            .abstained(message.abstained())
            .degraded(message.degraded())
            .model(message.model());
    }

    /** Akış boyunca biriken cevap; bağlantı ne zaman koparsa kopsun kaydedilebilir olmalı. */
    private final class Turn {
        private JsonNode sources;
        private final StringBuilder answer = new StringBuilder();
        private ObjectNode done;

        JsonNode sources() {
            return sources == null ? json.createArrayNode() : sources;
        }

        ObjectNode done() {
            if (done == null) {
                // AI "done" göndermeden kesildi ya da istemci ayrıldı: elde olan kadar.
                done = json.createObjectNode()
                    .put("answer", answer.toString())
                    .put("abstained", false)
                    .put("degraded", false);
                done.set("cited", json.createArrayNode());
            }
            return done;
        }

        void degrade() {
            done = null;
            done().put("degraded", true);
        }
    }
}
