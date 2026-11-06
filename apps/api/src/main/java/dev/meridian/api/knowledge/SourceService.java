package dev.meridian.api.knowledge;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.audit.AuditLog;
import dev.meridian.api.audit.Policy;
import dev.meridian.api.idempotency.IdempotencyStore;
import dev.meridian.api.outbox.OutboxWriter;
import dev.meridian.api.tenancy.TenantContext;
import tools.jackson.databind.json.JsonMapper;

@Service
class SourceService {

    static final String SOURCE_CREATED = "source.created";
    static final String SOURCE_DELETED = "source.deleted";

    private final SourceRepository sources;
    private final CollectionRepository collections;
    private final IdempotencyStore idempotency;
    private final OutboxWriter outbox;
    private final Policy policy;
    private final AuditLog audit;
    private final JsonMapper json;

    SourceService(SourceRepository sources, CollectionRepository collections, IdempotencyStore idempotency,
            OutboxWriter outbox, Policy policy, AuditLog audit, JsonMapper json) {
        this.sources = sources;
        this.collections = collections;
        this.idempotency = idempotency;
        this.outbox = outbox;
        this.policy = policy;
        this.audit = audit;
        this.json = json;
    }

    /**
     * Anahtar talebi, kaynak kaydı ve {@code source.created} olayı tek işlemde yazılır. Olay
     * kayıtla birlikte commit olur ya da hiç oluşmaz; yayını outbox aktarıcısı üstlenir.
     *
     * @param config sözleşmedeki kaynak yapılandırması, varsayılanları doldurulmuş ve sabit sırada
     */
    @Transactional
    Source create(String idempotencyKey, UUID collectionId, String name, Map<String, Object> config) {
        policy.require("source.create", Policy.CONTRIBUTORS);
        String tenantId = TenantContext.current().orElseThrow().tenantId().toString();
        String configJson = json.writeValueAsString(config);
        var replay = idempotency.claim(idempotencyKey, String.join("\u001F",
            "POST /v1/tenants/{tenantId}/sources", tenantId, collectionId.toString(), name, configJson));
        if (replay.isPresent()) {
            return sources.findById(replay.get().resourceId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        }
        // RLS altında başka kiracının koleksiyonu "yok" görünür; bileşik FK ikinci savunma hattıdır.
        if (collections.findById(collectionId).isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Koleksiyon bulunamadı");
        }
        Source source = sources.insert(UUID.randomUUID(), collectionId, name, (String) config.get("type"), configJson);

        var data = new LinkedHashMap<String, Object>();
        data.put("sourceId", source.id());
        data.put("collectionId", collectionId);
        data.put("type", source.type());
        data.put("config", config);
        outbox.append(SOURCE_CREATED, source.id(), data);

        idempotency.complete(idempotencyKey, source.id());
        audit.allowed("source.create", source.id());
        return source;
    }

    /** Kaynağı "silinmekte" durumuna alır; parçaların silinmesini AI servisi üstlenir. Tekrarlanabilir. */
    @Transactional
    void delete(UUID sourceId) {
        policy.require("source.delete", Policy.ADMINS);
        Source source = sources.findById(sourceId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (sources.markDeleting(sourceId)) {
            outbox.append(SOURCE_DELETED, sourceId, Map.of("sourceId", sourceId, "collectionId", source.collectionId()));
            audit.allowed("source.delete", sourceId);
        }
    }

    /**
     * Başarısız kaynağı yeni bir olayla kuyruğa alır: tüketici olayları kimlikle ayıkladığı için eski
     * olay yeniden gönderilemez. Zaten sırada ya da işlemdeyse dokunmaz; hazır ya da siliniyorsa 409.
     */
    @Transactional
    Source retry(UUID sourceId) {
        policy.require("source.retry", Policy.CONTRIBUTORS);
        Source source = sources.findById(sourceId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        return switch (source.status()) {
            case "pending", "indexing" -> source;
            case "failed" -> {
                Source queued = sources.markPending(sourceId);
                var data = new LinkedHashMap<String, Object>();
                data.put("sourceId", sourceId);
                data.put("collectionId", source.collectionId());
                data.put("type", source.type());
                data.put("config", json.readTree(sources.findConfig(sourceId)));
                outbox.append(SOURCE_CREATED, sourceId, data);
                audit.allowed("source.retry", sourceId);
                yield queued;
            }
            default -> throw new ResponseStatusException(HttpStatus.CONFLICT, "Yalnızca başarısız kaynak yeniden denenebilir");
        };
    }
}
