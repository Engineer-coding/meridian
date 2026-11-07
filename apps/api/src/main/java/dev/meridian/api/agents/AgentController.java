package dev.meridian.api.agents;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.ai.AiClient;
import dev.meridian.api.contract.api.AgentsApi;
import dev.meridian.api.contract.model.AgentApprovalRequest;
import dev.meridian.api.contract.model.AgentRun;
import dev.meridian.api.contract.model.CreateAgentRunRequest;
import dev.meridian.api.usage.UsageMeter;
import jakarta.servlet.http.HttpServletResponse;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * OpenAPI sözleşmesinden üretilen {@link AgentsApi} arayüzünü uygular. Her olay önce kaydedilir, sonra
 * iletilir: bağlantı koparsa kayıt, kullanıcının gördüğünden geride kalmaz.
 */
@RestController
class AgentController implements AgentsApi {

    private static final Logger log = LoggerFactory.getLogger(AgentController.class);
    private static final String RUN_PATH = "/internal/v1/agent/run";
    private static final int LIST_LIMIT = 50;

    private final AgentService service;
    private final AgentRunRepository runs;
    private final AiClient ai;
    private final UsageMeter usage;
    private final JsonMapper json;
    /**
     * Kayıtlı adımlar AI servisinin verisidir ve yanıttan geniş olabilir. Uygulama genelindeki katı okuma
     * istemci girdisi içindir: burada bilinmeyen alan listeyi 500'e düşürür, sözleşmedekiler döner.
     */
    private final JsonMapper stored;
    private final HttpServletResponse response;

    AgentController(AgentService service, AgentRunRepository runs, AiClient ai, UsageMeter usage, JsonMapper json,
            HttpServletResponse response) {
        this.service = service;
        this.runs = runs;
        this.ai = ai;
        this.usage = usage;
        this.json = json;
        this.stored = json.rebuild().disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES).build();
        this.response = response;
    }

    @Override
    public ResponseEntity<String> createAgentRun(UUID tenantId, CreateAgentRunRequest request) {
        usage.requireQuota();
        var run = service.start(request.getGoal());
        stream(tenantId, run);
        return null;
    }

    @Override
    public ResponseEntity<String> decideAgentRun(UUID tenantId, UUID runId, AgentApprovalRequest request) {
        // Ticket kararı kotadan bağımsızdır, ama sonrası modeli çalıştırır: dolu kotada karar verilmez.
        usage.requireQuota();
        var run = service.decide(runId, request.getApproved());
        stream(tenantId, run);
        return null;
    }

    @Override
    public ResponseEntity<List<AgentRun>> listAgentRuns(UUID tenantId) {
        return ResponseEntity.ok(runs.findLatest(LIST_LIMIT).stream().map(this::toApi).toList());
    }

    @Override
    public ResponseEntity<AgentRun> getAgentRun(UUID tenantId, UUID runId) {
        return runs.findById(runId)
            .map(run -> ResponseEntity.ok(toApi(run)))
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
    }

    /** Veritabanı bağlantısı akış sırasında tutulmaz; her kayıt kendi kısa işlemindedir. */
    private void stream(UUID tenantId, AgentRunRepository.Run run) {
        response.setStatus(HttpStatus.OK.value());
        response.setContentType(MediaType.TEXT_EVENT_STREAM_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader(HttpHeaders.CACHE_CONTROL, "no-cache");
        response.setHeader("X-Accel-Buffering", "no");

        var body = new LinkedHashMap<String, Object>();
        body.put("tenantId", tenantId);
        body.put("goal", run.goal());
        body.put("steps", json.readTree(run.steps()));
        body.put("tokensUsed", run.tokens());

        var outcome = new boolean[] {false};
        try {
            send("run", json.createObjectNode().put("id", run.id().toString()));
            try {
                ai.stream(RUN_PATH, body, (event, data) -> {
                    outcome[0] |= onEvent(run.id(), event, data);
                });
            } catch (AiClient.Unavailable e) {
                log.warn("ajan çalıştırılamadı: {}", e.getMessage());
            }
            if (!outcome[0]) {
                // AI servisi sonuç vermeden düştü.
                runs.finish(run.id(), "failed", "", "[]", "[]", "ai_unavailable", null, 0);
            }
            send("end", json.valueToTree(toApi(runs.findById(run.id()).orElseThrow())));
        } catch (UncheckedIOException e) {
            log.info("istemci ajan akışından ayrıldı run={}", run.id());
            runs.interrupt(run.id(), 0);
        }
    }

    /** @return çalıştırmayı bu turda sonlandıran bir olay geldiyse true */
    private boolean onEvent(UUID runId, String event, JsonNode data) {
        switch (event) {
            case "step" -> {
                runs.appendStep(runId, json.writeValueAsString(data));
                send("step", data);
                return false;
            }
            case "approval_required" -> {
                int tokens = record(data, null);
                var pending = json.createObjectNode()
                    .put("thought", data.path("thought").asString(""))
                    .put("title", data.get("title").asString())
                    .put("description", data.get("description").asString());
                runs.markWaiting(runId, json.writeValueAsString(pending), tokens);
                return true;
            }
            case "done" -> {
                String model = data.hasNonNull("model") ? data.get("model").asString() : null;
                int tokens = record(data, model);
                runs.finish(runId, data.get("status").asString(), data.get("answer").asString(),
                    json.writeValueAsString(data.get("cited")), json.writeValueAsString(data.get("sources")),
                    data.hasNonNull("stopReason") ? data.get("stopReason").asString() : null, model, tokens);
                return true;
            }
            default -> {
                log.debug("bilinmeyen ajan olayı atlandı: {}", event);
                return false;
            }
        }
    }

    private int record(JsonNode data, String model) {
        JsonNode counts = data.get("usage");
        if (counts == null || !counts.hasNonNull("promptTokens")) {
            return 0;
        }
        int prompt = counts.get("promptTokens").asInt();
        int completion = counts.get("completionTokens").asInt();
        usage.record(model, prompt, completion, false);
        return prompt + completion;
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

    private AgentRun toApi(AgentRunRepository.Run run) {
        var api = new AgentRun(run.id(), run.goal(), AgentRun.StatusEnum.fromValue(run.status()), run.tokens(),
            run.createdAt());
        api.setSteps(stored.readValue(run.steps(), new TypeReference<ArrayList<dev.meridian.api.contract.model.AgentStep>>() { }));
        api.setPending(run.pending() == null ? null
            : stored.readValue(run.pending(), dev.meridian.api.contract.model.AgentPendingTicket.class));
        api.setAnswer(run.answer());
        api.setCited(json.readValue(run.cited(), new TypeReference<ArrayList<Integer>>() { }));
        api.setSources(stored.readValue(run.sources(), new TypeReference<ArrayList<dev.meridian.api.contract.model.CitedSource>>() { }));
        api.setStopReason(run.stopReason());
        api.setModel(run.model());
        return api;
    }
}
