package dev.meridian.api.audit;

import java.util.List;
import java.util.UUID;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

import dev.meridian.api.contract.api.AuditApi;
import dev.meridian.api.contract.model.AuditEntry;
import dev.meridian.api.contract.model.AuditPage;

/** OpenAPI sözleşmesinden üretilen {@link AuditApi} arayüzünü uygular. */
@RestController
class AuditController implements AuditApi {

    private final Policy policy;
    private final AuditLog audit;

    AuditController(Policy policy, AuditLog audit) {
        this.policy = policy;
        this.audit = audit;
    }

    @Override
    public ResponseEntity<AuditPage> listAuditLog(UUID tenantId, String cursor, Integer limit) {
        policy.require("audit.read", Policy.ADMINS);
        int size = limit == null ? 20 : limit;
        List<AuditLog.Entry> rows = audit.findPage(cursor == null ? null : AuditCursor.decode(cursor), size + 1);
        List<AuditLog.Entry> page = rows.subList(0, Math.min(size, rows.size()));
        var body = new AuditPage(page.stream().map(AuditController::toApi).toList());
        if (rows.size() > size) {
            var last = page.getLast();
            body.setNextCursor(new AuditCursor(last.createdAt(), last.id()).encode());
        }
        return ResponseEntity.ok(body);
    }

    private static AuditEntry toApi(AuditLog.Entry entry) {
        var api = new AuditEntry(entry.id(), entry.action(), AuditEntry.OutcomeEnum.fromValue(entry.outcome()),
            entry.createdAt());
        api.setActorUserId(entry.actorUserId());
        api.setActorEmail(entry.actorEmail());
        api.setApiKeyId(entry.apiKeyId());
        api.setTargetId(entry.targetId());
        return api;
    }
}
