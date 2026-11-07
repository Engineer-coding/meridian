package dev.meridian.api.agents;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.audit.AuditLog;
import dev.meridian.api.audit.Policy;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.node.ObjectNode;

/** Yazma etkili kararlar tek işlemde: durum, ticket ve denetim kaydı birlikte commit olur ya da hiç olmaz. */
@Service
class AgentService {

    private final AgentRunRepository runs;
    private final AuditLog audit;
    private final Policy policy;
    private final JsonMapper json;

    AgentService(AgentRunRepository runs, AuditLog audit, Policy policy, JsonMapper json) {
        this.runs = runs;
        this.audit = audit;
        this.policy = policy;
        this.json = json;
    }

    @Transactional
    AgentRunRepository.Run start(String goal) {
        runs.expireStale();
        var run = runs.insert(UUID.randomUUID(), goal);
        audit.allowed("agent.start", run.id());
        return run;
    }

    /**
     * Onay kararını uygular. Ticket içeriği yalnızca kayıttaki öneriden okunur: istemci başka bir içerik
     * onaylatamaz. Çalıştırma başkasınınsa RLS altında yoktur (404).
     */
    @Transactional
    AgentRunRepository.Run decide(UUID runId, boolean approved) {
        policy.require("agent.approve", Policy.CONTRIBUTORS);
        runs.expireStale();
        var existing = runs.findById(runId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        var run = runs.claimPending(existing.id())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.CONFLICT, "Bu çalıştırma onay beklemiyor"));

        JsonNode pending = json.readTree(run.pending());
        String title = pending.get("title").asString();
        String description = pending.get("description").asString();

        String observation;
        if (approved) {
            UUID ticketId = UUID.randomUUID();
            runs.insertTicket(ticketId, runId, title, description);
            audit.allowed("ticket.create", ticketId);
            observation = "Kullanıcı onayladı. Ticket oluşturuldu, kimlik: " + ticketId;
        } else {
            audit.allowed("agent.reject", runId);
            observation = "Kullanıcı reddetti, ticket oluşturulmadı. Yeniden önerme.";
        }

        ObjectNode step = json.createObjectNode();
        step.put("thought", pending.path("thought").asString(""));
        step.put("action", "create_ticket");
        step.putObject("input").put("title", title).put("description", description);
        step.put("observation", observation);
        step.put("approved", approved);
        runs.clearPending(runId, json.writeValueAsString(step));
        return runs.findById(runId).orElseThrow();
    }
}
