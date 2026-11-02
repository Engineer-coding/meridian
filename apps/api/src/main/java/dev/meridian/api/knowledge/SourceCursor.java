package dev.meridian.api.knowledge;

import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Base64;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

/**
 * Opak sayfa imleci: önceki sayfanın son satırının (created_at, id) çifti. İmleç yetki
 * taşımaz: başka bir kiracının imleci gönderilse bile sorgu RLS altında yalnızca aktif
 * kiracının satırlarını görür.
 */
record SourceCursor(OffsetDateTime createdAt, UUID id) {

    static SourceCursor of(Source source) {
        return new SourceCursor(source.createdAt(), source.id());
    }

    String encode() {
        String raw = createdAt + "|" + id;
        return Base64.getUrlEncoder().withoutPadding().encodeToString(raw.getBytes(StandardCharsets.UTF_8));
    }

    static SourceCursor decode(String cursor) {
        try {
            String raw = new String(Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
            int separator = raw.indexOf('|');
            return new SourceCursor(OffsetDateTime.parse(raw.substring(0, separator)),
                UUID.fromString(raw.substring(separator + 1)));
        } catch (IllegalArgumentException | DateTimeParseException | IndexOutOfBoundsException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Geçersiz cursor");
        }
    }
}
