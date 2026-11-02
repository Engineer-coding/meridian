package dev.meridian.api.tenancy;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.idempotency.IdempotencyStore;

@Service
public class TenantOnboarding {

    private final TenantRepository tenants;
    private final IdempotencyStore idempotency;

    TenantOnboarding(TenantRepository tenants, IdempotencyStore idempotency) {
        this.tenants = tenants;
        this.idempotency = idempotency;
    }

    /**
     * Bağlamdaki kullanıcı adına, bağlamdaki kiracı kimliğiyle yeni bir kiracı oluşturur.
     * Anahtar talebi, kiracı ve sahiplik üyeliği tek işlemde yazılır: biri başarısız olursa
     * hiçbiri kalmaz ve aynı anahtarla yeniden denemek güvenlidir.
     */
    @Transactional
    public Tenant create(String idempotencyKey, String ownerEmail, String slug, String name) {
        var replay = idempotency.claim(idempotencyKey, String.join("\u001F", "POST /v1/tenants", slug, name));
        if (replay.isPresent()) {
            return tenants.findById(replay.get().resourceId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        }
        Tenant tenant = tenants.createWithOwner(ownerEmail, slug, name);
        idempotency.complete(idempotencyKey, tenant.id());
        return tenant;
    }
}
