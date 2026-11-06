package dev.meridian.api.apikeys;

import java.util.List;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;

import dev.meridian.api.contract.api.ApiKeysApi;
import dev.meridian.api.contract.model.ApiKey;
import dev.meridian.api.contract.model.ApiKeyScope;
import dev.meridian.api.contract.model.CreateApiKeyRequest;
import dev.meridian.api.contract.model.CreatedApiKey;

/** OpenAPI sözleşmesinden üretilen {@link ApiKeysApi} arayüzünü uygular. */
@RestController
class ApiKeyController implements ApiKeysApi {

    private static final int DEFAULT_DAYS = 90;

    private final ApiKeyService service;

    ApiKeyController(ApiKeyService service) {
        this.service = service;
    }

    @Override
    public ResponseEntity<CreatedApiKey> createApiKey(UUID tenantId, CreateApiKeyRequest request) {
        var scopes = request.getScopes().stream().map(ApiKeyScope::getValue).sorted().toList();
        int days = request.getExpiresInDays() == null ? DEFAULT_DAYS : request.getExpiresInDays();
        var created = service.create(request.getName(), scopes, days);
        return ResponseEntity.status(HttpStatus.CREATED).body(new CreatedApiKey(toApi(created.key()), created.secret()));
    }

    @Override
    public ResponseEntity<List<ApiKey>> listApiKeys(UUID tenantId) {
        return ResponseEntity.ok(service.list().stream().map(ApiKeyController::toApi).toList());
    }

    @Override
    public ResponseEntity<Void> revokeApiKey(UUID tenantId, UUID apiKeyId) {
        service.revoke(apiKeyId);
        return ResponseEntity.noContent().build();
    }

    private static ApiKey toApi(ApiKeyRepository.StoredKey key) {
        var api = new ApiKey(key.id(), key.name(), key.prefix(),
            key.scopes().stream().map(ApiKeyScope::fromValue).toList(), key.createdAt(), key.expiresAt());
        api.setLastUsedAt(key.lastUsedAt());
        api.setRevokedAt(key.revokedAt());
        return api;
    }
}
