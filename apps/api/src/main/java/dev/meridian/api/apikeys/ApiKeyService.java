package dev.meridian.api.apikeys;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.audit.AuditLog;
import dev.meridian.api.audit.Policy;
import dev.meridian.api.tenancy.TenantContext;

@Service
public class ApiKeyService {

    /** Filtrenin bilmesi gereken kadarı: anahtar kimin adına, hangi kapsamla çalışır. */
    public record Principal(UUID apiKeyId, UUID userId, List<String> scopes) {
    }

    record Created(ApiKeyRepository.StoredKey key, String secret) {
    }

    private static final int SECRET_BYTES = 32;
    private static final int PREFIX_CHARS = 12;

    private final ApiKeyRepository keys;
    private final Policy policy;
    private final AuditLog audit;
    private final SecureRandom random = new SecureRandom();

    ApiKeyService(ApiKeyRepository keys, Policy policy, AuditLog audit) {
        this.keys = keys;
        this.policy = policy;
        this.audit = audit;
    }

    /** Bağlamdaki kiracının geçerli anahtarıysa bulunur; başka kiracının anahtarı RLS altında "yok"tur. */
    @Transactional
    public Optional<Principal> authenticate(String secret) {
        return keys.useActive(hash(secret))
            .map(key -> new Principal(key.id(), key.createdBy(), key.scopes()));
    }

    @Transactional
    Created create(String name, List<String> scopes, int expiresInDays) {
        policy.require("api_key.create", Policy.ADMINS);
        byte[] bytes = new byte[SECRET_BYTES];
        random.nextBytes(bytes);
        String secret = "mrd_" + Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        var key = keys.insert(UUID.randomUUID(), TenantContext.current().orElseThrow().userId(), name,
            secret.substring(0, PREFIX_CHARS), hash(secret), scopes, OffsetDateTime.now().plusDays(expiresInDays));
        audit.allowed("api_key.create", key.id());
        return new Created(key, secret);
    }

    @Transactional(readOnly = true)
    List<ApiKeyRepository.StoredKey> list() {
        policy.require("api_key.read", Policy.ADMINS);
        return keys.findAll();
    }

    @Transactional
    void revoke(UUID id) {
        policy.require("api_key.revoke", Policy.ADMINS);
        if (!keys.exists(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        keys.revoke(id);
        audit.allowed("api_key.revoke", id);
    }

    /** Gizli değer 256 bit rastgele: sözlük saldırısı anlamsız, yavaş özet gerekmez. */
    private static String hash(String secret) {
        try {
            return HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(secret.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
