package dev.meridian.api.usage;

import java.util.List;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/**
 * Kullanıcı ve kiracı başına token-bucket. Betik Redis'te atomik çalışır: birden çok API örneği
 * aynı kovayı paylaşır. Redis kapalıysa istek geçer: oran sınırı korumadır, sohbetin ön koşulu değil.
 */
@Component
public class RateLimiter {

    private static final Logger log = LoggerFactory.getLogger(RateLimiter.class);

    /** Döndürdüğü değer: 0 = izin verildi, aksi hâlde beklenecek saniye. */
    private static final DefaultRedisScript<Long> TAKE = new DefaultRedisScript<>("""
        local capacity = tonumber(ARGV[1])
        local per_second = tonumber(ARGV[2]) / 60
        local now = redis.call('TIME')
        now = tonumber(now[1]) + tonumber(now[2]) / 1000000
        local state = redis.call('HMGET', KEYS[1], 'tokens', 'at')
        local tokens = tonumber(state[1]) or capacity
        local at = tonumber(state[2]) or now
        tokens = math.min(capacity, tokens + (now - at) * per_second)
        local wait = 0
        if tokens >= 1 then
            tokens = tokens - 1
        else
            wait = math.ceil((1 - tokens) / per_second)
        end
        redis.call('HSET', KEYS[1], 'tokens', tostring(tokens), 'at', tostring(now))
        redis.call('EXPIRE', KEYS[1], math.ceil(capacity / per_second) + 60)
        return wait
        """, Long.class);

    private final StringRedisTemplate redis;

    RateLimiter(StringRedisTemplate redis) {
        this.redis = redis;
    }

    /** @param bucket işlem türü: sohbet ve arama birbirinin kovasını tüketmez */
    public void acquire(String bucket, UUID tenantId, UUID userId, int capacity, int refillPerMinute) {
        Long wait;
        try {
            wait = redis.execute(TAKE, List.of(bucket + ":rate:" + tenantId + ":" + userId),
                String.valueOf(capacity), String.valueOf(refillPerMinute));
        } catch (DataAccessException e) {
            log.warn("oran sınırı uygulanamadı, istek geçiriliyor: {}", e.getMessage());
            return;
        }
        if (wait != null && wait > 0) {
            throw new TooManyMessages(wait);
        }
    }

    private static final class TooManyMessages extends ResponseStatusException {
        private final long retryAfterSeconds;

        TooManyMessages(long retryAfterSeconds) {
            super(HttpStatus.TOO_MANY_REQUESTS, "Çok fazla istek; lütfen biraz bekleyin");
            this.retryAfterSeconds = retryAfterSeconds;
        }

        @Override
        public HttpHeaders getHeaders() {
            var headers = new HttpHeaders();
            headers.set(HttpHeaders.RETRY_AFTER, String.valueOf(retryAfterSeconds));
            return headers;
        }
    }
}
