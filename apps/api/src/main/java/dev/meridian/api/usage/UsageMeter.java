package dev.meridian.api.usage;

import java.math.BigDecimal;
import java.net.URI;
import java.time.Clock;
import java.time.Duration;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import dev.meridian.api.tenancy.TenantContext;

/**
 * Günlük token kotası ve kullanım kaydı. Kota yumuşaktır: denetim istekten önce yapılır, kullanım
 * cevaptan sonra yazılır, bu yüzden eşzamanlı sorular sınırı bir cevap kadar aşabilir.
 */
@Service
@EnableConfigurationProperties(UsageMeter.UsageProperties.class)
public class UsageMeter {

    @ConfigurationProperties("meridian.usage")
    record UsageProperties(Map<String, Long> dailyTokens, BigDecimal promptUsdPerMillion,
            BigDecimal completionUsdPerMillion) {
    }

    private static final BigDecimal MILLION = BigDecimal.valueOf(1_000_000);

    private final UsageRepository usage;
    private final UsageProperties properties;
    private final Clock clock;

    UsageMeter(UsageRepository usage, UsageProperties properties) {
        this.usage = usage;
        this.properties = properties;
        this.clock = Clock.systemUTC();
    }

    /** Bugünün kotası dolduysa model çağrılmadan 429 döner. */
    public void requireQuota() {
        long limit = dailyLimit(usage.plan());
        if (usage.tokensSince(todayStart()) >= limit) {
            long seconds = Math.max(1, Duration.between(OffsetDateTime.now(clock), resetsAt()).toSeconds());
            throw new QuotaExceeded(seconds);
        }
    }

    public void record(String model, int promptTokens, int completionTokens, boolean estimated) {
        BigDecimal cost = properties.promptUsdPerMillion().multiply(BigDecimal.valueOf(promptTokens))
            .add(properties.completionUsdPerMillion().multiply(BigDecimal.valueOf(completionTokens)))
            .divide(MILLION);
        usage.insert(UUID.randomUUID(), TenantContext.current().orElseThrow().userId(), model, promptTokens,
            completionTokens, estimated, cost);
    }

    long dailyLimit(String plan) {
        Long limit = properties.dailyTokens().get(plan);
        if (limit == null) {
            throw new IllegalStateException("kotası tanımsız plan: " + plan);
        }
        return limit;
    }

    OffsetDateTime todayStart() {
        return LocalDate.now(clock).atStartOfDay().atOffset(ZoneOffset.UTC);
    }

    OffsetDateTime resetsAt() {
        return todayStart().plusDays(1);
    }

    private static final class QuotaExceeded extends ResponseStatusException {
        private final long retryAfterSeconds;

        QuotaExceeded(long retryAfterSeconds) {
            super(HttpStatus.TOO_MANY_REQUESTS, "Günlük token kotası doldu");
            this.retryAfterSeconds = retryAfterSeconds;
            getBody().setType(URI.create("https://meridian.dev/problems/quota-exceeded"));
        }

        @Override
        public HttpHeaders getHeaders() {
            var headers = new HttpHeaders();
            headers.set(HttpHeaders.RETRY_AFTER, String.valueOf(retryAfterSeconds));
            return headers;
        }
    }
}
