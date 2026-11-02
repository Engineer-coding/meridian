package dev.meridian.api.knowledge;

import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.idempotency.IdempotencyStore;
import dev.meridian.api.tenancy.TenantContext;

@Service
class CollectionService {

    private final CollectionRepository collections;
    private final IdempotencyStore idempotency;
    private final Roles roles;

    CollectionService(CollectionRepository collections, IdempotencyStore idempotency, Roles roles) {
        this.collections = collections;
        this.idempotency = idempotency;
        this.roles = roles;
    }

    @Transactional
    Collection create(String idempotencyKey, String name) {
        roles.require(Roles.ADMINS);
        String tenantId = TenantContext.current().orElseThrow().tenantId().toString();
        var replay = idempotency.claim(idempotencyKey,
            String.join("\u001F", "POST /v1/tenants/{tenantId}/collections", tenantId, name));
        if (replay.isPresent()) {
            return collections.findById(replay.get().resourceId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        }
        Collection collection = collections.insert(UUID.randomUUID(), name);
        idempotency.complete(idempotencyKey, collection.id());
        return collection;
    }
}
