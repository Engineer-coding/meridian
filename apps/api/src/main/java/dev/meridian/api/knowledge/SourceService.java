package dev.meridian.api.knowledge;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

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
    private final Roles roles;
    private final JsonMapper json;

    SourceService(SourceRepository sources, CollectionRepository collections, IdempotencyStore idempotency,
            OutboxWriter outbox, Roles roles, JsonMapper json) {
        this.sources = sources;
        this.collections = collections;
        this.idempotency = idempotency;
        this.outbox = outbox;
        this.roles = roles;
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
        roles.require(Roles.CONTRIBUTORS);
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
        return source;
    }

    /** Kaynağı "silinmekte" durumuna alır; parçaların silinmesini AI servisi üstlenir. Tekrarlanabilir. */
    @Transactional
    void delete(UUID sourceId) {
        roles.require(Roles.ADMINS);
        Source source = sources.findById(sourceId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (sources.markDeleting(sourceId)) {
            outbox.append(SOURCE_DELETED, sourceId, Map.of("sourceId", sourceId, "collectionId", source.collectionId()));
        }
    }
}
