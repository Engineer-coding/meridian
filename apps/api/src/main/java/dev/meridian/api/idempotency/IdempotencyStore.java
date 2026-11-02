package dev.meridian.api.idempotency;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/**
 * Idempotency-Key kayıtları (anahtar kullanıcı başına benzersizdir; RLS ile korunur).
 *
 * <p>Çağıranın işlemine katılır: anahtar, iş ile aynı işlemde talep edilir. Aynı anahtarla
 * eşzamanlı gelen ikinci istek, PostgreSQL'in benzersiz indeks kilidinde ilk işlem bitene
 * kadar bekler; ilk işlem commit ederse kaydı görür ve sonucu tekrarlar, rollback ederse
 * anahtarı kendisi alır. Ayrı bir "işleniyor" durumu gerekmez.
 */
@Component
@Transactional(propagation = Propagation.MANDATORY)
public class IdempotencyStore {

    /** Daha önce tamamlanmış bir isteğin sonucu. */
    public record Replay(UUID resourceId) {
    }

    private record Prior(String requestHash, UUID resourceId) {
    }

    private final JdbcClient jdbc;

    IdempotencyStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Anahtarı bu istek için talep eder. Anahtar yeniyse boş döner ve çağıran işi yapar.
     * Aynı istekle daha önce kullanılmışsa önceki sonucu döner. Farklı bir istekle
     * kullanılmışsa 422 fırlatır.
     */
    public Optional<Replay> claim(String key, String requestFingerprint) {
        String hash = sha256(requestFingerprint);
        int inserted = jdbc.sql("""
                INSERT INTO idempotency_keys (user_id, key, request_hash)
                VALUES (current_user_id(), :key, :hash)
                ON CONFLICT (user_id, key) DO NOTHING""")
            .param("key", key)
            .param("hash", hash)
            .update();
        if (inserted == 1) {
            return Optional.empty();
        }
        var prior = jdbc.sql("SELECT request_hash, resource_id FROM idempotency_keys WHERE user_id = current_user_id() AND key = :key")
            .param("key", key)
            .query((rs, rowNum) -> new Prior(rs.getString("request_hash"), rs.getObject("resource_id", UUID.class)))
            .single();
        if (!hash.equals(prior.requestHash())) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_CONTENT,
                "Bu Idempotency-Key farklı bir istekle kullanılmış");
        }
        return Optional.of(new Replay(prior.resourceId()));
    }

    /** İş tamamlandığında oluşan kaynağı anahtara bağlar. */
    public void complete(String key, UUID resourceId) {
        jdbc.sql("UPDATE idempotency_keys SET resource_id = :resourceId WHERE user_id = current_user_id() AND key = :key")
            .param("resourceId", resourceId)
            .param("key", key)
            .update();
    }

    private static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
